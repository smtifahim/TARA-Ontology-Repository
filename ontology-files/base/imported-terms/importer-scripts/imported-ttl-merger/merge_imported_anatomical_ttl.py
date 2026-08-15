"""
merge_imported_anatomical_ttl.py

Merges the two imported-terms TTL files into a single tara-imported-anatomical-terms.ttl:

  1. imported-tara-uberon-terms.ttl  — UBERON classes extracted by the UBERON importer
  2. imported-tara-ilx-terms.ttl     — InterLex terms used by TARA

Output: ontology-files/base/tara-imported-anatomical-terms.ttl

Uses ontology-generator/lib/ontology_merger.py so that namespace prefixes are
preserved cleanly (no auto-generated nsX prefixes in the output).

Run from the directory containing this script, or from anywhere — paths are
resolved relative to this file's location.

Usage:
    python merge_imported_anatomical_ttl.py

Author: Fahim Imam
Last Updated: 2026-07-04
"""

import sys
from pathlib import Path

# Resolve paths relative to this script's location
SCRIPT_DIR  = Path(__file__).resolve().parent
REPO_ROOT   = SCRIPT_DIR.parents[4]   # …/TARA-Ontology-Repository

IMPORTED_TTL_DIR = REPO_ROOT / "ontology-files" / "base" / "imported-terms" / "imported-ttl-files"
UBERON_TTL  = IMPORTED_TTL_DIR / "imported-tara-uberon-terms.ttl"
ILX_TTL     = IMPORTED_TTL_DIR / "imported-tara-ilx-terms.ttl"
OUTPUT_TTL  = REPO_ROOT / "ontology-files" / "base" / "tara-imported-anatomical-terms.ttl"

# Add the ontology-generator/lib directory to the Python path so we can import
# ontology_merger without installing it as a package.
LIB_DIR = REPO_ROOT / "ontology-generator" / "lib"
sys.path.insert(0, str(LIB_DIR))

from ontology_merger import merge_ontologies

# Namespace bindings to enforce in the merged output (prevents nsX auto-names)
NAMESPACES = {
    "owl"      : "http://www.w3.org/2002/07/owl#",
    "rdf"      : "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs"     : "http://www.w3.org/2000/01/rdf-schema#",
    "xsd"      : "http://www.w3.org/2001/XMLSchema#",
    "obo"      : "http://purl.obolibrary.org/obo/",
    "oboInOwl" : "http://www.geneontology.org/formats/oboInOwl#",
    "IAO"      : "http://purl.obolibrary.org/obo/IAO_",
    "BFO"      : "http://purl.obolibrary.org/obo/BFO_",
    "RO"       : "http://purl.obolibrary.org/obo/RO_",
    "UBERON"   : "http://purl.obolibrary.org/obo/UBERON_",
    "ILX"      : "http://uri.interlex.org/base/ilx_",
    "ilxtr"    : "http://uri.interlex.org/tgbugs/uris/readable/",
    "dcterms"  : "http://purl.org/dc/terms/",
}


def main():
    print("=" * 60)
    print("Merging imported TTL files into tara-imported-anatomical-terms.ttl")
    print("=" * 60)

    for path, label in ((UBERON_TTL, "UBERON terms"), (ILX_TTL, "ILX terms")):
        if not path.exists():
            print(f"ERROR: {label} file not found: {path}")
            sys.exit(1)

    # Display relative paths from repo root for cleaner output
    uberon_display = UBERON_TTL.relative_to(REPO_ROOT)
    ilx_display = ILX_TTL.relative_to(REPO_ROOT)
    output_display = OUTPUT_TTL.relative_to(REPO_ROOT)

    print(f"\nFile 1 (base):  {uberon_display}")
    print(f"File 2 (merge): {ilx_display}")
    print(f"Output:         {output_display}")
    print()

    merge_ontologies(
        str(UBERON_TTL),
        str(ILX_TTL),
        str(OUTPUT_TTL),
        bind_namespaces=NAMESPACES,
    )

    print(f"\nDone. Merged file saved to:\n  {output_display}")


if __name__ == "__main__":
    main()
