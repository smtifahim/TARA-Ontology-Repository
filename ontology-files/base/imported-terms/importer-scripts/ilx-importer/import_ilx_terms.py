"""
import_ilx_terms.py
-------------------
Fetches all terms belonging to the TARA Acupoint Ontology termset
(http://uri.interlex.org/base/ilx_0795339) from the InterLex API
(https://scicrunch.org/scicrunch/interlex/dashboard) and exports them
as a Turtle (.ttl) OWL ontology file.

For each term the script collects:
  - Label, definition (IAO:0000115), synonyms, and all annotation properties
  - Cross-reference IRIs (ilxtr:hasExistingId)
  - isPartOf (ilx:0112785) relationships, with the range term fully declared
  - rdfs:subClassOf hierarchy up to 'anatomical entity' (UBERON:0001062)

URI policy:
  - If a term has a UBERON existing ID, the UBERON IRI is used as the OWL
    class URI; otherwise the ILX IRI (http://uri.interlex.org/base/ilx_*)
    is used.

Output:
  ../../imported-ttl-files/imported-tara-ilx-terms.ttl

Usage:
  python import_ilx_terms.py
  
Author: Fahim Imam
Last Updated: 2026-07-04
"""

import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv
from rdflib import Graph, Literal, Namespace, RDF, RDFS, OWL, URIRef

# Load environment variables from .env in the same directory as this script
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# ---------------------------------------------------------------------------
# 1. API Configuration
# ---------------------------------------------------------------------------
API_KEY = os.getenv("SCICRUNCH_API_KEY")
if not API_KEY:
    sys.exit("Error: SCICRUNCH_API_KEY is not set. Add it to the .env file.")
BASE_URL = "https://scicrunch.org/api/1/ilx/search/curie"
REQUEST_DELAY = 0.3  # seconds between calls to respect rate limits

# Targeted entities
TERMSET_ILX = "ilx_0795339"   # TARA Acupoint Ontology Termset
INCLUDES_TERM_ILX = "ilx_0770273"  # includesTerm relationship
IS_PART_OF_ILX = "ilx_0112785"     # isPartOf relationship

# Stop hierarchy traversal at anatomical entity
ANATOMICAL_ENTITY_URI = URIRef("http://purl.obolibrary.org/obo/UBERON_0001062")

# ---------------------------------------------------------------------------
# 2. Namespaces (per project spec)
# ---------------------------------------------------------------------------
ILX_NS   = Namespace("http://uri.interlex.org/base/ilx_")   # ILX: prefix
ILXBASE  = Namespace("http://uri.interlex.org/base/")        # raw ilx_ URIs
ILXR     = Namespace("http://uri.interlex.org/base/readable/")
ILXTR    = Namespace("http://uri.interlex.org/tgbugs/uris/readable/")
UBERON   = Namespace("http://purl.obolibrary.org/obo/UBERON_")
IAO      = Namespace("http://purl.obolibrary.org/obo/IAO_")
oboInOwl = Namespace("http://www.geneontology.org/formats/oboInOwl#")
FMA_NS   = Namespace("http://purl.org/sig/ont/fma/fma")
fma_ns   = Namespace("http://purl.org/sig/ont/fma/")
BIRNLEX  = Namespace("http://uri.neuinfo.org/nif/nifstd/birnlex_")
NIFRID   = Namespace("http://uri.neuinfo.org/nif/nifstd/readable/")
NLX      = Namespace("http://uri.neuinfo.org/nif/nifstd/nlx_")
BFO      = Namespace("http://purl.obolibrary.org/obo/BFO_")

# ILX predicate URI overrides (replace raw ILX uri with standard URI)
ILX_PRED_OVERRIDES = {
    "ilx_0737161": oboInOwl.hasExactSynonym,
    "ilx_0737162": oboInOwl.hasRelatedSynonym,
    "ilx_0737163": oboInOwl.hasNarrowSynonym,
    "ilx_0737164": oboInOwl.hasBroadSynonym,
    "ilx_0381360": oboInOwl.hasDbXref,
}

# ILX class URI replacements (swap ILX URI → BFO URI for well-known BFO terms)
ILX_CLASS_REPLACEMENTS = {
    URIRef("http://uri.interlex.org/base/ilx_0102514"): URIRef("http://purl.obolibrary.org/obo/BFO_0000002"),
    URIRef("http://uri.interlex.org/base/ilx_0105405"): URIRef("http://purl.obolibrary.org/obo/BFO_0000004"),
}
# Labels to keep for those BFO replacements (all other annotation triples dropped)
BFO_KEEP_LABELS = {
    URIRef("http://purl.obolibrary.org/obo/BFO_0000002"): "continuant",
    URIRef("http://purl.obolibrary.org/obo/BFO_0000004"): "independent continuant",
}

# Prefix map for synonym 'type' field expansion  (e.g. "oboInOwl:hasExactSynonym")
SYNONYM_TYPE_PREFIXES = {
    "oboInOwl": "http://www.geneontology.org/formats/oboInOwl#",
    "fma":      "http://purl.org/sig/ont/fma/",
    "NIFRID":   "http://uri.neuinfo.org/nif/nifstd/readable/",
    "rdfs":     "http://www.w3.org/2000/01/rdf-schema#",
}

# ---------------------------------------------------------------------------
# 3. RDF Graph
# ---------------------------------------------------------------------------
g = Graph()
g.bind("ILX",      ILX_NS)
g.bind("ilxr",     ILXR)
g.bind("ilxtr",    ILXTR)
g.bind("UBERON",   UBERON)
g.bind("IAO",      IAO)
g.bind("oboInOwl", oboInOwl, override=True)
g.bind("FMA",      FMA_NS)
g.bind("fma",      fma_ns)
g.bind("BIRNLEX",  BIRNLEX)
g.bind("NIFRID",   NIFRID)
g.bind("NLX",      NLX)
g.bind("BFO",      BFO)
g.bind("owl",      OWL)
g.bind("rdfs",     RDFS)
g.bind("rdf",      RDF)

DEFINITION  = IAO["0000115"]      # http://purl.obolibrary.org/obo/IAO_0000115
HAS_EXISTING_ID = ILXTR.hasExistingId
IS_PART_OF  = ILXBASE[IS_PART_OF_ILX]   # http://uri.interlex.org/base/ilx_0112785
INCLUDES_TERM = ILXBASE[INCLUDES_TERM_ILX]

# ---------------------------------------------------------------------------
# 4. Helpers
# ---------------------------------------------------------------------------

def ilx_to_curie(ilx_id):
    """'ilx_0XXXXXX' → 'ILX:0XXXXXX'"""
    return "ILX:" + ilx_id.split("_", 1)[1]


def fetch_term_data(ilx_id):
    """Fetch full InterLex term data; returns parsed JSON or None."""
    curie = ilx_to_curie(ilx_id)
    url = f"{BASE_URL}/{curie}"
    time.sleep(REQUEST_DELAY)
    resp = requests.get(url, params={"key": API_KEY})
    if resp.status_code == 200:
        return resp.json()
    print(f"  Warning: HTTP {resp.status_code} for {curie}")
    return None


def get_canonical_uri(ilx_id, existing_ids):
    """Return UBERON URI if available among existing_ids, else ILX URI."""
    for eid in existing_ids:
        iri = eid.get("iri", "")
        if iri.startswith("http://purl.obolibrary.org/obo/UBERON_"):
            return URIRef(iri)
    return URIRef(f"http://uri.interlex.org/base/{ilx_id}")


def predicate_uri(annotation_ilx):
    """Map annotation_term_ilx to its predicate URI, applying overrides."""
    if annotation_ilx in ILX_PRED_OVERRIDES:
        return ILX_PRED_OVERRIDES[annotation_ilx]
    return URIRef(f"http://uri.interlex.org/base/{annotation_ilx}")


def expand_synonym_type(type_str):
    """Expand 'prefix:localname' synonym type to a full URI."""
    if ":" in type_str:
        prefix, local = type_str.split(":", 1)
        base = SYNONYM_TYPE_PREFIXES.get(prefix)
        if base:
            return URIRef(base + local)
    return URIRef(type_str)


def add_term_triples(ilx_id, detail, visited):
    """
    Add all RDF triples for one term, then recursively process its
    superclasses up to (but not past) anatomical entity.
    Returns the canonical URI for this term.
    """
    existing_ids = detail.get("existing_ids", [])
    term_uri = get_canonical_uri(ilx_id, existing_ids)

    if term_uri in visited:
        return term_uri
    visited.add(term_uri)

    g.add((term_uri, RDF.type, OWL.Class))

    # --- label ---
    label = detail.get("label", "")
    if label:
        g.add((term_uri, RDFS.label, Literal(label)))

    # --- definition (IAO:0000115) ---
    definition = detail.get("definition", "")
    if definition:
        g.add((term_uri, DEFINITION, Literal(definition)))

    # --- hasExistingId for every cross-reference IRI ---
    for eid in existing_ids:
        iri = eid.get("iri", "")
        if iri:
            g.add((term_uri, HAS_EXISTING_ID, URIRef(iri)))

    # --- synonyms (from top-level synonyms array) ---
    for syn in detail.get("synonyms", []):
        literal = syn.get("literal", "")
        syn_type = syn.get("type", "")
        if literal and syn_type:
            pred = expand_synonym_type(syn_type)
            g.add((term_uri, pred, Literal(literal)))

    # --- annotations (arbitrary annotation properties from InterLex) ---
    for ann in detail.get("annotations", []):
        ann_ilx = ann.get("annotation_term_ilx", "")
        value   = ann.get("value", "")
        if ann_ilx and value:
            pred = predicate_uri(ann_ilx)
            g.add((term_uri, pred, Literal(value)))

    # --- relationships: isPartOf and any others (excluding includesTerm) ---
    for rel in detail.get("relationships", []):
        rel_ilx = rel.get("relationship_term_ilx", "")
        if rel_ilx == INCLUDES_TERM_ILX:
            continue  # skip back-reference to the termset
        if rel_ilx == IS_PART_OF_ILX:
            t2_ilx = rel.get("term2_ilx", "")
            if not t2_ilx:
                continue
            # Fetch full data for the range term so it gets declared with all
            # metadata, the correct canonical URI (UBERON > ILX), and its hierarchy
            t2_detail = fetch_term_data(t2_ilx)
            if t2_detail and "data" in t2_detail:
                t2_uri = add_term_triples(t2_ilx, t2_detail["data"], visited)
            else:
                # Fallback: derive URI from curie in relationship data
                t2_curie = rel.get("term2_curie", "")
                if t2_curie.startswith("UBERON:"):
                    t2_num = t2_curie.split(":", 1)[1]
                    t2_uri = URIRef(f"http://purl.obolibrary.org/obo/UBERON_{t2_num}")
                else:
                    t2_uri = URIRef(f"http://uri.interlex.org/base/{t2_ilx}")
                g.add((t2_uri, RDF.type, OWL.Class))
                t2_label = rel.get("term2_label", "")
                if t2_label:
                    g.add((t2_uri, RDFS.label, Literal(t2_label)))
            g.add((term_uri, IS_PART_OF, t2_uri))

    # --- subClassOf hierarchy: recurse upward until anatomical entity ---
    for sc in detail.get("superclasses", []):
        sc_ilx = sc.get("ilx", "")
        if not sc_ilx:
            continue
        sc_detail = fetch_term_data(sc_ilx)
        if not sc_detail or "data" not in sc_detail:
            # Fallback: declare stub class with label only
            sc_uri = URIRef(f"http://uri.interlex.org/base/{sc_ilx}")
            g.add((sc_uri, RDF.type, OWL.Class))
            sc_label = sc.get("label", "")
            if sc_label:
                g.add((sc_uri, RDFS.label, Literal(sc_label)))
            g.add((term_uri, RDFS.subClassOf, sc_uri))
            continue

        sc_uri = add_term_triples(sc_ilx, sc_detail["data"], visited)
        g.add((term_uri, RDFS.subClassOf, sc_uri))

        # Stop recursing further once we have added anatomical entity itself
        if sc_uri == ANATOMICAL_ENTITY_URI:
            break

    return term_uri


# ---------------------------------------------------------------------------
# 5. Main
# ---------------------------------------------------------------------------

def main():
    print(f"Querying InterLex for termset: {ilx_to_curie(TERMSET_ILX)}...")

    termset_json = fetch_term_data(TERMSET_ILX)
    if not termset_json or "data" not in termset_json:
        print("Error: Could not retrieve termset data. Check the API key.")
        return

    ts_data = termset_json["data"]
    termset_uri = URIRef(f"http://uri.interlex.org/base/{TERMSET_ILX}")
    g.add((termset_uri, RDF.type, OWL.NamedIndividual))
    g.add((termset_uri, RDFS.label, Literal(ts_data.get("label", "TARA Acupoint Ontology Termset"))))

    # Collect all terms via includesTerm
    child_ilx_ids = []
    print("Extracting terms via 'includesTerm' relationships...")
    for rel in ts_data.get("relationships", []):
        if rel.get("relationship_term_ilx") == INCLUDES_TERM_ILX:
            t2_ilx = rel.get("term2_ilx")
            if t2_ilx:
                child_ilx_ids.append(t2_ilx)

    print(f"Found {len(child_ilx_ids)} terms. Fetching full metadata + hierarchy...")

    visited = set()  # tracks canonical URIs already processed (avoids re-fetching)

    for i, term_ilx in enumerate(child_ilx_ids, 1):
        print(f"  [{i}/{len(child_ilx_ids)}] {term_ilx}")
        term_detail = fetch_term_data(term_ilx)
        if not term_detail or "data" not in term_detail:
            continue

        term_uri = add_term_triples(term_ilx, term_detail["data"], visited)
        g.add((termset_uri, INCLUDES_TERM, term_uri))

    # -----------------------------------------------------------------------
    # Post-processing on the RDF graph
    # -----------------------------------------------------------------------

    # 1. Replace synonym predicate URIs that arrive as raw ILX IRIs in the graph
    PRED_URI_REPLACEMENTS = {
        URIRef("http://purl.org/sig/ont/fma/synonym"):                     oboInOwl.hasExactSynonym,
        URIRef("http://uri.neuinfo.org/nif/nifstd/readable/synonym"):      oboInOwl.hasExactSynonym,
        URIRef("http://uri.interlex.org/base/ilx_0737162"):               oboInOwl.hasRelatedSynonym,
        URIRef("http://uri.interlex.org/base/ilx_0737163"):               oboInOwl.hasNarrowSynonym,
        URIRef("http://uri.interlex.org/base/ilx_0737164"):               oboInOwl.hasBroadSynonym,
    }
    for old_pred, new_pred in PRED_URI_REPLACEMENTS.items():
        for s, o in list(g.subject_objects(old_pred)):
            g.remove((s, old_pred, o))
            g.add((s, new_pred, o))

    # 2. Replace BFO class URIs and strip all their triples except rdfs:label
    for old_uri, new_uri in ILX_CLASS_REPLACEMENTS.items():
        # Move all triples where old_uri is subject
        for p, o in list(g.predicate_objects(old_uri)):
            g.remove((old_uri, p, o))
        # Move all triples where old_uri is object
        for s, p in list(g.subject_predicates(old_uri)):
            g.remove((s, p, old_uri))
            g.add((s, p, new_uri))
        # Declare the BFO class with label only
        g.add((new_uri, RDF.type, OWL.Class))
        g.add((new_uri, RDFS.label, Literal(BFO_KEEP_LABELS[new_uri])))

    # 3. Add rdfs:label for annotation/object properties used in the graph
    PROP_LABELS = {
        ILXBASE[INCLUDES_TERM_ILX]:           "includesTerm",
        ILXBASE["ilx_0777130"]:               "hasDefinitionSource",
        IAO["0000115"]:                       "definition",
        ILXBASE[IS_PART_OF_ILX]:              "isPartOf",
        ILXBASE["ilx_0381387"]:               "hasLaterality",
        ILXBASE["ilx_0383241"]:               "isDeprecated",
    }
    for prop_uri, prop_label in PROP_LABELS.items():
        g.add((prop_uri, RDFS.label, Literal(prop_label)))

    # 4. IAO:0000102 class + termset subClassOf
    IAO_0000102 = IAO["0000102"]
    g.add((IAO_0000102, RDF.type, OWL.Class))
    g.add((IAO_0000102, RDFS.label, Literal("data about an ontology part")))
    g.add((termset_uri, RDFS.subClassOf, IAO_0000102))

    # 5. Ontology declaration
    ontology_uri = URIRef("http://www.acupunctureresearch.org/tara/ontology/tara-ilx-import.owl")
    today = date.today().strftime("%Y-%m-%d")
    ontology_comment = (
        "This file contains the imported terms from InterLex used by the TARA Acupoints Ontology "
        "(http://uri.interlex.org/base/ilx_0795339). It includes the basic hierarchy and the "
        f"partnomy of the imported terms. [Latest Update: {today}]"
    )
    g.add((ontology_uri, RDF.type, OWL.Ontology))
    g.add((ontology_uri, RDFS.comment, Literal(ontology_comment)))

    # 6. Serialize to TTL
    import os
    output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "imported-ttl-files")
    os.makedirs(output_dir, exist_ok=True)
    output_filename = os.path.join(output_dir, "imported-tara-ilx-terms.ttl")
    ttl_text = g.serialize(format="turtle")

    # 7. Text-level post-processing: fix rdflib-generated namespace prefixes
    # Replace any spurious nsN: aliases that rdflib may generate for oboInOwl
    ttl_text = re.sub(r'\bns\d+:', 'oboInOwl:', ttl_text)
    ttl_text = re.sub(r'@prefix ns\d+:.*?\n', '', ttl_text)
    # Fix rdflib built-in oboInOwl → <obo:> mapping if override didn't take effect
    ttl_text = ttl_text.replace(
        '@prefix oboInOwl: <obo:> .',
        '@prefix oboInOwl: <http://www.geneontology.org/formats/oboInOwl#> .'
    )

    # 8. Ensure the isPartOf prefix is present
    IS_PART_OF_PREFIX = '@prefix isPartOf: <http://uri.interlex.org/base/ilx_0112785> .\n'
    BFO_PREFIX        = '@prefix BFO: <http://purl.obolibrary.org/obo/BFO_> .\n'
    # Insert after the last @prefix line
    last_prefix_pos = ttl_text.rfind('@prefix ')
    insert_pos = ttl_text.index('\n', last_prefix_pos) + 1
    extras = ''
    if IS_PART_OF_PREFIX not in ttl_text:
        extras += IS_PART_OF_PREFIX
    if BFO_PREFIX not in ttl_text:
        extras += BFO_PREFIX
    if extras:
        ttl_text = ttl_text[:insert_pos] + extras + ttl_text[insert_pos:]

    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(ttl_text)

    print(f"\nDone! {len(child_ilx_ids)} primary terms + hierarchy written to: {output_filename}")


if __name__ == "__main__":
    main()
