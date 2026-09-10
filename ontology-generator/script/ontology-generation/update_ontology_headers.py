"""
================================================================================
TARA Acupoints Ontology - distribution header stamping (versioned tree)
================================================================================
Builds the four published Acupoints Ontology variants and writes them into the
per-version distribution tree:

    ontology-files/generated/temp-files/ttl/<input>
        -> docs/distribution/ontology/version/<VERSION>/<variant>/acupoints.ttl

Variants (the BFO upper ontology is included by default; "no-bfo" excludes the
BFO top-level classes):

    asserted            with BFO,  raw asserted axioms
    inferred            with BFO,  HermiT-reasoned closure
    no-bfo/asserted     without BFO, raw asserted axioms
    no-bfo/inferred     without BFO, HermiT-reasoned closure

Per variant (see lib/header_tools.process_variant):
  - staging IRIs (acupunctureresearch.org) are migrated to purl.org,
  - the merged file's ontology declaration(s) are replaced with the hand-authored
    front matter in ontology-files/base/headers/ontology-header.ttl,
  - the rdfs:comment(s) from every merged-in ontology declaration (core +
    each import/bridge module) are carried onto the canonical subject,
  - the script adds ONLY owl:versionInfo, owl:versionIRI, dcterms:issued, and
    owl:priorVersion (versions from script/versions.py).

Each file's owl:versionIRI is

    http://purl.org/tara/ontology/release/<VERSION>/<variant>/acupoints.ttl

(OBO-style "release" segment, parallel to the KB's .../kb/release/...). A PURL
prefix redirect on /tara/ontology/release/ resolves it; the redirect target may
use a differently named directory (e.g. .../distribution/ontology/version/...) -
PURL just swaps the matched prefix.

This script also text-bumps the hand-authored tara-acupoints-core.ttl's own
owl:versionInfo (double-confirmed). The originally generated flat distribution
files (distribution/tara-ontology/, distribution/no-bfo-upper/) are untouched.

Run from anywhere:
    python ontology-generator/script/ontology-generation/update_ontology_headers.py

Author: Fahim Imam
================================================================================
"""

import os
import sys

# .../ontology-generator/script/ontology-generation -> repo root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "ontology-generator", "script"))

from lib.header_tools import bump_base_versioninfo, confirm, process_variant  # noqa: E402
from versions import ACUPOINTS_VERSION, ACUPOINTS_PRIOR_VERSIONS  # noqa: E402

# =====================================================================
# CONFIGURATION
# =====================================================================

# Release version + prior-version list come from script/versions.py.
VERSION_NUMBER = ACUPOINTS_VERSION
PRIOR_VERSIONS = ACUPOINTS_PRIOR_VERSIONS

# owl:versionInfo text: "<VERSION> - <flavour>"
VERSION_INFO_TEMPLATE = "{version} - {flavour}"

# owl:versionIRI = VERSION_IRI_BASE + <VERSION>/<variant>/acupoints.ttl
VERSION_IRI_BASE = "http://purl.org/tara/ontology/release/"
DIST_FILE_NAME = "acupoints.ttl"

# Hand-authored front matter spliced into every variant, and the canonical
# ontology IRI it declares.
HEADER_TTL = os.path.join(REPO_ROOT, "ontology-files/base/headers/ontology-header.ttl")
CANONICAL_IRI = "http://purl.org/tara/ontology/acupoints.owl"

TEMP_TTL_DIR = os.path.join(REPO_ROOT, "ontology-files/generated/temp-files/ttl")
# Published under docs/ so GitHub Pages serves it (and a PURL can resolve to it).
DIST_VERSION_DIR = os.path.join(
    REPO_ROOT, "docs/distribution/ontology/version", VERSION_NUMBER
)

# Hand-authored core file whose own owl:versionInfo is text-bumped to match
# VERSION_NUMBER (double-confirmed; no owl:versionIRI is added).
BASE_CORE_TTL = os.path.join(REPO_ROOT, "ontology-files/base/tara-acupoints-core.ttl")

# (input file relative to TEMP_TTL_DIR, variant path segment, flavour text).
# The variant path segment is used verbatim for BOTH the output sub-directory
# and the owl:versionIRI, so the published path and the IRI can never drift.
VARIANTS = [
    ("no-upper/tara-acupoints.ttl",          "no-bfo/asserted",
     "Asserted Ontology (Excludes BFO Top-Level)"),
    ("no-upper/tara-acupoints-inferred.ttl", "no-bfo/inferred",
     "Inferred Ontology (Excludes BFO Top-Level)"),
    ("tara-acupoints.ttl",                   "asserted",
     "Asserted Ontology"),
    ("tara-acupoints-inferred.ttl",          "inferred",
     "Inferred Ontology"),
]


def main():
    print(f"TARA Acupoints Ontology - stamping version {VERSION_NUMBER}\n")

    for input_rel, variant_seg, flavour in VARIANTS:
        process_variant(
            os.path.join(TEMP_TTL_DIR, input_rel),
            os.path.join(DIST_VERSION_DIR, variant_seg, DIST_FILE_NAME),
            header_ttl=HEADER_TTL,
            canonical_iri=CANONICAL_IRI,
            version_info=VERSION_INFO_TEMPLATE.format(version=VERSION_NUMBER, flavour=flavour),
            version_iri=f"{VERSION_IRI_BASE}{VERSION_NUMBER}/{variant_seg}/{DIST_FILE_NAME}",
            prior_versions=PRIOR_VERSIONS,
        )

    print(f'\nAbout to bump owl:versionInfo to "{VERSION_NUMBER}" in the '
          f"hand-authored source file:\n  {BASE_CORE_TTL}")
    if confirm("Are you sure?") and confirm("Are you sure?"):
        bump_base_versioninfo(BASE_CORE_TTL, VERSION_NUMBER)
    else:
        print("Skipped: hand-authored source file was not modified.")

    print(f"\nDone. Versioned files written under:\n  {DIST_VERSION_DIR}")


if __name__ == "__main__":
    main()
