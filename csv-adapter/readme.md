# TARA Acupoints Ontology Adapter

This directory contains Python scripts for automating the generation and processing of the TARA Acupoints Ontology from curated CSV files.

## Scripts

### acupoints_ontology_adapter.py

The main script that automates the CSV to OWL transformation process for the TARA Acupoints Ontology. It reads the curated CSV files, transforms the content into an integrated OWL-DL ontology, and produces a set of merged Turtle files under [`../ontology-files/generated/ttl/`](../ontology-files/generated/ttl/).

Internally, the script uses the following helper modules:
* [`google_sheet_to_csvs.py`](#google_sheet_to_csvspy) — downloads the curated CSV files from the TARA Google Sheet
* [`convert_class_iris.py`](#convert_class_irispy) — converts textual IRI suffixes to numeric TARA IDs
* [`ontology_merger.py`](#ontology_mergerpy) — merges multiple ontology files into one
* [`hermit_reasoner.py`](#hermit_reasonerpy) — generates the inferred class hierarchy using HermiT

To run the complete pipeline in one step, use [`run_all.sh`](#run_allsh).

### google_sheet_to_csvs.py

Downloads each tab of the [Official TARA Ontology Curation Google Sheet](https://docs.google.com/spreadsheets/d/1hvUcTrw-b9ly8Yn1P706px22li0vsjslukYhxkTDlA8/) as a CSV file and saves them under [`../csv-files/`](../csv-files/). Run this script first to refresh the local CSV files before running the adapter.

### convert_class_iris.py

Converts class IRI suffixes from the human-readable textual form used during CSV authoring (e.g., `TARA:Meridian_Acupoint`) to a stable numeric form (e.g., `TARA:TARA_0123456`) using a SHA-256 hash. The conversion is deterministic and collision-resistant. This script is called automatically by the adapter and is not normally run standalone.

### ontology_merger.py

Merges two input ontology Turtle files into a single output file using RDFLib. Properly named namespace prefixes from the caller-supplied namespace dictionary are re-bound after merging to prevent RDFLib from emitting auto-generated `ns1`, `ns2`, ... prefixes for unrecognized namespaces. This script is called automatically by the adapter and is not normally run standalone.

### hermit_reasoner.py

Generates an inferred version of a merged ontology using the HermiT OWL reasoner (via [owlready2](https://pypi.org/project/owlready2/)). For each class, asserted named-class superclasses are replaced by the inferred direct superclasses, matching the behaviour of Protege's inferred hierarchy tab. Anonymous restriction and intersection axioms (BNodes) are preserved unchanged. The script accepts optional command-line arguments for input and output paths, falling back to the default paths when none are provided.

```
python hermit_reasoner.py                          # uses default input/output paths
python hermit_reasoner.py <input.ttl> <output.ttl> # explicit paths
```

Default run (acupoints ontology):
```
python hermit_reasoner.py
```

KB variant (articles knowledge base ontology):
```
python hermit_reasoner.py \
  "../ontology-files/generated/ttl/tara-acupoints-articles-kb-merged.ttl" \
  "../ontology-files/generated/ttl/tara-acupoints-kb-inferred.ttl"
```

### run_all.sh

A convenience shell script that runs the full generation pipeline in a single command — downloading the CSV files, generating and merging the ontology files, and producing both inferred ontology files with HermiT. The script resolves its own directory automatically so it can be invoked from any working directory.

```bash
./run_all.sh
```

The pipeline steps executed by the script are:

```
Step 1: Downloading CSV files from the TARA Google Sheet...
Step 2: Running ontology adapter to generate and merge TTL files...
Step 3a: Running HermiT on tara-acupoints-merged.ttl...
Step 3b: Running HermiT on tara-acupoints-articles-kb-merged.ttl...
Pipeline Completed Successfully.
Generated files are under: ../ontology-files/generated/ttl/
```

The same prerequisites listed below apply. The script will exit immediately if any step fails.

## Prerequisites

* Set your Python interpreter to `Python 3.8.X` or higher
* Install [RDFLib 7.0.0](https://pypi.org/project/rdflib/): `$ pip install rdflib`
* Install [owlready2](https://pypi.org/project/owlready2/) (required for `hermit_reasoner.py`): `$ pip install owlready2`
* Java 8 or higher must be available on the system PATH (required by HermiT via owlready2)
* Run `google_sheet_to_csvs.py` to download the curated CSV files from the [Official TARA Ontology Curation Google Sheet](https://docs.google.com/spreadsheets/d/1hvUcTrw-b9ly8Yn1P706px22li0vsjslukYhxkTDlA8/) into [`../csv-files/`](../csv-files/)
* **Note:** The `acupoints_ontology_adapter.py` script assumes that you have all the necessary input files available as follows:
  * All the input CSV files under [`../csv-files/`](../csv-files/)
  * The base ontology files ([`tara-acupoints-upper.ttl`](../ontology-files/base/tara-acupoints-upper.ttl), [`tara-acupoints-core.ttl`](../ontology-files/base/tara-acupoints-core.ttl), [`tara-imported-terms.ttl`](../ontology-files/base/tara-imported-terms.ttl)) located under [`../ontology-files/base/`](../ontology-files/base/)

## Generated Output Files

All generated Turtle files are saved under [`../ontology-files/generated/ttl/`](../ontology-files/generated/ttl/):

| File | Description |
|------|-------------|
| `tara-acupoints.ttl` | Main ontology generated from CSV files with numeric TARA IDs |
| `tara-articles.ttl` | Articles metadata ontology generated from the pain-related articles CSV |
| `tara-acupoints-merged.ttl` | `tara-acupoints.ttl` merged with the upper ontology and imported terms |
| `tara-acupoints-articles-kb-merged.ttl` | `tara-acupoints-merged.ttl` merged with `tara-articles.ttl` (knowledge base) |
| `tara-acupoints-inferred.ttl` | `tara-acupoints-merged.ttl` with inferred class hierarchy from HermiT |
| `tara-acupoints-kb-inferred.ttl` | `tara-acupoints-articles-kb-merged.ttl` with inferred class hierarchy from HermiT |

## Sample Execution

### acupoints_ontology_adapter.py

```
> Adding Base Ontology From: ../ontology-files/base/tara-acupoints-core.ttl
  Base Ontology Added Successfully.

> Adding Meridians From: ../csv-files/meridians.csv
  Meridians Added Successfully.

> Adding Acupoint Categories From: ../csv-files/acupoints-category.csv
  Acupoints Categories Added Successfully.

> Adding Acupoints From: ../csv-files/acupoints.csv
  Acupoints Added Successfully.

> Adding Extra Acupoints From: ../csv-files/extra-acupoints.csv
  Extra Acupoints Added Successfully.

> Adding Special Points From: ../csv-files/special-points.csv
  Special Points Added Successfully.

> Adding Special Points Association From: ../csv-files/special-points-association.csv
  Special Points Association Added Successfully.

> Adding Surface Locations for the Acupoints From: ../csv-files/acupoints-locations.csv
  Surface Locations for the Acupoints Added Successfully.

> Saving Updated Ontology At: ../ontology-files/generated/ttl/tara-acupoints.ttl
  Gerenerated Turtle File Location: ../ontology-files/generated/ttl/tara-acupoints.ttl

> Converting Textual IRI Suffixes Into Numeric Values For: ../ontology-files/generated/ttl/tara-acupoints.ttl
  Generated Turtle File With Converted IRI Suffixes: ../ontology-files/generated/ttl/tara-acupoints.ttl

> Merging Generated Ontology With Upper Ontology From: ../ontology-files/base/tara-acupoints-upper.ttl
  Merged Ontology Saved At: ../ontology-files/generated/ttl/tara-acupoints-merged.ttl

> Merging Generated Ontology With Imported Terms From: ../ontology-files/base/tara-imported-terms.ttl
  Merged Ontology Saved At: ../ontology-files/generated/ttl/tara-acupoints-merged.ttl

> Adding Aritcles Metadata From: ../csv-files/pain-related-articles.csv
  Articles Metadata Added Successfully.

> Saving Updated Ontology At: ../ontology-files/generated/ttl/tara-articles.ttl
  Gerenerated Turtle File Location: ../ontology-files/generated/ttl/tara-articles.ttl

> Merging Generated Ontology With Articles Metadata From: ../ontology-files/generated/ttl/tara-articles.ttl
  Merged Ontology Saved At: ../ontology-files/generated/ttl/tara-acupoints-articles-kb-merged.ttl

> End of Program Execution. All Steps Executed Succussfully.
```

### hermit_reasoner.py

```
> Loading Ontology From: ../ontology-files/generated/ttl/tara-acupoints-merged.ttl
> Running HermiT Reasoner (this may take a minute)...
  Reasoning Completed Successfully.
> Updating Class Hierarchy in Graph...
  Inferred Ontology Saved At: ../ontology-files/generated/ttl/tara-acupoints-inferred.ttl
```

