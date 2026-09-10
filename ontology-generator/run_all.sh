#!/usr/bin/env bash
# run_all.sh
# Runs the full TARA ontology generation + release pipeline:
#   1.  Download curated CSV files from the TARA acupoints Google Sheet
#   2.  Generate and merge the acupoints ontology TTLs (+ HermiT inference)
#   2b. Stamp the versioned acupoints distribution headers
#   3.  Generate the articles metadata knowledgebase TTLs (+ HermiT inference)
#   3b. Stamp the versioned articles-kb distribution headers
#   4.  Refresh the distribution version index (latest.json + index.html)
#
# Usage:
#   ./run_all.sh
#
# Prerequisites:
#   - Python 3.8 or higher
#   - pip install rdflib owlready2 openpyxl tqdm requests
#   - Java 8 or higher on the system PATH (for HermiT)
#
# Run from anywhere - this script cd's into ontology-generator/ first, and the
# generator scripts (now under script/) re-anchor to it themselves.
#
# Step 2b prompts (twice) before it bumps tara-acupoints-core.ttl's
# owl:versionInfo; answer 'n' to skip that edit.
#
# - Fahim Imam

set -euo pipefail

# Resolve the directory containing this script (ontology-generator/) and cd into
# it, so the relative script paths and the pipeline's "../" paths resolve.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================================================"
echo " TARA Ontology - Full Generation + Release Pipeline"
echo "================================================================"

# Step 1: Download curated CSV files from the TARA acupoints Google Sheet
echo ""
echo "Step 1: Downloading curated CSV files from the Google Sheet..."
python fetch_curated_data.py
echo ""

# Step 2: Generate and merge the acupoints ontology TTLs (runs HermiT)
echo "Step 2: Generating and merging the acupoints ontology TTLs..."
python script/ontology-generation/generate_ontology.py
echo ""

# Step 2b: Stamp the versioned acupoints distribution headers
echo "Step 2b: Stamping the versioned acupoints distribution headers..."
python script/ontology-generation/update_ontology_headers.py
echo ""

# Step 3: Generate the articles metadata knowledgebase TTLs (runs HermiT)
echo "Step 3: Generating the articles metadata knowledgebase TTLs..."
python script/kb-generation/generate_articles_kb.py
echo ""

# Step 3b: Stamp the versioned articles-kb distribution headers
echo "Step 3b: Stamping the versioned articles-kb distribution headers..."
python script/kb-generation/update_kb_headers.py
echo ""

# Step 4: Refresh the distribution version index (latest.json + index.html)
echo "Step 4: Refreshing the distribution version index..."
python script/publish_distribution.py
echo ""

echo "================================================================"
echo " Pipeline completed successfully."
echo "   working TTLs : ../ontology-files/generated/temp-files/ttl/"
echo "   distribution : ../docs/distribution/{ontology,kb}/version/"
echo "================================================================"
