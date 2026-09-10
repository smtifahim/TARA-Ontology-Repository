# Ontology header files

`ontology-header.ttl` and `kb-header.ttl` are the hand-authored front matter for
the two published TARA ontologies. Each declares **exactly one** `owl:Ontology`
at its canonical published IRI and carries the stable identity annotations:
`dc:title`, `dcterms:description`, `dc:creator`, `dc:contributor`, `dc:source`,
`dcterms:license`, `dc:date`, …

| file | canonical ontology IRI |
|---|---|
| `ontology-header.ttl` | `http://purl.org/tara/ontology/acupoints.owl` |
| `kb-header.ttl` | `http://purl.org/tara/ontology/kb/articles-kb.ttl` |

## How they are used

The header-stamping scripts
(`ontology-generator/script/ontology-generation/update_ontology_headers.py`,
`ontology-generator/script/kb-generation/update_kb_headers.py`) build each
distribution variant by:

1. taking the merged, reasoned Turtle from `ontology-files/generated/temp-files/`,
2. migrating staging IRIs (`acupunctureresearch.org` → `purl.org`),
3. capturing the `rdfs:comment`(s) from the merged source's **primary** ontology
   subject (matched by its staging IRI),
4. dropping every `owl:Ontology` declaration the merged file contains,
5. splicing in the matching file from this folder,
6. re-attaching the captured `rdfs:comment`(s), and
7. adding **only** the generated `owl:versionInfo`, `owl:versionIRI`,
   `dcterms:issued`, and `owl:priorVersion` (release numbers come from
   `ontology-generator/script/versions.py`).

## Editing rules

- Edit these files to change a released ontology's title, description, creators,
  contributors, license, or source.
- Do **not** add `owl:versionInfo`, `owl:versionIRI`, `owl:priorVersion`, or
  `dcterms:issued` here — they are generated, and the scripts reject a header
  file that contains them.
- Keep exactly one `owl:Ontology` subject, at the canonical IRI above.
- These are distribution front matter only. The hand-authored base ontologies
  (`tara-acupoints-core.ttl`, `articles-kb-core/tara-articles-kb-core.ttl`) keep
  their own separate `owl:versionInfo` for anyone loading a core file directly.
