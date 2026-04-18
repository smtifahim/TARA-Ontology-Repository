"""
Script to generate the inferred class hierarchy for TARA Acupoints Ontology
using the HermiT reasoner (via owlready2).

For each class, asserted named-class superclasses are replaced with inferred
direct superclasses, matching Protege's inferred-hierarchy-tab behaviour.
Logical axioms (restrictions, intersections stored as BNodes) are preserved.

Usage:
    python hermit_reasoner.py                        # uses default paths
    python hermit_reasoner.py <input.ttl> <output.ttl>

- Fahim Imam
"""
import os
import sys
import tempfile
import owlready2
from owlready2 import get_ontology, sync_reasoner_hermit, owl, ThingClass
from rdflib import Graph, URIRef, Namespace, BNode
from rdflib.namespace import RDFS, OWL

# --- Default paths (relative to csv-adapter/) ---
DEFAULT_INPUT_FILE  = "../ontology-files/generated/ttl/tara-acupoints-merged.ttl"
DEFAULT_OUTPUT_FILE = "../ontology-files/generated/ttl/tara-acupoints-inferred.ttl"

# --- Namespace prefixes ---
NAMESPACES = {
    "IAO"      : "http://purl.obolibrary.org/obo/IAO_",
    "RO"       : "http://purl.obolibrary.org/obo/RO_",
    "BFO"      : "http://purl.obolibrary.org/obo/BFO_",
    "obo"      : "http://purl.obolibrary.org/obo/",
    "TARA"     : "http://www.acupunctureresearch.org/tara/ontology/",
    "UBERON"   : "http://purl.obolibrary.org/obo/UBERON_",
    "OboInOwl" : "http://www.geneontology.org/formats/oboInOwl#",
    "swrl"     : "http://www.w3.org/2003/11/swrl#",
    "dcterms"  : "http://purl.org/dc/terms/",
    "dc"       : "http://purl.org/dc/elements/1.1/",
    "ILX"      : "http://uri.interlex.org/base/ilx_",
    "ilxtr"    : "http://uri.interlex.org/tgbugs/uris/readable/",
    "ilxr"     : "http://uri.interlex.org/base/readable/",
    "NIFRID"   : "http://uri.neuinfo.org/nif/nifstd/readable/",
    "FMA"      : "http://purl.org/sig/ont/fma/fma",
    "HP"       : "http://purl.obolibrary.org/obo/HP_",
    "MONDO"    : "http://purl.obolibrary.org/obo/MONDO_",
    "mondons"  : "http://purl.obolibrary.org/obo/mondo#",
    "protege"  : "http://protege.stanford.edu/plugins/owl/protege#",
}


def get_direct_inferred_named_superclasses(cls):
    """
    Return the direct inferred named superclasses for a class after HermiT
    has been run.

    owlready2 adds both asserted and inferred direct named superclasses to
    cls.is_a after reasoning. This function removes redundant entries: a
    parent X is redundant if another parent Y (Y != X) is a strict subclass
    of X, meaning X is already implied by Y.  This replicates Protege's
    inferred-hierarchy-tab behaviour where only the most specific
    superclasses are shown.
    """
    named_parents = [
        x for x in cls.is_a
        if isinstance(x, ThingClass)
        and x is not owl.Thing
        and x is not owl.Nothing
    ]

    if not named_parents:
        return []  # owl:Thing is the implicit parent; no triple needed

    # Keep x only when no sibling y is a strict subclass of x
    direct = [
        x for x in named_parents
        if not any(y is not x and issubclass(y, x) for y in named_parents)
    ]
    return direct


def main():
    # Accept optional CLI arguments; fall back to defaults
    INPUT_FILE  = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT_FILE
    OUTPUT_FILE = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUTPUT_FILE

    abs_input = os.path.abspath(INPUT_FILE)

    # ------------------------------------------------------------------
    # Step 1: Convert Turtle → N-Triples so owlready2 can parse it,
    #         then load and run HermiT
    # ------------------------------------------------------------------
    print(f"\n> Loading Ontology From: {INPUT_FILE}")
    g_load = Graph()
    g_load.parse(abs_input, format="turtle")

    # Write to a temporary N-Triples file (owlready2's native format)
    nt_fd, nt_path = tempfile.mkstemp(suffix=".nt")
    os.close(nt_fd)
    g_load.serialize(destination=nt_path, format="ntriples")

    print("> Running HermiT Reasoner (this may take a minute)...")
    onto = get_ontology(f"file://{nt_path}").load()
    with onto:
        sync_reasoner_hermit(infer_property_values=True)
    os.unlink(nt_path)
    print("  Reasoning Completed Successfully.")

    # ------------------------------------------------------------------
    # Step 2: Collect inferred results from owlready2
    # ------------------------------------------------------------------
    inferred_superclasses = {}  # {class_iri: [direct_super_iri, ...]}
    inferred_equivalents  = {}  # {class_iri: [equiv_iri, ...]}

    for cls in onto.classes():
        if cls.iri is None:
            continue

        direct_supers = get_direct_inferred_named_superclasses(cls)
        inferred_superclasses[cls.iri] = [
            sc.iri for sc in direct_supers if sc.iri is not None
        ]

        # Collect inferred equivalent classes (named classes only)
        equiv = [
            ec.iri for ec in cls.equivalent_to
            if isinstance(ec, ThingClass) and ec.iri is not None
        ]
        if equiv:
            inferred_equivalents[cls.iri] = equiv

    # ------------------------------------------------------------------
    # Step 3: Update the RDFLib graph — replace asserted named-class
    #         superclasses with the inferred direct ones
    # ------------------------------------------------------------------
    print("> Updating Class Hierarchy in Graph...")
    g = Graph()
    g.parse(abs_input, format="turtle")

    for cls_iri_str, direct_super_iris in inferred_superclasses.items():
        cls_ref = URIRef(cls_iri_str)

        # Remove all asserted rdfs:subClassOf to named classes (URIRefs).
        # BNode objects (anonymous restrictions / intersections) are kept
        # because they carry the logical axioms.
        for o in list(g.objects(cls_ref, RDFS.subClassOf)):
            if isinstance(o, URIRef):
                g.remove((cls_ref, RDFS.subClassOf, o))

        # Add the inferred direct named superclasses
        for sc_iri in direct_super_iris:
            g.add((cls_ref, RDFS.subClassOf, URIRef(sc_iri)))

    # Add inferred equivalent-class pairs not already in the graph
    for cls_iri_str, equiv_iris in inferred_equivalents.items():
        cls_ref = URIRef(cls_iri_str)
        existing = set(g.objects(cls_ref, OWL.equivalentClass))
        for eq_iri in equiv_iris:
            eq_ref = URIRef(eq_iri)
            if eq_ref not in existing:
                g.add((cls_ref, OWL.equivalentClass, eq_ref))

    # ------------------------------------------------------------------
    # Step 4: Re-bind namespaces and serialize
    # ------------------------------------------------------------------
    for prefix, uri in NAMESPACES.items():
        g.bind(prefix, Namespace(uri), override=True, replace=True)

    g.serialize(destination=OUTPUT_FILE, format="turtle")
    print(f"  Inferred Ontology Saved At: {OUTPUT_FILE}\n")


if __name__ == "__main__":
    main()

