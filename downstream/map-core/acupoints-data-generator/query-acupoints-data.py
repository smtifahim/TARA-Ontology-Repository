"""
query-acupoints-data.py — TARA Ontology Data Extractor for MAP-CORE

Runs a set of SPARQL queries against the TARA-Acupoints Stardog database and saves
the results as JSON files for use by MAP-CORE applications.

Queries run:
    sparql-queries/acupoints-metadata.rq   → ../data/json/acupoints-metadata.json
    sparql-queries/acupoints-locations.rq  → ../data/json/acupoints-locations.json

Prerequisites:
    - Stardog server must be running and accessible at the configured endpoint
    - STARDOG_TARA_PASSWORD must be set in a .env file in this directory
    - Install dependencies: pip install pystardog[cloud] python-dotenv

Author: Fahim Imam
Version: 1.0 (December 18, 2025)
"""

import stardog
import json
import os
from dotenv import load_dotenv
load_dotenv()

# Stardog DB connection authentication using stardog cloud endpoint
conn_details = {
                'endpoint': 'https://sd-c1e74c63.stardog.cloud:5820',
                'username': 'TARA',
                'password': os.getenv('STARDOG_TARA_PASSWORD')
               }

db_name = 'TARA-Acupoints'

# File locations for the queries needed for the TARA app
query_files = [
                './sparql-queries/acupoints-metadata.rq',
                './sparql-queries/acupoints-locations.rq'
              ]

# File locations for the generated query results in json format
generated_files = [
                    '../data/json/acupoints-metadata.json',
                    '../data/json/acupoints-locations.json'
                  ]

def checkServerStatus(admin):
    if (admin.healthcheck()):
        print ("        Server Status: Stardog server is running and able to accept traffic.")
    else:
        print ("        Server Status: Stardog server is NOT running. Please start the server and try again.")
        exit();

print ("\nProgram execution started...")
with stardog.Admin(**conn_details) as admin:  
    print ("\nStep 0: Checking Stardog server status..")
    checkServerStatus(admin)
    print ("Step 0: Done!")

with stardog.Connection(db_name, **conn_details) as conn: 
    for i, query_file in enumerate (query_files):
        print ("\nStep " + str(i+1) + ": Executing query from: " + query_file)
        with open(query_file, 'r') as file:
            query = file.read()
            result = conn.select(query, reasoning=False)
        print ("        Saving query results...")
        with open(generated_files[i], 'w') as file:
            json.dump(result, file, indent=2)
        print ("        Query results saved to: " + generated_files[i])
        print ("Step " + str(i+1) + ": Done!")
    conn.close()
print ("\nAll queries executed and results are saved successfully!\n")
