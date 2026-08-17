'''
ontology_merger.py — Ontology Merger (lib helper)

Merges two Turtle ontology files into a single output file using RDFLib.

The main challenge handled here is namespace prefix preservation: when RDFLib parses a
Turtle file that lacks explicit prefix declarations for a namespace, it auto-generates
positional prefixes (ns1, ns2, ...). If these are carried over during a merge they can
override the properly named prefixes already bound in the base graph. This module avoids
that by skipping auto-generated nsX prefixes when copying namespaces from the second
graph, then explicitly re-binding any caller-supplied namespace dict with override=True
so that the serialized output always uses the intended prefix names.

Called automatically by generate_ontology.py to produce the merged output files.
Not intended to be run as a standalone script.

Author: Fahim Imam
Last updated: August 16, 2026
'''

import os
import re
from rdflib import Graph, Namespace

def merge_ontologies(ontology1_path, ontology2_path, merged_ontology_path, bind_namespaces=None):
    # Load the first ontology
    g1 = Graph()
    g1.parse(ontology1_path, format="turtle")

    # Load the second ontology
    g2 = Graph()
    g2.parse(ontology2_path, format="turtle")

    # Merge namespaces from g2 into g1, skipping auto-generated rdflib prefixes
    # (e.g. ns1, ns2, ...) that rdflib assigns when a parsed file has no declared
    # prefix for a namespace. Copying those would override properly named prefixes
    # already bound in g1, causing the serialized output to use nsX names.
    for prefix, namespace in g2.namespaces():
        if not re.match(r'^ns\d+$', str(prefix)):
            g1.bind(prefix, namespace)

    # Add triples from g2 to g1
    for triple in g2:
        g1.add(triple)

    # Explicitly re-bind caller-supplied namespaces with override so that proper
    # prefix names take precedence over any auto-generated nsX names that may have
    # been introduced by either input file (e.g. tara-imported-terms.ttl uses full
    # URIs without declared prefixes, so rdflib auto-generates nsX for them).
    if bind_namespaces:
        for prefix, uri in bind_namespaces.items():
            g1.bind(prefix, Namespace(uri), override=True, replace=True)

    # Serialize the merged graph to a new TTL file
    g1.serialize(destination=merged_ontology_path, format="turtle")
    print ("  Merged Ontology Saved At: " + os.path.relpath(merged_ontology_path))


# Example testing usage
# ontology1_path = '../ontology-files/generated/ttl/tmp/tara-acupoints-temp.ttl'
# ontology2_path = '../ontology-files/base/tara-acupoints-upper.ttl'
# merged_ontology_path = '../ontology-files/generated/ttl/tara-acupoints.ttl'


# testing the function
# merge_ontologies(ontology1_path, ontology2_path, merged_ontology_path)

