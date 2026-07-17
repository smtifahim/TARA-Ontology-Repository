"""
query-acupoints-data.py — TARA Ontology Data Extractor for MAP-CORE

Runs a set of SPARQL queries against the TARA-Acupoints Stardog database and saves
the results as JSON and CSV files for use by MAP-CORE applications.

Uses downstream/common-scripts/lib/query_tara_data.py to run the queries and
write the results, instead of talking to Stardog directly.

Queries run:
    sparql-queries/acupoints-metadata.rq   → ../data/json/acupoints-metadata.json, ../data/csv/acupoints-metadata.csv
    sparql-queries/acupoints-locations.rq  → ../data/json/acupoints-locations.json, ../data/csv/acupoints-locations.csv

Prerequisites:
    - Stardog server must be running and accessible at the configured endpoint
    - STARDOG_TARA_USERNAME and STARDOG_TARA_PASSWORD must be set in a .env
      file in this directory
    - Install dependencies: pip install pystardog[cloud] python-dotenv

Author: Fahim Imam
Version: 1.2 (passes this script's own .env credentials and db name to query_tara_data.py)
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]  # …/TARA-Ontology-Repository

# Load this script's own .env (STARDOG_TARA_USERNAME / STARDOG_TARA_PASSWORD),
# regardless of the working directory the script is run from.
load_dotenv(dotenv_path=SCRIPT_DIR / ".env")

# Add downstream/common-scripts/lib to the Python path so we can import
# query_tara_data without installing it as a package.
LIB_DIR = REPO_ROOT / "downstream" / "common-scripts" / "lib"
sys.path.insert(0, str(LIB_DIR))

from query_tara_data import run_queries

DB_NAME = "TARA-Acupoints"
USERNAME = os.getenv("STARDOG_TARA_USERNAME")
PASSWORD = os.getenv("STARDOG_TARA_PASSWORD")

# File locations for the queries needed for the TARA's Map-Core app
QUERY_FILES = [
    str(SCRIPT_DIR / "sparql-queries" / "acupoints-metadata.rq"),
    str(SCRIPT_DIR / "sparql-queries" / "acupoints-locations.rq"),
]

# run_queries() writes json/ and csv/ subfolders under this directory,
# matching the existing ../data/json and ../data/csv layout.
OUTPUT_DIR = str(SCRIPT_DIR.parent / "data")


def main():
    print("\nProgram execution started...")
    summary = run_queries(
        query_files=QUERY_FILES,
        output_dir=OUTPUT_DIR,
        db_name=DB_NAME,
        username=USERNAME,
        password=PASSWORD,
    )
    print("\nAll queries executed and results are saved successfully!")
    for query_file, info in summary.items():
        print("> Summary: " + os.path.relpath(query_file) + " -> " + str(info["row_count"]) + " rows")


if __name__ == "__main__":
    main()
