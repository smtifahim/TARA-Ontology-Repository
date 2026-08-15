"""
reconcile_sheets.py — Google Sheets Paper_ID Reconciliation for TARA Ontology

Downloads four Google Sheets tabs (one "source of truth" article list plus
three extraction/mapping sheets) and cross-references them by article title
so that every extraction row can be tagged with its Paper_ID from the source
sheet.

Sheets
------
Sheet1 ("All_Articles")                       — source of truth article list
Sheet2 ("Disease-Conditions-112625")           — condition extraction sheet
Sheet3 ("Western-Conditions-112625-Mapped")    — condition mapping sheet
Sheet4 ("acupoints-list-mapped-112625")        — acupoint extraction sheet

Steps
-----
1. Download each tab as CSV and save it under input_sheets/<tab_name>.csv.
2. From Sheet1, keep only: Paper_ID, Title, Disease/ Condition (Western),
   Disease/ Condition (TCM), Acupoint List. This subset is the reconciliation
   reference used for every comparison below.
3. For Sheet2/Sheet3/Sheet4: compare each row's Article-Title against Sheet1's
   Title (case-sensitive; any Chinese-character substrings are stripped from
   Article-Title before comparing, since several titles are bilingual
   "English title <space> Chinese title" strings). On a match, prepend a new
   Paper_ID column populated from Sheet1. Save the result under
   output_sheets/<tab_name>.csv.
4. For each of Sheet2/3/4, also save a "Missing_in_<tab_name>.csv" report:
   Sheet1 rows that have NO matching title in that sheet. It reuses that
   sheet's own (Paper_ID-prepended) column headers, populating whichever
   columns map from Sheet1 (Title->Article-Title,
   Disease/Condition(Western)->Condition-Extracted-Western,
   Disease/Condition(TCM)->Condition-Extracted-TCM,
   Acupoint List->Acupoints-Extracted) and leaving the rest blank.
5. Save "Missing_in_All_Articles.csv": rows from Sheet2/3/4 whose title has
   no match in Sheet1 (i.e. Sheet1 is missing these entries), deduplicated by
   title across the three sheets. Uses Sheet1's own column headers (Paper_ID
   left blank, since these rows don't exist in Sheet1) plus a Source-Sheet(s)
   column recording which tab(s) the title came from.

Usage:
  python reconcile_sheets.py

Author: Fahim Imam
"""

import os
import re

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Directories
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(_HERE, 'input_sheets')
OUTPUT_DIR = os.path.join(_HERE, 'output_sheets')
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Sheet configuration
# ---------------------------------------------------------------------------
SHEET1 = {
    'sheet_id': '15vSWWzJzuWAb7wUSm2K2YKmCGawT21zBiRXi4P2bhis',
    'gid': '602913291',
    'tab_name': 'All_Articles',
}

TARGET_SHEETS = [
    {
        'sheet_id': '1V7Q6Ike8ojEjqWXi_DQDSwIevlvGxNmflDiRvirMJRA',
        'gid': '915593250',
        'tab_name': 'Disease-Conditions-112625',
    },
    {
        'sheet_id': '1V7Q6Ike8ojEjqWXi_DQDSwIevlvGxNmflDiRvirMJRA',
        'gid': '1740285817',
        'tab_name': 'Western-Conditions-112625-Mapped',
    },
    {
        'sheet_id': '1V7Q6Ike8ojEjqWXi_DQDSwIevlvGxNmflDiRvirMJRA',
        'gid': '237101142',
        'tab_name': 'acupoints-list-mapped-112625',
    },
]

# ---------------------------------------------------------------------------
# Column names
# ---------------------------------------------------------------------------
SHEET1_PAPER_ID_COL = 'Paper_ID'
SHEET1_TITLE_COL = 'Title'
SHEET1_COLUMNS = [
    'Paper_ID',
    'Title',
    'Disease/ Condition (Western)',
    'Disease/ Condition (TCM)',
    'Acupoint List',
]

TARGET_TITLE_COL = 'Article-Title'

# Sheet1 column -> target-sheet column, used to populate missing-article rows
# in both directions.
SHEET1_TO_TARGET_MAP = {
    'Title': 'Article-Title',
    'Disease/ Condition (Western)': 'Condition-Extracted-Western',
    'Disease/ Condition (TCM)': 'Condition-Extracted-TCM',
    'Acupoint List': 'Acupoints-Extracted',
}
TARGET_TO_SHEET1_MAP = {v: k for k, v in SHEET1_TO_TARGET_MAP.items()}

# ---------------------------------------------------------------------------
# Chinese-character stripping (CJK ideographs, CJK punctuation, fullwidth forms)
# ---------------------------------------------------------------------------
_CJK_RE = re.compile(
    r'[一-鿿㐀-䶿豈-﫿　-〿＀-￯]+'
)


def clean_title(text) -> str:
    """Strip Chinese-character substrings and surrounding whitespace for comparison."""
    if not isinstance(text, str):
        return ''
    text = _CJK_RE.sub('', text)
    # Parenthetical groups that held only Chinese text (e.g. "Gan (肝)") are
    # now empty shells like "()" or "( )" — drop those too.
    text = re.sub(r'\(\s*\)', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ---------------------------------------------------------------------------
# Formula-injection protection (Google Sheets CSV exports may contain
# leading =, +, -, @, | characters that spreadsheet apps treat as formulas)
# ---------------------------------------------------------------------------
_FORMULA_PREFIX_RE = re.compile(r'^[=+\-@|]')


def _csv_safe(val):
    if isinstance(val, str) and _FORMULA_PREFIX_RE.match(val):
        return '\t' + val
    return val


def _safe_apply(df: pd.DataFrame) -> pd.DataFrame:
    try:
        return df.map(_csv_safe)          # pandas >= 2.1
    except AttributeError:
        return df.applymap(_csv_safe)     # pandas < 2.1


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
def download_tab(sheet_id: str, gid: str, tab_name: str) -> pd.DataFrame:
    """Download one Google Sheets tab as CSV, save raw to input_sheets/, return a DataFrame."""
    url = (f"https://docs.google.com/spreadsheets/d/{sheet_id}"
           f"/gviz/tq?tqx=out:csv&gid={gid}")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    raw_path = os.path.join(INPUT_DIR, f"{tab_name}.csv")
    with open(raw_path, 'wb') as f:
        f.write(resp.content)
    print(f"  Saved input CSV: {raw_path}")

    df = pd.read_csv(raw_path, dtype=str, keep_default_na=False)
    # Drop trailing blank/unnamed columns (Google Sheets export artifact)
    df = df.loc[:, ~df.columns.str.match(r'^Unnamed:')]
    df = df.loc[:, [c for c in df.columns if c.strip() != '']]
    print(f"    {len(df)} rows, {len(df.columns)} columns.")
    return df


# ---------------------------------------------------------------------------
# Main reconciliation
# ---------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("TARA Google Sheets Reconciliation")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Step 1/2: Sheet1 — download, save raw, then build the 5-column
    # reconciliation subset and a title -> Paper_ID(s) lookup.
    # ------------------------------------------------------------------
    print(f"\n[Sheet1] Downloading tab: {SHEET1['tab_name']}")
    sheet1_full = download_tab(SHEET1['sheet_id'], SHEET1['gid'], SHEET1['tab_name'])

    missing_cols = [c for c in SHEET1_COLUMNS if c not in sheet1_full.columns]
    if missing_cols:
        raise ValueError(f"Sheet1 is missing expected column(s): {missing_cols}")
    sheet1 = sheet1_full[SHEET1_COLUMNS].copy()
    sheet1['_clean_title'] = sheet1[SHEET1_TITLE_COL].map(clean_title)

    # title -> list of Paper_IDs (a handful of Sheet1 titles are duplicated
    # across two different Paper_IDs; keep every match rather than dropping
    # data silently)
    title_to_paper_ids: dict = {}
    for _, row in sheet1.iterrows():
        title_to_paper_ids.setdefault(row['_clean_title'], []).append(row[SHEET1_PAPER_ID_COL])

    # title -> first-seen Sheet1 row (used to populate "Missing_in_<tab>" reports)
    title_to_sheet1_row: dict = {}
    for _, row in sheet1.iterrows():
        title_to_sheet1_row.setdefault(row['_clean_title'], row)

    all_sheet1_titles = set(title_to_paper_ids.keys())
    matched_sheet1_titles: set = set()

    # Collected across all three target sheets, for the reverse "Sheet1 is
    # missing these" report at the end.
    unmatched_target_rows: list = []  # list of (clean_title, source_tab_name, row)

    # ------------------------------------------------------------------
    # Step 3/4: Sheet2, Sheet3, Sheet4
    # ------------------------------------------------------------------
    for cfg in TARGET_SHEETS:
        tab_name = cfg['tab_name']
        print(f"\n[{tab_name}] Downloading tab...")
        df = download_tab(cfg['sheet_id'], cfg['gid'], tab_name)

        if TARGET_TITLE_COL not in df.columns:
            raise ValueError(f"'{TARGET_TITLE_COL}' column not found in tab '{tab_name}'.")

        clean_titles = df[TARGET_TITLE_COL].map(clean_title)

        paper_ids = []
        for i, ct in enumerate(clean_titles):
            candidates = title_to_paper_ids.get(ct)
            if candidates:
                matched_sheet1_titles.add(ct)
                paper_ids.append(';'.join(candidates))
            else:
                paper_ids.append('')
                unmatched_target_rows.append((ct, tab_name, df.iloc[i]))

        df.insert(0, SHEET1_PAPER_ID_COL, paper_ids)

        matched_count = sum(1 for p in paper_ids if p)
        print(f"    Matched {matched_count}/{len(df)} rows to a Sheet1 Paper_ID.")

        out_path = os.path.join(OUTPUT_DIR, f"{tab_name}.csv")
        _safe_apply(df).to_csv(out_path, index=False)
        print(f"    Saved output CSV: {out_path}")

        # --------------------------------------------------------------
        # Missing_in_<tab_name>.csv — Sheet1 rows with no match in this tab
        # --------------------------------------------------------------
        this_tab_titles = set(clean_titles)
        missing_titles = [t for t in sheet1['_clean_title'].tolist()
                          if t and t not in this_tab_titles]
        # de-duplicate while preserving order
        seen = set()
        missing_titles = [t for t in missing_titles if not (t in seen or seen.add(t))]

        missing_rows = []
        for t in missing_titles:
            s1_row = title_to_sheet1_row[t]
            out_row = {col: '' for col in df.columns}
            for paper_id in title_to_paper_ids[t]:
                out_row[SHEET1_PAPER_ID_COL] = paper_id
                for sheet1_col, target_col in SHEET1_TO_TARGET_MAP.items():
                    if target_col in df.columns:
                        out_row[target_col] = s1_row[sheet1_col]
                missing_rows.append(dict(out_row))

        missing_df = pd.DataFrame(missing_rows, columns=df.columns)
        missing_path = os.path.join(OUTPUT_DIR, f"Missing_in_{tab_name}.csv")
        _safe_apply(missing_df).to_csv(missing_path, index=False)
        print(f"    {len(missing_df)} Sheet1 article(s) missing from this tab.")
        print(f"    Saved missing-articles CSV: {missing_path}")

    # ------------------------------------------------------------------
    # Step 5: Missing_in_All_Articles.csv — Sheet2/3/4 rows with no match
    # in Sheet1, deduplicated by title across all three sheets.
    # ------------------------------------------------------------------
    print(f"\n[{SHEET1['tab_name']}] Building reverse missing-articles report...")
    by_title: dict = {}
    for clean_t, tab_name, row in unmatched_target_rows:
        if not clean_t:
            continue
        entry = by_title.setdefault(clean_t, {
            'Title': clean_t,
            'Disease/ Condition (Western)': '',
            'Disease/ Condition (TCM)': '',
            'Acupoint List': '',
            'Source-Sheet(s)': set(),
        })
        entry['Source-Sheet(s)'].add(tab_name)
        for target_col, sheet1_col in TARGET_TO_SHEET1_MAP.items():
            if target_col in row.index and not entry[sheet1_col]:
                val = row[target_col]
                if isinstance(val, str) and val.strip():
                    entry[sheet1_col] = val

    reverse_rows = []
    for entry in by_title.values():
        reverse_rows.append({
            'Paper_ID': '',
            'Title': entry['Title'],
            'Disease/ Condition (Western)': entry['Disease/ Condition (Western)'],
            'Disease/ Condition (TCM)': entry['Disease/ Condition (TCM)'],
            'Acupoint List': entry['Acupoint List'],
            'Source-Sheet(s)': '; '.join(sorted(entry['Source-Sheet(s)'])),
        })

    reverse_df = pd.DataFrame(
        reverse_rows,
        columns=SHEET1_COLUMNS + ['Source-Sheet(s)'],
    )
    reverse_path = os.path.join(OUTPUT_DIR, f"Missing_in_{SHEET1['tab_name']}.csv")
    _safe_apply(reverse_df).to_csv(reverse_path, index=False)
    print(f"    {len(reverse_df)} unique article(s) present in Sheet2/3/4 but missing from Sheet1.")
    print(f"    Saved missing-articles CSV: {reverse_path}")

    print("\nDone.")


if __name__ == '__main__':
    main()
