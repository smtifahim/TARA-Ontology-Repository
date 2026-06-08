"""
map_conditions_terms.py — Conditions Terms Mapper for TARA Ontology

This script:
  1. Downloads condition data from a specified Google Sheet and saves it as CSV
     under conditions_source_sheets/ (one CSV file per sheet tab, named by tab name).
  2. Maps each entry under "Normalized-Condition-Western" to a MONDO or HP ontology
     term using the NCBO BioPortal Annotator API.
  3. Saves the enriched data (original columns + mapping columns) under
     conditions_mapped_sheets/.

Performance strategy — deduplicate → chunk → parallel:
  - Content within parentheses is stripped from each condition text before lookup
    (e.g. "Low back pain (LBP)" is sent as "Low back pain").
  - Unique cleaned condition strings are extracted from the sheet; API calls are
    made only once per unique value regardless of how many rows share it.
  - Unique values are packed into chunks of CHUNK_SIZE terms separated by '\n\n',
    so each chunk is a single BioPortal Annotator request (instead of one per row).
  - Chunks are sent in parallel (MAX_WORKERS concurrent requests).
  - Results are mapped back to all rows in the dataframe using the cleaned text as
    a cache key.
  Character offsets ensure longest_only:true works correctly per term even in batch:
  since terms occupy non-overlapping offset ranges, BioPortal's longest-match
  suppression never crosses term boundaries.

Mapping priority (applied per condition text):
  1. Exact preferred label (PREF) in MONDO  → "Exact"
  2. Exact preferred label (PREF) in HP     → "Exact"
  3. Exact synonym        (SYN)  in MONDO   → "Synonym"
  4. Exact synonym        (SYN)  in HP      → "Synonym"

  Note: The NCBO BioPortal annotator returns match type "SYN" for synonyms stored
  in BioPortal. MONDO and HP predominantly index hasExactSynonym entries, so SYN
  results here correspond to exact synonyms in practice. Related synonyms are
  generally not indexed for text annotation.

  For conditions where multiple concepts are annotated (e.g. multi-concept cell
  values), all matched concepts from the highest-priority bucket are reported
  comma-separated in the same positional order across MONDO-OR-HP-TERM,
  MONDO-OR-HP-Term-URI, and Exact-OR-Synonym columns.

Output columns added to the source data:
  MONDO-OR-HP-TERM      : Preferred label(s) of the matched term(s)
  MONDO-OR-HP-Term-URI  : Ontology URI(s) of the matched term(s)
  Exact-OR-Synonym      : "Exact" or "Synonym" per matched term

Setup (one-time):
  1. Copy .env.example to .env in this directory.
  2. Set BIOPORTAL_API_KEY=<your_key> in the .env file.
  Required package: pip install requests pandas python-dotenv

Usage:
  python map_conditions_terms.py

Author: Fahim Imam
Last updated: June 8, 2026
"""

import os
import re
import time
import concurrent.futures
from collections import defaultdict

import requests
import pandas as pd
from dotenv import load_dotenv

# Load environment variables from .env file located in the same directory as this script.
# No extra steps needed at runtime as long as .env is present with BIOPORTAL_API_KEY set.
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))


# ---------------------------------------------------------------------------
# Source Sheet Configuration
#
# Each entry maps a tab name to its (Google Sheet ID, GID).
# The downloaded CSV will be saved as <tab_name>.csv under conditions_source_sheets/.
#
# To add a new conditions sheet in the future, add a new entry here:
#   '<Tab-Name>': ('<Google-Sheet-ID>', '<GID>'),
# ---------------------------------------------------------------------------
CONDITION_SHEETS = {
    'Disease-Conditions-112625': ('1V7Q6Ike8ojEjqWXi_DQDSwIevlvGxNmflDiRvirMJRA', '915593250'),

    # Future condition sheets — add new tab entries below:
    # 'Disease-Conditions-XXXXXX': ('<SHEET_ID>', '<GID>'),
}


# ---------------------------------------------------------------------------
# Directory Paths (relative to this script's location)
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.join(SCRIPT_DIR, 'conditions_source_sheets')
MAPPED_DIR = os.path.join(SCRIPT_DIR, 'conditions_mapped_sheets')

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(MAPPED_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Column Names
# ---------------------------------------------------------------------------
CONDITION_COLUMN  = 'Normalized-Condition-Western'
TERM_LABEL_COLUMN = 'MONDO-OR-HP-Term'
TERM_URI_COLUMN   = 'MONDO-OR-HP-Term-URI'
MATCH_TYPE_COLUMN = 'Exact-OR-Synonym'


# ---------------------------------------------------------------------------
# NCBO BioPortal API Configuration
# ---------------------------------------------------------------------------
BIOPORTAL_API_KEY       = os.getenv('BIOPORTAL_API_KEY')
BIOPORTAL_ANNOTATOR_URL = 'https://data.bioontology.org/annotator'
BIOPORTAL_API_BASE      = 'https://data.bioontology.org'

# Chunked-parallel settings
CHUNK_SIZE        = 100   # number of unique conditions per BioPortal API request
MAX_WORKERS       = 3     # concurrent chunk requests (keep low to avoid 429s)
CHUNK_SEPARATOR   = '\n\n'  # separator between terms within a chunk
CHUNK_DELAY       = 0.1   # polite delay (seconds) per chunk worker after its request

# Annotator query parameters
ANNOTATOR_PARAMS = {
    'ontologies'      : 'MONDO,HP',
    'longest_only'    : 'true',
    'exclude_numbers' : 'true',
    'whole_word_only' : 'true',
    'exclude_synonyms': 'false',   # Include synonyms; priority filtering is done below
    'expand_mappings' : 'false',
    'include'         : 'prefLabel',  # Request preferred label inline in annotatedClass
}

# Cache for preferred labels to avoid redundant API calls during a run
_label_cache: dict = {}


def download_sheet_as_csv(sheet_id: str, gid: str, tab_name: str) -> str:
    """
    Download a Google Sheet tab as CSV, save it under SOURCE_DIR,
    and return the saved file path.
    """
    url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        f"/gviz/tq?tqx=out:csv&gid={gid}"
    )
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    file_path = os.path.join(SOURCE_DIR, f"{tab_name}.csv")
    with open(file_path, 'wb') as f:
        f.write(response.content)
    print(f"  Saved source CSV: {file_path}")
    return file_path


def get_preferred_label(class_uri: str, annotated_class: dict) -> str:
    """
    Return the preferred label for an ontology class.

    Uses the inline prefLabel from the annotator response if available.
    Otherwise makes a separate BioPortal class API call (result is cached
    to avoid duplicate requests within the same script run).
    Falls back to the class URI if no label can be retrieved.
    """
    # Prefer the inline prefLabel already returned by the annotator
    inline_label = annotated_class.get('prefLabel')
    if inline_label:
        return inline_label

    if class_uri in _label_cache:
        return _label_cache[class_uri]

    # Determine ontology from the class URI to build the correct endpoint
    if 'MONDO_' in class_uri:
        ontology = 'MONDO'
    elif '/HP_' in class_uri or class_uri.startswith('http://purl.obolibrary.org/obo/HP_'):
        ontology = 'HP'
    else:
        ontology_link = annotated_class.get('links', {}).get('ontology', '')
        ontology = ontology_link.rstrip('/').split('/')[-1] if ontology_link else None

    label = None
    if ontology:
        encoded_uri = requests.utils.quote(class_uri, safe='')
        url = f"{BIOPORTAL_API_BASE}/ontologies/{ontology}/classes/{encoded_uri}"
        try:
            resp = requests.get(
                url,
                params={'apikey': BIOPORTAL_API_KEY, 'include': 'prefLabel'},
                timeout=15,
            )
            if resp.status_code == 200:
                label = resp.json().get('prefLabel')
        except requests.RequestException:
            pass  # Fall through to URI fallback

    _label_cache[class_uri] = label if label else class_uri
    return _label_cache[class_uri]


def get_ontology_name(annotated_class: dict) -> str:
    """
    Determine whether an annotatedClass belongs to MONDO or HP.
    Returns 'MONDO', 'HP', or the raw ontology name string.
    """
    class_uri     = annotated_class.get('@id', '')
    ontology_link = annotated_class.get('links', {}).get('ontology', '').rstrip('/')
    ontology_name = ontology_link.split('/')[-1].upper()

    if 'MONDO' in ontology_name or 'MONDO_' in class_uri:
        return 'MONDO'
    if ontology_name == 'HP' or '/HP_' in class_uri:
        return 'HP'
    return ontology_name


# ---------------------------------------------------------------------------
# Condition Text Cleaning
# ---------------------------------------------------------------------------

def clean_condition_text(text: str) -> str:
    """
    Strip all parenthetical groups (and their content) from a condition string
    before sending it to the BioPortal annotator, then normalise whitespace.

    Examples:
        "Attention Deficit Hyperactivity Disorder (ADHD)"
            → "Attention Deficit Hyperactivity Disorder"
        "Cerebrovascular disease (stroke) with dysphasia"
            → "Cerebrovascular disease with dysphasia"
        "Craniomandibular disorders (CMD) with primarily myogenic symptoms"
            → "Craniomandibular disorders with primarily myogenic symptoms"

    Nested parentheses are NOT expected in condition strings; a simple greedy
    removal of (…) groups is sufficient.
    """
    cleaned = re.sub(r'\([^)]*\)', '', text)
    # Collapse any double-spaces left after removal and strip edges
    cleaned = re.sub(r' {2,}', ' ', cleaned).strip()
    return cleaned


# ---------------------------------------------------------------------------
# Chunked Batch Annotation
# ---------------------------------------------------------------------------

def build_chunk(terms: list) -> tuple:
    """
    Pack a list of condition strings into a single text block separated by
    CHUNK_SEPARATOR and record the 1-indexed character offset range of each term.

    BioPortal annotator returns 1-indexed 'from'/'to' positions in annotation
    spans, so offsets stored here are also 1-indexed and inclusive.

    Returns:
        combined_text  : str   — full text to POST to BioPortal
        term_offsets   : list of (term_str, from_1idx, to_1idx)
    """
    sep_len      = len(CHUNK_SEPARATOR)
    term_offsets = []
    pos          = 0   # 0-based running character position

    for term in terms:
        from_1 = pos + 1            # convert to 1-indexed
        to_1   = pos + len(term)    # inclusive end, 1-indexed
        term_offsets.append((term, from_1, to_1))
        pos += len(term) + sep_len

    combined_text = CHUNK_SEPARATOR.join(terms)
    return combined_text, term_offsets


def annotate_chunk(chunk_text: str, term_offsets: list,
                   params_override: dict = None) -> dict:
    """
    Send one chunked text block to the BioPortal Annotator and map every
    returned annotation back to the term it belongs to by comparing annotation
    span positions against the recorded term offset ranges.

    A span is assigned to a term when:
        ann_from >= term_from  AND  ann_to <= term_to

    Spans that cross a CHUNK_SEPARATOR boundary (i.e. do not fully fall within
    any single term's range) are silently discarded as bogus cross-term matches.

    For each term, results are placed into four priority buckets:
        (MONDO, PREF), (HP, PREF), (MONDO, SYN), (HP, SYN)
    and the first non-empty bucket (in that order) becomes the final result.
    When a class_uri has both PREF and SYN spans for the same term, PREF wins.

    Args:
        params_override: optional dict of annotator parameters that override
                         the defaults in ANNOTATOR_PARAMS (used by the fallback
                         pass to relax whole_word_only).

    Returns:
        dict { term_str: (label_csv, uri_csv, match_type_csv) }
        Terms with no match get ('NOT FOUND', '', '').
    """
    params = {**ANNOTATOR_PARAMS}
    if params_override:
        params.update(params_override)
    post_data = {**params, 'text': chunk_text, 'apikey': BIOPORTAL_API_KEY}

    # Retry with exponential backoff on 429 Too Many Requests.
    # Other errors (network, 5xx) are also retried up to MAX_RETRIES times.
    MAX_RETRIES   = 5
    RETRY_BACKOFF = 2.0   # base wait in seconds; doubles on each retry (2, 4, 8, 16, 32)
    annotations   = None
    for attempt in range(MAX_RETRIES):
        try:
            # POST avoids URL length limits that silently drop large chunks when
            # using GET (some conditions are long multi-phrase strings).
            resp = requests.post(BIOPORTAL_ANNOTATOR_URL, data=post_data, timeout=60)
            if resp.status_code == 429:
                wait = RETRY_BACKOFF * (2 ** attempt)
                print(f"    [429] Rate limited — waiting {wait:.0f}s before retry "
                      f"({attempt + 1}/{MAX_RETRIES})...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            annotations = resp.json()
            break
        except requests.RequestException as exc:
            wait = RETRY_BACKOFF * (2 ** attempt)
            print(f"    [WARNING] API error (attempt {attempt + 1}/{MAX_RETRIES}): "
                  f"{exc} — retrying in {wait:.0f}s...")
            time.sleep(wait)

    if annotations is None:
        print(f"    [ERROR] Chunk failed after {MAX_RETRIES} attempts; "
              f"marking {len(term_offsets)} terms as NOT FOUND.")
        return {term: ('NOT FOUND', '', '') for term, _, _ in term_offsets}

    # --- Pass 1: collect class metadata and per-term, per-class match types ---
    # class_info[uri] = (ontology_str, pref_label_str)
    class_info: dict = {}
    # term_classes[term_str][class_uri] = set of matchType strings ('PREF', 'SYN')
    term_classes: dict = {term: defaultdict(set) for term, _, _ in term_offsets}

    for ann in annotations:
        annotated_class = ann.get('annotatedClass', {})
        class_uri       = annotated_class.get('@id', '')
        if not class_uri:
            continue

        if class_uri not in class_info:
            class_info[class_uri] = (
                get_ontology_name(annotated_class),
                get_preferred_label(class_uri, annotated_class),
            )

        for span in ann.get('annotations', []):
            ann_from   = span.get('from')
            ann_to     = span.get('to')
            match_type = span.get('matchType', '').upper()

            if ann_from is None or ann_to is None:
                continue

            # Find the term whose offset range fully contains this span
            for term, t_from, t_to in term_offsets:
                if ann_from >= t_from and ann_to <= t_to:
                    term_classes[term][class_uri].add(match_type)
                    break   # A span belongs to at most one term

    # --- Pass 2: fill priority buckets and select result per term ---
    priority_order = [
        (('MONDO', 'PREF'), 'Exact'),
        (('HP',    'PREF'), 'Exact'),
        (('MONDO', 'SYN'),  'Synonym'),
        (('HP',    'SYN'),  'Synonym'),
    ]

    results: dict = {}
    for term, _, _ in term_offsets:
        buckets: dict = {
            ('MONDO', 'PREF'): [],
            ('HP',    'PREF'): [],
            ('MONDO', 'SYN') : [],
            ('HP',    'SYN') : [],
        }

        for class_uri, match_types in term_classes[term].items():
            ontology, pref_label = class_info[class_uri]
            # Assign to highest-priority bucket for this class (PREF > SYN)
            for mt in ['PREF', 'SYN']:
                if mt in match_types:
                    bucket_key = (ontology, mt)
                    if bucket_key in buckets:
                        buckets[bucket_key].append((class_uri, pref_label))
                    break

        found = False
        for bucket_key, human_label in priority_order:
            entries = buckets[bucket_key]
            if entries:
                uris   = [uri   for uri,   _ in entries]
                labels = [label for _,   label in entries]
                results[term] = (
                    ', '.join(labels),
                    ', '.join(uris),
                    ', '.join([human_label] * len(entries)),
                )
                found = True
                break
        if not found:
            results[term] = ('NOT FOUND', '', '')

    return results


def annotate_unique_conditions(unique_terms: list) -> dict:
    """
    Given a deduplicated list of cleaned condition strings:
      1. Split them into chunks of CHUNK_SIZE and send in parallel (pass 1).
      2. Collect any terms still NOT FOUND and retry them in a fallback pass
         with whole_word_only=false, which catches word-form variants such as
         plurals ("disorders" matching "disorder"), hyphenation differences
         ("post-operative" matching "postoperative"), and similar mismatches
         that would fail a strict whole-word boundary check.

    BioPortal's annotator already performs sub-phrase / partial matching:
    with longest_only=true it finds the longest non-overlapping ontology term
    anywhere within the input text, so a condition like "Allergic rhinitis and
    asthma" will yield both "Allergic rhinitis" and "asthma" automatically.
    The fallback pass only relaxes word-boundary strictness, not the
    ontology or priority logic.

    Returns:
        dict { cleaned_term_str: (label_csv, uri_csv, match_type_csv) }
    """
    def _run_chunks(terms: list, label: str,
                    params_override: dict = None) -> dict:
        """Send a list of terms in parallel chunks; return merged results."""
        chunks       = [terms[i:i + CHUNK_SIZE]
                        for i in range(0, len(terms), CHUNK_SIZE)]
        total        = len(chunks)
        batch_result : dict = {}

        def process_chunk(idx_terms: tuple) -> dict:
            idx, chunk_terms = idx_terms
            combined_text, term_offsets = build_chunk(chunk_terms)
            print(f"    {label} chunk {idx + 1}/{total} ({len(chunk_terms)} terms)...")
            result = annotate_chunk(combined_text, term_offsets, params_override)
            time.sleep(CHUNK_DELAY)
            return result

        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futs = {ex.submit(process_chunk, (i, c)): i
                    for i, c in enumerate(chunks)}
            for fut in concurrent.futures.as_completed(futs):
                batch_result.update(fut.result())
        return batch_result

    # --- Pass 1: strict matching (whole_word_only=true, default params) ---
    print(f"    {len(unique_terms)} unique conditions → "
          f"{len(unique_terms) // CHUNK_SIZE + 1} chunk(s) of up to {CHUNK_SIZE} "
          f"terms each ({MAX_WORKERS} parallel workers)")
    combined_results = _run_chunks(unique_terms, label='Sending')

    # --- Pass 2: fallback for NOT FOUND — relax whole_word_only ---
    # Catches plurals ("disorders" → "disorder"), hyphen variants
    # ("post-operative" → "postoperative"), and similar word-form mismatches.
    not_found_terms = [t for t in unique_terms
                       if combined_results.get(t, ('NOT FOUND',))[0] == 'NOT FOUND']
    if not_found_terms:
        print(f"    {len(not_found_terms)} NOT FOUND → fallback pass "
              f"(whole_word_only=false)...")
        fallback_results = _run_chunks(
            not_found_terms,
            label='Fallback',
            params_override={'whole_word_only': 'false'},
        )
        for term, result in fallback_results.items():
            if result[0] != 'NOT FOUND':   # only promote if fallback found something
                combined_results[term] = result

    return combined_results


# ---------------------------------------------------------------------------
# Main Processing
# ---------------------------------------------------------------------------

def map_conditions_sheet(tab_name: str) -> None:
    """
    Download the source sheet, run NCBO BioPortal mapping on each unique
    condition (deduplicated, parentheses stripped), and save the enriched CSV.
    """
    if tab_name not in CONDITION_SHEETS:
        raise ValueError(
            f"Tab '{tab_name}' is not defined in CONDITION_SHEETS.\n"
            "Add its Google Sheet ID and GID to CONDITION_SHEETS at the top of this script."
        )

    sheet_id, gid = CONDITION_SHEETS[tab_name]

    # Step 1: Download source CSV
    print(f"\n[1] Downloading source sheet: {tab_name}")
    csv_path = download_sheet_as_csv(sheet_id, gid, tab_name)

    # Step 2: Load CSV — preserve original column order; drop empty trailing columns
    # (the source sheet contains blank filler columns after the last named column
    # which pandas would otherwise read as Unnamed: N columns)
    df = pd.read_csv(csv_path)
    df = df.loc[:, ~df.columns.str.match(r'^Unnamed:')]
    print(f"    Loaded {len(df)} rows, {len(df.columns)} columns.")

    if CONDITION_COLUMN not in df.columns:
        raise ValueError(
            f"Expected column '{CONDITION_COLUMN}' not found in sheet '{tab_name}'.\n"
            f"Available columns: {list(df.columns)}"
        )

    # Append mapping columns if not already present (preserves original column order)
    for col in [TERM_LABEL_COLUMN, TERM_URI_COLUMN, MATCH_TYPE_COLUMN]:
        if col not in df.columns:
            df[col] = ''

    # Step 3: Deduplicate and clean condition texts
    # Build a mapping from every raw cell value to its cleaned version.
    # Cleaning strips parenthetical groups so BioPortal receives clean medical terms.
    print(f"\n[2] Deduplicating and cleaning condition texts...")
    raw_conditions = df[CONDITION_COLUMN].tolist()

    raw_to_cleaned: dict = {}
    for raw in set(raw_conditions):
        if isinstance(raw, float) or (isinstance(raw, str) and not raw.strip()):
            raw_to_cleaned[raw] = ''
        else:
            raw_to_cleaned[raw] = clean_condition_text(str(raw).strip())

    unique_cleaned = sorted(set(v for v in raw_to_cleaned.values() if v))
    print(f"    {len(raw_conditions)} rows → {len(unique_cleaned)} unique cleaned conditions")

    # Step 4: Annotate unique conditions (chunked + parallel)
    print(f"\n[3] Mapping conditions using NCBO BioPortal Annotator (chunked + parallel)...")
    annotation_cache = annotate_unique_conditions(unique_cleaned)

    # Step 5: Apply cached results back to every row in the dataframe
    for i, row in df.iterrows():
        raw_text = row[CONDITION_COLUMN]
        cleaned  = raw_to_cleaned.get(raw_text, '')
        if cleaned:
            label, uri, match_type = annotation_cache.get(cleaned, ('NOT FOUND', '', ''))
        else:
            label, uri, match_type = 'NOT FOUND', '', ''
        df.at[i, TERM_LABEL_COLUMN] = label
        df.at[i, TERM_URI_COLUMN]   = uri
        df.at[i, MATCH_TYPE_COLUMN] = match_type

    # Step 6: Save mapped CSV
    output_path = os.path.join(MAPPED_DIR, f"{tab_name}.csv")
    df.to_csv(output_path, index=False)
    print(f"\n[4] Saved mapped CSV: {output_path}")


def main() -> None:
    if not BIOPORTAL_API_KEY:
        raise EnvironmentError(
            "BIOPORTAL_API_KEY is not set.\n"
            "Copy .env.example to .env in this directory and set your API key:\n"
            "  BIOPORTAL_API_KEY=your_api_key_here"
        )

    # Process all configured condition sheets.
    # To process only specific sheets, replace the loop with explicit calls, e.g.:
    #   map_conditions_sheet('Disease-Conditions-112625')
    for tab_name in CONDITION_SHEETS:
        map_conditions_sheet(tab_name)

    print("\nAll sheets processed successfully.")


if __name__ == "__main__":
    main()
