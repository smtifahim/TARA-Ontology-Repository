"""
query_tara_data.py — Reusable TARA Stardog Query Runner

Runs a set of SPARQL queries (stored as .rq files) against a TARA Stardog
database and saves the results of each query as both a JSON file (the raw
Stardog SPARQL JSON result) and a CSV file (flattened rows), under a
specified output directory.

Based on downstream/map-core/acupoints-data-generator/query-acupoints-data.py,
generalized into an importable module so other downstream scripts can reuse
the same query/export logic instead of duplicating it.

Import from other scripts (they do not need to sit next to this file):

    import sys
    from pathlib import Path

    REPO_ROOT = Path(__file__).resolve().parents[N]  # walk up to the repo root
    LIB_DIR = REPO_ROOT / "downstream" / "common-scripts" / "lib"
    sys.path.insert(0, str(LIB_DIR))

    from query_tara_data import run_queries

    run_queries(
        query_files=["sparql-queries/acupoints-metadata.rq"],
        output_dir="./data",
    )

    # Override the account and/or database for a specific call:
    run_queries(
        query_files=["sparql-queries/acupoints-metadata.rq"],
        output_dir="./data",
        db_name="TARA-Ontology",
        username="some_other_user",
        password="some_other_password",
    )

Connection defaults:
    This module loads its own .env file (downstream/common-scripts/lib/.env),
    independent of the caller's working directory, defining:
        STARDOG_TARA_USERNAME
        STARDOG_TARA_PASSWORD
    These are used whenever a caller does not pass username/password to
    run_queries(). The Stardog endpoint and default database name
    (TARA-Acupoints) are set as constants in this file.

Prerequisites:
    - Stardog server must be running and accessible at the configured endpoint
    - STARDOG_TARA_USERNAME and STARDOG_TARA_PASSWORD must be set in
      downstream/common-scripts/lib/.env (see "Connection defaults" above)
    - Install dependencies: pip install pystardog python-dotenv

Can also be run directly for a quick manual query against one or more .rq
files:

    python query_tara_data.py --queries query1.rq query2.rq --output-dir ./out

Author: Fahim Imam
Version: 1.1
"""

import argparse
import csv
import json
import os
from pathlib import Path

import stardog
from dotenv import load_dotenv

# Load this module's own .env, independent of the caller's working directory,
# so callers don't need to provide credentials just to get the defaults below.
_MODULE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=_MODULE_DIR / '.env')

# Default Stardog Cloud connection details for the TARA-Acupoints database.
# Pass username / password / db_name / endpoint to run_queries() to override
# these on a per-call basis (e.g. to target a different database or account).
DEFAULT_ENDPOINT = 'https://sd-c1e74c63.stardog.cloud:5820'
DEFAULT_USERNAME = os.getenv('STARDOG_TARA_USERNAME')
DEFAULT_PASSWORD = os.getenv('STARDOG_TARA_PASSWORD')
DEFAULT_DB_NAME = 'TARA-Ontology'  # default database to query if not overridden by caller


def check_server_status(admin):
    if admin.healthcheck():
        print("> Server Status: Stardog server is running and able to accept traffic.")
    else:
        raise RuntimeError("> Stardog server is NOT running or not reachable at the configured endpoint.")


def _load_query(query_file):
    with open(query_file, 'r') as file:
        return file.read()


def _results_to_rows(results):
    """Flattens a Stardog SPARQL JSON SELECT result into a header list and row dicts."""
    headers = results.get('head', {}).get('vars', [])
    bindings = results.get('results', {}).get('bindings', [])
    rows = [
        {header: binding.get(header, {}).get('value', '') for header in headers}
        for binding in bindings
    ]
    return headers, rows


def _save_json(results, output_path):
    with open(output_path, 'w') as file:
        json.dump(results, file, indent=2)


def _save_csv(headers, rows, output_path):
    with open(output_path, 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _display_path(path):
    """Renders a path relative to the current working directory for terminal output."""
    try:
        return os.path.relpath(path)
    except ValueError:
        # e.g. paths on different drives on Windows; fall back to the given path
        return str(path)


def run_queries(
    query_files,
    output_dir,
    db_name=None,
    username=None,
    password=None,
    endpoint=None,
    reasoning=False,
):
    """
    Executes each SPARQL query in query_files against the given Stardog
    database and saves the results under output_dir as both JSON and CSV.

    query_files: list of paths to .rq files.
    output_dir: directory under which "json/" and "csv/" subfolders are
        created and populated. One <query-basename>.json and
        <query-basename>.csv file is written per query file.
    db_name: Stardog database name to query. Defaults to DEFAULT_DB_NAME
        ('TARA-Acupoints').
    username, password: Stardog credentials. Default to STARDOG_TARA_USERNAME
        / STARDOG_TARA_PASSWORD from this module's own .env file.
    endpoint: Stardog Cloud endpoint. Defaults to DEFAULT_ENDPOINT.
    reasoning: whether to enable Stardog reasoning for the queries.

    Returns a dict mapping each query file to its output paths and row count:
        {query_file: {'json': path, 'csv': path, 'row_count': n}}
    """
    conn_details = {
        'endpoint': endpoint or DEFAULT_ENDPOINT,
        'username': username or DEFAULT_USERNAME,
        'password': password or DEFAULT_PASSWORD,
    }
    db_name = db_name or DEFAULT_DB_NAME

    json_dir = os.path.join(output_dir, 'json')
    csv_dir = os.path.join(output_dir, 'csv')
    os.makedirs(json_dir, exist_ok=True)
    os.makedirs(csv_dir, exist_ok=True)

    print("\nChecking Stardog server status...")
    with stardog.Admin(**conn_details) as admin:
        check_server_status(admin)

    summary = {}
    with stardog.Connection(db_name, **conn_details) as conn:
        for i, query_file in enumerate(query_files):
            print("\nExecuting query " + str(i + 1) + " of " + str(len(query_files)) + ": " + _display_path(query_file))
            query = _load_query(query_file)
            results = conn.select(query, reasoning=reasoning)
            headers, rows = _results_to_rows(results)

            basename = Path(query_file).stem
            json_path = os.path.join(json_dir, basename + '.json')
            csv_path = os.path.join(csv_dir, basename + '.csv')

            _save_json(results, json_path)
            _save_csv(headers, rows, csv_path)

            print("> Saved " + str(len(rows)) + " rows to:\n  " + _display_path(json_path) + "\n  " + _display_path(csv_path))
            summary[query_file] = {'json': json_path, 'csv': csv_path, 'row_count': len(rows)}

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Run SPARQL queries against a TARA Stardog database and save results as JSON and CSV."
    )
    parser.add_argument('--queries', nargs='+', required=True, help="Paths to one or more .rq query files.")
    parser.add_argument('--output-dir', required=True, help="Directory to write json/ and csv/ result subfolders into.")
    parser.add_argument('--db-name', default=DEFAULT_DB_NAME, help="Stardog database name (default: %(default)s).")
    parser.add_argument('--username', default=None, help="Stardog username (default: STARDOG_TARA_USERNAME from .env).")
    parser.add_argument('--password', default=None, help="Stardog password (default: STARDOG_TARA_PASSWORD from .env).")
    parser.add_argument('--endpoint', default=None, help="Stardog Cloud endpoint (default: %s)." % DEFAULT_ENDPOINT)
    parser.add_argument('--reasoning', action='store_true', help="Enable Stardog reasoning for the queries.")
    args = parser.parse_args()

    summary = run_queries(
        query_files=args.queries,
        output_dir=args.output_dir,
        db_name=args.db_name,
        username=args.username,
        password=args.password,
        endpoint=args.endpoint,
        reasoning=args.reasoning,
    )

    print("\nAll queries executed and results are saved successfully!")
    for query_file, info in summary.items():
        print("> Summary: " + _display_path(query_file) + " -> " + str(info['row_count']) + " rows")


if __name__ == "__main__":
    main()
