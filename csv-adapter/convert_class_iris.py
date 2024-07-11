'''
Script to convert IRI suffixes of the generated TARA Acupoints Ontology classes from CSV by acupoints_ontology_adapter.py
The script converts class IRIs with textual suffixes into numerical suffixes followed by TARA_ e.g., TARA_0123456 format.
- Fahim Imam
'''

import rdflib
import hashlib
import re

# Base namespace for new IRIs
base_namespace = "http://www.acupunctureresearch.org/tara/ontology/acupoints.owl#"

# Dictionary to keep track of generated IDs and ensure uniqueness
generated_ids = {}
iri_mapping = {}

def generate_numeric_id(text):
    # Use a hash function to generate a numeric ID
    hash_object = hashlib.sha256(text.encode())
    hex_dig = hash_object.hexdigest()
    # Convert the hash to an integer and then to a 6-digit number
    numeric_id = int(hex_dig, 16) % 10000000  # Ensure it's a 7-digit number
    return numeric_id

def convert_iri(old_iri):
    # Check if the IRI has already been converted
    if old_iri in iri_mapping:
        return iri_mapping[old_iri]

    # Match the pattern e.g., http://www.acupunctureresearch.org/tara/ontology/acupoints.owl#Meridian_Acupoint
    # (TARA:Meridan_Acupoint) 
    pattern = re.compile(r"http://www.acupunctureresearch.org/tara/ontology/acupoints.owl#(.*)")
    match = pattern.match(old_iri)
    if match:
        class_name = match.group(1)
        new_id = generate_numeric_id(class_name)
        # Handle collisions by regenerating the ID if it already exists
        while new_id in generated_ids and generated_ids[new_id] != class_name:
            class_name += "_"
            new_id = generate_numeric_id(class_name)
        # Store the generated ID and the corresponding class name to ensure uniqueness
        generated_ids[new_id] = class_name
        new_id_str = f"TARA_{new_id:07d}"  # Format as a 7-digit number with leading zeros if necessary
        # Construct the new IRI
        new_iri = f"{base_namespace}{new_id_str}"
        # Store the mapping
        iri_mapping[old_iri] = new_iri
        return new_iri
    return old_iri

# Check if the IRI is a property (object or annotation)
def is_property(graph, iri):
    for s, p, o in graph.triples((iri, rdflib.RDF.type, None)):
        if o in {rdflib.OWL.ObjectProperty, rdflib.OWL.AnnotationProperty}:
            return True
    return False

# Path to the Turtle files
# input_ttl_file = "../ontology-files/generated/tara-acupoints.ttl"
# output_ttl_file = "../ontology-files/generated/test-ontology.ttl"

def convert_iri_suffixes_to_numeric(input_ttl_file, output_ttl_file):
    # Load the RDF graph
    graph = rdflib.Graph()
    try:
        graph.parse(input_ttl_file, format="ttl")
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        exit(1)

    # Create a list of triples to remove and add to avoid modifying the graph while iterating
    triples_to_remove = []
    triples_to_add = []


    # Iterate over all triples in the graph
    for subj, pred, obj in graph:
        if isinstance(subj, rdflib.URIRef) and not is_property(graph, subj):
            new_subj = rdflib.URIRef(convert_iri(str(subj)))
        else:
            new_subj = subj
        
        if isinstance(obj, rdflib.URIRef) and not is_property(graph, obj):
            new_obj = rdflib.URIRef(convert_iri(str(obj)))
        else:
            new_obj = obj
        
        if (new_subj, pred, new_obj) != (subj, pred, obj):
            triples_to_remove.append((subj, pred, obj))
            triples_to_add.append((new_subj, pred, new_obj))

    # Remove old triples and add new triples to the graph
    for triple in triples_to_remove:
        graph.remove(triple)
    for triple in triples_to_add:
        graph.add(triple)

    # Add all namespace prefixes from the original graph to the new graph
    for prefix, namespace in graph.namespaces():
        graph.bind(prefix, namespace)

    # Serialize the updated graph to a new Turtle file
    try:
        graph.serialize(destination=output_ttl_file, format="ttl")
        print(f"  Generated Turtle File With Converted IRI Suffixes: {output_ttl_file}")
    except Exception as e:
        print(f"  An error occurred while writing to the file: {e}")

# Testing function
# convert_iri_suffixes_to_numeric(input_ttl_file, output_ttl_file)