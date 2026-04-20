#!/usr/bin/env bash
# run_all.sh
# Runs the full TARA Acupoints Ontology generation pipeline:
#   1. Download curated CSV files from the TARA Google Sheet
#   2. Generate and merge ontology files from the CSV files
#   3. Run HermiT to produce the inferred ontology files
#
# Usage:
#   ./run_all.sh
#
# Prerequisites:
#   - Python 3.8 or higher
#   - pip install rdflib owlready2
#   - Java 8 or higher on the system PATH
#
# All scripts must be run from the ontology-generator/ directory.
# This script changes into that directory automatically if needed.
#
# - Fahim Imam

set -euo pipefail

# Resolve the directory containing this script and cd into it,
# so relative paths inside the Python scripts work correctly.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================================================"
echo " TARA Acupoints Ontology - Full Generation Pipeline"
echo "================================================================"

# Step 1: Download curated CSV files from the TARA Google Sheet
echo ""
echo "Step 1: Downloading CSV files from the TARA Google Sheet..."
python fetch_curated_data.py
echo ""

# Step 2: Generate and merge the ontology files from the CSV files
echo "Step 2: Running ontology adapter to generate and merge TTL files..."
python generate_ontology.py
echo ""

# Step 3a: Run HermiT on tara-acupoints.ttl
echo "Step 3a: Running HermiT on tara-acupoints.ttl..."
python lib/hermit_reasoner.py
echo ""

# Step 3b: Run HermiT on tara-articles-kb.ttl
echo "Step 3b: Running HermiT on tara-articles-kb.ttl..."
python lib/hermit_reasoner.py \
  "../ontology-files/generated/ttl/kb/tara-articles-kb.ttl" \
  "../ontology-files/generated/ttl/kb/tara-articles-kb-inferred.ttl"
echo ""

echo "================================================================"
echo " Pipeline Completed Successfully."
echo " Generated files are under: ../ontology-files/generated/ttl/"
echo "================================================================"
