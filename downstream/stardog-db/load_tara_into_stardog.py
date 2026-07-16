"""
Loads the TARA Ontology and its UBERON dependencies into a Stardog Cloud database.
This script assumes that the stardog server is running, and the input turtle files are located under ./input_ttl directory.
This script also assumes that stardog python wrapper is installed in your system.

Steps (0-6):
    0. Check Stardog server status.
    1. Create (or recreate) the target database.
    2. Import namespace prefixes.
    3. Load tara-acupoints-inferred.ttl.
    4. Load uberon.ttl and uberon-reasoned.ttl.
    5. Run the simplified-relations SPARQL update queries.
    6. Export the merged graph to ./generated_ttl/.

Requirements:
    - `stardog` (Stardog Python client) and `python-dotenv` installed.
    - A .env file in this directory defining STARDOG_USERNAME and STARDOG_PASSWORD.
    - Must be run from the downstream/stardog-db/ directory, since all input and
      output paths are relative to it.

Usage:
    python load_tara_into_stardog.py

(version: 1.6; @Author: Fahim Imam)
"""


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

db_name = 'TARA-Ontology' # name of the database to be created in stardog. 
                           # You can change it if you want, but remember it will remove any existing database with the same name.

# source location of tara-acupoints-inferred.ttl, generated elsewhere in the repository.
# It is copied into input_files/ttl (see copySourceFiles()) so all input files live under a single local directory.
source_files = {
    'tara-acupoints-inferred.ttl'          : '../../ontology-files/generated/ttl/tara-acupoints-inferred.ttl',
}

# input files needed for TARA Ontology loading process. Please make sure these files are present in the specified locations.
input_files = {
    'tara-acupoints-inferred.ttl'          : './input_files/ttl/tara-acupoints-inferred.ttl',
    'uberon.ttl'                           : './input_files/ttl/uberon.ttl',
    'uberon-reasoned.ttl'                  : './input_files/ttl/uberon-reasoned.ttl',
    'simplified-isPartOf-query.rq'         : './input_files/sparql/simplified-isPartOf-query.rq',
    'simplified-isConnectedTo-query.rq'    : './input_files/sparql/simplified-isConnectedTo-query.rq',
    'simplified-hasPart-query.rq'          : './input_files/sparql/simplified-hasPart-query.rq',
}

# generated output files for TARA Ontology loading process
generated_files = {
    'tara-acupoints-graph-db.ttl'             : './generated_ttl/tara-acupoints-graph-db.ttl'
}


def copySourceFiles():
    os.makedirs(os.path.dirname(input_files['tara-acupoints-inferred.ttl']), exist_ok=True)
    shutil.copy(source_files['tara-acupoints-inferred.ttl'], input_files['tara-acupoints-inferred.ttl'])
    print ("        Copied tara-acupoints-inferred.ttl to " + input_files['tara-acupoints-inferred.ttl'])


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
    copySourceFiles()

    with stardog.Admin(**conn_details) as admin:

        print ("\nStep 0: Checking Stardog server status..")
        checkServerStatus(admin)
        print ("Step 0: Done!")

        print ("\nStep 1: Creating a new database called '" + db_name + "'")
        db = createNewDatabase(admin, db_name)
        print ("Step 1: Done!")

        print ("\nStep 2: Importing namespace prefixes...")
        db.import_namespaces(stardog.content.File(input_files['tara-acupoints-inferred.ttl']))
        db.import_namespaces(stardog.content.File(input_files['uberon.ttl']))
        db.import_namespaces(stardog.content.File(input_files['uberon-reasoned.ttl']))
        print ("Step 2: Done!")

    print ("\nStep 3: Adding TARA Ontology to the database. Please wait...")
    with stardog.Connection(db_name, **conn_details) as conn:
        conn.begin()
        print ("        Adding tara-acupoints-inferred.ttl to the database.")
        conn.add(stardog.content.File(input_files['tara-acupoints-inferred.ttl']))
        conn.commit()
        print ("Step 3: Done!")

        print ("\nStep 4: Adding UBERON to the database. Please wait...")
        conn.begin()
        print ("        Adding uberon.ttl to the database.")
        conn.add(stardog.content.File(input_files['uberon.ttl']))
        print ("        Adding uberon-reasoned.ttl to the database.")
        conn.add(stardog.content.File(input_files['uberon-reasoned.ttl']))
        conn.commit()
        print ("Step 4: Done!")

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