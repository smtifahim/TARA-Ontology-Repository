# TARA Acupoints Ontology Generator

This directory contains Python scripts for automating the generation and processing of the TARA Acupoints Ontology from curated CSV files.

## Contents

1. [Pipeline Overview](#pipeline-overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Scripts](#scripts)
   - [Main Scripts](#main-scripts)
   - [Library Modules](#library-modules)
5. [Generated Output Files](#generated-output-files)
6. [Sample Execution](#sample-execution)

## Pipeline Overview

The generation pipeline takes curated CSV files as input and produces a set of merged, reasoned Turtle ontology files as output. It runs in three steps:

```
Step 1:  fetch_curated_data.py   — download latest CSV files from the TARA Google Sheet
             ↓
         ../curated-data/acupoints/   ../curated-data/kb/

Step 2:  generate_ontology.py    — transform CSV data into OWL-DL, merge with base ontology
             ↓
         ../ontology-files/generated/ttl/tara-acupoints.ttl
         ../ontology-files/generated/ttl/kb/tara-articles-kb.ttl

Step 3:  lib/hermit_reasoner.py  — compute inferred class hierarchy with HermiT (run twice)
             ↓
         ../ontology-files/generated/ttl/tara-acupoints-inferred.ttl
         ../ontology-files/generated/ttl/kb/tara-articles-kb-inferred.ttl
```

All three steps are automated by [`run_all.sh`](#run_allsh).

## Prerequisites

* Python 3.8 or higher
* Install [RDFLib 7.0.0](https://pypi.org/project/rdflib/): `pip install rdflib`
* Install [owlready2](https://pypi.org/project/owlready2/) (required for HermiT): `pip install owlready2`
* Java 8 or higher on the system PATH (required by HermiT via owlready2)
* The following input files must be present before running `generate_ontology.py`:
  * Acupoints CSV files under [`../curated-data/acupoints/`](../curated-data/acupoints/) — run `fetch_curated_data.py` to download them
  * Articles CSV file under [`../curated-data/kb/`](../curated-data/kb/)
  * Base ontology files under [`../ontology-files/base/`](../ontology-files/base/): [`tara-acupoints-upper.ttl`](../ontology-files/base/tara-acupoints-upper.ttl), [`tara-acupoints-core.ttl`](../ontology-files/base/tara-acupoints-core.ttl), [`tara-imported-terms.ttl`](../ontology-files/base/tara-imported-terms.ttl)

## Quick Start

Run the full pipeline in one step from the `ontology-generator/` directory:

```bash
./run_all.sh
```

The script resolves its own directory automatically, so it can also be invoked from any working directory:

```bash
/path/to/ontology-generator/run_all.sh
```

Pipeline output:

```
Step 1: Downloading CSV files from the TARA Google Sheet...
Step 2: Running ontology adapter to generate and merge TTL files...
Step 3a: Running HermiT on tara-acupoints.ttl...
Step 3b: Running HermiT on tara-articles-kb.ttl...
Pipeline Completed Successfully.
Generated files are under: ../ontology-files/generated/ttl/
```

The script exits immediately if any step fails.

## Scripts

### Main Scripts

These are the scripts you interact with directly.

#### generate_ontology.py

The main CSV-to-OWL transformation script. Reads the curated CSV files, transforms their contents into an integrated OWL-DL ontology, and produces a set of merged Turtle files under [`../ontology-files/generated/ttl/`](../ontology-files/generated/ttl/).

Internally uses the following library modules (under [`lib/`](lib/)):
* [`lib/convert_class_iris.py`](#convert_class_irispy) — converts textual IRI suffixes to numeric TARA IDs
* [`lib/ontology_merger.py`](#ontology_mergerpy) — merges multiple ontology files into one
* [`lib/hermit_reasoner.py`](#hermit_reasonerpy) — generates the inferred class hierarchy using HermiT

#### fetch_curated_data.py

Downloads each tab of the [Official TARA Ontology Curation Google Sheet](https://docs.google.com/spreadsheets/d/1hvUcTrw-b9ly8Yn1P706px22li0vsjslukYhxkTDlA8/) as a CSV file and saves them to the appropriate local directories:

| Tab | Output location |
|-----|----------------|
| meridians, acupoints, acupoints-category, extra-acupoints, special-points, special-points-association, acupoints-locations | [`../curated-data/acupoints/`](../curated-data/acupoints/) |
| pain-related-articles | [`../curated-data/kb/`](../curated-data/kb/) |

Run this script before `generate_ontology.py` to ensure local CSV files are up to date.

### Library Modules

These modules are called automatically by `generate_ontology.py` and `run_all.sh`. They are not normally run standalone.

#### convert_class_iris.py

Converts class IRI suffixes from the human-readable textual form used during CSV authoring (e.g., `TARA:Meridian_Acupoint`) to a stable numeric form (e.g., `TARA:TARA_0123456`) using a SHA-256 hash. The conversion is deterministic and collision-resistant.

#### ontology_merger.py

Merges two input ontology Turtle files into a single output file using RDFLib. Properly named namespace prefixes from the caller-supplied namespace dictionary are re-bound after merging to prevent RDFLib from emitting auto-generated `ns1`, `ns2`, ... prefixes for unrecognized namespaces.

#### hermit_reasoner.py

Generates an inferred version of a merged ontology using the HermiT OWL reasoner (via [owlready2](https://pypi.org/project/owlready2/)). For each class, asserted named-class superclasses are replaced by the inferred direct superclasses, matching the behaviour of Protégé's inferred hierarchy tab. Anonymous restriction and intersection axioms (BNodes) are preserved unchanged.

The script accepts optional command-line arguments for input and output paths, falling back to defaults when none are provided:

```bash
python lib/hermit_reasoner.py                           # default paths (acupoints ontology)
python lib/hermit_reasoner.py <input.ttl> <output.ttl>  # explicit paths
```

KB variant (articles knowledge base):
```bash
python lib/hermit_reasoner.py \
  "../ontology-files/generated/ttl/kb/tara-articles-kb.ttl" \
  "../ontology-files/generated/ttl/kb/tara-articles-kb-inferred.ttl"
```

## Generated Output Files

All generated Turtle files are saved under [`../ontology-files/generated/ttl/`](../ontology-files/generated/ttl/):

| File | Description |
|------|-------------|
| `tara-acupoints.ttl` | Main ontology (`tara-acupoints-temp.ttl` merged with upper ontology and imported terms) |
| `tara-acupoints-inferred.ttl` | `tara-acupoints.ttl` with inferred class hierarchy from HermiT |
| `kb/tara-articles-kb.ttl` | `tara-acupoints.ttl` merged with `tara-articles-kb-temp.ttl` (knowledge base variant) |
| `kb/tara-articles-kb-inferred.ttl` | `kb/tara-articles-kb.ttl` with inferred class hierarchy from HermiT |
| `tmp/tara-acupoints-temp.ttl` | Intermediate: main ontology generated from CSV files with numeric TARA IDs |
| `tmp/tara-articles-kb-temp.ttl` | Intermediate: articles metadata ontology generated from the pain-related articles CSV |

## Sample Execution

### generate_ontology.py

```
> Adding Base Ontology From: ../ontology-files/base/tara-acupoints-core.ttl
  Base Ontology Added Successfully.

> Adding Meridians From: ../curated-data/acupoints/meridians.csv
  Meridians Added Successfully.

> Adding Acupoint Categories From: ../curated-data/acupoints/acupoints-category.csv
  Acupoints Categories Added Successfully.

> Adding Acupoints From: ../curated-data/acupoints/acupoints.csv
  Acupoints Added Successfully.

> Adding Extra Acupoints From: ../curated-data/acupoints/extra-acupoints.csv
  Extra Acupoints Added Successfully.

> Adding Special Points From: ../curated-data/acupoints/special-points.csv
  Special Points Added Successfully.

> Adding Special Points Association From: ../curated-data/acupoints/special-points-association.csv
  Special Points Association Added Successfully.

> Adding Surface Locations for the Acupoints From: ../curated-data/acupoints/acupoints-locations.csv
  Surface Locations for the Acupoints Added Successfully.

> Saving Updated Ontology At: ../ontology-files/generated/ttl/tmp/tara-acupoints-temp.ttl
  Generated Turtle File Location: ../ontology-files/generated/ttl/tmp/tara-acupoints-temp.ttl

> Converting Textual IRI Suffixes Into Numeric Values For: ../ontology-files/generated/ttl/tmp/tara-acupoints-temp.ttl
  Generated Turtle File With Converted IRI Suffixes: ../ontology-files/generated/ttl/tmp/tara-acupoints-temp.ttl

> Merging Generated Ontology With Upper Ontology From: ../ontology-files/base/tara-acupoints-upper.ttl
  Merged Ontology Saved At: ../ontology-files/generated/ttl/tara-acupoints.ttl

> Merging Generated Ontology With Imported Terms From: ../ontology-files/base/tara-imported-terms.ttl
  Merged Ontology Saved At: ../ontology-files/generated/ttl/tara-acupoints.ttl

> Adding Articles Metadata From: ../curated-data/kb/pain-related-articles.csv
  Articles Metadata Added Successfully.

> Saving Updated Ontology At: ../ontology-files/generated/ttl/tmp/tara-articles-kb-temp.ttl
  Generated Turtle File Location: ../ontology-files/generated/ttl/tmp/tara-articles-kb-temp.ttl

> Merging Generated Ontology With Articles Metadata From: ../ontology-files/generated/ttl/tmp/tara-articles-kb-temp.ttl
  Merged Ontology Saved At: ../ontology-files/generated/ttl/kb/tara-articles-kb.ttl

> End of Program Execution. All Steps Executed Successfully.
```

### hermit_reasoner.py

```
> Loading Ontology From: ../ontology-files/generated/ttl/tara-acupoints.ttl
> Running HermiT Reasoner (this may take a minute)...
  Reasoning Completed Successfully.
> Updating Class Hierarchy in Graph...
  Inferred Ontology Saved At: ../ontology-files/generated/ttl/tara-acupoints-inferred.ttl
```

