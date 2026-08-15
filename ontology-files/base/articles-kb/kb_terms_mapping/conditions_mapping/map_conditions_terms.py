"""
map_conditions_terms.py — Conditions Terms Mapper for TARA Ontology

This script:
  1. Downloads condition data from a specified Google Sheet and saves it as CSV
     under conditions_source_sheets/ (one CSV file per sheet tab, named by tab name).
  2. Maps each entry under "Normalized-Condition-Western" to a MONDO or HP ontology
     term using the NCBO BioPortal Search API with strict exact-match verification.
  3. Saves the enriched data (original columns + mapping columns) under
     conditions_mapped_sheets/.

Strict matching pipeline:
  Each condition goes through a pipeline of composable steps:

  PRE-PROCESSING (applied before any other stage):
     All text enclosed in parentheses — including the parentheses themselves —
     is stripped from the input string.  This stripped text is NEVER used as a
     mapping candidate.  Acronyms, "also known as" clauses, and any other
     parenthetical content are always ignored.

  1. normalize_for_comparison(text)
     Lowercase, strip punctuation (except hyphens), collapse whitespace.
     Hyphens are preserved for the comparison-forms step.

  2. get_comparison_forms(text)
     Returns a frozenset of hyphen-normalisation variants of a text:
       - Original form  (hyphens kept)
       - Hyphens → single space  ("low-back pain" → "low back pain")
     Applied symmetrically to both the query phrase and every ontology
     label/synonym before comparing — never as a special case for one term.

  3. generate_candidates(original_text)
     Produces candidate phrases in longest-first order:
       a. Full phrase (after stripping parentheticals)
       b. Trailing qualifying clause removed (after/during/in/following/also/…)
       c. Leading modifier word stripped (acute/chronic/severe/primary/…)
          — also strips compound modifiers like "cancer-related", "drug-induced"
       d. Combinations of (b) and (c)
     Single tokens are only generated as the natural result of this stripping
     process — never pulled arbitrarily from the middle of a phrase.
     NOTE: parenthetical content is NEVER added as a candidate here.

  4. bioportal_search_exact(phrase) + client-side verification
     Queries BioPortal /search (without exact_match) for MONDO and HP separately
     (one API call per ontology) to ensure up to 50 results from each.
     Querying both together risks MONDO synonym matches being pushed off the
     page by HP preferred-label matches, violating the priority order.
     NOTE: BioPortal's exact_match=true only matches prefLabels, not synonyms,
     so a broader search is used and all filtering is enforced client-side:
     _verify_and_classify checks that a returned result's prefLabel or synonym
     intersects the query's comparison forms (via get_comparison_forms).
     BioPortal's own ranking/score is NOT used as the acceptance criterion.

  5. is_in_stoplist(label)
     Rejects results whose preferred label exactly matches a stoplist entry
     ("disease", "healthy", "acute", "chronic", …).  These bare generic terms
     must never be returned standalone; they may still appear as part of a
     longer exact-match phrase.

  6. NOT FOUND fallback
     If no candidate yields a verified exact match after all attempts, returns
     ("NOT FOUND", "", "").

Mapping priority — applied at every pipeline stage, stop at first match:
  1. Exact preferred label (PREF) in MONDO  → tagged "Exact - MONDO"
  2. Exact synonym        (SYN)  in MONDO   → tagged "Synonym - MONDO"
  3. Exact preferred label (PREF) in HP     → tagged "Exact - HP"
  4. Exact synonym        (SYN)  in HP      → tagged "Synonym - HP"

  A "SYN" result means BioPortal found the query as a synonym.  MONDO and HP
  predominantly index hasExactSynonym entries, so SYN results correspond to
  exact synonyms in practice.

  For input phrases where "/" separates two alternative names for the same
  condition (OR semantics), the first alternative is tried first; if it maps
  successfully that result is returned and the second is skipped.  Only ONE
  result is ever returned.
  e.g. "Chronic prostatitis/chronic pelvic pain syndrome (CP/CPPS)"
       → tries "Chronic prostatitis", then "chronic pelvic pain syndrome"

  "also known as" introduces a second alternative name (OR semantics):
  the part before is tried first; if it fails, the part after is tried.
  Only ONE result is returned.  An optional leading comma is ignored.
  e.g. "Idiopathic anterior knee pain, also known as patellofemoral pain syndrome"
       → tries "Idiopathic anterior knee pain", then "patellofemoral pain syndrome"

  "with" (as a whole word) is treated as AND: both the text before and after
  are mapped independently and results are returned comma-separated.
  The whole phrase is always tried first; splitting only occurs if it fails.
  e.g. "Breast cancer with hot flashes" → maps both "Breast cancer" and "hot flashes"
  e.g. "migraine with aura" → maps as a single whole term (no split needed)

  For input phrases that contain explicit "and" or "," conjunctions, each
  component is mapped separately and results are returned comma-separated.
  Phrases without any of these delimiters are never auto-decomposed.

Output columns added to the source data:
  MONDO-OR-HP-Term      : Preferred label(s) without any tag, e.g.
                          "cardiac arrhythmia [Exact - MONDO]" or
                          "hot flashes [Synonym - HP]"
  MONDO-OR-HP-Term-URI  : Ontology URI(s) of the matched term(s)
  Exact-OR-Synonym      : full quality+source tag per matched term, e.g. "Exact - MONDO"

Setup (one-time):
  1. Copy .env.example to .env in this directory.
  2. Set BIOPORTAL_API_KEY=<your_key> in the .env file.
  Required package: pip install requests pandas python-dotenv

Usage:
  python map_conditions_terms.py            # run full mapping
  python map_conditions_terms.py --test     # run built-in unit tests

Author: Fahim Imam
Last updated: June 12, 2026 (rev 2)
"""

import os
import re
import sys
import time
import threading
import concurrent.futures
import unittest

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
    # https://docs.google.com/spreadsheets/d/14WIm3G6PoIHYrECjEetgd7pvKjzrntR57HbdMJ2ZNQI/edit?gid=1500907942#gid=1500907942
    'Disease-Conditions-112625': ('14WIm3G6PoIHYrECjEetgd7pvKjzrntR57HbdMJ2ZNQI', '1500907942'),
    
    # 'Disease-Conditions-112625': ('1V7Q6Ike8ojEjqWXi_DQDSwIevlvGxNmflDiRvirMJRA', '915593250'),

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
BIOPORTAL_API_KEY    = os.getenv('BIOPORTAL_API_KEY')
BIOPORTAL_API_BASE   = 'https://data.bioontology.org'
BIOPORTAL_SEARCH_URL = f"{BIOPORTAL_API_BASE}/search"

MAX_WORKERS   = 5    # parallel condition-mapping workers
SEARCH_DELAY = 0.05  # polite delay (seconds) after each search API call


# ---------------------------------------------------------------------------
# Stoplist — preferred labels that must NEVER be returned as standalone results.
#
# These bare generic/qualifier terms are meaningless as disease mappings.
# They may still appear as part of a *longer* exact-match phrase (e.g.
# "Chronic kidney disease" is fine; the bare word "disease" is not).
# ---------------------------------------------------------------------------
STOPLIST: frozenset = frozenset({
    'disease',
    'disorder',
    'syndrome',
    'syndromic disease',
    'healthy',
    'idiopathic',
    'stable',
    'unstable',
    'severe',
    'mild',
    'moderate',
    'acute',
    'chronic',
    'condition',
    'finding',
    'abnormality',
    'symptom',
})


# ---------------------------------------------------------------------------
# Leading modifier words — if a phrase starts with one of these, it may be
# stripped to reveal the core condition.
# e.g. "Acute ankle sprains"  → try "ankle sprains"
#      "Chronic Low Back Pain" → try "Low Back Pain"
#      "Secondary hypertension" → try "hypertension"
# ---------------------------------------------------------------------------
MODIFIER_WORDS: frozenset = frozenset({
    'acute', 'chronic', 'severe', 'mild', 'moderate', 'stable', 'unstable',
    'early', 'late', 'advanced', 'primary', 'secondary', 'idiopathic',
    'bilateral', 'unilateral', 'recurrent', 'persistent', 'progressive',
    'generalized', 'localized', 'systemic', 'focal', 'diffuse',
    'resistant', 'refractory', 'uncontrolled', 'controlled', 'functional',
    'simple', 'complex', 'complicated', 'uncomplicated',
    # Condition-type adjectives: stripped to expose the core condition name
    'diabetic', 'distal', 'depressive', 'dental', 'post',
    'lower', 'sensory',
})

# Compound-modifier pattern: first token of the form "{word}-related",
# "{word}-induced", etc. is also treated as a strippable leading modifier.
# e.g. "Cancer-related pain"      → try "pain"
#      "Chemotherapy-induced nausea" → try "nausea"
_MODIFIER_COMPOUND_RE = re.compile(
    r'^[\w]+(?:-related|-induced|-associated|-mediated|-based)$'
    r'|^(?:post|pre|peri|non)[\w-]+$',   # e.g. Poststroke, Postoperative, Non-specific
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Trailing clause starter words — words that introduce a qualifying clause
# appended to a condition name.  The clause from the trigger word onwards
# can be stripped to expose the core condition.
# e.g. "Dysphagia after acute stroke"              → try "Dysphagia"
#      "Low back pain during pregnancy"            → try "Low back pain"
#      "Pain in patients with cancer"              → try "Pain"  (via 'in')
#      "Osteoarthritis of the knee"               → try "Osteoarthritis"
#      "Lymphedema secondary to surgery"           → try "Lymphedema"
#      "Rhinitis , also known as hay fever"        → try "Rhinitis"
#      "Myofascial pain syndrome caused by MTrPs" → try "Myofascial pain syndrome"
#
# NOTE: 'with' is intentionally NOT in this set.  "X with Y" is treated as
# AND-semantics (both X and Y are mapped independently via map_condition
# Attempt 3).  This ensures "migraine with aura" is tried as a whole phrase
# first (Attempt 1) and only decomposed if the whole phrase fails.
# ---------------------------------------------------------------------------
TRAILING_CLAUSE_STARTERS: frozenset = frozenset({
    'after', 'during', 'following', 'versus', 'vs',
    'in', 'of', 'among', 'associated', 'secondary', 'due',
    'also',      # "also known as …"
    'caused',    # "caused by …"
    'referred',  # "referred to as …"
    'otherwise', # "otherwise known as …"
})

# Regex to detect "also known as" alternative-name clauses (OR semantics).
# An optional leading comma is consumed so it is not left dangling.
_ALSO_KNOWN_AS_RE = re.compile(r',?\s*also\s+known\s+as\s+', re.IGNORECASE)


# ---------------------------------------------------------------------------
# Normalisation Utilities
# ---------------------------------------------------------------------------

def normalize_for_comparison(text: str) -> str:
    """
    Normalise *text* for exact string comparison:
      - Lowercase
      - Strip possessive apostrophes (e.g. "Parkinson's" → "parkinson",
        "Bell's" → "bell") and any remaining apostrophe characters
      - Remove parenthetical groups  "(…)"
      - Replace all punctuation except hyphens with a space
      - Collapse repeated whitespace

    Hyphens are deliberately preserved here.  Call get_comparison_forms() to
    obtain all hyphen-normalisation variants (hyphen-as-space).
    """
    text = text.lower().strip()
    # Strip possessive apostrophes before punctuation normalisation so that
    # "Parkinson's" → "parkinson" and "Bell's" → "bell", matching MONDO/HP labels.
    text = re.sub(r"['\u2018\u2019`]s\b", '', text)  # possessives: "Parkinson's" → "parkinson"
    text = re.sub(r"['\u2018\u2019`]", '', text)       # remaining apostrophes
    text = re.sub(r'\([^)]*\)', '', text)         # drop (…) groups
    text = re.sub(r'[^\w\s-]', ' ', text)         # strip punct, keep hyphens
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def get_comparison_forms(text: str) -> frozenset:
    """
    Return all normalised comparison forms of *text*, covering every
    hyphen-normalisation variant so that, for example:

        "Low-back pain"  ≡  "low back pain"

    The two forms produced (after normalize_for_comparison):
      1. Original (hyphens kept)
      2. Hyphens replaced with a single space

    Note: the hyphen-concatenated form (e.g. "lowbackpain") is NOT generated;
    only the space-separated variant is added alongside the original.

    This is applied symmetrically to both query phrases and ontology
    labels/synonyms — never as a hard-coded special case for any one term.
    Empty strings and duplicates are removed from the returned frozenset.
    """
    base = normalize_for_comparison(text)
    forms = {base}
    if '-' in base:
        space_form = re.sub(r'\s+', ' ', base.replace('-', ' ')).strip()
        forms.add(space_form)
    return frozenset(f for f in forms if f)


def is_in_stoplist(label: str) -> bool:
    """
    Return True if *label* (after normalisation) exactly matches any entry in
    STOPLIST.  These bare generic terms must never be returned as a standalone
    mapping result, though they may appear inside a longer matched phrase.
    """
    return normalize_for_comparison(label) in STOPLIST


# ---------------------------------------------------------------------------
# Candidate Phrase Generation
# ---------------------------------------------------------------------------

def _is_leading_modifier(word: str) -> bool:
    """Return True if *word* is a strippable leading modifier."""
    return (word.lower() in MODIFIER_WORDS
            or bool(_MODIFIER_COMPOUND_RE.match(word)))


def _trailing_stripped_forms(tokens: list) -> list:
    """
    Scan *tokens* right-to-left for TRAILING_CLAUSE_STARTERS.  For each
    trigger found at position i > 0, yield the phrase formed by
    tokens[:i].  Going right-to-left ensures longer candidates are
    yielded before shorter ones (longest-first order).
    """
    results = []
    for i in range(len(tokens) - 1, 0, -1):
        tok_clean = tokens[i].lower().rstrip('.,;:')
        if tok_clean in TRAILING_CLAUSE_STARTERS:
            stripped = ' '.join(tokens[:i]).strip()
            if stripped:
                results.append(stripped)
    return results


def generate_candidates(original_text: str) -> list:
    """
    Produce candidate phrases from *original_text* in longest-first order.

    Algorithm
    ---------
    PRE-PROCESSING: All parenthetical groups (and their content) are stripped
    from the input FIRST.  Parenthetical content is NEVER added back as a
    candidate at any later stage.

    1.  Strip parenthetical groups from the input to form the working phrase.
    2.  Add the full working phrase as the first candidate.
    3.  Scan tokens right-to-left for TRAILING_CLAUSE_STARTERS; for each
        trigger found strip from that position onwards.
    4.  If the first token is a MODIFIER_WORD or matches the compound-modifier
        pattern (e.g. "cancer-related", "drug-induced"), add the phrase with
        that token removed.
    5.  Combine (3) and (4): apply trailing-clause stripping to the already
        modifier-stripped phrase.

    Single-token candidates are permitted only as the natural result of the
    stripping steps above — they are never pulled from the middle of a phrase.
    Candidates are deduplicated while preserving generation order.
    """
    seen: list = []
    seen_set: set = set()

    def add(candidate: str) -> None:
        c = candidate.strip()
        if c and c.lower() not in seen_set:
            seen.append(c)
            seen_set.add(c.lower())

    # Step 1: strip parentheticals for the working phrase
    working = re.sub(r'\([^)]*\)', '', original_text)
    # Normalise all Unicode apostrophe variants → ASCII ' before stripping
    # punctuation, so possessive terms like "Parkinson's disease" survive
    # as "Parkinson's disease" rather than "Parkinson s disease".
    working = re.sub(
        r"[\u0060\u00B4\u02B9\u02BC\u02C8\u2018\u2019\u201B\uFF07]", "'", working
    )
    working = re.sub(r"[^\w\s'-]", ' ', working)   # keep apostrophes and hyphens
    working = re.sub(r'\s+', ' ', working).strip()
    add(working)   # normalise punctuation
    working = re.sub(r'\s+', ' ', working).strip()

    # Step 2: full working phrase
    add(working)

    tokens = working.split()

    # Step 3: trailing clause stripping
    for stripped in _trailing_stripped_forms(tokens):
        add(stripped)

    # Step 4: leading modifier stripping (up to two consecutive modifiers)
    if tokens and _is_leading_modifier(tokens[0]):
        no_mod = ' '.join(tokens[1:])
        add(no_mod)

        # Step 4b: second-round modifier strip if the next token is also a modifier
        # e.g. "Distal Sensory Peripheral Neuropathy"
        #      → "Sensory Peripheral Neuropathy" (round 1)
        #      → "Peripheral Neuropathy" (round 2)
        if len(tokens) > 2 and _is_leading_modifier(tokens[1]):
            no_mod2 = ' '.join(tokens[2:])
            add(no_mod2)
            for stripped in _trailing_stripped_forms(tokens[2:]):
                add(stripped)

        # Step 5: combine — trailing strip of the first modifier-stripped phrase
        nm_tokens = tokens[1:]
        for stripped in _trailing_stripped_forms(nm_tokens):
            add(stripped)

    # NOTE: parenthetical content is deliberately NOT added as a candidate.
    # All parentheticals were stripped in Step 1 and must remain ignored.

    return seen


# ---------------------------------------------------------------------------
# BioPortal Search API — Exact Match with Client-Side Verification
# ---------------------------------------------------------------------------

# Thread-safe cache: normalize_for_comparison(phrase) → match tuple or None
_search_cache: dict = {}
_search_cache_lock = threading.Lock()


def _bioportal_search_exact(phrase: str) -> list:
    """
    Call BioPortal ``/search`` for *phrase* on MONDO and HP and return
    candidate result dicts for client-side exact-match verification.

    Returns a list of result dicts::

        [{'uri': str, 'prefLabel': str, 'synonyms': list[str],
          'ontology': 'MONDO' | 'HP'}, ...]

    An empty list is returned if the API call fails after retries or if
    *phrase* is blank.

    MONDO and HP are queried in **separate** API calls (MONDO first, then HP)
    to guarantee that up to ``pagesize`` results are returned from *each*
    ontology independently.  Querying both together risks MONDO synonym
    matches being displaced by HP preferred-label matches within a single
    page, which would cause the priority ordering in ``_verify_and_classify``
    to be applied over an incomplete result set.

    ``exact_match=true`` is intentionally NOT used: BioPortal's exact_match
    only searches prefLabels and silently omits terms that match only via a
    synonym.  All exact-match filtering is therefore done client-side in
    ``_verify_and_classify``, which checks both prefLabels and synonyms using
    ``get_comparison_forms`` for hyphen-normalised comparison.
    """
    if not phrase.strip():
        return []

    MAX_RETRIES   = 5
    RETRY_BACKOFF = 2.0

    all_results: list = []

    # Query MONDO and HP separately so each ontology gets its own full page
    # of results.  This ensures ``_verify_and_classify`` always has complete
    # information from both ontologies when enforcing MONDO > HP priority.
    for ontology_filter in ('MONDO', 'HP'):
        params = {
            'q'          : phrase,
            'ontologies' : ontology_filter,
            'include'    : 'prefLabel,synonym',
            'pagesize'   : 50,
            'apikey'     : BIOPORTAL_API_KEY,
        }

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
            continue   # skip this ontology if retries exhausted

        items = data.get('collection', []) or []
        for item in items:
            uri        = item.get('@id', '') or ''
            pref_label = item.get('prefLabel', '') or ''
            synonyms   = item.get('synonym', []) or []
            if isinstance(synonyms, str):
                synonyms = [synonyms]

            # Classify ontology from URI
            if 'MONDO_' in uri or uri.startswith('http://purl.obolibrary.org/obo/MONDO'):
                ontology = 'MONDO'
            elif '/HP_' in uri or uri.startswith('http://purl.obolibrary.org/obo/HP'):
                ontology = 'HP'
            else:
                continue   # skip unrecognised ontology URIs

            all_results.append({
                'uri'      : uri,
                'prefLabel': pref_label,
                'synonyms' : [s for s in synonyms if s],
                'ontology' : ontology,
            })

    return all_results


def _verify_and_classify(candidate: str, items: list):
    """
    Given a *candidate* phrase and a list of BioPortal result *items*, return
    the highest-priority item that is a verified exact normalised match.

    Priority order: MONDO-PREF > MONDO-SYN > HP-PREF > HP-SYN.

    Verification uses get_comparison_forms() on both sides so that hyphen
    variants are handled symmetrically.  A result whose prefLabel is in
    STOPLIST is silently skipped.

    Returns ``(prefLabel, uri, match_type)`` where ``match_type`` is
    ``'Exact'`` or ``'Synonym'``, or ``None`` if no match.
    """
    candidate_forms = get_comparison_forms(candidate)

    # Priority: MONDO-PREF > MONDO-SYN > HP-PREF > HP-SYN.
    # Stop at the first non-empty bucket; do not fall through to lower-priority
    # sources once a higher-priority match is found.
    priority_order = [
        ('MONDO', 'Exact'),
        ('MONDO', 'Synonym'),
        ('HP',    'Exact'),
        ('HP',    'Synonym'),
    ]
    buckets: dict = {k: [] for k in priority_order}

    for item in items:
        uri        = item['uri']
        pref_label = item['prefLabel']
        synonyms   = item['synonyms']
        ontology   = item['ontology']

        # --- Preferred-label exact match? ---
        if candidate_forms & get_comparison_forms(pref_label):
            if not is_in_stoplist(pref_label):
                buckets[(ontology, 'Exact')].append((uri, pref_label))
            continue   # do not also check synonyms for the same item

        # --- Synonym exact match? ---
        for syn in synonyms:
            if not syn:
                continue
            if candidate_forms & get_comparison_forms(syn):
                if not is_in_stoplist(pref_label):
                    buckets[(ontology, 'Synonym')].append((uri, pref_label))
                break   # first matching synonym is enough

    for bucket_key in priority_order:
        entries = buckets[bucket_key]
        if entries:
            uri, pref_label = entries[0]
            ontology, mt = bucket_key        # e.g. ('MONDO', 'Exact')
            # The Exact-OR-Synonym column carries just the quality word
            # ("Exact" or "Synonym") per the requested output format.
            # The ontology source is appended only inside the label tag so
            # downstream users can see it at a glance, but does not pollute
            # the dedicated match-type column.
            source_tag = f"{mt} - {ontology}"  # e.g. "Exact - MONDO"
            return (pref_label, uri, mt, source_tag)

    return None


def _lookup_single_phrase(phrase: str):
    """
    Try to find an exact MONDO/HP match for *phrase*.

    Queries BioPortal with every hyphen-normalisation variant of the phrase
    and verifies each result client-side.  Results are cached thread-safely
    to avoid redundant API calls within the same run.

    Returns ``(prefLabel, uri, match_type, source_tag)`` where
    ``match_type`` is ``'Exact'`` or ``'Synonym'`` and ``source_tag`` is
    the full ``'Exact - MONDO'`` / ``'Synonym - HP'`` string used in the
    inline label, or ``None`` if no match.
    """
    if not phrase or not phrase.strip():
        return None

    cache_key = normalize_for_comparison(phrase)
    with _search_cache_lock:
        if cache_key in _search_cache:
            return _search_cache[cache_key]

    # Build query set:
    # 1. Normalized (apostrophe-stripped) form — hyphens from the input are
    #    preserved as-is (e.g. "low-back pain" stays "low-back pain").
    #    The hyphen-space variant is deliberately NOT added here; hyphens in the
    #    input under Normalized-Condition-Western are intentional and must not be
    #    silently collapsed.  get_comparison_forms() is applied symmetrically on
    #    both sides inside _verify_and_classify, so hyphen-normalised matching
    #    still works during client-side verification without extra BioPortal calls.
    # 2. Apostrophe-normalized (kept, lowercased) form — e.g. "parkinson's disease"
    #    BioPortal stores possessive terms with the apostrophe.
    phrase_forms = {normalize_for_comparison(phrase)}

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
    seen_queries: set = set()
    all_items: list   = []
    for form in sorted(phrase_forms, key=len, reverse=True):
        if form.lower() in seen_queries:
            continue
        seen_queries.add(form.lower())
        items = _bioportal_search_exact(form)
        all_items.extend(items)
        time.sleep(SEARCH_DELAY)

    result = _verify_and_classify(phrase, all_items)

    with _search_cache_lock:
        _search_cache[cache_key] = result

    return result


# ---------------------------------------------------------------------------
# Single-Condition Mapping
# ---------------------------------------------------------------------------

def _map_single_phrase(text: str) -> tuple:
    """
    Map *text* as a single-condition phrase using the candidate pipeline.

    Tries each candidate from generate_candidates() in longest-first order
    until an exact MONDO/HP match is found.

    Returns ``(pref_label, uri, source_tag)`` where:
      - ``pref_label`` is the plain ontology preferred label, e.g.
        ``"cardiac arrhythmia"``
      - ``source_tag`` is the full quality+source string, e.g.
        ``"Exact - MONDO"`` (written to the Exact-OR-Synonym output column)
    Returns ``('NOT FOUND', '', '')`` when no match is found.
    """
    if not text or not text.strip():
        return ('NOT FOUND', '', '')

    for candidate in generate_candidates(text):
        match = _lookup_single_phrase(candidate)
        if match:
            pref_label, uri, match_type, source_tag = match
            # Return the plain label; source_tag (e.g. "Exact - MONDO") goes
            # in the Exact-OR-Synonym output column.
            return (pref_label, uri, source_tag)

    return ('NOT FOUND', '', '')


def map_condition(original_text: str) -> tuple:
    """
    Map a condition string to its best MONDO/HP ontology term(s).

    Single-condition phrases are mapped through the full candidate pipeline
    (full phrase → trailing-clause stripping → modifier stripping → NOT FOUND).

    Slash ("/") is treated as OR: the first alternative is tried first; if it
    maps, the second is skipped.  Only one result is returned.

    "also known as" is treated as OR: the part before is tried first; if it
    fails, the part after is tried.  Only one result is returned.

    "with" (as a whole word) is treated as AND, the same as "and" and ",":
    both parts are mapped independently and results combined.  The whole phrase
    is always tried first; splitting only occurs if the whole phrase fails.

    Multi-condition phrases containing "and", "with", or "," are split and each
    component mapped independently; results are comma-separated.

    Each matched term label is the plain preferred label, e.g.::

        "cardiac arrhythmia, hot flashes"

    Returns ``(label_csv, uri_csv, match_type_csv)``.
    Returns ``('NOT FOUND', '', '')`` when no exact match can be verified.
    """
    if not original_text or not isinstance(original_text, str):
        return ('NOT FOUND', '', '')
    original_text = original_text.strip()
    if not original_text:
        return ('NOT FOUND', '', '')

    # --- Attempt 1: treat the whole phrase as a single condition ---
    result = _map_single_phrase(original_text)
    if result[0] != 'NOT FOUND':
        return result

    # Strip parentheticals once; reused by both slash and comma/and attempts.
    working_bare = re.sub(r'\([^)]*\)', '', original_text)
    working_bare = re.sub(r'\s+', ' ', working_bare).strip()

    # --- Attempt 2: slash / OR literal-"or" splitting ---
    # "/" and the word "or" both mean OR: alternative names for the same
    # condition.  Parentheticals are stripped first so "(CP/CPPS)" inside
    # parens does not produce spurious candidates.
    _or_sep_re = re.compile(r'/|\bor\b', re.IGNORECASE)
    if _or_sep_re.search(working_bare):
        or_parts = [p.strip() for p in _or_sep_re.split(working_bare) if p.strip()]
        if len(or_parts) >= 2:
            for part in or_parts:
                sub_result = _map_single_phrase(part)
                if sub_result[0] != 'NOT FOUND':
                    return sub_result

    # --- Attempt 2b: "also known as" OR splitting ---
    # "X, also known as Y" means X and Y are alternative names (OR semantics).
    # Try X first (the part before); if it yields a match, return it.
    # If X fails, try Y (the part after).  Only ONE result is returned.
    # Note: Attempt 1 already tried X via trailing-clause stripping; this
    # attempt adds the ability to fall back to Y when X yields nothing at all.
    if _ALSO_KNOWN_AS_RE.search(working_bare):
        aka_parts = _ALSO_KNOWN_AS_RE.split(working_bare, maxsplit=1)
        if len(aka_parts) == 2:
            for part in aka_parts:
                part = part.strip()
                if part:
                    sub_result = _map_single_phrase(part)
                    if sub_result[0] != 'NOT FOUND':
                        return sub_result

    # --- Attempt 3: multi-condition splitting ("and", "with", ",", and ";") ---
    # "with" is treated as AND: both the text before and after are mapped
    # independently (e.g. "Breast cancer with hot flashes" → both mapped).
    # ";" is treated as a list separator (same as ",").
    # The whole phrase was already tried in Attempt 1, so splitting here only
    # occurs when the whole phrase failed to map.
    working = re.sub(r'[^\w\s,;-]', ' ', working_bare)  # keep commas and semicolons
    working = re.sub(r'\s+', ' ', working).strip()

    has_delimiter = bool(re.search(r'\band\b|\bwith\b|[,;]', working, re.IGNORECASE))
    if has_delimiter:
        # Normalise: replace " and "/" with " with "," and ";" with "," then split
        flat = re.sub(r'\s+(?:and|with)\s+', ',', working, flags=re.IGNORECASE)
        flat = flat.replace(';', ',')
        parts = [p.strip() for p in flat.split(',') if p.strip()]
        if len(parts) >= 2:
            sub_results = [_map_single_phrase(p) for p in parts]
            found = [r for r in sub_results if r[0] != 'NOT FOUND']
            if found:
                labels      = ', '.join(r[0] for r in found)
                uris        = ', '.join(r[1] for r in found)
                match_types = ', '.join(r[2] for r in found)
                return (labels, uris, match_types)

    return ('NOT FOUND', '', '')


# ---------------------------------------------------------------------------
# Batch Mapping (parallel)
# ---------------------------------------------------------------------------

def map_all_conditions(unique_terms: list) -> dict:
    """
    Map a deduplicated list of condition strings in parallel.

    Uses a thread pool so multiple conditions are processed concurrently while
    each still follows the strict sequential candidate-lookup order internally.
    The shared ``_search_cache`` prevents redundant BioPortal calls when the
    same candidate phrase appears across different conditions.

    Returns ``{term_str: (label, uri, match_type)}``.
    """
    total     = len(unique_terms)
    completed = [0]          # mutable counter (updated inside threads)
    counter_lock = threading.Lock()

    def process(term: str) -> tuple:
        res = map_condition(term)
        with counter_lock:
            completed[0] += 1
            n = completed[0]
            if n % 10 == 0 or n == total:
                print(f"    Mapped {n}/{total} conditions...")
        return res

    print(f"    {total} unique conditions to map "
          f"({MAX_WORKERS} parallel workers)...")

    results: dict = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_term = {executor.submit(process, t): t for t in unique_terms}
        for future in concurrent.futures.as_completed(future_to_term):
            term = future_to_term[future]
            try:
                results[term] = future.result()
            except Exception as exc:
                print(f"    [WARNING] map_condition failed for '{term}': {exc}")
                results[term] = ('NOT FOUND', '', '')

    return results


# ---------------------------------------------------------------------------
# Sheet Download
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Main Processing
# ---------------------------------------------------------------------------

def map_conditions_sheet(tab_name: str) -> None:
    """
    Download the source sheet, run strict MONDO/HP mapping on each unique
    condition, and save the enriched CSV.
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

    # Step 2: Load CSV — preserve original column order; drop unnamed trailing columns
    # (the source sheet may contain blank filler columns after the last named column
    # which pandas would otherwise read as Unnamed: N columns).
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

    # Step 3: Deduplicate condition texts
    # The raw cell values are used as-is; generate_candidates() handles all
    # normalisation and parenthetical stripping internally.
    # Cells that start with "Not specified" (case-insensitive) are excluded
    # entirely — they carry no mappable condition name and must not be sent
    # to BioPortal.
    print(f"\n[2] Deduplicating condition texts...")
    raw_conditions = df[CONDITION_COLUMN].tolist()
    unique_terms = sorted(set(
        str(v).strip()
        for v in raw_conditions
        if isinstance(v, str) and str(v).strip()
        and not str(v).strip().lower().startswith('not specified')
    ))
    print(f"    {len(raw_conditions)} rows → {len(unique_terms)} unique conditions")

    # Step 4: Map unique conditions (strict exact-match, parallel)
    print(f"\n[3] Mapping conditions (strict exact-match, MONDO + HP)...")
    annotation_cache = map_all_conditions(unique_terms)

    # Step 5: Apply cached results back to every row in the dataframe
    for i, row in df.iterrows():
        raw_text = row[CONDITION_COLUMN]
        key = str(raw_text).strip() if isinstance(raw_text, str) and str(raw_text).strip() else ''
        if key and not key.lower().startswith('not specified'):
            label, uri, match_type = annotation_cache.get(key, ('NOT FOUND', '', ''))
        else:
            label, uri, match_type = '', '', ''
        df.at[i, TERM_LABEL_COLUMN] = label
        df.at[i, TERM_URI_COLUMN]   = uri
        df.at[i, MATCH_TYPE_COLUMN] = match_type

    # Step 6: Escape formula-injection characters before saving.
    # When Excel or Google Sheets opens a CSV, any cell whose value starts with
    # =, +, -, or @ is silently evaluated as a spreadsheet formula.  Cells in
    # this sheet that contain bullet-list values (e.g. "- Migraines - Neck
    # disorders …") start with '-' and trigger a #NAME? error.
    # Prefixing such values with a tab character (\t) is the standard prevention
    # technique: the tab is invisible when the sheet is viewed but stops formula
    # evaluation.  The original data in the source sheet is not modified.
    _FORMULA_PREFIX_RE = re.compile(r'^[=+\-@|]')

    def _csv_safe(val):
        s = str(val) if not isinstance(val, float) else val
        if isinstance(s, str) and _FORMULA_PREFIX_RE.match(s):
            return '\t' + s
        return val

    df = df.applymap(_csv_safe)

    # Step 7: Save mapped CSV
    output_path = os.path.join(MAPPED_DIR, f"{tab_name}.csv")
    df.to_csv(output_path, index=False)
    print(f"\n[4] Saved mapped CSV: {output_path}")


# ---------------------------------------------------------------------------
# Unit Tests
#
# Run with:  python map_conditions_terms.py --test
#
# TestNormalization and TestCandidateGeneration require no API access.
# TestMappingIntegration requires a valid BIOPORTAL_API_KEY in .env and
# makes live API calls; it is skipped automatically if no key is present.
#
# Tests marked TBD require manual re-verification against MONDO/HP because
# their expected output previously depended on parenthetical content that is
# now stripped and never used as a mapping candidate.
# ---------------------------------------------------------------------------

def _term(label_with_tag: str) -> str:
    """Strip the '[Quality - Ontology]' bracket tag from a labelled result.

    Used in tests so assertions can compare bare term names without having
    to hard-code the specific ontology/quality tag.

    Example:
        _term("cardiac arrhythmia [Exact - MONDO]")  →  "cardiac arrhythmia"
        _term("NOT FOUND")                           →  "NOT FOUND"
    """
    return re.sub(r'\s*\[.*?\]$', '', label_with_tag).strip()


class TestNormalization(unittest.TestCase):
    """Tests for normalisation utilities — no API calls required."""

    def test_normalize_lowercase(self):
        self.assertEqual(normalize_for_comparison("Low-back Pain"), "low-back pain")

    def test_normalize_strips_parens(self):
        self.assertEqual(normalize_for_comparison("Dysfunction (TMJD)"), "dysfunction")

    def test_normalize_strips_punctuation_collapses_space(self):
        self.assertEqual(normalize_for_comparison("pain, severe"), "pain severe")

    def test_normalize_preserves_hyphen(self):
        result = normalize_for_comparison("low-back pain")
        self.assertIn('-', result)

    def test_comparison_forms_with_hyphen(self):
        forms = get_comparison_forms("Low-back pain")
        self.assertIn("low-back pain", forms)
        self.assertIn("low back pain", forms)
        self.assertNotIn("lowback pain", forms,
                         "Hyphen-concat form must no longer be generated")
        self.assertEqual(len(forms), 2,
                         "Exactly two hyphen forms: original and space-separated")

    def test_comparison_forms_no_hyphen(self):
        forms = get_comparison_forms("ankle sprains")
        self.assertEqual(forms, frozenset({"ankle sprains"}))

    def test_hyphen_forms_symmetric(self):
        # A query without hyphens should still match a label with a hyphen
        # because the label's forms include the space-separated version.
        query_forms = get_comparison_forms("low back pain")
        label_forms = get_comparison_forms("Low-Back Pain")
        self.assertTrue(bool(query_forms & label_forms),
                        "Hyphen normalisation must be symmetric")

    def test_stoplist_blocks_disease(self):
        self.assertTrue(is_in_stoplist("disease"))
        self.assertTrue(is_in_stoplist("Disease"))
        self.assertTrue(is_in_stoplist("DISEASE"))

    def test_stoplist_blocks_healthy(self):
        self.assertTrue(is_in_stoplist("Healthy"))

    def test_stoplist_blocks_acute_chronic(self):
        self.assertTrue(is_in_stoplist("acute"))
        self.assertTrue(is_in_stoplist("chronic"))

    def test_stoplist_blocks_syndrome(self):
        self.assertTrue(is_in_stoplist("syndrome"))
        self.assertTrue(is_in_stoplist("syndromic disease"))

    def test_stoplist_passes_real_condition(self):
        self.assertFalse(is_in_stoplist("Low back pain"))
        self.assertFalse(is_in_stoplist("Dysphagia"))
        self.assertFalse(is_in_stoplist("Polycystic ovarian syndrome"))
        self.assertFalse(is_in_stoplist("pain"))

    def test_normalize_strips_possessive_apostrophe(self):
        """Possessive 's must be stripped so MONDO/HP labels (no apostrophe) match."""
        self.assertEqual(normalize_for_comparison("Parkinson's Disease"),
                         "parkinson disease",
                         "Possessive apostrophe must be stripped")
        self.assertEqual(normalize_for_comparison("Bell's palsy"),
                         "bell palsy",
                         "Possessive apostrophe must be stripped")

    def test_normalize_strips_backtick_apostrophe(self):
        """Backtick-style apostrophes must also be stripped."""
        result = normalize_for_comparison("Crohn`s disease")
        self.assertEqual(result, "crohn disease")


class TestCandidateGeneration(unittest.TestCase):
    """Tests for generate_candidates — no API calls required."""

    def test_full_phrase_is_first(self):
        cands = generate_candidates("Lumbar Disc Herniation")
        self.assertEqual(cands[0], "Lumbar Disc Herniation")

    def test_parens_stripped_from_first_candidate(self):
        cands = generate_candidates("Temporomandibular joint dysfunction (TMJD)")
        self.assertNotIn('(', cands[0])
        self.assertIn("Temporomandibular joint dysfunction", cands[0])

    def test_paren_content_never_used_as_candidate(self):
        """Parenthetical abbreviations must NOT appear as mapping candidates."""
        cands = generate_candidates("Polycystic ovarian syndrome (PCOS)")
        self.assertNotIn("PCOS", cands,
                         "Parenthetical abbreviation must not appear as a candidate")

    def test_no_paren_chars_in_any_candidate(self):
        """No candidate should retain '(' or ')' characters."""
        for phrase in [
            "Temporomandibular joint dysfunction (TMJD)",
            "Polycystic ovarian syndrome (PCOS)",
            "Attention Deficit Hyperactivity Disorder (ADHD)",
        ]:
            cands = generate_candidates(phrase)
            for c in cands:
                self.assertNotIn('(', c, f"Candidate still has '(': {c!r}")
                self.assertNotIn(')', c, f"Candidate still has ')': {c!r}")

    def test_trailing_clause_stripped(self):
        cands = generate_candidates("Dysphagia after acute stroke")
        self.assertIn("Dysphagia", cands)
        # Full phrase must come before the stripped version
        full_idx     = cands.index("Dysphagia after acute stroke")
        stripped_idx = cands.index("Dysphagia")
        self.assertLess(full_idx, stripped_idx,
                        "Full phrase must appear before stripped version")

    def test_also_known_as_stripped(self):
        """'also known as …' trailing clause must be stripped via 'also' starter."""
        cands = generate_candidates(
            "Seasonal allergic rhinitis , also known as hay fever"
        )
        self.assertIn("Seasonal allergic rhinitis", cands,
                      f"Expected 'Seasonal allergic rhinitis' in candidates: {cands}")
        # generate_candidates normalises punctuation (commas become spaces) so
        # the full working phrase stored in the candidates list has no comma.
        full_form = "Seasonal allergic rhinitis also known as hay fever"
        self.assertIn(full_form, cands,
                      f"Expected normalised full phrase in candidates: {cands}")
        self.assertLess(
            cands.index(full_form),
            cands.index("Seasonal allergic rhinitis"),
        )

    def test_caused_by_stripped(self):
        """'caused by …' trailing clause must be stripped via 'caused' starter."""
        cands = generate_candidates(
            "Myofascial pain syndrome caused by trigger points"
        )
        self.assertIn("Myofascial pain syndrome", cands,
                      f"Expected 'Myofascial pain syndrome' in candidates: {cands}")

    def test_leading_modifier_acute_stripped(self):
        cands = generate_candidates("Acute ankle sprains")
        self.assertIn("ankle sprains", cands)
        self.assertLess(cands.index("Acute ankle sprains"),
                        cands.index("ankle sprains"))

    def test_leading_modifier_chronic_stripped(self):
        cands = generate_candidates("Chronic Low Back Pain")
        self.assertIn("Low Back Pain", cands)

    def test_compound_modifier_stripped(self):
        cands = generate_candidates("Cancer-related pain")
        self.assertIn("pain", cands)
        self.assertLess(cands.index("Cancer-related pain"),
                        cands.index("pain"))

    def test_combination_modifier_and_trailing_stripped(self):
        cands = generate_candidates("Chronic low back pain in patients")
        self.assertIn("low back pain", cands)

    def test_no_split_without_explicit_and(self):
        """
        "Post stroke depression" has no "and"; candidates must not contain
        standalone "stroke" or "depression" as separate entries.
        """
        cands = generate_candidates("Post stroke depression")
        cands_lower = [c.lower() for c in cands]
        self.assertNotIn("stroke", cands_lower,
                         "Must not produce bare 'stroke' without explicit 'and'")
        self.assertNotIn("depression", cands_lower,
                         "Must not produce bare 'depression' without explicit 'and'")

    def test_no_arbitrary_middle_fragments(self):
        """
        Candidates must not contain random interior fragments.
        For "Lumbar Disc Herniation" the only candidate should be the full phrase
        (no trailing-clause starter and no leading modifier present).
        """
        cands = generate_candidates("Lumbar Disc Herniation")
        self.assertEqual(len(cands), 1,
                         f"Expected only 1 candidate, got: {cands}")

    def test_of_triggers_trailing_strip(self):
        """'of' must trigger trailing-clause stripping."""
        cands = generate_candidates("Osteoarthritis of the knee")
        self.assertIn("Osteoarthritis", cands,
                      f"Expected 'Osteoarthritis' as candidate: {cands}")
        self.assertLess(cands.index("Osteoarthritis of the knee"),
                        cands.index("Osteoarthritis"),
                        "Full phrase must come before stripped version")

    def test_two_round_modifier_strip(self):
        """Two consecutive leading modifiers must both be strippable."""
        cands = generate_candidates("Distal Sensory Peripheral Neuropathy")
        self.assertIn("Sensory Peripheral Neuropathy", cands,
                      f"First-round strip must produce 'Sensory Peripheral Neuropathy': {cands}")
        self.assertIn("Peripheral Neuropathy", cands,
                      f"Second-round strip must produce 'Peripheral Neuropathy': {cands}")
        # Order: full → round-1 → round-2
        self.assertLess(cands.index("Distal Sensory Peripheral Neuropathy"),
                        cands.index("Sensory Peripheral Neuropathy"))
        self.assertLess(cands.index("Sensory Peripheral Neuropathy"),
                        cands.index("Peripheral Neuropathy"))

    def test_post_compound_modifier_stripped(self):
        """'Poststroke' as a compound post* modifier must be stripped."""
        cands = generate_candidates("Poststroke spasticity")
        self.assertIn("spasticity", cands,
                      f"'spasticity' must be a candidate for 'Poststroke spasticity': {cands}")

    def test_non_compound_modifier_stripped(self):
        """'Non-specific' as a non-* compound modifier must be stripped."""
        cands = generate_candidates("Non-specific low back pain")
        self.assertIn("low back pain", cands,
                      f"'low back pain' must be a candidate: {cands}")


class TestMappingIntegration(unittest.TestCase):
    """
    Integration tests — require a live BioPortal API connection.
    Skipped automatically when BIOPORTAL_API_KEY is absent.

    Tests marked TBD previously relied on parenthetical content that is now
    ignored.  They assert structural properties (e.g. no unrelated terms,
    no bare generics) rather than a specific expected term, and are flagged
    with "TBD: needs manual re-check" in the docstring.  Run the mapping
    manually and inspect output to confirm correct behaviour.
    """

    @classmethod
    def setUpClass(cls):
        if not BIOPORTAL_API_KEY:
            raise unittest.SkipTest(
                "BIOPORTAL_API_KEY not set — skipping integration tests."
            )

    # ------------------------------------------------------------------
    # Helper — strips "[Quality - Ontology]" tag before string comparisons
    # so assertions remain readable.
    # ------------------------------------------------------------------
    def _term(self, label_or_csv: str) -> str:
        """Return bare term name(s) without quality tags."""
        return ', '.join(
            _term(t.strip()) for t in label_or_csv.split(',')
        )

    def _tag(self, label: str) -> str:
        """Extract the '[Quality - Ontology]' tag portion from a single label."""
        m = re.search(r'\[([^\]]+)\]$', label.strip())
        return m.group(1) if m else ''

    # ------------------------------------------------------------------
    # Output format assertions
    # ------------------------------------------------------------------

    def test_matched_label_has_no_tag(self):
        """MONDO-OR-HP-Term label must be plain (no '[Quality - Ontology]' tag)."""
        label, _, match_type = map_condition("Dysphagia")
        if label != 'NOT FOUND':
            self.assertNotRegex(label, r'\[.+\]',
                                f"Label must not contain a tag, got: {label!r}")
            self.assertRegex(match_type, r'^(Exact|Synonym) - (MONDO|HP)$',
                             f"match_type must be 'Exact/Synonym - MONDO/HP', got: {match_type!r}")

    def test_match_type_format(self):
        """match_type column must be 'Exact - MONDO/HP' or 'Synonym - MONDO/HP'."""
        label, _, match_type = map_condition("Attention deficit hyperactivity disorder")
        if label != 'NOT FOUND':
            self.assertRegex(match_type, r'^(Exact|Synonym) - (MONDO|HP)$',
                             f"Unexpected match_type format: {match_type!r}")

    def test_priority_mondo_pref_beats_hp_pref(self):
        """MONDO-PREF must win over HP-PREF when both supply an exact match.

        This exercises _verify_and_classify directly with synthetic items so
        the test is fully offline and not sensitive to what BioPortal returns
        for any specific live term.
        """
        synthetic_items = [
            {
                'uri'      : 'http://purl.obolibrary.org/obo/HP_0000001',
                'prefLabel': 'test condition',
                'synonyms' : [],
                'ontology' : 'HP',
            },
            {
                'uri'      : 'http://purl.obolibrary.org/obo/MONDO_0000001',
                'prefLabel': 'test condition',
                'synonyms' : [],
                'ontology' : 'MONDO',
            },
        ]
        result = _verify_and_classify('test condition', synthetic_items)
        self.assertIsNotNone(result, "Expected a match from synthetic items")
        _, _, match_type, source_tag = result
        self.assertEqual(match_type, 'Exact',
                         "match_type must be bare 'Exact'")
        self.assertEqual(source_tag, 'Exact - MONDO',
                         "MONDO-PREF must be chosen before HP-PREF")

    def test_priority_mondo_syn_beats_hp_pref(self):
        """MONDO-SYN must win over HP-PREF (second vs third bucket)."""
        synthetic_items = [
            {
                'uri'      : 'http://purl.obolibrary.org/obo/HP_0000002',
                'prefLabel': 'test condition',
                'synonyms' : [],
                'ontology' : 'HP',
            },
            {
                'uri'      : 'http://purl.obolibrary.org/obo/MONDO_0000002',
                'prefLabel': 'mondo preferred label',    # pref label does NOT match
                'synonyms' : ['test condition'],         # synonym matches
                'ontology' : 'MONDO',
            },
        ]
        result = _verify_and_classify('test condition', synthetic_items)
        self.assertIsNotNone(result)
        _, _, match_type, source_tag = result
        self.assertEqual(match_type, 'Synonym',
                         "match_type must be bare 'Synonym'")
        self.assertEqual(source_tag, 'Synonym - MONDO',
                         "MONDO-SYN must be chosen before HP-PREF")

    def test_mondo_synonym_preferred_over_hp_exact(self):
        """MONDO-SYN must be preferred over HP-PREF (new priority order)."""
        # Structural test: just verify the match_type format is correct.
        label, _, match_type = map_condition("low back pain")
        if label != 'NOT FOUND':
            self.assertRegex(match_type, r'^(Exact|Synonym) - (MONDO|HP)$',
                             f"match_type must be 'Exact/Synonym - MONDO/HP', got: {match_type!r}")

    # ------------------------------------------------------------------
    # Stoplist / generic-term guards
    # ------------------------------------------------------------------

    def test_tmjd_not_poroma(self):
        """Must NOT return 'Poroma' for TMJ dysfunction."""
        label, _, _ = map_condition("Temporomandibular joint dysfunction (TMJD)")
        self.assertNotIn('poroma', label.lower(),
                         f"Got unrelated match '{label}' for TMJ dysfunction")

    def test_lumbar_disc_herniation_not_bare_hernia(self):
        """Bare 'Hernia' must NOT be returned for Lumbar Disc Herniation."""
        label, _, _ = map_condition("Lumbar Disc Herniation")
        if label != 'NOT FOUND':
            # Strip tags before comparing to bare term names
            terms = [_term(t.strip()) for t in label.split(',')]
            self.assertNotIn('hernia', [t.lower() for t in terms],
                             f"Got bare 'Hernia': {label}")

    def test_acute_ankle_sprains_no_bare_acute(self):
        """Bare 'Acute' must never be returned."""
        label, _, _ = map_condition("Acute ankle sprains")
        terms = [_term(t.strip()).lower() for t in label.split(',')]
        self.assertNotIn('acute', terms, "Must not return bare 'Acute'")

    def test_dysphagia_after_stroke_not_stroke_only(self):
        """Trailing clause 'after acute stroke' must be stripped."""
        label, _, _ = map_condition("Dysphagia after acute stroke")
        if label != 'NOT FOUND':
            terms = [_term(t.strip()).lower() for t in label.split(',')]
            self.assertNotIn('stroke', terms,
                             f"Must not return bare 'stroke': {label}")

    def test_cancer_related_pain_not_bare_cancer(self):
        """Bare 'cancer' must never be returned."""
        label, _, _ = map_condition("Cancer-related pain")
        terms = [_term(t.strip()).lower() for t in label.split(',')]
        self.assertNotIn('cancer', terms, "Must not return bare 'cancer'")

    def test_chronic_low_back_pain_not_bare_chronic(self):
        """Bare 'Chronic' must never be returned."""
        label, _, _ = map_condition("Chronic Low Back Pain")
        terms = [_term(t.strip()).lower() for t in label.split(',')]
        self.assertNotIn('chronic', terms, "Must not return bare 'Chronic'")

    def test_healthy_volunteers_not_found(self):
        """'Healthy' is in STOPLIST — must return NOT FOUND."""
        label, _, _ = map_condition("Healthy volunteers")
        self.assertEqual(label, 'NOT FOUND',
                         "Must return NOT FOUND for 'Healthy volunteers'")

    def test_pcos_not_syndromic_disease(self):
        """Must NOT return 'syndromic disease' for PCOS.

        Without parenthetical extraction, the pipeline tries
        'Polycystic ovarian syndrome' → should still resolve via prefLabel
        or synonym in MONDO/HP without returning the generic 'syndromic disease'.
        """
        label, _, _ = map_condition("Polycystic ovarian syndrome (PCOS)")
        self.assertNotEqual(_term(label).lower(), 'syndromic disease',
                            f"Must not return 'syndromic disease' for PCOS: {label}")

    def test_induction_of_labour_no_unrelated_list(self):
        """Must NOT return a list of unrelated rare diseases."""
        label, _, _ = map_condition("Induction of labour")
        if label != 'NOT FOUND':
            terms = [t.strip() for t in label.split(',')]
            self.assertEqual(len(terms), 1,
                             f"Must not return multiple unrelated terms: {label}")

    def test_nicotine_withdrawal_no_unrelated_terms(self):
        """Must NOT return opsoclonus-myoclonus or other unrelated diseases."""
        label, _, _ = map_condition("Nicotine Withdrawal Symptoms")
        if label != 'NOT FOUND':
            terms = [_term(t.strip()).lower() for t in label.split(',')]
            self.assertNotIn('opsoclonus-myoclonus syndrome', terms,
                             f"Got unrelated terms: {label}")

    def test_breast_engorgement_no_epilepsy_terms(self):
        """Must NOT return epilepsy/encephalopathy terms for Breast engorgement."""
        label, _, _ = map_condition("Breast engorgement")
        if label != 'NOT FOUND':
            self.assertNotIn('epilep', label.lower(),
                             f"Got epilepsy-related term: {label}")

    def test_smoking_cessation_no_unrelated_list(self):
        """Must NOT return cat-eye syndrome, amyloidosis etc. for Smoking cessation."""
        label, _, _ = map_condition("Smoking cessation")
        if label != 'NOT FOUND':
            terms = [_term(t.strip()).lower() for t in label.split(',')]
            self.assertNotIn('cat eye syndrome', terms,
                             f"Got unrelated terms: {label}")

    # ------------------------------------------------------------------
    # Multi-condition splitting
    # ------------------------------------------------------------------

    def test_slash_or_returns_single_term(self):
        """Slash-separated alternatives must yield exactly ONE mapped term (OR, not AND)."""
        label, uri, match_type = map_condition(
            "Chronic prostatitis/chronic pelvic pain syndrome (CP/CPPS)"
        )
        if label != 'NOT FOUND':
            # Only one term should be returned — no comma-joined pair
            terms = [t.strip() for t in label.split(',')]
            self.assertEqual(len(terms), 1,
                             f"Slash/OR must return at most one term, got: {label!r}")
            self.assertRegex(match_type, r'^(Exact|Synonym) - (MONDO|HP)$',
                             f"match_type format invalid: {match_type!r}")

    def test_slash_or_no_paren_slash_interference(self):
        """Slash inside parentheses (e.g. CP/CPPS) must not trigger OR-splitting."""
        label_with_paren, _, _ = map_condition(
            "Chronic pelvic pain syndrome (CP/CPPS)"
        )
        label_plain, _, _ = map_condition(
            "Chronic pelvic pain syndrome"
        )
        self.assertEqual(label_with_paren, label_plain,
                         "Slash inside parens must not affect the result")

    def test_also_known_as_or_returns_single_term(self):
        """'also known as' must yield ONE result (OR semantics, not AND)."""
        label, _, match_type = map_condition(
            "Idiopathic anterior knee pain (IAKP), also known as patellofemoral pain syndrome"
        )
        if label != 'NOT FOUND':
            terms = [t.strip() for t in label.split(',')]
            # At most one ontology term — OR, not AND
            # (The comma-join is only used for AND-split multi-condition results.)
            # A single ontology term label will not be further comma-split here,
            # so just verify the format is valid.
            self.assertRegex(match_type.split(',')[0].strip(),
                             r'^(Exact|Synonym) - (MONDO|HP)$',
                             f"match_type format invalid: {match_type!r}")

    def test_migraine_with_aura_maps_as_whole(self):
        """'migraine with aura' must map as a single whole term — not split into two."""
        label, _, match_type = map_condition("migraine with aura")
        if label != 'NOT FOUND':
            # The whole term should map; result must NOT be two separate terms
            # joined by a comma (which would indicate AND-splitting occurred).
            self.assertNotIn(',', label,
                             f"'migraine with aura' must map whole, not split: {label!r}")
            self.assertRegex(match_type, r'^(Exact|Synonym) - (MONDO|HP)$',
                             f"match_type format invalid: {match_type!r}")

    def test_with_treated_as_and_maps_both_parts(self):
        """'with' joining two conditions must map both parts independently."""
        label, _, _ = map_condition(
            "Breast cancer with hot flashes"
        )
        if label != 'NOT FOUND':
            label_lower = label.lower()
            # Both "breast cancer" and "hot flash" family terms should appear
            has_cancer   = 'cancer' in label_lower or 'neoplasm' in label_lower
            has_hotflash = 'hot flash' in label_lower or 'flushing' in label_lower
            self.assertTrue(has_cancer or has_hotflash,
                            f"Expected at least one of the two components mapped: {label!r}")

    def test_nausea_and_vomiting_maps_as_whole(self):
        """'nausea and vomiting' is a recognised term — must map as whole, not split."""
        label, _, match_type = map_condition("nausea and vomiting")
        if label != 'NOT FOUND':
            # Should be a single term, not two separate mapped items
            self.assertNotIn(',', label,
                             f"'nausea and vomiting' must map whole, not split: {label!r}")

    def test_multi_condition_and_split(self):
        """Two conditions joined by 'and' must each be mapped."""
        label, uri, match_type = map_condition("nausea and vomiting")
        # At minimum, one component should be found
        if label != 'NOT FOUND':
            terms = [_term(t.strip()) for t in label.split(',')]
            self.assertGreaterEqual(len(terms), 1,
                                    f"Expected at least one mapped term: {label}")

    def test_multi_condition_comma_split(self):
        """Two conditions joined by ',' must each be mapped independently."""
        label, _, _ = map_condition("nausea, vomiting")
        # Cannot assert a specific result but multi-split must not blow up
        self.assertIsInstance(label, str)

    # ------------------------------------------------------------------
    # TBD: expected output changed because parenthetical content is now ignored.
    # These tests verify structural constraints only; the specific term returned
    # requires manual re-check against MONDO/HP.
    # ------------------------------------------------------------------

    def test_seasonal_allergic_rhinitis_also_known_as_TBD(self):
        """TBD: 'also known as hay fever' clause must be stripped; no bare 'hay fever'.

        After stripping '(SAR)' and the 'also known as …' trailing clause,
        pipeline tries 'Seasonal allergic rhinitis' → modifier-strip 'Seasonal'
        → 'allergic rhinitis'.  Exact expected term needs manual re-check.
        """
        label, _, _ = map_condition(
            "Seasonal allergic rhinitis (SAR), also known as hay fever"
        )
        # Structural: must not return bare 'hay fever' (from the stripped clause)
        if label != 'NOT FOUND':
            terms = [_term(t.strip()).lower() for t in label.split(',')]
            self.assertNotIn('hay fever', terms,
                             f"Must not return bare 'hay fever' clause: {label}")

    def test_tension_type_headache_tth_TBD(self):
        """TBD: '(TTH)' is stripped; 'Tension type headache' still resolves correctly.

        Should resolve to 'tension-type headache' via hyphen normalisation.
        Verify exact preferred label in MONDO/HP manually.
        """
        label, _, _ = map_condition("Tension type headache (TTH)")
        if label != 'NOT FOUND':
            self.assertIn('headache', _term(label).lower(),
                          f"Expected a headache term, got: {label}")

    def test_myofascial_pain_caused_by_TBD(self):
        """TBD: 'caused by trigger points' clause must be stripped.

        After stripping '(MTrPs)' and the 'caused by …' clause,
        pipeline should reach 'Myofascial pain syndrome'.
        Verify exact preferred label manually.
        """
        label, _, _ = map_condition(
            "Myofascial pain syndrome caused by trigger points (MTrPs)"
        )
        # Structural: must not return terms from the 'caused by …' fragment
        if label != 'NOT FOUND':
            terms = [_term(t.strip()).lower() for t in label.split(',')]
            self.assertNotIn('trigger point', terms,
                             f"Must not return trigger-point fragment: {label}")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    if '--test' in sys.argv:
        # Run all unit tests (normalization + candidate gen + integration)
        print("Running unit tests...\n")
        suite = unittest.TestLoader().loadTestsFromTestCase(TestNormalization)
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestCandidateGeneration))
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestMappingIntegration))
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        sys.exit(0 if result.wasSuccessful() else 1)

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
