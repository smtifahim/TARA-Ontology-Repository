'''
Python script to merge two input ontologies and save the merged ontology into a file.
-Fahim Imam
'''
from rdflib import Graph

def merge_ontologies(ontology1_path, ontology2_path, merged_ontology_path):
    # Load the first ontology
    g1 = Graph()
    g1.parse(ontology1_path, format="turtle")

    # Load the second ontology
    g2 = Graph()
    g2.parse(ontology2_path, format="turtle")

    # Merge namespaces from g2 into g1
    for prefix, namespace in g2.namespaces():
        g1.bind(prefix, namespace)

    # Add triples from g2 to g1
    for triple in g2:
        g1.add(triple)

    # Serialize the merged graph to a new TTL file
    g1.serialize(destination=merged_ontology_path, format="turtle")
    print ("  Merged Ontology Saved At: " + merged_ontology_path)

# Example usage
# ontology1_path = '../ontology-files/generated/tara-acupoints.ttl'
# ontology2_path = '../ontology-files/tara-acupoints-upper.ttl'
# merged_ontology_path = '../ontology-files/tara-acupoints-merged.ttl'

ontology1_path = '../ontology-files/generated/tara-acupoints-merged.ttl'
ontology2_path = '../ontology-files/acupoints-inferred.ttl'
merged_ontology_path = '../ontology-files/generated/tara-acupoints-inferred.ttl'

# testing the function
merge_ontologies(ontology1_path, ontology2_path, merged_ontology_path)

