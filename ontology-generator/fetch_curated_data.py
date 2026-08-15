"""
fetch_curated_data.py — Curated Data Downloader for the TARA Ontology Generator

Downloads each curated tab from the Official TARA Ontology Curation Google Sheet as a CSV
file and saves it to the appropriate local directory under ../curated-data/.

Sheet URL: https://docs.google.com/spreadsheets/d/1hvUcTrw-b9ly8Yn1P706px22li0vsjslukYhxkTDlA8/

Output directories:
    ../curated-data/acupoints/   meridians, acupoints, acupoints-category, extra-acupoints,
                                 special-points, special-points-association, acupoints-locations
    ../curated-data/kb/          pain-related-articles

Run this script before generate_ontology.py to ensure the local CSV files are up to date.
It can also be invoked automatically as Step 1 of run_all.sh.

Author: Fahim Imam
Last updated: July 8, 2026
"""

import requests
import os

# Sheet ID and GIDs for each tab. Make sure the CSV file names are consistent with the ones used in the ontology adapter code.
SHEET_ID = '1hvUcTrw-b9ly8Yn1P706px22li0vsjslukYhxkTDlA8'
GIDS = {
        'meridians'                 : '152592560',
        'acupoints-category'        : '1444462972',
        'acupoints'                 : '792538788',
        'extra-acupoints'           : '1018943262',
        'special-points'            : '1777093137',
        'acupoints-locations'       : '1094677629',
        'special-points-association': '984678930',
        'acupoints-nerves'          : '542969034',
        'acupoints-veins-arteries'  : '88026915'
        }

# Directories to save the CSV files
ACUPOINTS_DIR = "../curated-data/acupoints"
KB_DIR = "../curated-data/kb"
os.makedirs(ACUPOINTS_DIR, exist_ok=True)
os.makedirs(KB_DIR, exist_ok=True)

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

# Download and save each tab as a CSV
def download_tab_as_csv(sheet_id, gid, tab_name, output_dir):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}"
    response = requests.get(url)
    
    if response.status_code == 200:
        file_path = os.path.join(output_dir, f"{tab_name}.csv")
        with open(file_path, 'wb') as file:
            file.write(response.content)
        print(f"Downloaded and saved {tab_name} as {file_path}")
    else:
        print(f"Failed to download {tab_name}: {response.status_code}")

# The main function
def main():
    # Download and save each tab
    for tab_name, gid in GIDS.items():
        download_tab_as_csv(SHEET_ID, gid, tab_name, TAB_OUTPUT_DIRS[tab_name])

if __name__ == "__main__":
    main()