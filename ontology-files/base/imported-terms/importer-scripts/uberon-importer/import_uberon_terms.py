"""
import_uberon_terms.py

Collects UBERON URIs from:
  1. Google Sheet tabs: Meridians, Acupoints-Locations, Acupoints-Nerves, Acupoints-Veins-Arteries
  2. imported-tara-ilx-terms.ttl

Extracts matching classes from uberon.ttl using rdflib with these rules:
  - Hierarchy walks up rdfs:subClassOf chains to UBERON:0001062 (anatomical entity)
  - CL_, GO_, NCBITaxon_, PATO_ classes are excluded from the output
    (but walked through to find UBERON ancestors, so no class is left bare)
  - No class above UBERON:0001062 is included
  - Annotation properties: all copied as-is
  - OWL axioms kept: named-class subClassOf + BFO:0000050 (part_of) restrictions only
  - SubClassOf restrictions with excluded-class fillers are dropped

Requirements: pip install requests rdflib

Author: Fahim Imam
Last Updated: 2026-07-04
"""

import csv, io, re, sys, urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import requests
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib import RDF, RDFS, OWL as OWL_URI

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR    = Path(__file__).resolve().parent
REPO_ROOT     = SCRIPT_DIR.parents[4]

TTL_DIR       = REPO_ROOT / "ontology-files" / "base" / "imported-terms" / "imported-ttl-files"
ILX_TTL       = TTL_DIR / "imported-tara-ilx-terms.ttl"
OUTPUT_TTL    = TTL_DIR / "imported-tara-uberon-terms.ttl"
URI_LIST_FILE = SCRIPT_DIR / "tara-uberon-uris.txt"

UBERON_TTL     = SCRIPT_DIR / "uberon.ttl"
UBERON_OWL_URL = "http://purl.obolibrary.org/obo/uberon.owl"   # fallback download

# ---------------------------------------------------------------------------
# Google Sheet
# ---------------------------------------------------------------------------
SHEET_ID = "1hvUcTrw-b9ly8Yn1P706px22li0vsjslukYhxkTDlA8"
SHEET_TABS = [
    ("Meridians",      "Associated Organ URI"),
    ("Acupoints-Locations",      "Identified Locations URI"),
    ("Acupoints-Nerves",         "Nerve Location URI"),
    ("Acupoints-Veins-Arteries", "Vasculature URI"),
]
UBERON_PREFIX = "http://purl.obolibrary.org/obo/UBERON_"
UBERON_RE     = re.compile(r'http://purl\.obolibrary\.org/obo/UBERON_\d+')

# ---------------------------------------------------------------------------
# Ontology constants
# ---------------------------------------------------------------------------
UPPER_TERM = URIRef("http://purl.obolibrary.org/obo/UBERON_0001062")  # anatomical entity

# SubClassOf restrictions using these object properties are kept
KEEP_OBJECT_PROPS: Set[URIRef] = {
    URIRef("http://purl.obolibrary.org/obo/BFO_0000050"),  # part of
    URIRef("http://purl.obolibrary.org/obo/BFO_0000051"),  # has part
    URIRef("http://purl.obolibrary.org/obo/RO_0001025"),   # located in
    URIRef("http://purl.obolibrary.org/obo/RO_0002170"),   # connected to
}

# Classes whose URIs start with these prefixes are excluded from the output
# (walked through for bridging but not included as classes)
EXCLUDE_PREFIXES: Tuple[str, ...] = (
    "http://purl.obolibrary.org/obo/CL_",
    "http://purl.obolibrary.org/obo/GO_",
    "http://purl.obolibrary.org/obo/NCBITaxon_",
    "http://purl.obolibrary.org/obo/PATO_",
    "http://purl.obolibrary.org/obo/RO_",
)

# Annotation properties to suppress entirely (not copied to output)
SKIP_ANNOTATION_PROPS: Set[URIRef] = {
    URIRef("http://www.geneontology.org/formats/oboInOwl#inSubset"),
    URIRef("http://www.geneontology.org/formats/oboInOwl#id"),
    URIRef("http://purl.obolibrary.org/obo/OMO_0002000"),
    URIRef("http://purl.obolibrary.org/obo/RO_0002175"),
    URIRef("http://purl.obolibrary.org/obo/RO_0002171"),
    URIRef("http://purl.obolibrary.org/obo/IAO_0000233"),
    URIRef("http://purl.obolibrary.org/obo/IAO_0006012"),
    URIRef("http://purl.obolibrary.org/obo/RO_0002161"),
}
SKIP_ANNOT_PREFIXES: Tuple[str, ...] = (
    "http://purl.obolibrary.org/obo/UBPROP_",
)

# Bare object-property assertions to ignore explicitly
SKIP_OBJECT_PROPS: Set[URIRef] = {
    URIRef("http://purl.obolibrary.org/obo/RO_0020105"),
    URIRef("http://purl.obolibrary.org/obo/RO_0002162"),
}

OWL_NS = Namespace("http://www.w3.org/2002/07/owl#")

_STRUCTURAL_PREDS = {
    RDF.type, RDFS.subClassOf,
    OWL_URI.equivalentClass, OWL_URI.disjointWith,
    OWL_URI.onProperty, OWL_URI.someValuesFrom, OWL_URI.allValuesFrom,
    OWL_URI.hasValue, OWL_URI.minCardinality, OWL_URI.maxCardinality,
    OWL_URI.cardinality, OWL_URI.intersectionOf, OWL_URI.unionOf,
    OWL_URI.complementOf, OWL_URI.oneOf, RDF.first, RDF.rest,
}

# ---------------------------------------------------------------------------
# URI helpers
# ---------------------------------------------------------------------------

def _is_excluded(uri: URIRef) -> bool:
    s = str(uri)
    return s.startswith(EXCLUDE_PREFIXES)


def _is_skipped_annotation(uri: URIRef) -> bool:
    """True if this annotation property should be suppressed from the output."""
    return uri in SKIP_ANNOTATION_PROPS or str(uri).startswith(SKIP_ANNOT_PREFIXES)


def _is_uberon(uri: URIRef) -> bool:
    return str(uri).startswith(UBERON_PREFIX)

# ---------------------------------------------------------------------------
# Google Sheet helpers
# ---------------------------------------------------------------------------

def fetch_sheet_csv(sheet_id: str, tab_name: str) -> List[Dict]:
    url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        f"/gviz/tq?tqx=out:csv&sheet={requests.utils.quote(tab_name)}"
    )
    print(f"  Fetching tab '{tab_name}' ...")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return list(csv.DictReader(io.StringIO(resp.text)))


def extract_uberon_uris_from_column(rows: List[Dict], column: str) -> Set[str]:
    uris: Set[str] = set()
    for row in rows:
        uris.update(UBERON_RE.findall(row.get(column, "") or ""))
    return uris


def extract_uberon_uris_from_ttl(ttl_path: Path) -> Set[str]:
    text = ttl_path.read_text(encoding="utf-8")
    uris: Set[str] = set(UBERON_RE.findall(text))
    for m in re.finditer(r'UBERON[_:](\d+)', text):
        uris.add(f"{UBERON_PREFIX}{m.group(1)}")
    return uris

# ---------------------------------------------------------------------------
# UBERON download (fallback if uberon.ttl is missing)
# ---------------------------------------------------------------------------

def ensure_uberon_source() -> Path:
    if UBERON_TTL.exists():
        print(f"  Using {UBERON_TTL.name} ({UBERON_TTL.stat().st_size // (1024*1024)} MB)")
        return UBERON_TTL
    # Try uberon.owl in same directory
    owl_path = SCRIPT_DIR / "uberon.owl"
    if owl_path.exists():
        print(f"  uberon.ttl not found; using {owl_path.name}")
        return owl_path
    print(f"  Downloading UBERON ontology from {UBERON_OWL_URL} ...")
    urllib.request.urlretrieve(UBERON_OWL_URL, owl_path)
    return owl_path

# ---------------------------------------------------------------------------
# rdflib extraction helpers
# ---------------------------------------------------------------------------

def _copy_bnode_subtree(src: Graph, dst: Graph, node: BNode,
                        visited: Optional[Set] = None):
    if visited is None:
        visited = set()
    if node in visited:
        return
    # If this node itself is an owl:Restriction with a disallowed property, don't copy it
    if (node, RDF.type, OWL_NS.Restriction) in src:
        disallowed = all(
            isinstance(prop, URIRef) and prop not in KEEP_OBJECT_PROPS
            for prop in src.objects(node, OWL_NS.onProperty)
        )
        if disallowed:
            return
    visited.add(node)
    for p, o in src.predicate_objects(node):
        # Skip nested blank nodes that are restrictions with disallowed properties
        if isinstance(o, BNode) and (o, RDF.type, OWL_NS.Restriction) in src:
            disallowed = all(
                isinstance(prop, URIRef) and prop not in KEEP_OBJECT_PROPS
                for prop in src.objects(o, OWL_NS.onProperty)
            )
            if disallowed:
                continue
        dst.add((node, p, o))
        if isinstance(o, BNode):
            _copy_bnode_subtree(src, dst, o, visited)


def _is_allowed_restriction(src: Graph, bn: BNode) -> bool:
    if (bn, RDF.type, OWL_NS.Restriction) not in src:
        return False
    for prop in src.objects(bn, OWL_NS.onProperty):
        if isinstance(prop, URIRef) and prop in KEEP_OBJECT_PROPS:
            return True
    return False


def _restriction_fillers(src: Graph, bn: BNode) -> Set[URIRef]:
    fillers: Set[URIRef] = set()
    for pred in (OWL_NS.someValuesFrom, OWL_NS.allValuesFrom,
                 OWL_NS.hasValue, OWL_NS.onClass):
        for obj in src.objects(bn, pred):
            if isinstance(obj, URIRef):
                fillers.add(obj)
    return fillers


def _walk_through_excluded_to_uberon(src: Graph,
                                     start: URIRef,
                                     all_terms: Set[URIRef]) -> Set[URIRef]:
    """
    Starting from an excluded (CL/GO/etc) class, walk its rdfs:subClassOf chain
    to find UBERON ancestors that are in all_terms.
    """
    result: Set[URIRef] = set()
    visited: Set[URIRef] = set()
    queue = [start]
    while queue:
        curr = queue.pop()
        if curr in visited:
            continue
        visited.add(curr)
        for parent in src.objects(curr, RDFS.subClassOf):
            if isinstance(parent, URIRef):
                if parent in all_terms:
                    result.add(parent)
                elif _is_excluded(parent) or not _is_uberon(parent):
                    # Continue walking through other non-UBERON classes too
                    queue.append(parent)
    return result

# ---------------------------------------------------------------------------
# Step 1: collect all UBERON terms to extract
# ---------------------------------------------------------------------------

def collect_terms_to_extract(src: Graph, seed_uris: Set[str]) -> Set[URIRef]:
    """
    BFS from seed terms, walking rdfs:subClassOf upward.
    - Adds only UBERON classes (not CL/GO/NCBITaxon/PATO) to the result.
    - Walks THROUGH excluded classes so their UBERON ancestors are captured.
    - Stops at UPPER_TERM (does not include anything above it).
    - Also enqueues UBERON filler classes of kept restrictions.
    """
    queue: List[URIRef] = [URIRef(u) for u in seed_uris]
    visited: Set[URIRef] = set()      # already-queued nodes
    result:  Set[URIRef] = set()      # UBERON classes to include in output

    while queue:
        term = queue.pop()
        if term in visited:
            continue
        visited.add(term)

        # Only add UBERON classes to result (excludes CL/GO/etc and BFO above ceiling)
        if _is_uberon(term):
            result.add(term)
            if term == UPPER_TERM:
                continue   # ceiling reached: don't walk further up

        # Walk named superclasses
        for parent in src.objects(term, RDFS.subClassOf):
            if isinstance(parent, URIRef) and parent not in visited:
                queue.append(parent)

        # Walk allowed-restriction fillers (part_of only)
        for sc in src.objects(term, RDFS.subClassOf):
            if isinstance(sc, BNode) and _is_allowed_restriction(src, sc):
                for filler in _restriction_fillers(src, sc):
                    if _is_uberon(filler) and filler not in visited:
                        queue.append(filler)

    return result

# ---------------------------------------------------------------------------
# Step 2: build bridge map (UBERON parent for each class, bridging excluded)
# ---------------------------------------------------------------------------

def build_bridge_map(src: Graph,
                     all_terms: Set[URIRef]) -> Dict[URIRef, Set[URIRef]]:
    """
    For every class in all_terms, build the set of effective UBERON parents:
      - Direct named subClassOf that is also in all_terms: add as-is
      - Named subClassOf that is EXCLUDED (CL/GO/etc): walk through to find
        the nearest UBERON ancestor(s) in all_terms
      - Named subClassOf above the ceiling (not in all_terms, not excluded): skip
    Returns dict: class_uri -> {uberon_parent_uris}
    """
    bridge_map: Dict[URIRef, Set[URIRef]] = {}
    for term in all_terms:
        parents: Set[URIRef] = set()
        for parent in src.objects(term, RDFS.subClassOf):
            if isinstance(parent, URIRef):
                if parent in all_terms:
                    parents.add(parent)
                elif _is_excluded(parent):
                    for uberon_anc in _walk_through_excluded_to_uberon(
                            src, parent, all_terms):
                        parents.add(uberon_anc)
                # else: above ceiling or unrelated — skip
        bridge_map[term] = parents
    return bridge_map

# ---------------------------------------------------------------------------
# Step 3: copy classes into output graph
# ---------------------------------------------------------------------------

def copy_class_to_graph(src: Graph, dst: Graph,
                        cls_uri: URIRef,
                        obj_props: Set[URIRef],
                        effective_parents: Set[URIRef]):
    """
    Copy one class into dst:
      - owl:Class declaration
      - Effective subClassOf parents (already bridged)
      - All annotation property assertions
      - SubClassOf blank-node restrictions for KEEP_OBJECT_PROPS
        (only if filler is NOT an excluded class)
    Bare object-property assertions are skipped.
    """
    dst.add((cls_uri, RDF.type, OWL_NS.Class))

    # Named-class hierarchy (bridged)
    for parent in effective_parents:
        dst.add((cls_uri, RDFS.subClassOf, parent))

    # Axioms from source
    for p, o in src.predicate_objects(cls_uri):
        if p == RDF.type:
            continue  # already added

        elif p == OWL_URI.disjointWith or p == OWL_URI.equivalentClass:
            continue  # skip disjointWith and equivalentClass entirely

        elif p == RDFS.subClassOf:
            if isinstance(o, BNode):
                if _is_allowed_restriction(src, o):
                    # Only keep restriction if ALL fillers are UBERON classes
                    fillers = _restriction_fillers(src, o)
                    if not fillers:
                        continue  # no filler — skip
                    if any(not _is_uberon(f) for f in fillers):
                        continue  # non-UBERON filler — skip
                    dst.add((cls_uri, RDFS.subClassOf, o))
                    _copy_bnode_subtree(src, dst, o)
            # Named subClassOf handled above via effective_parents — skip here

        elif isinstance(p, URIRef) and (p in obj_props or p in SKIP_OBJECT_PROPS):
            # Bare object-property assertion — skip
            continue

        elif isinstance(p, URIRef) and _is_skipped_annotation(p):
            # Suppressed annotation property — skip
            continue

        else:
            # Annotation / datatype assertion — copy if value is not an excluded URI
            if isinstance(o, URIRef) and _is_excluded(o):
                continue  # reference to excluded class — skip
            dst.add((cls_uri, p, o))
            if isinstance(o, BNode):
                _copy_bnode_subtree(src, dst, o)


def copy_property_decls(src: Graph, dst: Graph):
    # Annotation property declarations — skip suppressed ones
    used_preds: Set[URIRef] = {
        p for p in dst.predicates()
        if isinstance(p, URIRef)
        and p not in _STRUCTURAL_PREDS
        and not _is_skipped_annotation(p)
    }
    for pred in used_preds:
        if (pred, RDF.type, OWL_NS.AnnotationProperty) in src:
            for p, o in src.predicate_objects(pred):
                if _is_skipped_annotation(p):
                    continue
                dst.add((pred, p, o))
                if isinstance(o, BNode):
                    _copy_bnode_subtree(src, dst, o)

    # Object property declarations — only rdfs:label for the kept properties
    for prop in KEEP_OBJECT_PROPS:
        dst.add((prop, RDF.type, OWL_NS.ObjectProperty))
        for label in src.objects(prop, RDFS.label):
            dst.add((prop, RDFS.label, label))

# ---------------------------------------------------------------------------
# Step 4 (post-processing): remove classes not reachable from UPPER_TERM
# ---------------------------------------------------------------------------

def remove_unclassified(dst: Graph) -> int:
    """
    Remove any owl:Class in dst that has no subClassOf path leading up to
    UPPER_TERM (anatomical entity).  Iterates to fixpoint so that removing
    a class does not leave other classes dangling.

    After each pass, also removes:
      - SubClassOf restrictions whose filler is a removed class
      - All blank-node triples that become orphaned by those removals

    Returns the total number of classes removed.
    """
    total_removed = 0

    while True:
        # Collect all named OWL classes currently in the graph
        classes: Set[URIRef] = {
            s for s, p, o in dst.triples((None, RDF.type, OWL_NS.Class))
            if isinstance(s, URIRef)
        }

        # For each class find its named parents that are also in classes
        parent_map: Dict[URIRef, Set[URIRef]] = {c: set() for c in classes}
        for c in classes:
            for parent in dst.objects(c, RDFS.subClassOf):
                if isinstance(parent, URIRef) and parent in classes:
                    parent_map[c].add(parent)

        # BFS downward from UPPER_TERM to find everything reachable
        connected: Set[URIRef] = set()
        queue: List[URIRef] = [UPPER_TERM]
        while queue:
            curr = queue.pop()
            if curr in connected:
                continue
            connected.add(curr)
            for child, parents in parent_map.items():
                if curr in parents and child not in connected:
                    queue.append(child)

        to_remove = classes - connected
        if not to_remove:
            break   # fixpoint reached

        # 1. Remove all triples where the removed class is subject or object
        for c in to_remove:
            for p, o in list(dst.predicate_objects(c)):
                dst.remove((c, p, o))
            for s, p in list(dst.subject_predicates(c)):
                dst.remove((s, p, c))

        # 2. Remove SubClassOf restrictions whose filler is a removed class
        #    A restriction blank node is orphaned when its someValuesFrom / etc.
        #    pointed to a now-removed class.
        for subj in list(dst.subjects(RDF.type, OWL_NS.Class)):
            for sc in list(dst.objects(subj, RDFS.subClassOf)):
                if not isinstance(sc, BNode):
                    continue
                if (sc, RDF.type, OWL_NS.Restriction) not in dst:
                    continue
                fillers = _restriction_fillers(dst, sc)
                if fillers and any(f in to_remove for f in fillers):
                    # Remove the SubClassOf axiom pointing to this restriction
                    dst.remove((subj, RDFS.subClassOf, sc))
                    # Remove all triples of the blank node itself
                    for p, o in list(dst.predicate_objects(sc)):
                        dst.remove((sc, p, o))

        total_removed += len(to_remove)

    return total_removed


def remove_orphaned_anon_classes(dst: Graph) -> int:
    """
    Remove blank-node class expressions (anonymous classes) that were
    introduced by annotation property range/domain declarations but are
    not directly referenced by any named UBERON class via rdfs:subClassOf.

    These would otherwise appear as unclassified anonymous nodes in OWL editors.
    Returns number of blank nodes removed.
    """
    # Collect blank nodes that are reachable as the VALUE of a subClassOf from
    # a named UBERON class — these are valid restriction blank nodes we want.
    valid_bnodes: Set[BNode] = set()
    for s, p, o in dst.triples((None, RDFS.subClassOf, None)):
        if isinstance(s, URIRef) and isinstance(o, BNode):
            valid_bnodes.add(o)

    # Find all blank nodes declared as owl:Class that are NOT in valid_bnodes
    orphaned: Set[BNode] = {
        s for s, p, o in dst.triples((None, RDF.type, OWL_NS.Class))
        if isinstance(s, BNode) and s not in valid_bnodes
    }

    # For each orphaned blank node, also find any property that references it
    # (e.g., owl:domain / owl:range on annotation properties) and remove those
    # triples too, then remove the blank node's own triples.
    count = 0
    for bn in orphaned:
        for s, p in list(dst.subject_predicates(bn)):
            dst.remove((s, p, bn))
        for p, o in list(dst.predicate_objects(bn)):
            dst.remove((bn, p, o))
        count += 1

    return count

# ---------------------------------------------------------------------------
# Top-level extraction
# ---------------------------------------------------------------------------

def extract_uberon(uri_list_file: Path, output_ttl: Path):
    seed_uris: Set[str] = {
        line.strip()
        for line in uri_list_file.read_text().splitlines()
        if line.strip().startswith(UBERON_PREFIX)
    }
    print(f"  Seed terms: {len(seed_uris)}")

    src_path = ensure_uberon_source()
    fmt = "turtle" if src_path.suffix == ".ttl" else "xml"
    print(f"  Parsing {src_path.name} (format={fmt}) ...")
    src = Graph()
    src.parse(str(src_path), format=fmt)
    print(f"  Loaded {len(src):,} triples")

    obj_props: Set[URIRef] = set(src.subjects(RDF.type, OWL_NS.ObjectProperty))

    print("  Collecting UBERON classes to extract ...")
    all_terms = collect_terms_to_extract(src, seed_uris)
    all_terms = {t for t in all_terms if (t, RDF.type, OWL_NS.Class) in src}
    print(f"  {len(all_terms)} classes selected")

    print("  Building bridge map (resolving excluded-class parents) ...")
    bridge_map = build_bridge_map(src, all_terms)

    # Sanity check: how many classes have no parent (except UPPER_TERM itself)?
    floating = [
        t for t in all_terms
        if not bridge_map.get(t) and t != UPPER_TERM
    ]
    if floating:
        print(f"  WARNING: {len(floating)} classes have no UBERON parent after "
              f"bridging; they will be attached directly to owl:Thing.")
        for t in floating[:5]:
            print(f"    {t}")

    dst = Graph()
    onto_uri = URIRef(
        "http://www.acupunctureresearch.org/tara/ontology/imported/tara-uberon-import.owl"
    )
    dst.add((onto_uri, RDF.type, OWL_NS.Ontology))
    dst.add((onto_uri, RDFS.comment, Literal(
        "Imported UBERON terms for the TARA Acupoints Ontology. "
        "Generated by import_uberon_terms.py. "
        "Hierarchy up to UBERON:0001062 (anatomical entity). "
        "CL, GO, NCBITaxon, and PATO classes excluded. "
        "OWL axioms: named-class subClassOf + BFO:0000050 (part_of) restrictions only."
    )))

    print("  Copying class axioms ...")
    for i, cls_uri in enumerate(sorted(all_terms)):
        copy_class_to_graph(src, dst, cls_uri, obj_props, bridge_map.get(cls_uri, set()))
        if (i + 1) % 100 == 0:
            print(f"    {i + 1}/{len(all_terms)} done")

    print("  Copying property declarations ...")
    copy_property_decls(src, dst)

    print("  Post-processing: removing classes not under anatomical entity ...")
    removed = remove_unclassified(dst)
    print(f"  Removed {removed} unclassified class(es)")

    print("  Post-processing: removing orphaned anonymous class expressions ...")
    removed_anon = remove_orphaned_anon_classes(dst)
    print(f"  Removed {removed_anon} anonymous blank-node class expression(s)")

    print(f"  Output graph: {len(dst):,} triples")
    dst.serialize(destination=str(output_ttl), format="turtle")
    print(f"  Saved: {output_ttl}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("TARA UBERON Importer")
    print("=" * 70)

    extract_only = "--extract-only" in sys.argv

    if not extract_only:
        all_uris: Set[str] = set()

        print("\n[1] Collecting UBERON URIs from Google Sheet ...")
        for tab_name, col_name in SHEET_TABS:
            try:
                rows = fetch_sheet_csv(SHEET_ID, tab_name)
                uris = extract_uberon_uris_from_column(rows, col_name)
                print(f"    '{tab_name}' / '{col_name}': {len(uris)} URIs")
                all_uris.update(uris)
            except Exception as exc:
                print(f"  WARNING: Could not fetch tab '{tab_name}': {exc}", file=sys.stderr)

        print("\n[2] Collecting UBERON URIs from ILX TTL file ...")
        if ILX_TTL.exists():
            ttl_uris = extract_uberon_uris_from_ttl(ILX_TTL)
            print(f"    {len(ttl_uris)} URIs found in {ILX_TTL.name}")
            all_uris.update(ttl_uris)
        else:
            print(f"  WARNING: ILX TTL not found: {ILX_TTL}", file=sys.stderr)

        print(f"\n[3] Writing {len(all_uris)} unique URIs to {URI_LIST_FILE} ...")
        URI_LIST_FILE.write_text("\n".join(sorted(all_uris)) + "\n", encoding="utf-8")
        print(f"    Saved: {URI_LIST_FILE}")
    else:
        print(f"\n[--extract-only] Using existing {URI_LIST_FILE}")

    print("\n[4] Extracting UBERON terms with rdflib ...")
    extract_uberon(URI_LIST_FILE, OUTPUT_TTL)

    print("\n" + "=" * 70)
    print(f"Done!  Output: {OUTPUT_TTL}")
    print("=" * 70)


if __name__ == "__main__":
    main()
