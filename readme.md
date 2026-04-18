# TARA Acupoints Ontology Project Repository

This repository contains the source files, curated data, and generation pipeline for the TARA Acupoints Ontology. The ontology project is part of the [Topological Atlas and Repository for Acupoint Research (TARA)](https://www.acupunctureresearch.org/tara) project funded by the National Institute of Health (NIH). The goal of the project is to establish a new comprehensive, computable resource for the acupuncture research and clinician community.

## About the Ontology

The TARA Acupoints Ontology is an OWL-DL ontology that provides a formal, structured representation of acupuncture point knowledge. It covers:

- **Acupoints** — classical and extra acupoints with standard WHO nomenclature and numeric TARA identifiers
- **Meridians** — the fourteen primary meridian channels and their associated acupoints
- **Anatomical locations** — surface and relational anatomical locations for each acupoint, linked to terms from [UBERON](https://obofoundry.org/ontology/uberon.html) and [InterLex (ILX)](https://interlex.org/)
- **Special point categories** — designations such as Five-Shu points, Yuan-Source points, Luo-Connecting points, and others
- **Pain-related articles** — metadata for pain research articles associating conditions with acupoints

The ontology is built on a suite of established upper-level and mid-level ontologies:


| Ontology                                                                                           | Role                                   |
| -------------------------------------------------------------------------------------------------- | -------------------------------------- |
| [Basic Formal Ontology (BFO)](https://obofoundry.org/ontology/bfo.html)                            | Top-level formal structure             |
| [UBERON](https://obofoundry.org/ontology/uberon.html)                                              | Anatomical entity terms                |
| [Relation Ontology (RO)](https://obofoundry.org/ontology/ro.html)                                  | Object properties                      |
| [Information Artifact Ontology (IAO)](https://github.com/information-artifact-ontology/IAO)        | Annotation properties                  |
| [Dublin Core Metadata (DC)](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/)     | Article metadata annotation            |
| [MONDO](https://obofoundry.org/ontology/mondo.html), [HP](https://obofoundry.org/ontology/hp.html) | Disease and phenotype terms (imported) |

## Ontology Architecture

The ontology is organized in four layers, each building on the one below it:

```
tara-acupoints-inferred.ttl          (4) Inferred — class hierarchy computed by HermiT
        |
tara-acupoints-merged.ttl            (3) Merged — main ontology + upper ontology + imported terms
        |
tara-acupoints.ttl                   (2) Main — generated from curated CSV files by the adapter
        |
tara-acupoints-core.ttl              (1) Core — hand-authored classes, properties, and axioms
tara-acupoints-upper.ttl                 Upper — subset of BFO/UBERON/RO/IAO/DC terms
tara-imported-terms.ttl                  Imported — MONDO, HP, and other external terms
```

A parallel knowledge base variant (`tara-acupoints-articles-kb-merged.ttl`, `tara-acupoints-kb-inferred.ttl`) includes the pain-related articles metadata alongside the acupoints ontology.

## Repository Structure


| Directory                             | Description                                                                                                                                                                                                                                                                |
| ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`csv-adapter/`](./csv-adapter)       | Python scripts for generating the ontology from CSV files.<br />See the [adapter readme](./csv-adapter/readme.md) for the<br />full pipeline description, prerequisites, and sample output.                                                                               |
| [`csv-files/`](./csv-files)           | Curated CSV files that serve as the input data for the adapter. Sourced from the TARA Ontology<br /> <br />Curation Google Sheet. <br />See the [CSV files readme](./csv-files/readme.md).                                                                               |
| [`ontology-files/`](./ontology-files) | Base ontology files (under[`base/`](./ontology-files/base/)), generated output files (under [`generated/ttl/`](./ontology-files/generated/ttl/)), archived prior versions, and imported external terms. <br />See the [ontology files readme](./ontology-files/readme.md). |

## Quick Start

**Prerequisites:** Python 3.8+, RDFLib 7.0.0, owlready2, and Java 8+ on your PATH. See the [adapter readme](./csv-adapter/readme.md#prerequisites) for installation details.

Run the full pipeline from the `csv-adapter/` directory:

```bash
cd csv-adapter
./run_all.sh
```

This downloads the latest CSV files from the TARA Google Sheet, generates and merges the ontology files, and produces both inferred ontology files using the HermiT OWL reasoner. All output files are written to [`ontology-files/generated/ttl/`](./ontology-files/generated/ttl/).

## Data Sources

The acupoint knowledge curated in the CSV files is drawn primarily from two authoritative reference works:

- World Health Organization. *WHO Standard Acupuncture Point Locations in the Western Pacific Region*. WHO Regional Office for the Western Pacific, 2008. ISBN 978-92-9061-248-7. [Available online](https://iris.who.int/handle/10665/353407).
- D. Liangyue, G. Yijun, H. Shuhui, et al. *Chinese Acupuncture and Moxibustion*. Revised ed. Foreign Languages Press, Beijing, 1999. ISBN 978-7-119-01758-7.

## Archived Versions

Prior released versions of the ontology are preserved under [`ontology-files/archived/`](./ontology-files/archived/):


| Version | Directory                                                             |
| ------- | --------------------------------------------------------------------- |
| 0.5     | [`archived/version-0.5/`](./ontology-files/archived/version-0.5/)     |
| 0.5.1   | [`archived/version-0.5.1/`](./ontology-files/archived/version-0.5.1/) |
| 0.7     | [`archived/version-0.7/`](./ontology-files/archived/version-0.7/)     |
| 0.7.1   | [`archived/version-0.7.1/`](./ontology-files/archived/version-0.7.1/) |
| 1.0.0   | [`archived/version-1.0.0/`](./ontology-files/archived/version-1.0.0/) |
