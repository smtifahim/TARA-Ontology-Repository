"""
import_mondo_hp_terms.py

Collects MONDO and HP URIs from:
  downstream/data-core/kb_generator/kb_terms_mapping/conditions_mapping/
  conditions_mapped_sheets/Disease-Conditions-112625.csv
  (column: MONDO-OR-HP-Term-URI, values often comma-separated)

Downloads the full MONDO and HP ontologies (OWL), converts each to TTL with
ROBOT, zips and removes the large source OWL files, then extracts matching
classes from mondo.ttl / hp.ttl using rdflib with these rules:
  - Hierarchy walks up rdfs:subClassOf chains to MONDO:0000001 (disease or
    disorder) and HP:0000001 (All), one ceiling per source ontology
  - CL_, GO_, NCBITaxon_, PATO_, RO_, and CHEBI_ classes are excluded from
    the output (but walked through to find MONDO/HP ancestors, so no class
    is left bare)
  - No MONDO/HP disease/phenotype class above either ceiling term is included
  - Annotation properties: all copied as-is (same skip-list conventions as
    import_uberon_terms.py); every IAO_ term referenced anywhere in the
    output (as predicate or value) additionally gets its rdfs:label backfilled
  - OWL axioms kept: named-class subClassOf plus restrictions on the
    following object properties only:
      * disease has feature  (RO:0004029) and its subproperty
        mondo:disease_has_major_feature
      * disease has location (RO:0004026) and its subproperty RO:0004027
    The rdfs:subPropertyOf relation between each pair above is preserved.
    A restriction is dropped only if one of its fillers falls under an
    excluded prefix above (e.g. CHEBI_).
  - MONDO:0000001's own ancestor chain is walked (named subClassOf only) up
    to BFO:0000001 (entity); each BFO ancestor is declared with rdfs:label
    and rdfs:subClassOf only (no other annotations).
  - Every UBERON class used as a disease-has-location filler is declared
    (rdfs:label + rdfs:subClassOf only) with its own ancestor chain walked
    up to BFO:0000001 as well, so no UBERON class is left unclassified.
  - Post-processing: HP:0000001 (All) is grafted under BFO:0000001 (entity)
    with an explicit rdfs:subClassOf edge, since HP's root has no native
    parent in the source ontology.

Requirements: pip install requests rdflib; ROBOT on PATH (https://robot.obolibrary.org/)

Author: Fahim Imam
Version: 1.1
"""

import csv
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Dict, List, Set, Tuple

import requests
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib import RDF, RDFS, OWL as OWL_URI

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[4]

TTL_DIR = REPO_ROOT / "ontology-files" / "base" / "imported-terms" / "imported-ttl-files"
OUTPUT_TTL = TTL_DIR / "imported-tara-mondo-hp-terms.ttl"

# Local working directories (all relative to this script)
OWL_DIR = SCRIPT_DIR / "downloaded-owl-files"
GENERATED_TTL_DIR = SCRIPT_DIR / "generated-ttl-files"
SEED_URIS_DIR = SCRIPT_DIR / "seed-uris"

for _dir in (TTL_DIR, OWL_DIR, GENERATED_TTL_DIR, SEED_URIS_DIR):
    os.makedirs(_dir, exist_ok=True)

MONDO_URI_LIST_FILE = SEED_URIS_DIR / "tara-mondo-uris.txt"
HP_URI_LIST_FILE = SEED_URIS_DIR / "tara-hp-uris.txt"

MONDO_OWL = OWL_DIR / "mondo.owl"
MONDO_TTL = GENERATED_TTL_DIR / "mondo.ttl"
MONDO_OWL_URL = "https://purl.obolibrary.org/obo/mondo.owl"

HP_OWL = OWL_DIR / "hp.owl"
HP_TTL = GENERATED_TTL_DIR / "hp.ttl"
HP_OWL_URL = "https://purl.obolibrary.org/obo/hp.owl"

# ---------------------------------------------------------------------------
# Source CSV (seed URIs)
# ---------------------------------------------------------------------------
CONDITIONS_CSV = (
    REPO_ROOT / "downstream" / "data-core" / "kb_generator" / "kb_terms_mapping"
    / "conditions_mapping" / "conditions_mapped_sheets" / "Disease-Conditions-112625.csv"
)
URI_COLUMN = "MONDO-OR-HP-Term-URI"

# ---------------------------------------------------------------------------
# Namespace prefixes
# ---------------------------------------------------------------------------
MONDO_PREFIX = "http://purl.obolibrary.org/obo/MONDO_"
HP_PREFIX = "http://purl.obolibrary.org/obo/HP_"
UBERON_PREFIX = "http://purl.obolibrary.org/obo/UBERON_"
BFO_PREFIX = "http://purl.obolibrary.org/obo/BFO_"
IAO_PREFIX = "http://purl.obolibrary.org/obo/IAO_"
OBOINOWL_PREFIX = "http://www.geneontology.org/formats/oboInOwl#"
MONDO_HASH_PREFIX = "http://purl.obolibrary.org/obo/mondo#"
MONDO_RE = re.compile(r'http://purl\.obolibrary\.org/obo/MONDO_\d+')
HP_RE = re.compile(r'http://purl\.obolibrary\.org/obo/HP_\d+')

# ---------------------------------------------------------------------------
# Ontology constants
# ---------------------------------------------------------------------------
MONDO_ROOT = URIRef("http://purl.obolibrary.org/obo/MONDO_0000001")  # disease or disorder
HP_ROOT = URIRef("http://purl.obolibrary.org/obo/HP_0000001")        # All
BFO_ENTITY = URIRef("http://purl.obolibrary.org/obo/BFO_0000001")    # entity
UPPER_TERMS: Set[URIRef] = {MONDO_ROOT, HP_ROOT}

# Roots used when checking which classes survive the final unclassified-class
# pruning pass. Wider than UPPER_TERMS because it must also keep the BFO
# ancestor chain above MONDO:0000001 and the UBERON/BFO stub hierarchy above
# disease-has-location restriction fillers (see collect_stub_ancestors).
PRUNE_ROOTS: Set[URIRef] = UPPER_TERMS | {BFO_ENTITY}

# SubClassOf restrictions using these object properties are kept
KEEP_OBJECT_PROPS: Set[URIRef] = {
    URIRef("http://purl.obolibrary.org/obo/RO_0004029"),                       # disease has feature
    URIRef("http://purl.obolibrary.org/obo/mondo#disease_has_major_feature"),  # subproperty
    URIRef("http://purl.obolibrary.org/obo/RO_0004026"),                       # disease has location
    URIRef("http://purl.obolibrary.org/obo/RO_0004027"),                       # subproperty
}

# Classes whose URIs start with these prefixes are excluded from the output
# (walked through for bridging, and disallowed as restriction fillers, but
# never included as classes themselves)
EXCLUDE_PREFIXES: Tuple[str, ...] = (
    "http://purl.obolibrary.org/obo/CL_",
    "http://purl.obolibrary.org/obo/GO_",
    "http://purl.obolibrary.org/obo/NCBITaxon_",
    "http://purl.obolibrary.org/obo/PATO_",
    "http://purl.obolibrary.org/obo/RO_",
    "http://purl.obolibrary.org/obo/CHEBI_",
)

# Annotation properties to suppress entirely (not copied to output)
# — same conventions as import_uberon_terms.py
SKIP_ANNOTATION_PROPS: Set[URIRef] = {
    URIRef("http://www.geneontology.org/formats/oboInOwl#inSubset"),
    URIRef("http://www.geneontology.org/formats/oboInOwl#id"),
    URIRef("http://purl.obolibrary.org/obo/OMO_0002000"),
    URIRef("http://purl.obolibrary.org/obo/RO_0002175"),
    URIRef("http://purl.obolibrary.org/obo/RO_0002171"),
    URIRef("http://purl.obolibrary.org/obo/IAO_0000233"),
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
    return str(uri).startswith(EXCLUDE_PREFIXES)


def _is_skipped_annotation(uri: URIRef) -> bool:
    """True if this annotation property should be suppressed from the output."""
    return uri in SKIP_ANNOTATION_PROPS or str(uri).startswith(SKIP_ANNOT_PREFIXES)


def _is_accepted(uri: URIRef) -> bool:
    s = str(uri)
    return s.startswith(MONDO_PREFIX) or s.startswith(HP_PREFIX)

# ---------------------------------------------------------------------------
# CSV seed-URI extraction
# ---------------------------------------------------------------------------

def extract_seed_uris_from_csv(csv_path: Path, column: str) -> Tuple[Set[str], Set[str]]:
    mondo_uris: Set[str] = set()
    hp_uris: Set[str] = set()
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if column not in (reader.fieldnames or []):
            raise ValueError(
                f"Column '{column}' not found in {_display_path(csv_path)}.\n"
                f"Available columns: {reader.fieldnames}"
            )
        for row in reader:
            cell = row.get(column, "") or ""
            mondo_uris.update(MONDO_RE.findall(cell))
            hp_uris.update(HP_RE.findall(cell))
    return mondo_uris, hp_uris

# ---------------------------------------------------------------------------
# MONDO / HP download + ROBOT conversion
# ---------------------------------------------------------------------------

def _display_path(path) -> str:
    """Renders a path relative to the current working directory for terminal output."""
    try:
        return os.path.relpath(str(path))
    except ValueError:
        # e.g. paths on different drives on Windows; fall back to the given path
        return str(path)


def download_file(url: str, dest: Path) -> None:
    print(f"  Downloading {url} ...")
    with requests.get(url, stream=True, timeout=600) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
    size_mb = dest.stat().st_size / (1024 * 1024)
    print(f"  Saved {_display_path(dest)} ({size_mb:.1f} MB)")


def convert_owl_to_ttl(owl_path: Path, ttl_path: Path) -> None:
    print(f"  Converting {_display_path(owl_path)} -> {_display_path(ttl_path)} via ROBOT ...")
    cmd = [
        "robot", "convert",
        "--add-prefix", f"MONDO: {MONDO_PREFIX}",
        "--add-prefix", f"HP: {HP_PREFIX}",
        "--input", str(owl_path),
        "--format", "ttl",
        "--output", str(ttl_path),
    ]
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        print(
            "  ERROR: 'robot' command not found on PATH.\n"
            "  Install ROBOT: https://robot.obolibrary.org/",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"  Saved {_display_path(ttl_path)}")


def zip_and_remove(path: Path) -> None:
    """Compresses path into path.zip (deflated) and deletes the original."""
    zip_path = path.with_suffix(path.suffix + ".zip")
    print(f"  Compressing {_display_path(path)} -> {_display_path(zip_path)} ...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(path, arcname=path.name)
    path.unlink()
    print(f"  Removed {_display_path(path)} (kept {_display_path(zip_path)})")


def unzip_file(zip_path: Path, dest_path: Path) -> None:
    """Extracts dest_path.name from zip_path into dest_path.parent."""
    print(f"  Unzipping {_display_path(zip_path)} -> {_display_path(dest_path)} ...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extract(dest_path.name, path=str(dest_path.parent))
    print(f"  Restored {_display_path(dest_path)}")


def ensure_ontology_ttl(name: str, url: str, owl_path: Path, ttl_path: Path) -> Path:
    if ttl_path.exists():
        print(f"  Using existing {_display_path(ttl_path)} ({ttl_path.stat().st_size // (1024*1024)} MB)")
        return ttl_path

    ttl_zip_path = ttl_path.with_suffix(ttl_path.suffix + ".zip")
    if ttl_zip_path.exists():
        unzip_file(ttl_zip_path, ttl_path)
        return ttl_path

    if not owl_path.exists():
        download_file(url, owl_path)
    else:
        print(f"  Using existing {_display_path(owl_path)} ({owl_path.stat().st_size // (1024*1024)} MB)")
    convert_owl_to_ttl(owl_path, ttl_path)
    zip_and_remove(owl_path)
    return ttl_path

# ---------------------------------------------------------------------------
# rdflib extraction helpers
# ---------------------------------------------------------------------------

def _copy_bnode_subtree(src: Graph, dst: Graph, node: BNode, visited=None):
    if visited is None:
        visited = set()
    if node in visited:
        return
    if (node, RDF.type, OWL_NS.Restriction) in src:
        disallowed = all(
            isinstance(prop, URIRef) and prop not in KEEP_OBJECT_PROPS
            for prop in src.objects(node, OWL_NS.onProperty)
        )
        if disallowed:
            return
    visited.add(node)
    for p, o in src.predicate_objects(node):
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
    for pred in (OWL_NS.someValuesFrom, OWL_NS.allValuesFrom, OWL_NS.hasValue, OWL_NS.onClass):
        for obj in src.objects(bn, pred):
            if isinstance(obj, URIRef):
                fillers.add(obj)
    return fillers


def _walk_through_excluded_to_accepted(src: Graph, start: URIRef, all_terms: Set[URIRef]) -> Set[URIRef]:
    """
    Starting from an excluded (CL/GO/NCBITaxon/PATO/RO/CHEBI) class, walk its
    rdfs:subClassOf chain to find MONDO/HP ancestors that are in all_terms.
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
                elif _is_excluded(parent) or not _is_accepted(parent):
                    queue.append(parent)
    return result

# ---------------------------------------------------------------------------
# Step 1: collect all MONDO/HP terms to extract
# ---------------------------------------------------------------------------

def collect_terms_to_extract(src: Graph, seed_uris: Set[str]) -> Set[URIRef]:
    """
    BFS from seed terms, walking rdfs:subClassOf upward.
    - Adds only MONDO/HP classes (not CL/GO/NCBITaxon/PATO/RO/CHEBI) to the result.
    - Walks THROUGH excluded classes so their MONDO/HP ancestors are captured.
    - Stops at either ceiling term (MONDO:0000001 / HP:0000001).
    - Also enqueues MONDO/HP filler classes of kept disease-feature /
      disease-location restrictions.
    """
    queue: List[URIRef] = [URIRef(u) for u in seed_uris]
    visited: Set[URIRef] = set()
    result: Set[URIRef] = set()

    while queue:
        term = queue.pop()
        if term in visited:
            continue
        visited.add(term)

        if _is_accepted(term):
            result.add(term)
            if term in UPPER_TERMS:
                continue

        for parent in src.objects(term, RDFS.subClassOf):
            if isinstance(parent, URIRef) and parent not in visited:
                queue.append(parent)

        for sc in src.objects(term, RDFS.subClassOf):
            if isinstance(sc, BNode) and _is_allowed_restriction(src, sc):
                for filler in _restriction_fillers(src, sc):
                    if _is_accepted(filler) and filler not in visited:
                        queue.append(filler)

    return result

# ---------------------------------------------------------------------------
# Step 2: build bridge map (MONDO/HP parent for each class, bridging excluded)
# ---------------------------------------------------------------------------

def build_bridge_map(src: Graph, all_terms: Set[URIRef]) -> Dict[URIRef, Set[URIRef]]:
    bridge_map: Dict[URIRef, Set[URIRef]] = {}
    for term in all_terms:
        parents: Set[URIRef] = set()
        for parent in src.objects(term, RDFS.subClassOf):
            if isinstance(parent, URIRef):
                if parent in all_terms:
                    parents.add(parent)
                elif _is_excluded(parent):
                    for accepted_anc in _walk_through_excluded_to_accepted(src, parent, all_terms):
                        parents.add(accepted_anc)
        bridge_map[term] = parents
    return bridge_map

# ---------------------------------------------------------------------------
# Step 3: copy classes into output graph
# ---------------------------------------------------------------------------

def copy_class_to_graph(src: Graph, dst: Graph, cls_uri: URIRef,
                        obj_props: Set[URIRef], effective_parents: Set[URIRef]):
    """
    Copy one class into dst:
      - owl:Class declaration
      - Effective subClassOf parents (already bridged)
      - All annotation property assertions
      - SubClassOf blank-node restrictions for KEEP_OBJECT_PROPS (only if no
        filler falls under an excluded prefix)
    Bare object-property assertions are skipped.
    """
    dst.add((cls_uri, RDF.type, OWL_NS.Class))

    for parent in effective_parents:
        dst.add((cls_uri, RDFS.subClassOf, parent))

    for p, o in src.predicate_objects(cls_uri):
        if p == RDF.type:
            continue

        elif p == OWL_URI.disjointWith or p == OWL_URI.equivalentClass:
            continue

        elif p == RDFS.subClassOf:
            if isinstance(o, BNode):
                if _is_allowed_restriction(src, o):
                    fillers = _restriction_fillers(src, o)
                    if not fillers:
                        continue
                    if any(_is_excluded(f) for f in fillers):
                        continue  # excluded-namespace filler — skip
                    dst.add((cls_uri, RDFS.subClassOf, o))
                    _copy_bnode_subtree(src, dst, o)
            # Named subClassOf handled above via effective_parents — skip here

        elif isinstance(p, URIRef) and (p in obj_props or p in SKIP_OBJECT_PROPS):
            continue  # bare object-property assertion — skip

        elif isinstance(p, URIRef) and _is_skipped_annotation(p):
            continue  # suppressed annotation property — skip

        else:
            if isinstance(o, URIRef) and _is_excluded(o):
                continue  # reference to excluded class — skip
            dst.add((cls_uri, p, o))
            if isinstance(o, BNode):
                _copy_bnode_subtree(src, dst, o)


def copy_property_decls(src: Graph, dst: Graph):
    used_preds: Set[URIRef] = {
        p for p in dst.predicates()
        if isinstance(p, URIRef) and p not in _STRUCTURAL_PREDS and not _is_skipped_annotation(p)
    }
    for pred in used_preds:
        if (pred, RDF.type, OWL_NS.AnnotationProperty) in src:
            for p, o in src.predicate_objects(pred):
                if _is_skipped_annotation(p):
                    continue
                dst.add((pred, p, o))
                if isinstance(o, BNode):
                    _copy_bnode_subtree(src, dst, o)

    for prop in KEEP_OBJECT_PROPS:
        dst.add((prop, RDF.type, OWL_NS.ObjectProperty))
        for label in src.objects(prop, RDFS.label):
            dst.add((prop, RDFS.label, label))
        # Preserve the subPropertyOf hierarchy among the 4 kept properties
        # only (e.g. mondo:disease_has_major_feature -> RO:0004029,
        # RO:0004027 -> RO:0004026); drop any external superproperty.
        for super_prop in src.objects(prop, RDFS.subPropertyOf):
            if super_prop in KEEP_OBJECT_PROPS:
                dst.add((prop, RDFS.subPropertyOf, super_prop))

# ---------------------------------------------------------------------------
# Step 4 (post-processing): remove classes not reachable from either ceiling
# ---------------------------------------------------------------------------

def remove_unclassified(dst: Graph) -> int:
    """
    Remove any owl:Class in dst that has no subClassOf path leading up to
    one of PRUNE_ROOTS (MONDO:0000001, HP:0000001, or BFO:0000001). Iterates
    to fixpoint, and also removes SubClassOf restrictions whose filler is a
    removed class plus any blank-node triples orphaned by those removals.
    """
    total_removed = 0

    while True:
        classes: Set[URIRef] = {
            s for s, p, o in dst.triples((None, RDF.type, OWL_NS.Class))
            if isinstance(s, URIRef)
        }

        parent_map: Dict[URIRef, Set[URIRef]] = {c: set() for c in classes}
        for c in classes:
            for parent in dst.objects(c, RDFS.subClassOf):
                if isinstance(parent, URIRef) and parent in classes:
                    parent_map[c].add(parent)

        connected: Set[URIRef] = set()
        queue: List[URIRef] = list(PRUNE_ROOTS)
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
            break

        # Find restriction blank nodes whose filler is about to be removed,
        # using the graph as it stands BEFORE any triples are stripped this
        # pass (stripping a to-be-removed class's triples first would delete
        # the very someValuesFrom/etc. triple this filler check depends on,
        # leaving an empty, dangling owl:Restriction node behind).
        restrictions_to_orphan: List[Tuple[URIRef, BNode]] = []
        for subj in classes:
            for sc in dst.objects(subj, RDFS.subClassOf):
                if not isinstance(sc, BNode):
                    continue
                if (sc, RDF.type, OWL_NS.Restriction) not in dst:
                    continue
                fillers = _restriction_fillers(dst, sc)
                if fillers and any(f in to_remove for f in fillers):
                    restrictions_to_orphan.append((subj, sc))

        for subj, sc in restrictions_to_orphan:
            dst.remove((subj, RDFS.subClassOf, sc))
            for p, o in list(dst.predicate_objects(sc)):
                dst.remove((sc, p, o))

        for c in to_remove:
            for p, o in list(dst.predicate_objects(c)):
                dst.remove((c, p, o))
            for s, p in list(dst.subject_predicates(c)):
                dst.remove((s, p, c))

        total_removed += len(to_remove)

    return total_removed


def remove_orphaned_anon_classes(dst: Graph) -> int:
    """
    Remove blank-node class expressions not directly referenced by any named
    class via rdfs:subClassOf (same as import_uberon_terms.py).
    """
    valid_bnodes: Set[BNode] = set()
    for s, p, o in dst.triples((None, RDFS.subClassOf, None)):
        if isinstance(s, URIRef) and isinstance(o, BNode):
            valid_bnodes.add(o)

    orphaned: Set[BNode] = {
        s for s, p, o in dst.triples((None, RDF.type, OWL_NS.Class))
        if isinstance(s, BNode) and s not in valid_bnodes
    }

    count = 0
    for bn in orphaned:
        for s, p in list(dst.subject_predicates(bn)):
            dst.remove((s, p, bn))
        for p, o in list(dst.predicate_objects(bn)):
            dst.remove((bn, p, o))
        count += 1

    return count

# ---------------------------------------------------------------------------
# Stub ancestor classes (BFO chain above MONDO:0000001, and the UBERON/BFO
# hierarchy above every disease-has-location restriction filler)
# ---------------------------------------------------------------------------

def collect_stub_ancestors(src: Graph, start: URIRef, ceiling: URIRef,
                           allowed_prefixes: Tuple[str, ...]) -> Tuple[Set[URIRef], Set[Tuple[URIRef, URIRef]]]:
    """
    Walks named (URIRef) rdfs:subClassOf parents from start upward, following
    only classes whose URI starts with one of allowed_prefixes, stopping at
    ceiling. Restriction blank nodes are never followed — this is a minimal
    "hierarchy skeleton" walk, not a full class-content copy.

    Returns (classes, edges):
      classes: start plus every ancestor class visited (candidates for a
        minimal owl:Class + rdfs:label stub declaration)
      edges: (child, parent) pairs to declare as rdfs:subClassOf
    """
    classes: Set[URIRef] = {start}
    edges: Set[Tuple[URIRef, URIRef]] = set()
    visited: Set[URIRef] = {start}
    queue: List[URIRef] = [start]

    while queue:
        term = queue.pop()
        if term == ceiling:
            continue
        for parent in src.objects(term, RDFS.subClassOf):
            if not isinstance(parent, URIRef) or not str(parent).startswith(allowed_prefixes):
                continue
            edges.add((term, parent))
            classes.add(parent)
            if parent not in visited:
                visited.add(parent)
                queue.append(parent)

    return classes, edges


def add_stub_classes(src: Graph, dst: Graph, classes: Set[URIRef], edges: Set[Tuple[URIRef, URIRef]]) -> None:
    """Declares minimal classes (rdf:type + rdfs:label only) plus rdfs:subClassOf edges."""
    for cls in classes:
        dst.add((cls, RDF.type, OWL_NS.Class))
        for label in src.objects(cls, RDFS.label):
            dst.add((cls, RDFS.label, label))
    for child, parent in edges:
        dst.add((child, RDFS.subClassOf, parent))


def find_restriction_filler_uris(dst: Graph, prefix: str) -> Set[URIRef]:
    """Finds every URI matching prefix used as a filler of any owl:Restriction currently in dst."""
    fillers: Set[URIRef] = set()
    for bn in dst.subjects(RDF.type, OWL_NS.Restriction):
        for pred in (OWL_NS.someValuesFrom, OWL_NS.allValuesFrom, OWL_NS.hasValue, OWL_NS.onClass):
            for obj in dst.objects(bn, pred):
                if isinstance(obj, URIRef) and str(obj).startswith(prefix):
                    fillers.add(obj)
    return fillers


def add_iao_labels(src: Graph, dst: Graph) -> int:
    """
    Ensures every IAO_ URI mentioned anywhere in dst (as subject, predicate,
    or object — including IAO properties used only in another IAO property's
    own metadata, e.g. IAO:0000115's own IAO:0000116 editor note) has its
    rdfs:label copied over from src.
    """
    iao_uris: Set[URIRef] = set()
    for s, p, o in dst:
        for term in (s, p, o):
            if isinstance(term, URIRef) and str(term).startswith(IAO_PREFIX):
                iao_uris.add(term)

    count = 0
    for uri in iao_uris:
        for label in src.objects(uri, RDFS.label):
            if (uri, RDFS.label, label) not in dst:
                dst.add((uri, RDFS.label, label))
                count += 1
    return count

# ---------------------------------------------------------------------------
# Top-level extraction
# ---------------------------------------------------------------------------

def extract_mondo_hp(mondo_ttl_path: Path, hp_ttl_path: Path,
                     mondo_uri_file: Path, hp_uri_file: Path, output_ttl: Path):
    mondo_seeds: Set[str] = {
        line.strip() for line in mondo_uri_file.read_text().splitlines()
        if line.strip().startswith(MONDO_PREFIX)
    }
    hp_seeds: Set[str] = {
        line.strip() for line in hp_uri_file.read_text().splitlines()
        if line.strip().startswith(HP_PREFIX)
    }
    seed_uris = mondo_seeds | hp_seeds
    print(f"  Seed terms: {len(mondo_seeds)} MONDO, {len(hp_seeds)} HP")

    src = Graph()
    print(f"  Parsing {_display_path(mondo_ttl_path)} ...")
    src.parse(str(mondo_ttl_path), format="turtle")
    print(f"  Parsing {_display_path(hp_ttl_path)} ...")
    src.parse(str(hp_ttl_path), format="turtle")
    print(f"  Loaded {len(src):,} triples total")

    obj_props: Set[URIRef] = set(src.subjects(RDF.type, OWL_NS.ObjectProperty))

    print("  Collecting MONDO/HP classes to extract ...")
    all_terms = collect_terms_to_extract(src, seed_uris)
    all_terms = {t for t in all_terms if (t, RDF.type, OWL_NS.Class) in src}
    print(f"  {len(all_terms)} classes selected")

    print("  Building bridge map (resolving excluded-class parents) ...")
    bridge_map = build_bridge_map(src, all_terms)

    floating = [t for t in all_terms if not bridge_map.get(t) and t not in UPPER_TERMS]
    if floating:
        print(f"  WARNING: {len(floating)} classes have no MONDO/HP parent after "
              f"bridging; they will be attached directly to owl:Thing.")
        for t in floating[:5]:
            print(f"    {t}")

    dst = Graph()
    dst.bind("MONDO", Namespace(MONDO_PREFIX))
    dst.bind("HP", Namespace(HP_PREFIX))
    dst.bind("UBERON", Namespace(UBERON_PREFIX))
    dst.bind("IAO", Namespace(IAO_PREFIX))
    dst.bind("oboInOwl", Namespace(OBOINOWL_PREFIX))
    dst.bind("mondo", Namespace(MONDO_HASH_PREFIX))

    onto_uri = URIRef(
        "http://www.acupunctureresearch.org/tara/ontology/imported/tara-mondo-hp-import.owl"
    )
    dst.add((onto_uri, RDF.type, OWL_NS.Ontology))
    dst.add((onto_uri, RDFS.comment, Literal(
        "Imported MONDO and HP terms for the TARA Acupoints Ontology. "
        "Generated by import_mondo_hp_terms.py. "
        "Seed terms sourced from Disease-Conditions-112625.csv (MONDO-OR-HP-Term-URI column). "
        "Hierarchy up to MONDO:0000001 (disease or disorder) and HP:0000001 (All), with "
        "MONDO:0000001 further walked to BFO:0000001 (entity) and HP:0000001 grafted under "
        "BFO:0000001 as a post-processing step. "
        "CL, GO, NCBITaxon, PATO, RO, and CHEBI classes excluded. "
        "OWL axioms: named-class subClassOf plus disease-has-feature "
        "(RO:0004029 / mondo:disease_has_major_feature) and disease-has-location "
        "(RO:0004026 / RO:0004027) restrictions only, with the subPropertyOf relation "
        "between each pair preserved. UBERON disease-has-location fillers are declared "
        "with a minimal label + subClassOf hierarchy up to BFO:0000001."
    )))

    print("  Copying class axioms ...")
    for i, cls_uri in enumerate(sorted(all_terms)):
        copy_class_to_graph(src, dst, cls_uri, obj_props, bridge_map.get(cls_uri, set()))
        if (i + 1) % 500 == 0:
            print(f"    {i + 1}/{len(all_terms)} done")

    print("  Copying property declarations ...")
    copy_property_decls(src, dst)

    print("  Walking MONDO:0000001's ancestor chain up to BFO:0000001 (entity) ...")
    bfo_classes, bfo_edges = collect_stub_ancestors(src, MONDO_ROOT, BFO_ENTITY, (BFO_PREFIX,))
    bfo_classes.discard(MONDO_ROOT)  # MONDO:0000001 already has a full declaration
    add_stub_classes(src, dst, bfo_classes, bfo_edges)
    print(f"    Added {len(bfo_classes)} BFO class(es) (rdfs:label + rdfs:subClassOf only)")

    print("  Declaring UBERON disease-has-location fillers, walked up to BFO:0000001 ...")
    uberon_fillers = find_restriction_filler_uris(dst, UBERON_PREFIX)
    uberon_classes: Set[URIRef] = set()
    uberon_edges: Set[Tuple[URIRef, URIRef]] = set()
    for filler in uberon_fillers:
        classes, edges = collect_stub_ancestors(src, filler, BFO_ENTITY, (UBERON_PREFIX, BFO_PREFIX))
        uberon_classes |= classes
        uberon_edges |= edges
    add_stub_classes(src, dst, uberon_classes, uberon_edges)
    print(f"    Declared {len(uberon_classes)} UBERON/BFO class(es) for "
          f"{len(uberon_fillers)} disease-has-location filler(s) "
          f"(rdfs:label + rdfs:subClassOf only)")

    print("  Backfilling rdfs:label for every IAO: term referenced in the output ...")
    iao_labels_added = add_iao_labels(src, dst)
    print(f"    Added {iao_labels_added} IAO rdfs:label triple(s)")

    print("  Post-processing: removing classes not under MONDO/HP/BFO root ...")
    removed = remove_unclassified(dst)
    print(f"  Removed {removed} unclassified class(es)")

    print("  Post-processing: removing orphaned anonymous class expressions ...")
    removed_anon = remove_orphaned_anon_classes(dst)
    print(f"  Removed {removed_anon} anonymous blank-node class expression(s)")

    if (HP_ROOT, RDF.type, OWL_NS.Class) in dst:
        print("  Post-processing: moving HP:0000001 (All) under BFO:0000001 (entity) ...")
        dst.add((HP_ROOT, RDFS.subClassOf, BFO_ENTITY))

    print(f"  Output graph: {len(dst):,} triples")
    dst.serialize(destination=str(output_ttl), format="turtle")
    print(f"  Saved: {_display_path(output_ttl)}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("TARA MONDO/HP Importer")
    print("=" * 70)

    extract_only = "--extract-only" in sys.argv

    if not extract_only:
        print(f"\n[1] Collecting MONDO/HP URIs from {_display_path(CONDITIONS_CSV)} ...")
        mondo_uris, hp_uris = extract_seed_uris_from_csv(CONDITIONS_CSV, URI_COLUMN)
        print(f"    {len(mondo_uris)} unique MONDO URIs, {len(hp_uris)} unique HP URIs")

        print(f"\n[2] Writing MONDO URIs to {_display_path(MONDO_URI_LIST_FILE)} ...")
        MONDO_URI_LIST_FILE.write_text("\n".join(sorted(mondo_uris)) + "\n", encoding="utf-8")
        print(f"    Saved: {_display_path(MONDO_URI_LIST_FILE)}")

        print(f"\n[3] Writing HP URIs to {_display_path(HP_URI_LIST_FILE)} ...")
        HP_URI_LIST_FILE.write_text("\n".join(sorted(hp_uris)) + "\n", encoding="utf-8")
        print(f"    Saved: {_display_path(HP_URI_LIST_FILE)}")
    else:
        print(f"\n[--extract-only] Using existing {_display_path(MONDO_URI_LIST_FILE)} / "
              f"{_display_path(HP_URI_LIST_FILE)}")

    print("\n[4] Ensuring MONDO ontology is downloaded and converted to TTL ...")
    mondo_ttl_path = ensure_ontology_ttl("MONDO", MONDO_OWL_URL, MONDO_OWL, MONDO_TTL)

    print("\n[5] Ensuring HP ontology is downloaded and converted to TTL ...")
    hp_ttl_path = ensure_ontology_ttl("HP", HP_OWL_URL, HP_OWL, HP_TTL)

    print("\n[6] Extracting MONDO/HP terms with rdflib ...")
    extract_mondo_hp(mondo_ttl_path, hp_ttl_path, MONDO_URI_LIST_FILE, HP_URI_LIST_FILE, OUTPUT_TTL)

    print("\n[7] Compressing generated TTL files to save space ...")
    zip_and_remove(mondo_ttl_path)
    zip_and_remove(hp_ttl_path)

    print("\n" + "=" * 70)
    print(f"Done!  Output: {_display_path(OUTPUT_TTL)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
