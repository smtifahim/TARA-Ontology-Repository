"""
================================================================================
TARA Articles Knowledge Base - distribution header stamping (versioned tree)
================================================================================
Builds the four published Articles-KB variants and writes them into the
per-version distribution tree:

    ontology-files/generated/temp-files/ttl/<input>
        -> docs/distribution/kb/version/<KB_VERSION>/<variant>/articles-kb.ttl

Variants mirror the acupoints layout (BFO upper included by default; "no-bfo"
excludes the BFO top level):

    asserted            with BFO,  raw asserted axioms
    inferred            with BFO,  HermiT-reasoned closure
    no-bfo/asserted     without BFO, raw asserted axioms
    no-bfo/inferred     without BFO, HermiT-reasoned closure

Per variant (see lib/header_tools.process_variant):
  - staging IRIs (acupunctureresearch.org) are migrated to purl.org,
  - the merged file's ontology declaration(s) - its own staging subject
    (.../kb/articles-metadata.owl), the merged-in acupoints header, and the
    import/bridge stubs - are replaced with the hand-authored front matter in
    ontology-files/base/headers/kb-header.ttl, which declares the canonical KB
    IRI .../kb/articles-kb.ttl (dc:title "TARA Articles Knowledge Base", ...),
  - the rdfs:comment(s) from every merged-in ontology declaration (the KB core
    + the acupoints ontology + each import/bridge module) are carried onto the
    canonical subject,
  - the script adds ONLY owl:versionInfo, owl:versionIRI, dcterms:issued, and
    owl:priorVersion.

The KB is versioned INDEPENDENTLY of the acupoints ontology; the acupoints
release it was built against is recorded in owl:versionInfo. Both version
numbers and the prior-version list come from script/versions.py.

`tara-articles-kb-core.ttl` (the hand-authored base) keeps its own separate
owl:versionInfo and is NOT touched here. The originally generated flat
distribution files are left untouched.

Run from anywhere:
    python ontology-generator/script/kb-generation/update_kb_headers.py

Author: Fahim Imam
================================================================================
"""

import os
import sys

# .../ontology-generator/script/kb-generation -> repo root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "ontology-generator", "script"))

from lib.header_tools import NEW_BASE, process_variant  # noqa: E402
from versions import ACUPOINTS_VERSION, KB_VERSION, KB_PRIOR_VERSIONS  # noqa: E402

# =====================================================================
# CONFIGURATION
# =====================================================================
# Version numbers + prior-version list come from script/versions.py.
#   KB_VERSION        - the Articles KB's own release version
#   ACUPOINTS_VERSION - the acupoints release this KB build was merged against

# owl:versionInfo text: "<KB_VERSION> - <flavour>; <acupoints credit>"
ACUPOINTS_CREDIT_TEMPLATE = "built using TARA Ontology v. {acupoints_version}"
VERSION_INFO_TEMPLATE = "{version} - {flavour}; " + ACUPOINTS_CREDIT_TEMPLATE

# owl:versionIRI = VERSION_IRI_BASE + <KB_VERSION>/<variant>/articles-kb.ttl
VERSION_IRI_BASE = "http://purl.org/tara/ontology/kb/release/"
DIST_FILE_NAME = "articles-kb.ttl"

# Hand-authored front matter and the canonical ontology IRI it declares
# (title, description, creator, ...). The merged file declares the KB ontology
# under a staging IRI (.../kb/articles-metadata.owl) plus one stub per merged
# import/bridge module; process_variant drops them all, keeps their
# rdfs:comment(s), and splices this header in.
HEADER_TTL = os.path.join(REPO_ROOT, "ontology-files/base/headers/kb-header.ttl")
CANONICAL_IRI = NEW_BASE + "kb/articles-kb.ttl"

TEMP_TTL_DIR = os.path.join(REPO_ROOT, "ontology-files/generated/temp-files/ttl")
# Published under docs/ so GitHub Pages serves it (and a PURL can resolve to it).
DIST_VERSION_DIR = os.path.join(
    REPO_ROOT, "docs/distribution/kb/version", KB_VERSION
)

# (input file relative to TEMP_TTL_DIR, variant path segment, flavour text).
VARIANTS = [
    ("no-upper/kb/tara-articles-kb.ttl",                   "no-bfo/asserted",
     "Asserted Ontology (Excludes BFO Top-Level)"),
    ("no-upper/kb/tara-articles-kb-no-upper-inferred.ttl", "no-bfo/inferred",
     "Inferred Ontology (Excludes BFO Top-Level)"),
    ("kb/tara-articles-kb-with-upper.ttl",                 "asserted",
     "Asserted Ontology"),
    ("kb/tara-articles-kb-inferred.ttl",                   "inferred",
     "Inferred Ontology"),
]


def main():
    print(f"TARA Articles KB - stamping version {KB_VERSION} "
          f"(built with TARA Acupoints Ontology {ACUPOINTS_VERSION})\n")

    for input_rel, variant_seg, flavour in VARIANTS:
        process_variant(
            os.path.join(TEMP_TTL_DIR, input_rel),
            os.path.join(DIST_VERSION_DIR, variant_seg, DIST_FILE_NAME),
            header_ttl=HEADER_TTL,
            canonical_iri=CANONICAL_IRI,
            version_info=VERSION_INFO_TEMPLATE.format(
                version=KB_VERSION, flavour=flavour, acupoints_version=ACUPOINTS_VERSION
            ),
            version_iri=f"{VERSION_IRI_BASE}{KB_VERSION}/{variant_seg}/{DIST_FILE_NAME}",
            prior_versions=KB_PRIOR_VERSIONS,
        )

    print(f"\nDone. Versioned files written under:\n  {DIST_VERSION_DIR}")


if __name__ == "__main__":
    main()
