"""
================================================================================
Ontology Variant Build and Namespace Migration Pipeline
================================================================================
Purpose:
    Automates the delivery maintenance of four distinct deployment variants of 
    the Acupoints Ontology. It migrates internal IRIs from a staging domain to 
    a permanent PURL namespace, performs version history rolling, and inserts 
    unique version identifiers along with creation timestamps.

Input Variations (Managed via Global File Path Variables):
    1. Asserted Base (Raw semantic axioms, excluding upper-level BFO boundaries)
    2. Inferred Base (Reasoner-computed closure, excluding upper-level BFO boundaries)
    3. Asserted BFO (Raw semantic axioms, merged with upper-level BFO classes)
    4. Inferred BFO (Reasoner-computed closure, merged with upper-level BFO classes)

Operations Executed Per Variant File:
    - Namespace Translation: Rewrites staging domain base addresses 
      (acupunctureresearch.org) into production addresses (purl.org).
    - Metadata Preservation: Retains Dublin Core properties (dc:title, dc:creator,
      etc.) while surgically updating versioning information.
    - Version History Rotation: Automatically transfers legacy 'owl:versionInfo' 
      strings into 'owl:priorVersion' declarations to track provenance.
    - Variant Mapping: Injects explicit unique 'owl:versionIRI' nodes to 
      differentiate variations on triple stores and local workspaces.
    - Timestamp Stamping: Appends a dynamic human-readable 'dcterms:created' date.

Post-Processing (Base Source File):
    - Also bumps 'owl:versionInfo' on the hand-authored base ontology source
      file (ontology-files/base/tara-acupoints-core.ttl) to the current
      VERSION_NUMBER, via a targeted text substitution that preserves its
      formatting/comments. No 'owl:versionIRI' is added to this file, since
      it is the editable source rather than a published variant.

Dependencies:
    - rdflib (RDF graph processing tool library)
    - os, datetime (Built-in Python workflow utilities)

Usage:
    Configure input/output global string file paths below and run directly via CLI:
    $ python update_ontology_headers.py
    
Author: Fahim Imam
Last Updated: August 15, 2026
================================================================================
"""

import os
import re
from datetime import datetime
from rdflib import DCTERMS, Graph, RDF, OWL, URIRef, Literal, Namespace
from rdflib.namespace import DC


# Should always update this to reflect the current global semantic version
VERSION_NUMBER = "1.7.0"

# =====================================================================
# GLOBAL CONFIGURATION: INPUT PATHS (Existing generated TTL files)
# =====================================================================

# TARA ACUPOINTS Ontology Input Paths
GENERATED_DIR = "../ontology-files/generated/temp-files/ttl/"
INPUT_ASSERTED_BASE = os.path.join(GENERATED_DIR, "no-upper/tara-acupoints.ttl")
INPUT_INFERRED_BASE = os.path.join(GENERATED_DIR, "no-upper/tara-acupoints-inferred.ttl")
INPUT_ASSERTED_BFO  = os.path.join(GENERATED_DIR, "tara-acupoints.ttl")
INPUT_INFERRED_BFO  = os.path.join(GENERATED_DIR, "tara-acupoints-inferred.ttl")

# ARTICLES KB Input Paths
INPUT_ASSERTED_KB = os.path.join(GENERATED_DIR, "no-upper/kb/tara-articles-kb.ttl")
INPUT_INFERRED_KB = os.path.join(GENERATED_DIR, "no-upper/kb/tara-articles-kb-no-upper-inferred.ttl")
INPUT_ASSERTED_KB_BFO  = os.path.join(GENERATED_DIR, "kb/tara-articles-kb-with-upper.ttl")
INPUT_INFERRED_KB_BFO  = os.path.join(GENERATED_DIR, "kb/tara-articles-kb-inferred.ttl")

# =====================================================================
# GLOBAL CONFIGURATION: OUTPUT PATHS (Where to save the updated files)
# =====================================================================

# TARA ACUPOINTS Ontology Output Paths
OUTPUT_DIR = "../ontology-files/generated/distribution/"
OUTPUT_ASSERTED_BASE = os.path.join(OUTPUT_DIR, "no-bfo-upper/tara-ontology/tara-acupoints.ttl")
OUTPUT_INFERRED_BASE = os.path.join(OUTPUT_DIR, "no-bfo-upper/tara-ontology/tara-acupoints-inferred.ttl")
OUTPUT_ASSERTED_BFO  = os.path.join(OUTPUT_DIR, "tara-ontology/tara-acupoints.ttl")
OUTPUT_INFERRED_BFO  = os.path.join(OUTPUT_DIR, "tara-ontology/tara-acupoints-inferred.ttl")

# ARTICLES KB Versioned Output Paths
OUTPUT_ASSERTED_KB = os.path.join(OUTPUT_DIR, "no-bfo-upper/tara-articles-kb/tara-articles-kb.ttl")
OUTPUT_INFERRED_KB = os.path.join(OUTPUT_DIR, "no-bfo-upper/tara-articles-kb/tara-articles-kb-inferred.ttl")
OUTPUT_ASSERTED_KB_BFO  = os.path.join(OUTPUT_DIR, "tara-articles-kb/tara-articles-kb.ttl")
OUTPUT_INFERRED_KB_BFO  = os.path.join(OUTPUT_DIR, "tara-articles-kb/tara-articles-kb-inferred.ttl")

# =====================================================================
# GLOBAL CONFIGURATION: BASE ONTOLOGY SOURCE FILE (post-processing target)
# =====================================================================
# Hand-authored source file that the generated variants above are built
# from. It only gets its owl:versionInfo bumped to the current
# VERSION_NUMBER -- no owl:versionIRI is added, since this is the editable
# source, not a published/deployed release artifact.
BASE_ONTOLOGY_CORE_TTL = "../ontology-files/base/tara-acupoints-core.ttl"

# =====================================================================
# GLOBAL CONFIGURATION: NAMESPACES AND IDENTITY
# =====================================================================
OLD_BASE = "http://www.acupunctureresearch.org/tara/ontology/"
NEW_BASE = "http://purl.org/tara/ontology/"
ONTOLOGY_IRI = URIRef("http://purl.org/tara/ontology/acupoints.owl")
VERSION_NAMESPACE = "http://purl.org/tara/ontology/v/"
DCTERMS = Namespace("http://purl.org/dc/terms/")

def migrate_namespaces(source_graph):
    """Translates all internal IRIs from acupunctureresearch.org to purl.org."""
    migrated_graph = Graph()
    
    # Update prefix bindings
    for prefix, namespace in source_graph.namespaces():
        ns_str = str(namespace)
        if ns_str.startswith(OLD_BASE):
            ns_str = ns_str.replace(OLD_BASE, NEW_BASE, 1)
        migrated_graph.bind(prefix, URIRef(ns_str))

    # Explicitly bind the dcterms prefix so serialization looks clean
    migrated_graph.bind("dcterms", DCTERMS)

    def convert_node(node):
        if isinstance(node, URIRef) and str(node).startswith(OLD_BASE):
            return URIRef(str(node).replace(OLD_BASE, NEW_BASE, 1))
        return node

    for s, p, o in source_graph:
        migrated_graph.add((convert_node(s), convert_node(p), convert_node(o)))
        
    return migrated_graph

def find_ontology_subject(graph):
    """
    Identifies the primary ontology declaration in a (possibly merged) graph.
    Merged variant files contain multiple owl:Ontology subjects -- one for
    the actual ontology plus one for each imported/bridged module (BFO
    upper, UBERON import, ILX import, MONDO/HP import, etc.) -- so the
    first match found cannot be trusted. The primary ontology is the only
    one carrying a dc:title; imported modules only declare rdf:type and
    rdfs:comment.
    """
    ontology_subjects = list(graph.subjects(RDF.type, OWL.Ontology))

    for subject in ontology_subjects:
        if (subject, DC.title, None) in graph:
            return subject

    # Fallback: no titled ontology subject found.
    return ontology_subjects[0] if ontology_subjects else ONTOLOGY_IRI


def target_version_header(graph, variant_path, flavor_text):
    """
    Surgically updates version metadata:
    - Moves old owl:versionInfo to owl:priorVersion
    - Injects the new owl:versionInfo using the global VERSION_NUMBER
    - Adds current dynamic date as dcterms:created
    - Keeps all other annotations intact (title, creator, etc.)
    """
    ont_sub = find_ontology_subject(graph)

    # 1. Capture the existing owl:versionInfo before deleting it
    old_version_infos = list(graph.objects(ont_sub, OWL.versionInfo))
    
    # 2. Clear old version properties and old creation dates
    graph.remove((ont_sub, OWL.versionIRI, None))
    graph.remove((ont_sub, OWL.versionInfo, None))
    graph.remove((ont_sub, DCTERMS.created, None))
    
    # 3. If an old version string existed, assign it to owl:priorVersion
    if old_version_infos:
        graph.remove((ont_sub, OWL.priorVersion, None)) 
        # FIX 2: Add each old version string literal individually, not as a raw list
        for old_info in old_version_infos:
            graph.add((ont_sub, OWL.priorVersion, old_info))
    
    # 4. Generate the current date in "August 15, 2026" format
    current_date_str = datetime.now().strftime("%B %d, %Y")
    
    # 5. Construct the unique versionIRI (e.g., .../version/inferred-base/acupoints.owl)
    unique_version_iri = URIRef(f"{VERSION_NAMESPACE}{variant_path}/acupoints.owl")
    
    # 6. Combine the global version variable with the descriptive flavor text
    full_version_label = f"{VERSION_NUMBER} - {flavor_text}"
    
    # 7. Inject the fresh metadata triples into the header
    graph.add((ont_sub, OWL.versionIRI, unique_version_iri))
    graph.add((ont_sub, OWL.versionInfo, Literal(full_version_label)))
    graph.add((ont_sub, DCTERMS.created, Literal(current_date_str)))


def reorder_ontology_header(graph, output_path):
    """
    Post-processing step run after a variant file has been saved: pulls every
    owl:Ontology-typed subject's triples (the ontology declaration itself --
    title, version info, etc. -- plus any bridged/imported module stubs, but
    never class/property/individual metadata) out of wherever rdflib's turtle
    serializer scattered them, and re-emits them as a single block directly
    under the @prefix declarations at the top of the file.
    """
    ontology_subjects = set(graph.subjects(RDF.type, OWL.Ontology))
    if not ontology_subjects:
        return

    header_graph = Graph()
    body_graph = Graph()
    for prefix, namespace in graph.namespaces():
        header_graph.bind(prefix, namespace)
        body_graph.bind(prefix, namespace)

    for s, p, o in graph:
        (header_graph if s in ontology_subjects else body_graph).add((s, p, o))

    header_serialized = header_graph.serialize(format="turtle").splitlines()
    header_prefix_lines = [line for line in header_serialized if line.startswith("@prefix")]
    header_lines = [line for line in header_serialized if not line.startswith("@prefix")]
    header_block = "\n".join(header_lines).strip("\n")

    body_lines = body_graph.serialize(format="turtle").splitlines()
    body_prefix_lines = [line for line in body_lines if line.startswith("@prefix")]
    rest_block = "\n".join(
        line for line in body_lines if not line.startswith("@prefix")
    ).strip("\n")

    # A prefix used only by the ontology header block (e.g. the bare
    # ontology IRI namespace, which the body never references) would
    # otherwise be silently dropped, leaving it unbound in the output.
    prefix_lines = sorted(set(header_prefix_lines) | set(body_prefix_lines))

    final_text = "\n".join(prefix_lines) + "\n\n" + header_block + "\n\n" + rest_block + "\n"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_text)


def process_variant(input_path, output_path, variant_key, flavor_text):
    """Helper function to run the full extraction and transformation workflow."""
    print(f"Processing: {input_path} -> {output_path}")

    # Load raw file
    raw_graph = Graph().parse(input_path, format="turtle")

    # Step 1: Handle global namespace replacement
    migrated_graph = migrate_namespaces(raw_graph)

    # Step 2: Handle header history rotation and creation timestamping
    target_version_header(migrated_graph, variant_key, flavor_text)

    # Save the output file out
    migrated_graph.serialize(destination=output_path, format="turtle")

    # Post-processing: move the ontology header/metadata block to the top,
    # right after the namespace declarations
    reorder_ontology_header(migrated_graph, output_path)


def update_base_ontology_version_info(path):
    """
    Post-processing step for the hand-authored base ontology source file:
    replaces its existing owl:versionInfo value with the current
    VERSION_NUMBER. No owl:priorVersion, owl:versionIRI, or dcterms:created
    is touched here -- that full header rotation is only applied to the
    generated distribution variants via target_version_header().

    Uses a targeted text substitution rather than an RDF parse/serialize
    round-trip, so the file's hand-curated formatting, comments, and
    triple ordering are left untouched.
    """
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    updated_content, replacement_count = re.subn(
        r'(owl:versionInfo\s+")[^"]*(")',
        rf'\g<1>{VERSION_NUMBER}\g<2>',
        content,
        count=1,
    )

    if replacement_count == 0:
        raise ValueError(f"No owl:versionInfo found to update in: {path}")

    with open(path, "w", encoding="utf-8") as f:
        f.write(updated_content)

    print(f"Updated owl:versionInfo to \"{VERSION_NUMBER}\" in base file: {path}")


def confirm(prompt_text):
    """Asks a Yes/No question at the console and returns True only on an explicit 'y'/'yes'."""
    response = input(f"{prompt_text} (y/n): ").strip().lower()
    return response in ("y", "yes")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Beginning update execution for version: {VERSION_NUMBER}\n")
    
    # Process Variant 1: Asserted Base
    process_variant(
        INPUT_ASSERTED_BASE, OUTPUT_ASSERTED_BASE, 
        VERSION_NUMBER + "/no-bfo/asserted", "Asserted Ontology (Excludes BFO Top-Level)"
    )

    # Process Variant 2: Inferred Base
    process_variant(
        INPUT_INFERRED_BASE, OUTPUT_INFERRED_BASE, 
        VERSION_NUMBER + "/no-bfo/inferred", "Inferred Ontology (Excludes BFO Top-Level)"
    )

    # Process Variant 3: Asserted + BFO
    process_variant(
        INPUT_ASSERTED_BFO, OUTPUT_ASSERTED_BFO, 
        VERSION_NUMBER + "/asserted", "Asserted Ontology"
    )

    # Process Variant 4: Inferred + BFO
    process_variant(
        INPUT_INFERRED_BFO, OUTPUT_INFERRED_BFO, 
        VERSION_NUMBER + "/inferred", "Inferred Ontology"
    )
    
     # Process Variant 1: Asserted KB
    process_variant(
        INPUT_ASSERTED_KB, OUTPUT_ASSERTED_KB, 
        VERSION_NUMBER + "/kb/no-bfo/asserted", "Asserted Ontology (Excludes BFO Top-Level)"
    )

    # Process Variant 2: Inferred KB
    process_variant(
        INPUT_INFERRED_KB, OUTPUT_INFERRED_KB, 
        VERSION_NUMBER + "/kb/no-bfo/inferred", "Inferred Ontology (Excludes BFO Top-Level)"
    )

    # Process Variant 3: Asserted KB + BFO
    process_variant(
        INPUT_ASSERTED_KB_BFO, OUTPUT_ASSERTED_KB_BFO, 
        VERSION_NUMBER + "/kb/asserted", "Asserted Ontology"
    )

    # Process Variant 4: Inferred KB + BFO
    process_variant(
        INPUT_INFERRED_KB_BFO, OUTPUT_INFERRED_KB_BFO, 
        VERSION_NUMBER + "/kb/inferred", "Inferred Ontology"
    )

    # Post-processing: bump the hand-authored base source file's
    # owl:versionInfo to match, without stamping a versionIRI on it.
    # This directly overwrites a hand-curated source file, so it requires
    # two explicit confirmations before proceeding.
    print(f"\nAbout to update owl:versionInfo to \"{VERSION_NUMBER}\" in: {BASE_ONTOLOGY_CORE_TTL}")
    if confirm("Are you sure?") and confirm("Are you sure?"):
        update_base_ontology_version_info(BASE_ONTOLOGY_CORE_TTL)
    else:
        print("Skipped: base ontology source file's owl:versionInfo was not updated.")

    print("\nSuccess! All files updated, version metadata rotated, and creation date stamped.")

if __name__ == "__main__":
    main()