"""
This code is written to download the spcified tabs in csv format from the google sheet called the 'Official-TARA-Ontology-Curation-Sheet'.
Link to the google Sheet: https://docs.google.com/spreadsheets/d/1hvUcTrw-b9ly8Yn1P706px22li0vsjslukYhxkTDlA8/ 
- Fahim Imam
"""

import requests
import os

# Sheet ID and GIDs for each tab. Make sure the CSV file names are consitent with the ones used in the ontology adapter code.
SHEET_ID = '1hvUcTrw-b9ly8Yn1P706px22li0vsjslukYhxkTDlA8'
GIDS = {
        'meridians'                 : '152592560',
        'acupoints-category'        : '1444462972',
        'acupoints'                 : '792538788',
        'extra-acupoints'           : '1018943262',
        'special-points'            : '1777093137',
        'special-points-association': '984678930'
       }

# Directory to save the CSV files
output_dir = "../csv-files"
os.makedirs(output_dir, exist_ok=True)

# Download and save each tab as a CSV
def download_tab_as_csv(sheet_id, gid, tab_name):
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
        download_tab_as_csv(SHEET_ID, gid, tab_name)

if __name__ == "__main__":
    main()