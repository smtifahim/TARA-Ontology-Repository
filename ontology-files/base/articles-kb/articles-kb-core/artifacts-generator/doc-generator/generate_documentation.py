#!/usr/bin/env python3
"""Generate Markdown documentation for tara-articles-kb-core.ttl.

Parses the ttl directly with rdflib (no manifest step) and produces:
  1. Core Classes  - the owl:Class hierarchy defined in the file, plus any
     custom rdfs:Datatype used as a property range.
  2. Metadata Property Hierarchy - the full tara-kb:hasTARAArticlesMetadata
     subPropertyOf tree, with domain/range per property. Other annotation
     properties (dcterms:*, obo:*, tara-ap:*) are not part of this tree and
     are not documented here.
  3. Data Quality Notes - flags computed from the graph itself (not
     hardcoded), so this stays accurate as the ttl evolves:
       - a grouping property (dcterms:type tara-kb:grouping) that still
         carries an rdfs:range (groupings should never hold a value)
       - a non-grouping property with no rdfs:range asserted

Usage:
    python3 generate_documentation.py
    python3 generate_documentation.py --ttl path/to/file.ttl --out path/to/output.md

Requires: rdflib (pip install rdflib)
"""

import argparse
from pathlib import Path

import rdflib
from rdflib import Namespace, RDF, RDFS, OWL
from rdflib.namespace import SKOS

TARA = Namespace("http://www.acupunctureresearch.org/tara/ontology/")
TARA_KB = Namespace("http://www.acupunctureresearch.org/tara/ontology/kb/")
DCTERMS = Namespace("http://purl.org/dc/terms/")

ROOT_PROPERTY = TARA_KB.hasTARAArticlesMetadata

DEFAULT_TTL = Path(__file__).resolve().parent.parent.parent / "tara-articles-kb-core.ttl"
DEFAULT_OUT = Path(__file__).resolve().parent / "tara-articles-kb-core-doc.md"


def label_of(g, uri):
    if uri is None:
        return None
    lbl = g.value(uri, RDFS.label)
    if lbl:
        return str(lbl)
    s = str(uri)
    return s.split("#")[-1] if "#" in s else s.rsplit("/", 1)[-1]


def qname_of(g, uri):
    try:
        return g.qname(uri)
    except Exception:
        return str(uri)


def is_grouping(g, uri):
    return any(str(t).endswith("grouping") for t in g.objects(uri, DCTERMS.type))


def format_range(g, rng):
    if rng is None:
        return "*not specified*"
    if str(rng).startswith(str(rdflib.XSD)):
        return f"`{qname_of(g, rng)}`"
    if rng == RDF.JSON:
        return "`rdf:JSON`"
    return f"`{label_of(g, rng)}`"


def format_domain(g, dom):
    return f"`{label_of(g, dom)}`" if dom is not None else "*not specified*"


# ---------------------------------------------------------------------------
# Core Classes
# ---------------------------------------------------------------------------

def collect_classes(g):
    """Return {class_uri: subclass_of_uri_or_None} for owl:Class in the TARA namespace."""
    classes = {}
    for s in g.subjects(RDF.type, OWL.Class):
        if isinstance(s, rdflib.URIRef) and str(s).startswith(str(TARA)):
            classes[s] = g.value(s, RDFS.subClassOf)
    return classes


def collect_datatypes(g):
    """Custom rdfs:Datatype definitions in the TARA namespace."""
    dtypes = {}
    for s in g.subjects(RDF.type, RDFS.Datatype):
        if isinstance(s, rdflib.URIRef) and str(s).startswith(str(TARA)):
            dtypes[s] = {
                "label": label_of(g, s),
                "qname": qname_of(g, s),
                "comment": g.value(s, RDFS.comment),
                "alt_label": g.value(s, SKOS.altLabel),
            }
    return dtypes


def domains_used_by_hierarchy(g, root):
    """Set of class URIs used as rdfs:domain by any property under root."""
    domains = set()

    def walk(uri, visited):
        if uri in visited:
            return
        visited.add(uri)
        dom = g.value(uri, RDFS.domain)
        if dom is not None:
            domains.add(dom)
        for child in g.subjects(RDFS.subPropertyOf, uri):
            if str(child).startswith(str(TARA_KB)):
                walk(child, visited)

    walk(root, set())
    return domains


def render_classes_section(g):
    classes = collect_classes(g)
    datatypes = collect_datatypes(g)
    used_as_domain = domains_used_by_hierarchy(g, ROOT_PROPERTY)

    # group by root (top-level ancestor with no subClassOf, or subClassOf outside this set)
    children_of = {}
    roots = []
    for cls, parent in classes.items():
        if parent in classes:
            children_of.setdefault(parent, []).append(cls)
        else:
            roots.append(cls)

    lines = ["## Core Classes", ""]
    lines.append(
        "Classes defined in `tara-articles-kb-core.ttl`. Classes marked **(domain)** are used as "
        "`rdfs:domain` by at least one property under `tara-kb:hasTARAArticlesMetadata`; classes "
        "marked *(range only)* are referenced only as an `rdfs:range` target."
    )
    lines.append("")

    def render(cls, depth, out):
        lbl = label_of(g, cls)
        qn = qname_of(g, cls)
        desc = g.value(cls, DCTERMS.description)
        tag = ""
        if cls in used_as_domain:
            tag = " **(domain)**"
        elif not children_of.get(cls):
            tag = " *(range only)*"
        indent = "  " * depth
        out.append(f"{indent}- **{lbl}** — `{qn}`{tag}")
        if desc:
            first_sentence = str(desc).split(". ")[0].strip().rstrip(".") + "."
            out.append(f"{indent}  {first_sentence}")
        for child in sorted(children_of.get(cls, []), key=lambda c: label_of(g, c)):
            render(child, depth + 1, out)

    tree_lines = []
    for r in sorted(roots, key=lambda c: label_of(g, c)):
        render(r, 0, tree_lines)
    lines.extend(tree_lines)

    if datatypes:
        lines.append("")
        lines.append("**Custom datatype(s):**")
        for uri, info in datatypes.items():
            lines.append(
                f"- `{info['qname']}` (\"{info['label']}\") — "
                f"{info['comment'] if info['comment'] else 'no rdfs:comment provided'}"
            )

    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Property hierarchy
# ---------------------------------------------------------------------------

def build_children_map(g):
    children = {}
    for s, _, o in g.triples((None, RDFS.subPropertyOf, None)):
        if str(s).startswith(str(TARA_KB)):
            children.setdefault(o, []).append(s)
    return children


def render_property_tree(g, children):
    lines = ["## Metadata Property Hierarchy", ""]
    lines.append(
        "Full hierarchy of `tara-kb:hasTARAArticlesMetadata` and its `rdfs:subPropertyOf` "
        "descendants. A property tagged *(grouping — organizational only)* carries "
        "`dcterms:type tara-kb:grouping` and never holds an extracted value itself. "
        "`Domain`/`Range` of *not specified* means the property has no `rdfs:domain`/"
        "`rdfs:range` asserted in the file."
    )
    lines.append("")

    def walk(uri, depth, visited, out):
        if uri in visited:
            return
        visited.add(uri)
        lbl = label_of(g, uri)
        qn = qname_of(g, uri)
        grouping = is_grouping(g, uri)
        dom = format_domain(g, g.value(uri, RDFS.domain))
        rng = format_range(g, g.value(uri, RDFS.range))
        tag = " *(grouping — organizational only)*" if grouping else ""
        indent = "  " * depth
        out.append(f"{indent}- **{lbl}** — `{qn}`{tag} — Domain: {dom} · Range: {rng}")
        for child in sorted(children.get(uri, []), key=lambda c: label_of(g, c)):
            walk(child, depth + 1, visited, out)

    tree_lines = []
    walk(ROOT_PROPERTY, 0, set(), tree_lines)
    lines.extend(tree_lines)
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Data quality notes (computed, not hardcoded)
# ---------------------------------------------------------------------------

def render_notes_section(g, children):
    notes = []

    def walk(uri, visited):
        if uri in visited:
            return
        visited.add(uri)
        grouping = is_grouping(g, uri)
        has_range = g.value(uri, RDFS.range) is not None
        lbl = label_of(g, uri)
        qn = qname_of(g, uri)
        if grouping and has_range:
            notes.append(
                f"- `{qn}` (\"{lbl}\") is a grouping property but still carries an `rdfs:range` — "
                "grouping properties should not have a range, since they never hold a value directly."
            )
        if not grouping and not has_range:
            notes.append(
                f"- `{qn}` (\"{lbl}\") holds a value (not a grouping property) but has no `rdfs:range` asserted."
            )
        for child in sorted(children.get(uri, []), key=lambda c: label_of(g, c)):
            walk(child, visited)

    walk(ROOT_PROPERTY, set())

    if not notes:
        return []

    lines = ["## Data Quality Notes", "", "Computed from the current file — re-run this script after edits to refresh:", ""]
    lines.extend(notes)
    lines.append("")
    return lines


# ---------------------------------------------------------------------------

def generate(ttl_path: Path) -> str:
    g = rdflib.Graph()
    g.parse(str(ttl_path), format="turtle")

    lines = [
        "# TARA Articles KB: Core Ontology Documentation",
        "",
        f"Auto-generated from [`{ttl_path.name}`](../../{ttl_path.name}) by "
        "`artifacts-generator/doc-generator/generate_documentation.py`. Do not hand-edit — re-run the script instead.",
        "",
    ]
    lines.extend(render_classes_section(g))
    children = build_children_map(g)
    lines.extend(render_property_tree(g, children))
    lines.extend(render_notes_section(g, children))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ttl", type=Path, default=DEFAULT_TTL, help="Path to tara-articles-kb-core.ttl")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Path to write the generated Markdown")
    args = parser.parse_args()

    content = generate(args.ttl)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(content, encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
