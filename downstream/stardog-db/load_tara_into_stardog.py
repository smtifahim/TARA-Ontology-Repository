"""
Builds a Stardog Cloud database that merges the TARA Articles Knowledge Base with
the SCKAN-MAR-2026 connectivity knowledge base.
This script assumes the Stardog server is running and the stardog python wrapper
is installed in your system.

Steps:
    0.   Check Stardog server status.
    1.   Create (or recreate) the target database.
    2.   Import namespace prefixes.
    3.   Load the current release's articles-kb.ttl (no-bfo / inferred), resolved
         from docs/distribution/kb/version/latest.json.
    3.1. Merge the SCKAN-MAR-2026 Stardog database in - exported over the wire as
         TriG and added as-is. That database already contains UBERON and its
         reasoned closure, so UBERON is no longer loaded separately (old Step 4).
    5.   Run the simplified-relations SPARQL update queries.
    6.   Export the merged graph to ./generated_ttl/.

Requirements:
    - `stardog` (Stardog Python client) and `python-dotenv` installed.
    - A .env file in this directory defining STARDOG_USERNAME and STARDOG_PASSWORD.
    - The credentials must have read access to the SCKAN-MAR-2026 database on the
      same Stardog endpoint.
    - Must be run from the downstream/stardog-db/ directory, since all input and
      output paths are relative to it.

Usage:
    python load_tara_into_stardog.py

(version: 1.7; @Author: Fahim Imam)
"""


import json
import os
import sys
import shutil
import stardog
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Stardog DB connection details from environment variables
conn_details = {
  'endpoint': 'https://sd-c1e74c63.stardog.cloud:5820',
  'username': os.getenv('STARDOG_USERNAME'),
  'password': os.getenv('STARDOG_PASSWORD')
}

db_name = 'TARA-Ontology-1-7-2' # name of the database to be created in stardog.
                           # You can change it if you want, but remember it will remove any existing database with the same name.

# Existing Stardog database whose full contents (already includes UBERON + its
# reasoned closure) are merged into db_name at Step 3.1.
sckan_source_db = 'SCKAN-MAR-2026'

# Source ontology: the current release's canonical (no-bfo / inferred) Articles
# Knowledge Base file from the published distribution. Its version is resolved
# at run time from docs/distribution/kb/version/latest.json, so this always
# tracks the most recently published version. It is copied into input_files/ttl
# (see prepareInputFiles()) so all input files live under a single local directory.
DIST_DIR = '../../docs/distribution'  # relative to downstream/stardog-db/


def latest_distribution_ttl(component, filename):
    """Path to <filename> for the current release of docs/distribution/<component>/,
    using the canonical variant (no-bfo/inferred) and the version named in that
    component's latest.json."""
    version_dir = os.path.join(DIST_DIR, component, 'version')
    latest_json = os.path.join(version_dir, 'latest.json')
    if not os.path.isfile(latest_json):
        sys.exit("Cannot find " + os.path.abspath(latest_json) +
                 " - run the distribution pipeline (publish_distribution.py) first.")
    with open(latest_json, encoding='utf-8') as fh:
        meta = json.load(fh)
    variant = meta.get('canonicalVariant') or 'no-bfo/inferred'
    path = os.path.join(version_dir, str(meta['latest']), *variant.split('/'), filename)
    if not os.path.isfile(path):
        sys.exit("Expected release file not found: " + os.path.abspath(path))
    return path


source_files = {
    'articles-kb.ttl'                      : latest_distribution_ttl('kb', 'articles-kb.ttl'),
}

# input files needed for TARA Ontology loading process. Please make sure these files are present in the specified locations.
input_files = {
    'articles-kb.ttl'                      : './input_files/ttl/articles-kb.ttl',
    'sckan.trig'                           : './input_files/ttl/sckan-mar-2026.trig',   # written by prepareInputFiles() from the SCKAN-MAR-2026 db
    # UBERON now comes bundled inside SCKAN-MAR-2026, so it is no longer loaded separately:
    # 'uberon.ttl'                         : './input_files/ttl/uberon.ttl',
    # 'uberon-reasoned.ttl'                : './input_files/ttl/uberon-reasoned.ttl',
    'simplified-isPartOf-query.rq'         : './input_files/sparql/simplified-isPartOf-query.rq',
    'simplified-isConnectedTo-query.rq'    : './input_files/sparql/simplified-isConnectedTo-query.rq',
    'simplified-hasPart-query.rq'          : './input_files/sparql/simplified-hasPart-query.rq',
}

# generated output files for TARA Ontology loading process
generated_files = {
    'tara-acupoints-graph-db.ttl'          : './generated_ttl/tara-acupoints-graph-db.ttl'
}


def prepareInputFiles():
    os.makedirs(os.path.dirname(input_files['articles-kb.ttl']), exist_ok=True)
    shutil.copy(source_files['articles-kb.ttl'], input_files['articles-kb.ttl'])
    print ("        Copied " + source_files['articles-kb.ttl'] + "\n               to " + input_files['articles-kb.ttl'])

    # Export the SCKAN-MAR-2026 database over the wire as TriG (streamed to disk
    # so a large export never has to sit in memory). It is already reasoned, so
    # no reasoning flag is used - the asserted + materialised triples all come
    # across.
    print ("        Exporting '" + sckan_source_db + "' from Stardog (this can take a while)...")
    written = 0
    os.makedirs(os.path.dirname(input_files['sckan.trig']), exist_ok=True)
    with stardog.Connection(sckan_source_db, **conn_details) as src, \
         open(input_files['sckan.trig'], 'wb') as out, \
         src.export(content_type=stardog.content_types.TRIG, stream=True, chunk_size=1 << 20) as stream:
        for chunk in stream:
            out.write(chunk)
            written += len(chunk)
    print ("        Exported " + sckan_source_db + " -> " + input_files['sckan.trig'] +
           " (" + "{:.1f}".format(written / 1e6) + " MB)")


def checkServerStatus(admin):
    if (admin.healthcheck()):
        print ("        Server Status: Stardog server is running and able to accept traffic.")
    else:
        print ("        Server Status: Stardog server is NOT running. Please start the server and try again.")
        sys.exit(1)

# checking if the named database already exists        
def checkDBExists(admin, db_name):
        for database in admin.databases():
            if database.name == db_name:
                return True
        return False

def createNewDatabase(admin, db_name):
    if checkDBExists(admin, db_name):
        print ("        Dropping the existing database named '" + db_name + "'")
        db = admin.database(db_name)
        db.drop()
    # create options with edge.properties set to True. This supports rdf* queries
    options = {"edge.properties": True}
    db = admin.new_database(db_name, options=options)
    print ("        The new database '" + db_name + "' is created.")
    return db

def main():
    print ("\nThe TARA Ontology loading process started.\nThere are 7 steps in this process (Step 0 to Step 6).")

    print ("\nPreparing input files...")
    prepareInputFiles()

    with stardog.Admin(**conn_details) as admin:

        print ("\nStep 0: Checking Stardog server status..")
        checkServerStatus(admin)
        print ("Step 0: Done!")

        print ("\nStep 1: Creating a new database called '" + db_name + "'")
        db = createNewDatabase(admin, db_name)
        print ("Step 1: Done!")

        print ("\nStep 2: Importing namespace prefixes...")
        db.import_namespaces(stardog.content.File(input_files['articles-kb.ttl']))
        db.import_namespaces(stardog.content.File(input_files['sckan.trig'],
                                                 content_type=stardog.content_types.TRIG))
        print ("Step 2: Done!")

    print ("\nStep 3: Adding TARA Ontology to the database. Please wait...")
    with stardog.Connection(db_name, **conn_details) as conn:
        conn.begin()
        print ("        Adding articles-kb.ttl to the database.")
        conn.add(stardog.content.File(input_files['articles-kb.ttl']))
        conn.commit()
        print ("Step 3: Done!")
        
        print ("\nStep 3.1: Merging the '" + sckan_source_db + "' database. Please wait...")
        conn.begin()
        print ("        Adding the exported " + sckan_source_db + " TriG to the database.")
        conn.add(stardog.content.File(input_files['sckan.trig'],
                                      content_type=stardog.content_types.TRIG))
        conn.commit()
        print ("Step 3.1: Done!")

        # Step 4 (loading uberon.ttl / uberon-reasoned.ttl) is no longer needed:
        # SCKAN-MAR-2026, merged in at Step 3.1, already contains UBERON and its
        # reasoned closure.
        # print ("\nStep 4: Adding UBERON to the database. Please wait...")
        # conn.begin()
        # print ("        Adding uberon.ttl to the database.")
        # conn.add(stardog.content.File(input_files['uberon.ttl']))
        # print ("        Adding uberon-reasoned.ttl to the database.")
        # conn.add(stardog.content.File(input_files['uberon-reasoned.ttl']))
        # conn.commit()
        # print ("Step 4: Done!")

        print ("\nStep 5: Executing insert query for simplified relations. Please wait...")
        with open(input_files['simplified-isPartOf-query.rq'], 'r') as file:
            query = file.read()
            print ("        Running insert query for simplified ilxtr:isPartOf relations.")
            conn.update(query)
        with open(input_files['simplified-hasPart-query.rq'], 'r') as file:
            query = file.read()
            print ("        Running insert query for simplified ilxtr:hasPart relations.")
            conn.update(query)
        with open(input_files['simplified-isConnectedTo-query.rq'], 'r') as file:
            query = file.read()
            print ("        Running insert query for simplified ilxtr:isConnectedTo relations.")
            conn.update(query)
        print ("Step 5: Done!")

        # Step 6: Saving tara-acupoints-graph-db.ttl
        print ("\nStep 6: Saving tara-acupoints-graph-db.ttl...")
        os.makedirs(os.path.dirname(generated_files['tara-acupoints-graph-db.ttl']), exist_ok=True)
        with open(generated_files['tara-acupoints-graph-db.ttl'], "wb") as result_file:
            result_file.write (conn.export())
            print ("        File saved at: " + generated_files['tara-acupoints-graph-db.ttl'])
        print ("Step 6: Done!")

    print ("\nEnd of program execution. All steps executed successfully.\n\n")


if __name__ == "__main__":
    main()