# UBERON Importer for TARA

This directory contains the script used to extract and import UBERON terms into the TARA Acupoints Ontology.

## Script

**`import_uberon_terms.py`**

Collects UBERON URIs from multiple sources, extracts the corresponding OWL classes and their hierarchy from a local copy of UBERON, and saves the result as a Turtle file.

## Requirements

- Python 3.8+
- `requests` and `rdflib` Python packages:

```bash
pip install requests rdflib
```

- A local copy of `uberon.ttl` placed in the same directory as the script. The file can be downloaded from: `http://purl.obolibrary.org/obo/uberon.owl`

## Usage

**Full run** (collects URIs from Google Sheets and ILX TTL, then extracts):

```bash
python import_uberon_terms.py
```

**Extraction only** (skips URI collection, uses the existing `tara-uberon-uris.txt`):

```bash
python import_uberon_terms.py --extract-only
```

## Input Sources

The script collects UBERON URIs from the following sources:

1. **Google Sheet** (`1hvUcTrw-b9ly8Yn1P706px22li0vsjslukYhxkTDlA8`):

   - Tab `Meridians`, column `Associated Organ URI`
   - Tab `Acupoints-Locations`, column `Identified Locations URI`
   - Tab `Acupoints-Nerves`, column `Nerve Location URI`
   - Tab `Acupoints-Veins-Arteries`, column `Vasculature URI`
2. **ILX imported terms file**: `imported-ttl-files/imported-tara-ilx-terms.ttl`

   - Extracts all UBERON URIs used as OWL classes or as values of `isPartOf` annotation properties.

The combined unique set of URIs is written to `tara-uberon-uris.txt`.

## Extraction Rules

- The hierarchy is walked upward via `rdfs:subClassOf` chains for all collected terms.
- The upper bound of the hierarchy is `UBERON:0001062` (anatomical entity). No class above this term is included.
- Classes from `CL_`, `GO_`, `NCBITaxon_`, `PATO_`, and `RO_` are excluded from the output. Where a UBERON class has a parent in one of these excluded namespaces, the script bridges directly to the nearest UBERON ancestor instead.
- Filler classes referenced by kept object property restrictions are also included (with their own hierarchy).
- All annotation property assertions are copied for each class.
- `owl:equivalentClass` and `owl:disjointWith` axioms are discarded.
- Unclassified classes (those with no subClassOf path to `UBERON:0001062`) and orphaned anonymous class expressions are removed in a post-processing step.

## Object Property Axioms

Only `rdfs:subClassOf` restrictions using the following object properties are kept. All other object property axioms are removed.


| Property      | Label        |
| ------------- | ------------ |
| `BFO:0000050` | part of      |
| `BFO:0000051` | has part     |
| `RO:0001025`  | located in   |
| `RO:0002170`  | connected to |

Restrictions are only retained if their filler class is a UBERON term. Restrictions with fillers from excluded namespaces are dropped.

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
imported-ttl-files/imported-tara-uberon-terms.ttl
```

The file includes:

- All extracted UBERON OWL class declarations with annotations
- The class hierarchy up to `UBERON:0001062` (anatomical entity)
- Selected `rdfs:subClassOf` restrictions (part of, has part, located in, connected to)
- Declarations for the four retained object properties (type and label only)
- Declarations for all annotation properties used
