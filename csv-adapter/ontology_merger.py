'''
Python script to merge two input ontologies and save the merged ontology into a file.
-Fahim Imam
'''
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
    print ("  Merged Ontology Saved At: " + merged_ontology_path)

# Example testing usage
# ontology1_path = '../ontology-files/generated/tara-acupoints.ttl'
# ontology2_path = '../ontology-files/tara-acupoints-upper.ttl'
# merged_ontology_path = '../ontology-files/tara-acupoints-merged.ttl'


# testing the function
# merge_ontologies(ontology1_path, ontology2_path, merged_ontology_path)

