# TARA Acupoints Mapper

This directory contains the script and data used to map acupoint mentions
from source Google Sheets to their corresponding TARA Ontology acupoint
labels and CURIEs.

## Contents

- `script/map_tara_acupoints.py` - main script.
- `script/.env` - local file (not committed) holding Stardog credentials.
- `input_files/acupoints_source_sheets/` - source data downloaded from
  Google Sheets, one CSV per configured tab.
- `input_files/sparql/query/` - SPARQL query used to retrieve acupoint
  labels and synonyms from Stardog (`tara-acupoints-alt-labels.rq`).
- `input_files/sparql/query_results/json/` and `.../csv/` - query results
  saved by `query_tara_data.py`, one JSON and one CSV file per query.
- `output_files/acupoints_mapped_sheets/` - final mapped CSVs, one per
  source sheet tab, with the mapping columns filled in.

## What the script does

1. Downloads each Google Sheet tab configured in `ACUPOINTS_SHEETS` (in
   `map_tara_acupoints.py`) and saves it as a CSV under
   `input_files/acupoints_source_sheets/`. Add new tabs there as they come
   up; each entry is a tab name mapped to its (Google Sheet ID, GID).
2. Runs `input_files/sparql/query/tara-acupoints-alt-labels.rq` against
   Stardog (via `downstream/common-scripts/lib/query_tara_data.py`) and
   saves the results as JSON and CSV under
   `input_files/sparql/query_results/`.
3. For every downloaded sheet, reads the `Acupoints-Normalized` column,
   splits each cell on commas (the only true separator between distinct
   acupoints), and matches each individual acupoint against the
   `Acupoint_Label` / `Acupoint_Alt_Label` values from the query results.

## Matching rules

Both the source acupoint text and the ontology label/synonym values are
normalized the same way before comparison: lowercase, then strip everything
that is not a letter or digit (whitespace, dashes, dots, and any other
punctuation). For example, "ST 36", "st-36", and "St.36" all normalize to
"st36" and are treated as equivalent. A primary `Acupoint_Label` match takes
precedence over an `Acupoint_Alt_Label` match on collision.

## Output columns

The following columns already exist in the source sheets and are
overwritten with freshly computed values. All other columns and the
original row order are left unchanged.

- `Acupoints-Mapped` - matched `Acupoint_Label` value(s), comma-separated,
  in the same order they appear in `Acupoints-Normalized` (unmapped entries
  are skipped in this column).
- `Acupoints-Unmappable` - the original acupoint text(s) that could not be
  matched, comma-separated, in their original order.
- `Acupoints_TARA_IDs` - the `Acupoint_CURIE` for each entry in
  `Acupoints-Mapped`, comma-separated, in the same order.

## Requirements

- Python 3
- `stardog` (Stardog Python client), `pandas`, `requests`, `python-dotenv`

Install dependencies:

```
pip install pystardog pandas requests python-dotenv
```

## Setup

Create a `.env` file in `script/` with your Stardog credentials:

```
STARDOG_TARA_USERNAME=your_username
STARDOG_TARA_PASSWORD=your_password
```

The Stardog database name is set directly in `map_tara_acupoints.py`
(`DB_NAME`); update it there if the target database changes.

## Usage

Run the script from the `script/` directory:

```
cd downstream/data-core/kb_generator/kb_terms_mapping/acupoints_mapping/script
python map_tara_acupoints.py
```

Each run re-downloads the source sheets, re-runs the SPARQL query, and
overwrites the mapped CSVs under `output_files/acupoints_mapped_sheets/`.

## Sample Execution

```
$ cd downstream/data-core/kb_generator/kb_terms_mapping/acupoints_mapping/script
$ python map_tara_acupoints.py

==============================================================================================
TARA Acupoints Mapper
==============================================================================================

Step 0: Running tara-acupoints-alt-labels.rq query against Stardog...

Checking Stardog server status...
> Server Status: Stardog server is running and able to accept traffic.

Executing query 1 of 1: ../input_files/sparql/query/tara-acupoints-alt-labels.rq
> Saved 414 rows to:
  ../input_files/sparql/query_results/json/tara-acupoints-alt-labels.json
  ../input_files/sparql/query_results/csv/tara-acupoints-alt-labels.csv
  Saved query results for acupoint alternate labels from TARA Ontology.

Step 1: Building acupoint label/synonym lookup table...
> Built lookup table with 2042 normalized label/synonym entries.

Processing tab: acupoints-list-mapped-112625

Step 2: Downloading source sheet 'acupoints-list-mapped-112625'...
> Saved source CSV: ../input_files/acupoints_source_sheets/acupoints-list-mapped-112625.csv
> Loaded 1781 rows, 10 columns.

Step 3: Matching 'Acupoints-Normalized' values against the TARA Ontology lookup
> 826 rows fully mapped, 327 rows partially mapped, 60 rows fully unmappable.
> Saved mapped CSV: ../output_files/acupoints_mapped_sheets/acupoints-list-mapped-112625.csv

Done. All steps completed successfully.
> Mapped sheets are saved under: ../output_files/acupoints_mapped_sheets
==============================================================================================
```

If the server status check reports the server as not running, verify access
to the Stardog Cloud instance and rerun the script.
