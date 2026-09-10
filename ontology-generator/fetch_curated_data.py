"""
fetch_curated_data.py — Curated Data Downloader for the TARA Ontology Generator

Downloads each curated tab from the TARA Ontology Curation Google Sheet as a CSV
file and saves it to the appropriate local directory under ../curated-data/.

Sheet URL: https://docs.google.com/spreadsheets/d/18lqD3dHS53wtEd05Xtfx8w_AapJRFBYMGL5bTK5a-3w/

Which sheet (and thus which version of the curation data) to pull from is
managed by the maintainer: edit SHEET_ID below.

Tabs are fetched by name rather than by numeric GID: the script first reads the
spreadsheet's `htmlview` page (a plain unauthenticated GET, same access level as
the CSV download) to build a {tab name -> gid} map, matches each wanted name
case-insensitively, then downloads that tab through the sheet's CSV *export*
endpoint (`/export?format=csv&gid=...`).

    Why export and not the gviz endpoint: the older
    `/gviz/tq?tqx=out:csv&sheet=<name>` endpoint is lossy - it type-infers
    columns, stops at blank rows (dropping every row after the first gap), and
    collapses empty columns. On this sheet it silently returned ~1200 of the
    ~1580 acupoints-locations rows. `/export?format=csv` returns the tab
    verbatim: every row, every column, exactly as displayed.

The lower-case names in TAB_NAMES are also the CSV file names the ontology
adapter code expects.

Run this script before generate_ontology.py to ensure the local CSV files are up
to date.
Author: Fahim Imam
Last updated: September 8, 2026
"""

import os
import re
import sys

import requests

# Google Sheet to pull from. The maintainer sets which sheet / version by
# editing this ID.
SHEET_ID = '18lqD3dHS53wtEd05Xtfx8w_AapJRFBYMGL5bTK5a-3w'

# Curated tab names (lower-case). Fetched by name; see the module docstring.
TAB_NAMES = [
    'meridians',
    'acupoints-category',
    'acupoints',
    'extra-acupoints',
    'special-points',
    'acupoints-locations',
    'special-points-association',
    'acupoints-nerves',
    'acupoints-veins-arteries',
]

# Directory to save the CSV files - the canonical curation-sheet location that
# generate_ontology.py reads from (its CURATED_DATA_DIR).
ACUPOINTS_DIR = "../curated-data/ontology-curation-sheet/acupoints"
os.makedirs(ACUPOINTS_DIR, exist_ok=True)

# Map each tab to its output directory
TAB_OUTPUT_DIRS = {
                    'meridians'                 : ACUPOINTS_DIR,
                    'acupoints-category'        : ACUPOINTS_DIR,
                    'acupoints'                 : ACUPOINTS_DIR,
                    'extra-acupoints'           : ACUPOINTS_DIR,
                    'special-points'            : ACUPOINTS_DIR,
                    'acupoints-locations'       : ACUPOINTS_DIR,
                    'special-points-association': ACUPOINTS_DIR,
                    'acupoints-nerves'          : ACUPOINTS_DIR,
                    'acupoints-veins-arteries'  : ACUPOINTS_DIR
                 }


def fetch_tab_gids(sheet_id):
    """Return {lower-case tab name -> gid string} for every tab in the sheet.

    Reads the spreadsheet's htmlview page, whose embedded sheet switcher lists
    each tab as  items.push({name: "<Tab Name>", pageUrl: "...gid=<digits>..."}).
    No API key or auth needed - works for any link-shared sheet.
    """
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/htmlview"
    resp = requests.get(url)
    resp.raise_for_status()
    pairs = re.findall(
        r'items\.push\(\{name:\s*"([^"]+)",\s*pageUrl:\s*"[^"]*?gid=(\d+)',
        resp.text,
    )
    if not pairs:
        raise RuntimeError(
            "Could not read the tab list from the sheet's htmlview page - the "
            "page format may have changed, or the sheet is not link-shared."
        )
    return {name.strip().lower(): gid for name, gid in pairs}


def download_tab_as_csv(sheet_id, tab_name, gid, output_dir):
    """Download one tab (by gid) through the CSV export endpoint and save it."""
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    response = requests.get(url)

    if response.status_code == 200:
        file_path = os.path.join(output_dir, f"{tab_name}.csv")
        with open(file_path, 'wb') as file:
            file.write(response.content)
        print(f"Downloaded and saved {tab_name} (gid {gid}) as {file_path}")
    else:
        print(f"Failed to download {tab_name}: {response.status_code}")


# The main function
def main():
    gid_map = fetch_tab_gids(SHEET_ID)

    missing = [name for name in TAB_NAMES if name not in gid_map]
    if missing:
        print(
            "ERROR: these tab names were not found in the sheet "
            f"(available: {', '.join(sorted(gid_map))}):\n  " + "\n  ".join(missing)
        )
        sys.exit(1)

    for tab_name in TAB_NAMES:
        download_tab_as_csv(
            SHEET_ID, tab_name, gid_map[tab_name], TAB_OUTPUT_DIRS[tab_name]
        )


if __name__ == "__main__":
    main()
