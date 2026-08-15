"""
map_conditions_terms_v2.py — Two-Pass Conditions Terms Mapper for TARA Ontology

Self-contained alternative to map_conditions_terms.py.  All shared logic
(normalisation, candidate generation, BioPortal Search wrappers, stoplist,
modifier words, etc.) is copied directly here — no imports from the original
script.

Two-pass strategy
-----------------

Pass 1 — BioPortal Annotator (fast, high-recall)
  Strip parentheticals from every condition, deduplicate, then send the clean
  texts to the BioPortal Annotator API.  100 conditions are concatenated per
  API call (separated by double newlines) so the whole deduplication set is
  covered with very few HTTP requests.  The annotator returns ALL matching
  ontology terms found within the text, giving a rich comma-separated list of
  mappings for each condition ordered by priority:
      MONDO-Exact > MONDO-Synonym > HP-Exact > HP-Synonym
  For each unique URI, only the highest-priority match type is kept.
  Parameters mirror the existing script.js usage:
      ontologies=MONDO,HP  longest_only=true  exclude_numbers=true
      whole_word_only=true  exclude_synonyms=false  expand_mappings=false

  After all annotator results are back, post-process: any individual mapped
  term whose preferred label is a bare stopword or modifier word is removed
  from that result's CSV slot (URI and tag removed from the same ordinal
  position).  Results are saved to temp-mappings-<tab>.csv.

Pass 2 — Full normalisation pipeline for NOT FOUND rows
  Collect every condition still marked NOT FOUND after Pass 1 post-processing.
  Apply the full normalisation pipeline (apostrophe stripping, hyphen variants,
  modifier/trailing-clause stripping, slash/OR and "also known as" OR logic,
  "and"/"with"/";"/"," AND splitting) using the BioPortal Search API.
  20 conditions per chunk, 3 parallel workers.

Merge
  Replace NOT FOUND entries in temp-mappings-<tab>.csv with any new hits from
  Pass 2.  Save the final output as <tab>-V2.csv in conditions_mapped_sheets/.

Output columns (same as map_conditions_terms.py):
  MONDO-OR-HP-Term      — plain preferred label(s), comma-separated
  MONDO-OR-HP-Term-URI  — ontology URI(s), same order
  Exact-OR-Synonym      — quality+source tag(s), e.g. "Exact - MONDO", same order

Usage:
  python map_conditions_terms_v2.py            # run full two-pass mapping
  python map_conditions_terms_v2.py --help     # show this docstring

Author: Fahim Imam
Last updated: June 12, 2026
"""

import os
import re
import sys
import time
import threading
import concurrent.futures

import requests
import pandas as pd
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(_HERE, '.env'))

# ---------------------------------------------------------------------------
# Sheet / directory configuration
# (Keep in sync with map_conditions_terms.py when new tabs are added.)
# ---------------------------------------------------------------------------
CONDITION_SHEETS = {
    'Disease-Conditions-112625': ('1V7Q6Ike8ojEjqWXi_DQDSwIevlvGxNmflDiRvirMJRA', '915593250'),

    # Future condition sheets — add new tab entries below:
    # 'Disease-Conditions-XXXXXX': ('<SHEET_ID>', '<GID>'),
}

SOURCE_DIR = os.path.join(_HERE, 'conditions_source_sheets')
MAPPED_DIR = os.path.join(_HERE, 'conditions_mapped_sheets')
os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(MAPPED_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Column names
# ---------------------------------------------------------------------------
CONDITION_COLUMN  = 'Normalized-Condition-Western'
TERM_LABEL_COLUMN = 'MONDO-OR-HP-Term'
TERM_URI_COLUMN   = 'MONDO-OR-HP-Term-URI'
MATCH_TYPE_COLUMN = 'Exact-OR-Synonym'
SUGGESTED_COLUMN  = 'Suggested-Normalized-Conditions-Western'

# ---------------------------------------------------------------------------
# BioPortal API
# ---------------------------------------------------------------------------
BIOPORTAL_API_KEY       = os.getenv('BIOPORTAL_API_KEY')
BIOPORTAL_API_BASE      = 'https://data.bioontology.org'
BIOPORTAL_ANNOTATOR_URL = f"{BIOPORTAL_API_BASE}/annotator"
BIOPORTAL_SEARCH_URL    = f"{BIOPORTAL_API_BASE}/search"

SEARCH_DELAY = 0.05   # polite delay between Search API calls (Pass 2)

# ---------------------------------------------------------------------------
# Two-pass tuning
# ---------------------------------------------------------------------------
PASS1_CHUNK_SIZE  = 100   # conditions per Annotator API call
PASS1_MAX_WORKERS = 3     # parallel Annotator workers
PASS2_CHUNK_SIZE  = 20    # conditions per Search-API progress print
PASS2_MAX_WORKERS = 3     # parallel Search-API workers

# ---------------------------------------------------------------------------
# Stoplist — bare generic terms that must never stand alone as a mapping
# ---------------------------------------------------------------------------
STOPLIST: frozenset = frozenset({
    'disease', 'disorder', 'syndrome', 'syndromic disease',
    'healthy', 'idiopathic', 'stable', 'unstable',
    'severe', 'mild', 'moderate', 'acute', 'chronic',
    'condition', 'finding', 'abnormality', 'symptom',
})

# ---------------------------------------------------------------------------
# Leading modifier words — first token may be stripped to reveal core term
# ---------------------------------------------------------------------------
MODIFIER_WORDS: frozenset = frozenset({
    'acute', 'chronic', 'severe', 'mild', 'moderate', 'stable', 'unstable',
    'early', 'late', 'advanced', 'primary', 'secondary', 'idiopathic',
    'bilateral', 'unilateral', 'recurrent', 'persistent', 'progressive',
    'generalized', 'localized', 'systemic', 'focal', 'diffuse',
    'resistant', 'refractory', 'uncontrolled', 'controlled', 'functional',
    'simple', 'complex', 'complicated', 'uncomplicated',
    'diabetic', 'distal', 'depressive', 'dental', 'major', 'post',
    'lower', 'bronchial', 'sensory',
})

_MODIFIER_COMPOUND_RE = re.compile(
    r'^[\w]+(?:-related|-induced|-associated|-mediated|-based)$'
    r'|^(?:post|pre|peri|non)[\w-]+$',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Trailing clause starters — strip from this token onward to expose core term
# ---------------------------------------------------------------------------
TRAILING_CLAUSE_STARTERS: frozenset = frozenset({
    'after', 'during', 'following', 'versus', 'vs',
    'in', 'of', 'among', 'associated', 'secondary', 'due',
    'also', 'caused', 'referred', 'otherwise',
})

_ALSO_KNOWN_AS_RE = re.compile(r',?\s*also\s+known\s+as\s+', re.IGNORECASE)

# ---------------------------------------------------------------------------
# Annotation priority order
# ---------------------------------------------------------------------------
_PRIORITY_ORDER = [
    ('MONDO', 'Exact'),
    ('MONDO', 'Synonym'),
    ('HP',    'Exact'),
    ('HP',    'Synonym'),
]
_PRIORITY_RANK = {k: i for i, k in enumerate(_PRIORITY_ORDER)}


# ===========================================================================
# Normalisation utilities  (self-contained copy from map_conditions_terms.py)
# ===========================================================================

def normalize_for_comparison(text: str) -> str:
    """Lowercase, strip apostrophes/parens/punctuation, collapse whitespace."""
    text = text.lower().strip()
    text = re.sub(r"['\u2018\u2019`]s\b", '', text)   # possessives
    text = re.sub(r"['\u2018\u2019`]", '', text)        # remaining apostrophes
    text = re.sub(r'\([^)]*\)', '', text)               # drop (…) groups
    text = re.sub(r'[^\w\s-]', ' ', text)               # strip punct, keep hyphens
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def get_comparison_forms(text: str) -> frozenset:
    """Return {original-normalised, hyphen-as-space} forms of *text*."""
    base = normalize_for_comparison(text)
    forms = {base}
    if '-' in base:
        space_form = re.sub(r'\s+', ' ', base.replace('-', ' ')).strip()
        forms.add(space_form)
    return frozenset(f for f in forms if f)


def is_in_stoplist(label: str) -> bool:
    return normalize_for_comparison(label) in STOPLIST


def _is_leading_modifier(word: str) -> bool:
    return word.lower() in MODIFIER_WORDS or bool(_MODIFIER_COMPOUND_RE.match(word))


def _trailing_stripped_forms(tokens: list) -> list:
    """Yield candidate phrases by stripping trailing clauses right-to-left."""
    results = []
    for i in range(len(tokens) - 1, 0, -1):
        if tokens[i].lower().rstrip('.,;:') in TRAILING_CLAUSE_STARTERS:
            stripped = ' '.join(tokens[:i]).strip()
            if stripped:
                results.append(stripped)
    return results


def generate_candidates(original_text: str) -> list:
    """
    Produce candidate phrases in longest-first order (used by Pass 2).
    1. Strip parentheticals → working phrase
    2. Full working phrase
    3. Trailing-clause stripped forms
    4. Leading-modifier stripped (up to two rounds)
    5. Trailing-clause strip of modifier-stripped phrase
    """
    seen: list = []
    seen_set: set = set()

    def add(candidate: str) -> None:
        c = candidate.strip()
        if c and c.lower() not in seen_set:
            seen.append(c)
            seen_set.add(c.lower())

    working = re.sub(r'\([^)]*\)', '', original_text)
    # Normalise all Unicode apostrophe variants → ASCII ' before stripping
    # punctuation, so possessive terms like "Parkinson's disease" survive
    # as "Parkinson's disease" rather than "Parkinson s disease".
    working = re.sub(
        r"[\u0060\u00B4\u02B9\u02BC\u02C8\u2018\u2019\u201B\uFF07]", "'", working
    )
    working = re.sub(r"[^\w\s'-]", ' ', working)   # keep apostrophes and hyphens
    working = re.sub(r'\s+', ' ', working).strip()
    add(working)

    tokens = working.split()

    for stripped in _trailing_stripped_forms(tokens):
        add(stripped)

    if tokens and _is_leading_modifier(tokens[0]):
        no_mod = ' '.join(tokens[1:])
        add(no_mod)

        if len(tokens) > 2 and _is_leading_modifier(tokens[1]):
            no_mod2 = ' '.join(tokens[2:])
            add(no_mod2)
            for s in _trailing_stripped_forms(tokens[2:]):
                add(s)

        for s in _trailing_stripped_forms(tokens[1:]):
            add(s)

    return seen


# ===========================================================================
# BioPortal Search API — used exclusively by Pass 2
# ===========================================================================

_search_cache: dict = {}
_search_cache_lock = threading.Lock()


def _bioportal_search_exact(phrase: str) -> list:
    """Call /search?exact_match=true for MONDO and HP.  Returns list of result dicts."""
    if not phrase.strip():
        return []

    params = {
        'q'          : phrase,
        'ontologies' : 'MONDO,HP',
        'exact_match': 'false',
        'include'    : 'prefLabel,synonym',
        'pagesize'   : 50,
        'apikey'     : BIOPORTAL_API_KEY,
    }
    MAX_RETRIES, RETRY_BACKOFF = 5, 2.0

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(BIOPORTAL_SEARCH_URL, params=params, timeout=30)
            if resp.status_code == 429:
                wait = RETRY_BACKOFF * (2 ** attempt)
                print(f"    [429] Rate limited — waiting {wait:.0f}s "
                      f"(attempt {attempt + 1}/{MAX_RETRIES})...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            break
        except requests.RequestException as exc:
            wait = RETRY_BACKOFF * (2 ** attempt)
            print(f"    [WARNING] Search API error "
                  f"(attempt {attempt + 1}/{MAX_RETRIES}): {exc} "
                  f"— retrying in {wait:.0f}s...")
            time.sleep(wait)
    else:
        return []

    items, results = data.get('collection', []) or [], []
    for item in items:
        uri      = item.get('@id', '') or ''
        pref     = item.get('prefLabel', '') or ''
        synonyms = item.get('synonym', []) or []
        if isinstance(synonyms, str):
            synonyms = [synonyms]
        if   'MONDO_' in uri or uri.startswith('http://purl.obolibrary.org/obo/MONDO'):
            ontology = 'MONDO'
        elif '/HP_'   in uri or uri.startswith('http://purl.obolibrary.org/obo/HP'):
            ontology = 'HP'
        else:
            continue
        results.append({'uri': uri, 'prefLabel': pref,
                        'synonyms': [s for s in synonyms if s], 'ontology': ontology})
    return results


def _verify_and_classify(candidate: str, items: list):
    """
    Client-side exact-match verification against BioPortal Search results.
    Priority: MONDO-Exact > MONDO-Synonym > HP-Exact > HP-Synonym.
    Returns (prefLabel, uri, match_type, source_tag) or None.
    """
    candidate_forms = get_comparison_forms(candidate)
    priority_order  = [('MONDO', 'Exact'), ('MONDO', 'Synonym'),
                       ('HP', 'Exact'),    ('HP', 'Synonym')]
    buckets: dict   = {k: [] for k in priority_order}

    for item in items:
        uri, pref, synonyms, onto = (item['uri'], item['prefLabel'],
                                     item['synonyms'], item['ontology'])
        if candidate_forms & get_comparison_forms(pref):
            if not is_in_stoplist(pref):
                buckets[(onto, 'Exact')].append((uri, pref))
            continue
        for syn in synonyms:
            if syn and (candidate_forms & get_comparison_forms(syn)):
                if not is_in_stoplist(pref):
                    buckets[(onto, 'Synonym')].append((uri, pref))
                break

    for key in priority_order:
        if buckets[key]:
            uri, pref = buckets[key][0]
            onto, mt  = key
            return (pref, uri, mt, f"{mt} - {onto}")
    return None


def _lookup_single_phrase(phrase: str):
    """Thread-safe cached lookup via the Search API."""
    if not phrase or not phrase.strip():
        return None
    cache_key = normalize_for_comparison(phrase)
    with _search_cache_lock:
        if cache_key in _search_cache:
            return _search_cache[cache_key]

    # Build query set:
    # 1. Normalized (apostrophe-stripped) forms from get_comparison_forms — e.g. "parkinson disease"
    # 2. Apostrophe-normalized (kept, lowercased) form — e.g. "parkinson's disease"
    #    BioPortal stores possessive terms with the apostrophe; sending without
    #    it may miss them under exact_match=true.
    phrase_forms = set(get_comparison_forms(phrase))

    # Normalize all Unicode apostrophe variants → ASCII ' then add lowercased form
    apos_norm = re.sub(
        r"[\u0060\u00B4\u02B9\u02BC\u02C8\u2018\u2019\u201B\uFF07]", "'", phrase
    ).lower().strip()
    if apos_norm:
        phrase_forms.add(apos_norm)

    # Also add the original phrase lowercased as-is (preserves whatever
    # apostrophe character the source CSV contains, in case BioPortal
    # accepts it directly).
    phrase_forms.add(phrase.lower().strip())

    # Deduplicate by the raw lowercased query string (NOT by normalized form)
    # so that "bell palsy" and "bell's palsy" are sent as separate queries.
    seen_q: set = set()
    all_items   = []
    for form in sorted(phrase_forms, key=len, reverse=True):
        if form.lower() in seen_q:
            continue
        seen_q.add(form.lower())
        all_items.extend(_bioportal_search_exact(form))
        time.sleep(SEARCH_DELAY)

    result = _verify_and_classify(phrase, all_items)
    with _search_cache_lock:
        _search_cache[cache_key] = result
    return result


def _map_single_phrase(text: str) -> tuple:
    """Try every candidate from generate_candidates(); return first match."""
    if not text or not text.strip():
        return ('NOT FOUND', '', '')
    for candidate in generate_candidates(text):
        match = _lookup_single_phrase(candidate)
        if match:
            pref, uri, _mt, source_tag = match
            return (pref, uri, source_tag)
    return ('NOT FOUND', '', '')


def map_condition(original_text: str) -> tuple:
    """
    Full normalisation pipeline (Pass 2).
    Attempt 1 : whole phrase
    Attempt 2 : slash / OR splitting
    Attempt 2b: "also known as" OR splitting
    Attempt 3 : "and" / "with" / "," / ";" AND splitting
    """
    if not original_text or not isinstance(original_text, str):
        return ('NOT FOUND', '', '')
    original_text = original_text.strip()
    if not original_text:
        return ('NOT FOUND', '', '')

    result = _map_single_phrase(original_text)
    if result[0] != 'NOT FOUND':
        return result

    bare = re.sub(r'\([^)]*\)', '', original_text)
    bare = re.sub(r'\s+', ' ', bare).strip()

    # Attempt 2: slash OR literal " or " splitting — try each part independently
    _or_sep_re = re.compile(r'/|\bor\b', re.IGNORECASE)
    if _or_sep_re.search(bare):
        parts = [p.strip() for p in _or_sep_re.split(bare) if p.strip()]
        if len(parts) >= 2:
            for part in parts:
                r = _map_single_phrase(part)
                if r[0] != 'NOT FOUND':
                    return r

    if _ALSO_KNOWN_AS_RE.search(bare):
        aka_parts = _ALSO_KNOWN_AS_RE.split(bare, maxsplit=1)
        if len(aka_parts) == 2:
            for part in aka_parts:
                part = part.strip()
                if part:
                    r = _map_single_phrase(part)
                    if r[0] != 'NOT FOUND':
                        return r

    working = re.sub(r'[^\w\s,;-]', ' ', bare)
    working = re.sub(r'\s+', ' ', working).strip()
    if re.search(r'\band\b|\bwith\b|[,;]', working, re.IGNORECASE):
        flat  = re.sub(r'\s+(?:and|with)\s+', ',', working, flags=re.IGNORECASE)
        flat  = flat.replace(';', ',')
        parts = [p.strip() for p in flat.split(',') if p.strip()]
        if len(parts) >= 2:
            found = [r for r in (_map_single_phrase(p) for p in parts)
                     if r[0] != 'NOT FOUND']
            if found:
                return (', '.join(r[0] for r in found),
                        ', '.join(r[1] for r in found),
                        ', '.join(r[2] for r in found))

    return ('NOT FOUND', '', '')


# ===========================================================================
# Sheet download
# ===========================================================================

def download_sheet_as_csv(sheet_id: str, gid: str, tab_name: str) -> str:
    url = (f"https://docs.google.com/spreadsheets/d/{sheet_id}"
           f"/gviz/tq?tqx=out:csv&gid={gid}")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    file_path = os.path.join(SOURCE_DIR, f"{tab_name}.csv")
    with open(file_path, 'wb') as f:
        f.write(response.content)
    print(f"  Saved source CSV: {file_path}")
    return file_path


# ===========================================================================
# Formula-injection protection
# ===========================================================================

_FORMULA_PREFIX_RE = re.compile(r'^[=+\-@|]')


def _csv_safe(val):
    s = str(val) if not isinstance(val, float) else val
    if isinstance(s, str) and _FORMULA_PREFIX_RE.match(s):
        return '\t' + s
    return val


def _safe_apply(df: pd.DataFrame) -> pd.DataFrame:
    """Apply _csv_safe across the whole dataframe (pandas 1.x / 2.x compat)."""
    try:
        return df.applymap(_csv_safe)      # pandas < 2.1
    except AttributeError:
        return df.map(_csv_safe)           # pandas >= 2.1


# ===========================================================================
# Pass 1 — BioPortal Annotator (100 conditions per API call)
# ===========================================================================

def _strip_parens(text: str) -> str:
    """Remove parenthetical groups and collapse whitespace."""
    return re.sub(r'\s+', ' ', re.sub(r'\([^)]*\)', '', text)).strip()


def _is_not_specified(text: str) -> bool:
    """Return True if *text* starts with (or only contains) 'not specified'."""
    return bool(re.match(r'not\s+specified', text.strip(), re.IGNORECASE))


def _compute_suggested_form(text: str) -> str:
    """
    Compute the suggested normalised form of *text* for Pass 1 (Annotator).
    Applied after deduplication to produce the value stored in
    Suggested-Normalized-Conditions-Western and sent to BioPortal:
      1. Remove parenthetical groups  (…)
      2. Normalise ALL Unicode apostrophe variants to a plain ASCII apostrophe
         so BioPortal receives a consistent character.  The apostrophe is
         KEPT — BioPortal stores terms like "Bell's palsy" and "Parkinson's
         disease" with the apostrophe, so stripping it prevents matching.
      3. Replace "/" with " or "       ("A/B" → "A or B")
      4. Collapse whitespace

    Unicode apostrophe variants normalised to U+0027:
        U+0060  GRAVE ACCENT                `
        U+00B4  ACUTE ACCENT                ´
        U+02B9  MODIFIER LETTER PRIME       ʹ
        U+02BC  MODIFIER LETTER APOSTROPHE  ʼ
        U+02C8  MODIFIER LETTER VERTICAL LINE ˈ
        U+2018  LEFT SINGLE QUOTATION MARK  '
        U+2019  RIGHT SINGLE QUOTATION MARK '
        U+201B  SINGLE HIGH-REVERSED-9 QUOTATION MARK ‛
        U+FF07  FULLWIDTH APOSTROPHE        ＇
    """
    text = re.sub(r'\([^)]*\)', '', text)   # remove (…) groups

    # Normalise all apostrophe-like characters to plain ASCII ' — keep them
    text = re.sub(
        r"[\u0060\u00B4\u02B9\u02BC\u02C8\u2018\u2019\u201B\uFF07]",
        "'",
        text,
    )

    text = text.replace('/', ' or ')        # slash → " or "
    return re.sub(r'\s+', ' ', text).strip()


def _classify_uri_ontology(uri: str):
    """Return 'MONDO', 'HP', or None."""
    if re.search(r'MONDO[_:]', uri, re.IGNORECASE) or 'obo/MONDO' in uri:
        return 'MONDO'
    if re.search(r'/HP[_:]', uri, re.IGNORECASE) or 'obo/HP_' in uri:
        return 'HP'
    return None


def _prioritize_annotations(matches: list) -> tuple:
    """
    Given a list of (uri, pref_label, ontology, match_type) tuples from the
    Annotator, find the highest-priority non-empty bucket from:
        MONDO-Exact > MONDO-Synonym > HP-Exact > HP-Synonym
    and return ONLY the matches from that bucket.

    This ensures that, for example, if a term has any MONDO-Exact match,
    all MONDO-Synonym / HP-Exact / HP-Synonym matches are discarded.
    If there are only HP-Synonym matches, those are kept.

    Stopword/modifier filtering is deferred to post-processing, so ALL matches
    (including modifier words) are returned here.

    Returns ('NOT FOUND', '', '') when there are no matches.
    """
    if not matches:
        return ('NOT FOUND', '', '')

    # Group matches into priority buckets (duplicates within a bucket allowed
    # at this stage; they are deduplicated by URI below).
    buckets: dict = {k: [] for k in _PRIORITY_ORDER}
    for uri, pref_label, ontology, match_type in matches:
        if not pref_label:
            continue
        key = (ontology, match_type)
        if key in buckets:
            buckets[key].append((uri, pref_label))

    # Find the highest-priority bucket that has any hits
    winning_key = None
    for key in _PRIORITY_ORDER:
        if buckets[key]:
            winning_key = key
            break

    if winning_key is None:
        return ('NOT FOUND', '', '')

    # Deduplicate URIs within the winning bucket; sort for deterministic output
    seen_uris: set = set()
    winning_items: list = []
    for uri, pref_label in buckets[winning_key]:
        if uri not in seen_uris:
            winning_items.append((uri, pref_label))
            seen_uris.add(uri)
    winning_items.sort(key=lambda x: x[1].lower())

    onto, mt = winning_key
    tag    = f"{mt} - {onto}"
    labels = [pref for _, pref in winning_items]
    uris   = [uri  for uri, _  in winning_items]
    tags   = [tag] * len(winning_items)
    return (', '.join(labels), ', '.join(uris), ', '.join(tags))


def _annotate_batch(clean_conditions: list) -> dict:
    """
    POST one batch of (parenthetical-stripped) conditions to BioPortal's
    Annotator endpoint.

    Conditions are joined with '\\n\\n' so the annotator treats them as
    distinct sentences and cannot produce cross-condition matches.
    1-based character offsets are tracked for each condition so every
    returned annotation can be mapped back to its source row.

    Parameters sent match the script.js usage:
        ontologies=MONDO,HP  longest_only=true  exclude_numbers=true
        whole_word_only=true  exclude_synonyms=false  expand_mappings=false
        include=prefLabel

    Returns {clean_condition_text: [(uri, pref_label, ontology, match_type), ...]}.
    All raw matches (including stopword labels) are returned; filtering is
    done in the post-processing step.
    """
    if not clean_conditions:
        return {}

    SEP = '\n\n'

    # Build concatenated text and track 1-based char offsets per condition
    offsets: list = []
    pos = 1
    for cond in clean_conditions:
        start = pos
        end   = pos + len(cond) - 1
        offsets.append((start, end))
        pos = end + 1 + len(SEP)   # advance past condition + separator

    full_text = SEP.join(clean_conditions)

    params = {
        'text'            : full_text,
        'ontologies'      : 'MONDO,HP',
        'longest_only'    : 'true',
        'exclude_numbers' : 'true',
        'whole_word_only' : 'true',
        'exclude_synonyms': 'false',
        'expand_mappings' : 'false',
        'include'         : 'prefLabel',
        'apikey'          : BIOPORTAL_API_KEY,
    }

    MAX_RETRIES, RETRY_BACKOFF = 5, 2.0
    annotations = []

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(
                BIOPORTAL_ANNOTATOR_URL,
                data=params,
                timeout=180,    # annotator may be slow for large batches
            )
            if resp.status_code == 429:
                wait = RETRY_BACKOFF * (2 ** attempt)
                print(f"    [429] Rate limited — waiting {wait:.0f}s "
                      f"(attempt {attempt + 1}/{MAX_RETRIES})...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            annotations = resp.json()
            break
        except requests.RequestException as exc:
            wait = RETRY_BACKOFF * (2 ** attempt)
            print(f"    [WARNING] Annotator API error "
                  f"(attempt {attempt + 1}/{MAX_RETRIES}): {exc} "
                  f"— retrying in {wait:.0f}s...")
            time.sleep(wait)

    results: dict = {cond: [] for cond in clean_conditions}
    if not annotations:
        return results

    for ann in annotations:
        try:
            ann_annotations = ann.get('annotations', [])
            if not ann_annotations:
                continue
            first_ann  = ann_annotations[0]
            ann_from   = first_ann.get('from', 0)
            ann_to     = first_ann.get('to',   0)
            match_raw  = first_ann.get('matchType', '')   # 'PREF' or 'SYN'
            ann_class  = ann.get('annotatedClass', {})
            uri        = ann_class.get('@id', '')
            pref_label = ann_class.get('prefLabel', '')
        except (KeyError, IndexError, TypeError):
            continue

        if not uri or not pref_label:
            continue
        if match_raw not in ('PREF', 'SYN'):
            continue

        ontology = _classify_uri_ontology(uri)
        if ontology is None:
            continue

        match_type = 'Exact' if match_raw == 'PREF' else 'Synonym'

        # Map annotation back to source condition via 1-based char offsets
        for i, (start, end) in enumerate(offsets):
            if ann_from >= start and ann_to <= end:
                results[clean_conditions[i]].append(
                    (uri, pref_label, ontology, match_type)
                )
                break

    return results


def _pass1_map_batch(unique_conditions: list) -> dict:
    """
    Map *unique_conditions* via the BioPortal Annotator in chunks of
    PASS1_CHUNK_SIZE using PASS1_MAX_WORKERS parallel workers.

    Returns {clean_condition: (label_csv, uri_csv, tag_csv)}.
    """
    total  = len(unique_conditions)
    chunks = [unique_conditions[i: i + PASS1_CHUNK_SIZE]
              for i in range(0, total, PASS1_CHUNK_SIZE)]

    completed = [0]
    lock      = threading.Lock()

    def _worker(chunk: list) -> dict:
        batch       = _annotate_batch(chunk)
        prioritized = {cond: _prioritize_annotations(matches)
                       for cond, matches in batch.items()}
        with lock:
            completed[0] += len(chunk)
            n = completed[0]
            if n % PASS1_CHUNK_SIZE == 0 or n == total:
                print(f"      Pass 1: {n}/{total} conditions processed "
                      f"({len(chunks)} chunk(s) total)...")
        return prioritized

    print(f"    {total} unique conditions → Pass 1 Annotator API "
          f"({PASS1_MAX_WORKERS} workers, {PASS1_CHUNK_SIZE} conditions/chunk, "
          f"{len(chunks)} chunk(s))...")

    results: dict = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=PASS1_MAX_WORKERS) as ex:
        futures = {ex.submit(_worker, chunk): chunk for chunk in chunks}
        for fut in concurrent.futures.as_completed(futures):
            chunk = futures[fut]
            try:
                results.update(fut.result())
            except Exception as exc:
                print(f"    [WARNING] Pass 1 chunk failed: {exc}")
                for cond in chunk:
                    results[cond] = ('NOT FOUND', '', '')

    return results


# ===========================================================================
# Post-processing — remove bare stopword / modifier hits from Pass 1 results
# ===========================================================================

def _is_bare_stopword_or_modifier(label: str) -> bool:
    """Return True if *label* is a bare stopword or modifier (meaningless alone)."""
    norm = normalize_for_comparison(label)
    return norm in STOPLIST or norm in MODIFIER_WORDS


def _remove_stopword_hits(label_csv: str, uri_csv: str, tag_csv: str):
    """
    Given the three CSV-formatted mapping columns for one row, remove any
    individual term whose preferred label is a bare stopword / modifier.
    The remaining terms keep their original relative order.

    Returns the filtered ``(label_csv, uri_csv, tag_csv)`` tuple.
    If all terms are removed the row becomes ``('NOT FOUND', '', '')``.
    """
    if label_csv == 'NOT FOUND':
        return (label_csv, uri_csv, tag_csv)

    labels = [l.strip() for l in label_csv.split(',')]
    uris   = [u.strip() for u in uri_csv.split(',')]   if uri_csv   else [''] * len(labels)
    tags   = [t.strip() for t in tag_csv.split(',')]   if tag_csv   else [''] * len(labels)

    # Pad shorter lists (guard against mis-aligned CSVs)
    while len(uris) < len(labels):
        uris.append('')
    while len(tags) < len(labels):
        tags.append('')

    kept_labels, kept_uris, kept_tags = [], [], []
    for lbl, uri, tag in zip(labels, uris, tags):
        if not _is_bare_stopword_or_modifier(lbl):
            kept_labels.append(lbl)
            kept_uris.append(uri)
            kept_tags.append(tag)

    if not kept_labels:
        return ('NOT FOUND', '', '')

    return (
        ', '.join(kept_labels),
        ', '.join(kept_uris),
        ', '.join(kept_tags),
    )


# ===========================================================================
# Pass 2 — full normalisation pipeline for remaining NOT FOUND rows
# ===========================================================================

def _pass2_map_batch(not_found_terms: list) -> dict:
    """
    Apply the full map_condition() pipeline to *not_found_terms* using
    PASS2_MAX_WORKERS parallel workers.

    Returns {original_text: (label_csv, uri_csv, tag_csv)}.
    """
    total     = len(not_found_terms)
    completed = [0]
    lock      = threading.Lock()

    def _worker(term: str):
        res = map_condition(term)
        with lock:
            completed[0] += 1
            n = completed[0]
            if n % PASS2_CHUNK_SIZE == 0 or n == total:
                print(f"      Pass 2: {n}/{total} conditions processed...")
        return (term, res)

    print(f"    {total} NOT FOUND conditions → Pass 2 full-pipeline "
          f"({PASS2_MAX_WORKERS} workers, {PASS2_CHUNK_SIZE}/chunk)...")

    results: dict = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=PASS2_MAX_WORKERS) as ex:
        futures = {ex.submit(_worker, t): t for t in not_found_terms}
        for fut in concurrent.futures.as_completed(futures):
            try:
                term, res = fut.result()
                results[term] = res
            except Exception as exc:
                term = futures[fut]
                print(f"    [WARNING] Pass 2 failed for '{term}': {exc}")
                results[term] = ('NOT FOUND', '', '')
    return results


# ===========================================================================
# Main two-pass pipeline
# ===========================================================================

def map_conditions_sheet_v2(tab_name: str) -> None:
    """
    Run the full two-pass mapping pipeline for *tab_name*.

    Step 1  Download source Google Sheet as CSV.
    Step 2  Build orig→clean mapping; deduplicate by stripped text.
    Step 3  Pass 1 — BioPortal Annotator (100/chunk, 3 workers).
    Step 4  Post-process: remove bare-stopword/modifier hits; save temp CSV.
    Step 5  Identify unique NOT FOUND conditions for Pass 2.
    Step 6  Pass 2 — full normalisation pipeline (20/chunk, 3 workers).
    Step 7  Merge Pass 2 hits; save final <tab>-V2.csv.
    """
    if tab_name not in CONDITION_SHEETS:
        raise ValueError(
            f"Tab '{tab_name}' is not defined in CONDITION_SHEETS.\n"
            "Add its Google Sheet ID and GID to CONDITION_SHEETS in this script."
        )

    sheet_id, gid = CONDITION_SHEETS[tab_name]

    # ------------------------------------------------------------------
    # Step 1: Download source CSV
    # ------------------------------------------------------------------
    print(f"\n[1] Downloading source sheet: {tab_name}")
    csv_path = download_sheet_as_csv(sheet_id, gid, tab_name)

    df = pd.read_csv(csv_path)
    df = df.loc[:, ~df.columns.str.match(r'^Unnamed:')]
    print(f"    Loaded {len(df)} rows, {len(df.columns)} columns.")

    if CONDITION_COLUMN not in df.columns:
        raise ValueError(
            f"Column '{CONDITION_COLUMN}' not found in sheet '{tab_name}'.\n"
            f"Available columns: {list(df.columns)}"
        )

    for col in [TERM_LABEL_COLUMN, TERM_URI_COLUMN, MATCH_TYPE_COLUMN]:
        if col not in df.columns:
            df[col] = ''

    # Insert SUGGESTED_COLUMN right after CONDITION_COLUMN so it is visible
    # alongside the original text in the output CSV.
    if SUGGESTED_COLUMN not in df.columns:
        cond_idx = df.columns.get_loc(CONDITION_COLUMN)
        df.insert(cond_idx + 1, SUGGESTED_COLUMN, '')

    # ------------------------------------------------------------------
    # Step 2: Deduplicate — apply _compute_suggested_form to every original
    #         text.  The suggested form is stored in the new
    #         Suggested-Normalized-Conditions-Western column and is used as
    #         the actual query sent to the BioPortal Annotator in Pass 1.
    #         Deduplication is done on the suggested form so conditions that
    #         differ only in parentheticals/apostrophes/slashes share one call.
    # ------------------------------------------------------------------
    print(f"\n[2] Building unique condition set and computing suggested normalisations...")
    raw_values = df[CONDITION_COLUMN].tolist()

    # original text → suggested normalised form
    # Conditions starting with "not specified" are skipped entirely.
    orig_to_suggested: dict = {}
    for v in raw_values:
        if isinstance(v, str) and v.strip():
            orig = v.strip()
            if _is_not_specified(orig):
                continue
            orig_to_suggested[orig] = _compute_suggested_form(orig)

    # Deduplicate by suggested form; keep first-seen original as representative
    suggested_to_orig: dict = {}
    for orig, suggested in orig_to_suggested.items():
        if suggested and suggested not in suggested_to_orig:
            suggested_to_orig[suggested] = orig

    unique_suggested = sorted(suggested_to_orig.keys())
    print(f"    {len(raw_values)} rows → {len(unique_suggested)} unique "
          f"(suggested-normalised) conditions")

    # ------------------------------------------------------------------
    # Step 3: Pass 1 — BioPortal Annotator
    # ------------------------------------------------------------------
    print(f"\n[3] Pass 1 — BioPortal Annotator "
          f"(batch {PASS1_CHUNK_SIZE}, {PASS1_MAX_WORKERS} workers)...")
    pass1_results = _pass1_map_batch(unique_suggested)

    # ------------------------------------------------------------------
    # Step 4: Post-process; save temp CSV
    # ------------------------------------------------------------------
    print(f"\n[4] Post-processing Pass 1 results "
          f"(removing bare stopword/modifier hits)...")

    # Build full lookup: original text → (label, uri, tag)
    # Rows with the same suggested form share the same Pass 1 result.
    annotation: dict = {}
    for orig, suggested in orig_to_suggested.items():
        raw_result = pass1_results.get(suggested, ('NOT FOUND', '', ''))
        lbl, uri, tag = raw_result
        lbl, uri, tag = _remove_stopword_hits(lbl, uri, tag)
        annotation[orig] = (lbl, uri, tag)

    # Apply to dataframe; also populate the Suggested-Normalized-Conditions-Western column
    df_temp = df.copy()
    for i, row in df_temp.iterrows():
        raw_text = row[CONDITION_COLUMN]
        key = str(raw_text).strip() if isinstance(raw_text, str) and str(raw_text).strip() else ''
        if key:
            df_temp.at[i, SUGGESTED_COLUMN] = orig_to_suggested.get(key, '')
            lbl, uri, tag = annotation.get(key, ('NOT FOUND', '', ''))
        else:
            lbl, uri, tag = 'NOT FOUND', '', ''
        df_temp.at[i, TERM_LABEL_COLUMN] = lbl
        df_temp.at[i, TERM_URI_COLUMN]   = uri
        df_temp.at[i, MATCH_TYPE_COLUMN] = tag

    temp_path = os.path.join(MAPPED_DIR, f"temp-mappings-{tab_name}.csv")
    _safe_apply(df_temp).to_csv(temp_path, index=False)

    not_found_keys = [k for k, (lbl, _, _) in annotation.items()
                      if lbl == 'NOT FOUND']
    mapped_count   = len(annotation) - len(not_found_keys)
    print(f"    {mapped_count} mapped, {len(not_found_keys)} still NOT FOUND "
          f"after Pass 1 post-processing.")
    print(f"    Saved temp CSV: {temp_path}")

    # ------------------------------------------------------------------
    # Step 5 + 6: Pass 2 (skip if nothing to do)
    # ------------------------------------------------------------------
    if not not_found_keys:
        print("\n[5/6] No NOT FOUND conditions — skipping Pass 2.")
        pass2_results: dict = {}
    else:
        unique_not_found = sorted(set(not_found_keys))
        print(f"\n[5] {len(unique_not_found)} unique NOT FOUND conditions "
              f"identified for Pass 2.")
        print(f"\n[6] Pass 2 — full normalisation pipeline "
              f"({PASS2_MAX_WORKERS} workers)...")
        pass2_results = _pass2_map_batch(unique_not_found)

    # ------------------------------------------------------------------
    # Step 7: Merge Pass 2 results; save final CSV
    # ------------------------------------------------------------------
    print(f"\n[7] Merging Pass 2 results and saving final CSV...")
    pass2_hits = 0
    for orig in not_found_keys:
        p2 = pass2_results.get(orig, ('NOT FOUND', '', ''))
        if p2[0] != 'NOT FOUND':
            annotation[orig] = p2
            pass2_hits += 1

    # Apply merged results back to the temp dataframe
    df_final = df_temp.copy()
    for i, row in df_final.iterrows():
        raw_text = row[CONDITION_COLUMN]
        key = str(raw_text).strip() if isinstance(raw_text, str) and str(raw_text).strip() else ''
        if key and key in annotation:
            lbl, uri, tag = annotation[key]
            df_final.at[i, TERM_LABEL_COLUMN] = lbl
            df_final.at[i, TERM_URI_COLUMN]   = uri
            df_final.at[i, MATCH_TYPE_COLUMN] = tag

    output_path = os.path.join(MAPPED_DIR, f"{tab_name}-V2.csv")
    _safe_apply(df_final).to_csv(output_path, index=False)

    total_mapped = sum(1 for (lbl, _, _) in annotation.values() if lbl != 'NOT FOUND')
    total_not_found = len(annotation) - total_mapped
    print(f"    Pass 2 resolved {pass2_hits} additional conditions.")
    print(f"    Final: {total_mapped} mapped, {total_not_found} NOT FOUND.")
    print(f"    Saved final CSV: {output_path}")


# ===========================================================================
# Entry point
# ===========================================================================

def main():
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__)
        sys.exit(0)

    if not BIOPORTAL_API_KEY:
        print(
            "[ERROR] BIOPORTAL_API_KEY is not set.\n"
            "Create a .env file in this directory with:\n"
            "  BIOPORTAL_API_KEY=<your_key>"
        )
        sys.exit(1)

    print("=" * 60)
    print("TARA Conditions Mapper v2 — Two-Pass Pipeline")
    print("=" * 60)

    for tab_name in CONDITION_SHEETS:
        print(f"\nProcessing tab: {tab_name}")
        map_conditions_sheet_v2(tab_name)

    print("\nDone.")


if __name__ == '__main__':
    main()
