"""
map_tara_acupoints.py — Acupoints Terms Mapper for TARA Ontology

This script:
  1. Downloads acupoints data from one or more Google Sheet tabs and saves
     each as a CSV under input_files/acupoints_source_sheets/ (one file per
     tab, named by tab name). Add new tabs to ACUPOINTS_SHEETS below.
  2. Runs the SPARQL query in
     input_files/sparql/query/tara-acupoints-alt-labels.rq against the
     TARA-Acupoints Stardog database (via downstream/common-scripts/lib/
     query_tara_data.py) and saves the results as JSON and CSV under
     input_files/sparql/query_results/{json,csv}/.
  3. For every downloaded sheet, reads the 'Acupoints-Normalized' column,
     splits each cell on commas (the only true separator between distinct
     acupoints), and matches each individual acupoint against the
     Acupoint_Label / Acupoint_Alt_Label values from
     tara-acupoints-alt-labels.csv.

Matching:
  Both the source acupoint text and the ontology Acupoint_Label /
  Acupoint_Alt_Label values are normalized the same way before comparison:
      lowercase, then strip everything that is not a letter or digit
      (whitespace, dashes, dots, and any other punctuation).
  e.g. "ST 36", "st-36", "St.36" all normalize to "st36" and match each other.
  A primary Acupoint_Label match always takes precedence over an
  Acupoint_Alt_Label match if both would otherwise resolve to the same
  normalized text (this only matters in the rare case of a collision).

Output columns written back into each mapped sheet (these columns already
exist in the source sheets and are overwritten with freshly computed values;
all other columns and the original row order are left untouched):
  Acupoints-Mapped      : Acupoint_Label(s) that were matched, comma-separated,
                           in the same order they appear in Acupoints-Normalized
                           (unmapped entries are skipped in this column).
  Acupoints-Unmappable  : the original acupoint text(s) that could not be
                           matched, comma-separated, in their original order.
  Acupoints_TARA_IDs    : Acupoint_CURIE for each entry in Acupoints-Mapped,
                           comma-separated, in the same order.

Setup (one-time):
  STARDOG_TARA_USERNAME and STARDOG_TARA_PASSWORD must be set in a .env file
  in this directory (script/.env).
  Required packages: pip install pystardog pandas requests python-dotenv

Usage:
  python map_tara_acupoints.py

Author: Fahim Imam
Version: 1.0
"""

import itertools
import os
import re
import sys
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent  # …/acupoints_mapping
REPO_ROOT = SCRIPT_DIR.parents[6]  # …/TARA-Ontology-Repository

load_dotenv(dotenv_path=SCRIPT_DIR / '.env')

# Add downstream/common-scripts/lib to the Python path so we can import
# query_tara_data without installing it as a package.
LIB_DIR = REPO_ROOT / 'downstream' / 'common-scripts' / 'lib'
sys.path.insert(0, str(LIB_DIR))

from query_tara_data import run_queries

# ---------------------------------------------------------------------------
# Source Sheet Configuration
#
# Each entry maps a tab name to its (Google Sheet ID, GID). The downloaded
# CSV is saved as <tab_name>.csv under input_files/acupoints_source_sheets/.
#
# To add a new acupoints sheet in the future, add a new entry here:
# ---------------------------------------------------------------------------
ACUPOINTS_SHEETS = {
    'acupoints-list-mapped-112625': ('14WIm3G6PoIHYrECjEetgd7pvKjzrntR57HbdMJ2ZNQI', '1541369758'),
     #'acupoints-list-mapped-112625': ('1V7Q6Ike8ojEjqWXi_DQDSwIevlvGxNmflDiRvirMJRA', '237101142'),

    # Future acupoint sheets — add new tab entries below:
    # 'tab-name': ('<SHEET_ID>', '<GID>'),
}

# ---------------------------------------------------------------------------
# Directories
# ---------------------------------------------------------------------------
SOURCE_DIR = BASE_DIR / 'input_files' / 'acupoints_source_sheets'
QUERY_DIR = BASE_DIR / 'input_files' / 'sparql' / 'query'
QUERY_RESULTS_DIR = BASE_DIR / 'input_files' / 'sparql' / 'query_results'
MAPPED_DIR = BASE_DIR / 'output_files' / 'acupoints_mapped_sheets'

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(MAPPED_DIR, exist_ok=True)

ALT_LABELS_QUERY_FILE = QUERY_DIR / 'tara-acupoints-alt-labels.rq'

# ---------------------------------------------------------------------------
# Stardog connection (TARA-Acupoints database)
# ---------------------------------------------------------------------------
DB_NAME = 'TARA-Ontology'
USERNAME = os.getenv('STARDOG_TARA_USERNAME')
PASSWORD = os.getenv('STARDOG_TARA_PASSWORD')

# ---------------------------------------------------------------------------
# Column names
# ---------------------------------------------------------------------------
ACUPOINTS_NORMALIZED_COLUMN = 'Acupoints-Normalized'
ACUPOINTS_MAPPED_COLUMN = 'Acupoints-Mapped'
ACUPOINTS_UNMAPPABLE_COLUMN = 'Acupoints-Unmappable'
ACUPOINTS_TARA_IDS_COLUMN = 'Acupoints_TARA_IDs'


# ===========================================================================
# Normalization
# ===========================================================================

_NORMALIZE_RE = re.compile(r'[^a-z0-9]')


def _step(steps, message: str) -> None:
    """Prints a numbered 'Step N: <message>' line, drawing N from steps (itertools.count())."""
    print(f"\nStep {next(steps)}: {message}")


def normalize_for_matching(text) -> str:
    """Lowercase and strip everything but letters/digits (spaces, dashes, dots, etc.)."""
    if text is None:
        return ''
    return _NORMALIZE_RE.sub('', str(text).lower())


def parse_acupoints_normalized(raw_value) -> list:
    """Splits an Acupoints-Normalized cell into individual acupoint tokens.

    Comma is the only true separator. Empty/NaN values and "Not specified"
    (case-insensitive) resolve to no tokens.
    """
    if pd.isna(raw_value):
        return []
    text = str(raw_value).strip()
    if not text or text.lower().startswith('not specified'):
        return []
    return [tok.strip() for tok in text.split(',') if tok.strip()]


# ===========================================================================
# Formula-injection protection (defensive, since values originate from
# free-text spreadsheet cells and are written back out as CSV)
# ===========================================================================

_FORMULA_PREFIX_RE = re.compile(r'^[=+\-@|]')


def _csv_safe(val):
    if isinstance(val, str) and _FORMULA_PREFIX_RE.match(val):
        return '\t' + val
    return val


def _safe_apply(df: pd.DataFrame) -> pd.DataFrame:
    """Apply _csv_safe across the whole dataframe (pandas 1.x / 2.x compat)."""
    try:
        return df.map(_csv_safe)           # pandas >= 2.1
    except AttributeError:
        return df.applymap(_csv_safe)      # pandas < 2.1


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
    print(f"> Saved source CSV: {os.path.relpath(file_path)}")
    return file_path


# ===========================================================================
# Acupoint lookup table (from tara-acupoints-alt-labels.csv)
# ===========================================================================

def build_alt_labels_lookup(csv_path: str) -> dict:
    """
    Builds a normalized-text -> (Acupoint_Label, Acupoint_CURIE) lookup from
    the tara-acupoints-alt-labels query results.

    Primary labels are indexed in a first pass, then alt labels in a second
    pass (only filling in normalized forms not already claimed), so a
    primary Acupoint_Label always takes precedence over an
    Acupoint_Alt_Label on collision.
    """
    df = pd.read_csv(csv_path, keep_default_na=False)
    lookup: dict = {}

    for _, row in df.iterrows():
        label = str(row.get('Acupoint_Label', '')).strip()
        curie = str(row.get('Acupoint_CURIE', '')).strip()
        if not label or not curie:
            continue
        lookup.setdefault(normalize_for_matching(label), (label, curie))

    for _, row in df.iterrows():
        label = str(row.get('Acupoint_Label', '')).strip()
        curie = str(row.get('Acupoint_CURIE', '')).strip()
        alt_field = str(row.get('Acupoint_Alt_Label', '')).strip()
        if not label or not curie or not alt_field:
            continue
        for alt in alt_field.split(','):
            alt = alt.strip()
            if not alt:
                continue
            lookup.setdefault(normalize_for_matching(alt), (label, curie))

    return lookup


def map_tokens(tokens: list, lookup: dict):
    """Maps a list of raw acupoint tokens against lookup.

    Returns (mapped_labels, mapped_curies, unmapped_tokens), each a list in
    the original token order (unmapped tokens keep their original text).
    """
    mapped_labels, mapped_curies, unmapped = [], [], []
    for tok in tokens:
        hit = lookup.get(normalize_for_matching(tok))
        if hit:
            label, curie = hit
            mapped_labels.append(label)
            mapped_curies.append(curie)
        else:
            unmapped.append(tok)
    return mapped_labels, mapped_curies, unmapped


# ===========================================================================
# Per-sheet mapping pipeline
# ===========================================================================

def map_acupoints_sheet(tab_name: str, lookup: dict, steps) -> None:
    print(f"\nProcessing tab: {tab_name}")
    sheet_id, gid = ACUPOINTS_SHEETS[tab_name]

    _step(steps, f"Downloading source sheet '{tab_name}'...")
    csv_path = download_sheet_as_csv(sheet_id, gid, tab_name)

    df = pd.read_csv(csv_path, keep_default_na=False)
    df = df.loc[:, ~df.columns.str.match(r'^Unnamed:')]
    print(f"> Loaded {len(df)} rows, {len(df.columns)} columns.")

    if ACUPOINTS_NORMALIZED_COLUMN not in df.columns:
        raise ValueError(
            f"Column '{ACUPOINTS_NORMALIZED_COLUMN}' not found in sheet '{tab_name}'.\n"
            f"Available columns: {list(df.columns)}"
        )

    for col in (ACUPOINTS_MAPPED_COLUMN, ACUPOINTS_UNMAPPABLE_COLUMN, ACUPOINTS_TARA_IDS_COLUMN):
        if col not in df.columns:
            df[col] = ''

    _step(steps, f"Matching '{ACUPOINTS_NORMALIZED_COLUMN}' values against the TARA Ontology lookup")
    fully_mapped, partially_mapped, fully_unmapped = 0, 0, 0

    for i, row in df.iterrows():
        tokens = parse_acupoints_normalized(row[ACUPOINTS_NORMALIZED_COLUMN])
        if not tokens:
            df.at[i, ACUPOINTS_MAPPED_COLUMN] = ''
            df.at[i, ACUPOINTS_UNMAPPABLE_COLUMN] = ''
            df.at[i, ACUPOINTS_TARA_IDS_COLUMN] = ''
            continue

        mapped_labels, mapped_curies, unmapped = map_tokens(tokens, lookup)
        df.at[i, ACUPOINTS_MAPPED_COLUMN] = ', '.join(mapped_labels)
        df.at[i, ACUPOINTS_UNMAPPABLE_COLUMN] = ', '.join(unmapped)
        df.at[i, ACUPOINTS_TARA_IDS_COLUMN] = ', '.join(mapped_curies)

        if unmapped and mapped_labels:
            partially_mapped += 1
        elif unmapped:
            fully_unmapped += 1
        else:
            fully_mapped += 1

    print(f"> {fully_mapped} rows fully mapped, {partially_mapped} rows partially mapped, "
          f"{fully_unmapped} rows fully unmappable.")

    output_path = os.path.join(MAPPED_DIR, f"{tab_name}.csv")
    _safe_apply(df).to_csv(output_path, index=False)
    print(f"> Saved mapped CSV: {os.path.relpath(output_path)}")


# ===========================================================================
# Entry point
# ===========================================================================

def main():
    print("=" * 94)
    print("TARA Acupoints Mapper")
    print("=" * 94)

    steps = itertools.count()

    _step(steps, "Running tara-acupoints-alt-labels.rq query against Stardog...")
    query_summary = run_queries(
        query_files=[str(ALT_LABELS_QUERY_FILE)],
        output_dir=str(QUERY_RESULTS_DIR),
        db_name=DB_NAME,
        username=USERNAME,
        password=PASSWORD,
    )
    alt_labels_csv = query_summary[str(ALT_LABELS_QUERY_FILE)]['csv']
    print(f"  Saved query results for acupoint alternate labels from TARA Ontology.")

    _step(steps, "Building acupoint label/synonym lookup table...")
    lookup = build_alt_labels_lookup(alt_labels_csv)
    print(f"> Built lookup table with {len(lookup)} normalized label/synonym entries.")

    for tab_name in ACUPOINTS_SHEETS:
        map_acupoints_sheet(tab_name, lookup, steps)

    print("\nDone. All steps completed successfully.")
    print(f"> Mapped sheets are saved under: {os.path.relpath(MAPPED_DIR)}")
    print("=" * 94)


if __name__ == '__main__':
    main()
