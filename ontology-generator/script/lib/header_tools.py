"""
================================================================================
Shared helpers for the TARA header-stamping scripts
================================================================================
`script/ontology-generation/update_ontology_headers.py` (acupoints) and
`script/kb-generation/update_kb_headers.py` (articles KB) build each published
distribution variant from a merged, reasoned Turtle file by:

  1. Namespace migration - rewrite every staging-domain IRI
     (www.acupunctureresearch.org/tara/ontology/) and prefix binding to the
     published PURL namespace (purl.org/tara/ontology/).

  2. Header replacement - the merged file's own ontology declaration(s) (the
     core header plus one owl:Ontology stub per merged import / bridge module)
     are discarded and replaced with the hand-authored front matter in
     ontology-files/base/headers/{ontology-header.ttl, kb-header.ttl}: the
     canonical ontology IRI, dc:title, dcterms:description, dc:creator,
     dc:contributor, dc:source, dcterms:license, ... - distribution-specific
     identity metadata only, no rdfs:comment.

  3. Comment carry-over - the rdfs:comment(s) from EVERY merged-in ontology
     declaration (the core plus every import / bridge module) are copied onto
     the canonical subject - deduplicated and sorted - so the distribution file
     documents what was merged in.

  4. Version stamping - the script adds ONLY the generated owl:versionInfo,
     owl:versionIRI, dcterms:issued, and owl:priorVersion (release numbers and
     prior-version list from script/versions.py).

  5. Header reordering - the single ontology declaration is emitted as one
     block directly under the @prefix lines at the top of the file.

The hand-authored base ontologies (tara-acupoints-core.ttl,
articles-kb-core/tara-articles-kb-core.ttl) keep their own separate
owl:versionInfo and are not affected here (except that
update_ontology_headers.py, by convention, also text-bumps
tara-acupoints-core.ttl's owl:versionInfo via bump_base_versioninfo()).

Author: Fahim Imam
================================================================================
"""

import os
import re
from datetime import datetime

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS

DCTERMS = Namespace("http://purl.org/dc/terms/")

# Staging -> published namespace (see migrate_namespaces()).
OLD_BASE = "http://www.acupunctureresearch.org/tara/ontology/"
NEW_BASE = "http://purl.org/tara/ontology/"

# Version metadata is generated per release, never authored into a header file.
_GENERATED_HEADER_PROPS = (OWL.versionInfo, OWL.versionIRI, OWL.priorVersion, DCTERMS.issued)


def migrate_namespaces(source_graph):
    """Return a copy of `source_graph` with every acupunctureresearch.org IRI
    (and prefix binding) rewritten to purl.org."""
    migrated = Graph()

    for prefix, namespace in source_graph.namespaces():
        ns_str = str(namespace)
        if ns_str.startswith(OLD_BASE):
            ns_str = ns_str.replace(OLD_BASE, NEW_BASE, 1)
        migrated.bind(prefix, URIRef(ns_str))
    migrated.bind("dcterms", DCTERMS)

    def convert(node):
        if isinstance(node, URIRef) and str(node).startswith(OLD_BASE):
            return URIRef(str(node).replace(OLD_BASE, NEW_BASE, 1))
        return node

    for s, p, o in source_graph:
        migrated.add((convert(s), convert(p), convert(o)))
    return migrated


def load_header(header_ttl, canonical_iri):
    """Parse a hand-authored header file and validate it: exactly one
    owl:Ontology subject at `canonical_iri`, no generated version properties
    (owl:versionInfo / owl:versionIRI / owl:priorVersion / dcterms:issued), and
    no rdfs:comment (those are carried from the merge sources, not authored
    here). Returns the parsed Graph."""
    if not os.path.exists(header_ttl):
        raise FileNotFoundError(f"Header file not found: {header_ttl}")
    hg = Graph().parse(header_ttl, format="turtle")

    onts = list(hg.subjects(RDF.type, OWL.Ontology))
    canon = URIRef(canonical_iri)
    if onts != [canon]:
        raise ValueError(
            f"{header_ttl} must declare exactly one owl:Ontology <{canonical_iri}>; "
            f"found {[str(o) for o in onts] or 'none'}"
        )
    for prop in _GENERATED_HEADER_PROPS:
        if (canon, prop, None) in hg:
            raise ValueError(
                f"{header_ttl}: {hg.qname(prop)} is generated per release - "
                f"remove it from the header file (see script/versions.py)"
            )
    if (canon, RDFS.comment, None) in hg:
        raise ValueError(
            f"{header_ttl}: rdfs:comment is carried from the merge sources - "
            f"remove it from the header file; use dcterms:description for the "
            f"distribution-specific summary"
        )
    return hg


def reorder_ontology_header(graph, output_path, primary_sub=None):
    """Serialise `graph` to `output_path` as Turtle with the ontology header
    hoisted into one block directly under the @prefix declarations (rdflib's
    serializer otherwise scatters it).

    When `primary_sub` is given, the header keeps ONLY that subject's triples;
    any other owl:Ontology declaration is dropped."""
    ontology_subjects = set(graph.subjects(RDF.type, OWL.Ontology))
    if not ontology_subjects:
        graph.serialize(destination=output_path, format="turtle")
        return

    keep = {primary_sub} if primary_sub is not None else ontology_subjects

    header_graph = Graph()
    body_graph = Graph()
    for prefix, namespace in graph.namespaces():
        header_graph.bind(prefix, namespace)
        body_graph.bind(prefix, namespace)

    for s, p, o in graph:
        if s in ontology_subjects:
            if s in keep:
                header_graph.add((s, p, o))
            # else: a non-primary owl:Ontology stub - drop it entirely
        else:
            body_graph.add((s, p, o))

    header_serialized = header_graph.serialize(format="turtle").splitlines()
    header_prefix_lines = [ln for ln in header_serialized if ln.startswith("@prefix")]
    header_block = "\n".join(
        ln for ln in header_serialized if not ln.startswith("@prefix")
    ).strip("\n")

    body_serialized = body_graph.serialize(format="turtle").splitlines()
    body_prefix_lines = [ln for ln in body_serialized if ln.startswith("@prefix")]
    rest_block = "\n".join(
        ln for ln in body_serialized if not ln.startswith("@prefix")
    ).strip("\n")

    # A prefix used only by the ontology header block (e.g. the bare ontology
    # IRI namespace, which the body never references) would otherwise be
    # dropped, leaving it unbound.
    prefix_lines = sorted(set(header_prefix_lines) | set(body_prefix_lines))

    final_text = "\n".join(prefix_lines) + "\n\n" + header_block + "\n\n" + rest_block + "\n"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_text)


def process_variant(input_path, output_path, *, header_ttl, canonical_iri,
                    version_info, version_iri, prior_versions=()):
    """Build one distribution variant.

    - `header_ttl`    : hand-authored ontology-files/base/headers/*.ttl to splice in.
    - `canonical_iri` : the owl:Ontology IRI that header file declares.
    - `version_info` / `version_iri` : the generated owl:versionInfo string and
                        per-variant owl:versionIRI.
    - `prior_versions`: strings stamped as owl:priorVersion (newest first).

    The rdfs:comment(s) from EVERY owl:Ontology declaration in the merged file -
    the core ontology plus one per merged import / bridge module - are carried
    onto the canonical subject (deduplicated, sorted), so the distribution file
    documents what was merged in. The header file carries no rdfs:comment.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input variant not found: {input_path}")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    print(f"  {os.path.relpath(input_path)}\n    -> {os.path.relpath(output_path)}")

    graph = migrate_namespaces(Graph().parse(input_path, format="turtle"))
    canon = URIRef(canonical_iri)

    # rdfs:comment(s) from every merged-in ontology declaration, kept for
    # re-attachment after the header swap. Deduplicated by text (keeping the
    # first literal seen, so its language tag survives) and sorted, so the
    # build is reproducible.
    by_text = {}
    for s in set(graph.subjects(RDF.type, OWL.Ontology)):
        for o in graph.objects(s, RDFS.comment):
            by_text.setdefault(str(o), o)
    merge_source_comments = [by_text[t] for t in sorted(by_text)]

    # discard every ontology declaration the merged file carries (core header
    # + one stub per merged import/bridge module)
    for ont_sub in set(graph.subjects(RDF.type, OWL.Ontology)):
        graph.remove((ont_sub, None, None))

    # splice in the hand-authored front matter
    for triple in load_header(header_ttl, canonical_iri):
        graph.add(triple)

    # carry the merge sources' comments onto the canonical subject
    for comment in merge_source_comments:
        graph.add((canon, RDFS.comment, comment))

    # generated version metadata - the only thing this script owns
    graph.add((canon, OWL.versionInfo, Literal(version_info)))
    graph.add((canon, OWL.versionIRI, URIRef(version_iri)))
    graph.add((canon, DCTERMS.issued, Literal(datetime.now().strftime("%B %d, %Y"))))
    for prior in prior_versions:
        graph.add((canon, OWL.priorVersion, Literal(prior)))

    reorder_ontology_header(graph, output_path, primary_sub=canon)


def confirm(prompt_text):
    """Console y/n prompt; True only on an explicit 'y' / 'yes'."""
    return input(f"{prompt_text} (y/n): ").strip().lower() in ("y", "yes")


def bump_base_versioninfo(path, version):
    """Replace the first `owl:versionInfo "<x>"` literal in a hand-authored
    source file with `version`, via a targeted text substitution (no RDF
    round-trip, so the file's formatting, comments, and triple order survive).
    Raises if no owl:versionInfo is present."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    updated_content, replacement_count = re.subn(
        r'(owl:versionInfo\s+")[^"]*(")',
        rf"\g<1>{version}\g<2>",
        content,
        count=1,
    )
    if replacement_count == 0:
        raise ValueError(f"No owl:versionInfo found to update in: {path}")

    with open(path, "w", encoding="utf-8") as f:
        f.write(updated_content)
    print(f'Updated owl:versionInfo to "{version}" in: {path}')
