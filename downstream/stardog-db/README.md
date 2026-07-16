# TARA Ontology Loader for Stardog

This directory contains the script used to load the TARA Ontology and its UBERON
dependencies into a Stardog Cloud database.

## Contents

- `load_tara_into_stardog.py` - main loading script.
- `input_files/ttl/` - UBERON turtle files (`uberon.ttl`, `uberon-reasoned.ttl`).
  `tara-acupoints-inferred.ttl` is copied into this folder automatically by the
  script from `ontology-files/generated/ttl/` at the repository root.
- `input_files/sparql/` - SPARQL update queries used to insert simplified relations
  (`isPartOf`, `hasPart`, `isConnectedTo`).
- `generated_ttl/` - output folder; the script writes the final merged graph here
  as `tara-acupoints-graph-db.ttl`.
- `.env` - local file (not committed) holding Stardog credentials.

## Requirements

- Python 3
- `stardog` (Stardog Python client)
- `python-dotenv`
- Network access to the Stardog Cloud endpoint and a valid Stardog account

Install dependencies:

```
pip install pystardog python-dotenv
```

## Setup

Create a `.env` file in this directory with your Stardog credentials:

```
STARDOG_USERNAME=your_username
STARDOG_PASSWORD=your_password
```

The Stardog Cloud endpoint is set directly in `load_tara_into_stardog.py`
(`conn_details['endpoint']`); update it there if your endpoint changes.

## Usage

Run the script from this directory, since all input and output paths are
relative to it:

```
cd downstream/stardog-db
python load_tara_into_stardog.py
```

The script drops and recreates the `TARA-Ontology` database on each run, so
any existing database with that name will be removed first.

## Sample Execution

```
$ cd downstream/stardog-db
$ python load_tara_into_stardog.py

The TARA Ontology loading process started.
There are 7 steps in this process (Step 0 to Step 6).

Preparing input files...
        Copied tara-acupoints-inferred.ttl to ./input_files/ttl/tara-acupoints-inferred.ttl

Step 0: Checking Stardog server status..
        Server Status: Stardog server is running and able to accept traffic.
Step 0: Done!

Step 1: Creating a new database called 'TARA-Ontology'
        Dropping the existing database named 'TARA-Ontology'
        The new database 'TARA-Ontology' is created.
Step 1: Done!

Step 2: Importing namespace prefixes...
Step 2: Done!

Step 3: Adding TARA Ontology to the database. Please wait...
        Adding tara-acupoints-inferred.ttl to the database.
Step 3: Done!

Step 4: Adding UBERON to the database. Please wait...
        Adding uberon.ttl to the database.
        Adding uberon-reasoned.ttl to the database.
Step 4: Done!

Step 5: Executing insert query for simplified relations. Please wait...
        Running insert query for simplified ilxtr:isPartOf relations.
        Running insert query for simplified ilxtr:hasPart relations.
        Running insert query for simplified ilxtr:isConnectedTo relations.
Step 5: Done!

Step 6: Saving tara-acupoints-graph-db.ttl...
        File saved at: ./generated_ttl/tara-acupoints-graph-db.ttl
Step 6: Done!

End of program execution. All steps executed successfully.
```

If Step 0 reports the server as not running, start or check access to the
Stardog Cloud instance and rerun the script.
