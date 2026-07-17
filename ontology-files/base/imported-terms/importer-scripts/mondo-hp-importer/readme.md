# MONDO/HP Importer for TARA

This directory contains the script used to extract and import MONDO (disease)
and HP (phenotype) terms into the TARA Acupoints Ontology.

## Script

**`import_mondo_hp_terms.py`**

Collects MONDO and HP seed URIs from a conditions-mapping CSV, downloads the
full MONDO and HP ontologies, converts them to Turtle with ROBOT, then
extracts the corresponding OWL classes and their hierarchy using `rdflib`,
saving the result as a Turtle file.

## Requirements

- Python 3.8+
- `requests` and `rdflib` Python packages:

```bash
pip install requests rdflib
```

- [ROBOT](https://robot.obolibrary.org/) available on `PATH`. Note: recent
  ROBOT releases (v1.9+) require Java 11+; if only an older JDK is available,
  ROBOT v1.7.2 is known to work fully (including `convert`) on Java 8.

## Usage

**Full run** (collects seed URIs from the CSV, then downloads/converts/extracts):

```bash
python import_mondo_hp_terms.py
```

**Extraction only** (skips CSV URI collection, uses the existing files under `seed-uris/`):

```bash
python import_mondo_hp_terms.py --extract-only
```

All terminal output shows paths relative to the current working directory.

## Directory Layout

```
mondo-hp-importer/
  import_mondo_hp_terms.py
  seed-uris/               tara-mondo-uris.txt, tara-hp-uris.txt
  downloaded-owl-files/    mondo.owl.zip, hp.owl.zip (raw .owl deleted after conversion)
  generated-ttl-files/     mondo.ttl.zip, hp.ttl.zip (raw .ttl deleted after extraction)
```

`downloaded-owl-files/` and `generated-ttl-files/` normally hold only the
zipped archives — the large raw `.owl`/`.ttl` files are unzipped on demand
into the same folder for a run and re-zipped (then deleted) once no longer
needed, so very little disk space is used at rest between runs.

## Input Source

Seed URIs are collected from:

```
downstream/data-core/kb_generator/kb_terms_mapping/conditions_mapping/
conditions_mapped_sheets/Disease-Conditions-112625.csv
```

column `MONDO-OR-HP-Term-URI` (values are often comma-separated). Each cell
is scanned for `MONDO_` and `HP_` URIs; the unique sets are written to
`seed-uris/tara-mondo-uris.txt` and `seed-uris/tara-hp-uris.txt`.

## Download, Conversion, and Caching

For each ontology (MONDO: `https://purl.obolibrary.org/obo/mondo.owl`, HP:
`https://purl.obolibrary.org/obo/hp.owl`):

1. If `generated-ttl-files/<name>.ttl` already exists, it is used as-is.
2. Else if `generated-ttl-files/<name>.ttl.zip` exists, it is unzipped and used.
3. Else the `.owl` file is downloaded into `downloaded-owl-files/` (or reused
   if already present), converted to Turtle with `robot convert` (adding the
   `MONDO:`/`HP:` prefixes), and the `.owl` file is zipped and deleted.

After extraction finishes and the final output Turtle file has been written,
`mondo.ttl` and `hp.ttl` are zipped and deleted, leaving only the `.zip`
archives in `generated-ttl-files/` until the next run needs them.

## Extraction Rules

- The hierarchy is walked upward via `rdfs:subClassOf` chains for all seed terms.
- The upper bounds are `MONDO:0000001` (disease or disorder) and `HP:0000001`
  (All), one ceiling per source ontology.
- Classes from `CL_`, `GO_`, `NCBITaxon_`, `PATO_`, `RO_`, and `CHEBI_` are
  excluded from the output. Where a MONDO/HP class has a parent in one of
  these excluded namespaces, the script bridges directly to the nearest
  MONDO/HP ancestor instead.
- Filler classes referenced by kept object property restrictions are also
  included (with their own hierarchy), as long as the filler is not under an
  excluded prefix.
- All annotation property assertions are copied for each MONDO/HP class.
- `owl:equivalentClass` and `owl:disjointWith` axioms are discarded.
- Unclassified classes (no subClassOf path to a root — see below) and
  orphaned anonymous class expressions are removed in a post-processing step.

### BFO and UBERON hierarchy

- `MONDO:0000001`'s own ancestor chain is walked (named `subClassOf` only) up
  to `BFO:0000001` (entity). Each BFO ancestor is declared with `rdfs:label`
  and `rdfs:subClassOf` only — no other annotations.
- Every UBERON class used as a `disease has location` filler is declared the
  same minimal way (`rdfs:label` + `rdfs:subClassOf` only), with its own
  ancestor chain walked up to `BFO:0000001` as well, so no UBERON class is
  left unclassified.
- `HP:0000001` (All) has no native parent in the source ontology, so as a
  final post-processing step it is grafted directly under `BFO:0000001` with
  an explicit `rdfs:subClassOf` edge.

### IAO labels

Every `IAO_` term referenced anywhere in the output — as a predicate, or as
a value (including IAO properties used only in another IAO property's own
metadata) — has its `rdfs:label` backfilled from the source ontology.

## Object Property Axioms

Only `rdfs:subClassOf` restrictions using the following object properties are
kept. All other object property axioms are removed.

| Property                          | Label                       |
| ---------------------------------- | ---------------------------- |
| `RO:0004029`                       | disease has feature          |
| `mondo:disease_has_major_feature`  | subproperty of `RO:0004029`  |
| `RO:0004026`                       | disease has location         |
| `RO:0004027`                       | subproperty of `RO:0004026`  |

The `rdfs:subPropertyOf` relation between each pair above is preserved in
the output. Restrictions are dropped only if one of their fillers falls
under an excluded prefix (e.g. `CHEBI_`).

## Suppressed Annotation Properties

The following annotation properties and their values are removed from the output:

- `oboInOwl:inSubset`
- `oboInOwl:id`
- `OMO:0002000`
- `RO:0002175`
- `RO:0002171`
- `IAO:0000233`
- `RO:0002161`
- All `UBPROP_` annotation properties

## Output

The extracted ontology is saved to:

```
imported-ttl-files/imported-tara-mondo-hp-terms.ttl
```

The file includes:

- All extracted MONDO/HP OWL class declarations with annotations
- The class hierarchy up to `MONDO:0000001` / `HP:0000001`, further extended
  through `BFO:0000001` (entity) as described above
- UBERON classes referenced by `disease has location` restrictions, with a
  minimal label + subClassOf hierarchy up to `BFO:0000001`
- Selected `rdfs:subClassOf` restrictions (disease has feature, disease has location)
- Declarations for the four retained object properties, including their
  `rdfs:subPropertyOf` hierarchy
- Declarations for all annotation properties used, including backfilled
  `IAO:` labels
- Namespace prefixes: `MONDO:`, `HP:`, `UBERON:`, `IAO:`, `oboInOwl:`, `mondo:`
