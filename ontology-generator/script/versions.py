"""
================================================================================
TARA release versions - single source of truth
================================================================================
Imported by the header-stamping scripts:
    script/ontology-generation/update_ontology_headers.py
    script/kb-generation/update_kb_headers.py

These are the RELEASE (distribution) version numbers. They are maintained
INDEPENDENTLY per ontology - a TARA Articles KB release is not tied to the
Acupoints Ontology's version, though every KB release is built against a
specific acupoints release (recorded in the KB's owl:versionInfo).

Each hand-authored *base* ontology file (ontology-files/base/...) carries its
own separate owl:versionInfo and is NOT driven by the numbers here - except
that update_ontology_headers.py, by long-standing convention, also bumps
tara-acupoints-core.ttl's owl:versionInfo to ACUPOINTS_VERSION (behind a
double confirmation).

Bump the relevant constant here when cutting a release, then run the matching
header script.

Author: Fahim Imam
================================================================================
"""

# TARA Acupoints Ontology Release Version.
ACUPOINTS_VERSION = "1.7.2"

# TARA Articles Knowledge-Base Release Version (Independent of ACUPOINTS_VERSION).
KB_VERSION = "0.5"

# Prior release version strings, stamped as owl:priorVersion on each
# distribution file (newest first). Empty list -> no owl:priorVersion.
# The merged source no longer carries an old owl:versionInfo to rotate, so
# provenance of superseded releases is maintained here by hand.
ACUPOINTS_PRIOR_VERSIONS = ["1.7.0"]
KB_PRIOR_VERSIONS = []
