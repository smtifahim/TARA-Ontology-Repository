# TARA Acupoints Ontology Project Repository

This repository contains the source files, curated data, and generation pipeline for the TARA Acupoints Ontology. The ontology project is part of the [Topological Atlas and Repository for Acupoint Research (TARA)](https://www.acupunctureresearch.org/tara) project funded by the National Institute of Health (NIH). The goal of the project is to establish a new comprehensive, computable resource for the acupuncture research and clinician community.

For a full description of the TARA Acupoints Ontology — including its scope, upper-level ontologies, four-layer architecture, property reference tables, loading instructions, and query examples — see the **[TARA Acupoints Ontology readme](./ontology-files/readme.md)**.

## Repository Structure


| Directory                             | Description                                                                                                                                                                                                                                                                |
| ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`ontology-generator/`](./ontology-generator) | Python scripts for generating the ontology from curated data files.<br />See the [generator readme](./ontology-generator/readme.md) for the<br />full pipeline description, prerequisites, and sample output.                                                                               |
| [`curated-data/`](./curated-data)           | Curated CSV files that serve as the input data for the generator. Sourced from the TARA Ontology<br /> <br />Curation Google Sheet. <br />See the [curated data readme](./curated-data/readme.md).                                                                               |
| [`ontology-files/`](./ontology-files) | Base ontology files (under [`base/`](./ontology-files/base/)), generated output files (under [`generated/ttl/`](./ontology-files/generated/ttl/)), and archived prior versions (under [`generated/archived/`](./ontology-files/generated/archived/)). <br />See the [ontology files readme](./ontology-files/readme.md) for comprehensive ontology documentation. |
| [`sparql/`](./sparql) | SPARQL query notebook ([`tara-sparql-queries.ipynb`](./sparql/tara-sparql-queries.ipynb)) and sample query result files. |
| [`downstream/`](./downstream) | Data extraction pipelines for external groups and projects that consume the TARA Acupoints Ontology. Each subdirectory contains scripts and generated data for a specific downstream consumer. <br />See the [downstream readme](./downstream/readme.md). |

## Quick Start

**Prerequisites:** Python 3.8+, RDFLib 7.0.0, owlready2, and Java 8+ on your PATH. See the [generator readme](./ontology-generator/readme.md#prerequisites) for installation details.

Run the full pipeline from the `ontology-generator/` directory:

```bash
cd ontology-generator
./run_all.sh
```

This downloads the latest CSV files from the TARA Google Sheet, generates and merges the ontology files, and produces both inferred ontology files using the HermiT OWL reasoner. All output files are written to [`ontology-files/generated/ttl/`](./ontology-files/generated/ttl/).

## Data Sources

The acupoint knowledge curated in the CSV files is drawn primarily from two authoritative reference works:

- World Health Organization. *WHO Standard Acupuncture Point Locations in the Western Pacific Region*. WHO Regional Office for the Western Pacific, 2008. ISBN 978-92-9061-248-7. [Available online](https://iris.who.int/handle/10665/353407).
- D. Liangyue, G. Yijun, H. Shuhui, et al. *Chinese Acupuncture and Moxibustion*. Revised ed. Foreign Languages Press, Beijing, 1999. ISBN 978-7-119-01758-7.

## Archived Versions

Prior released versions of the ontology are preserved under [`ontology-files/generated/archived/`](./ontology-files/generated/archived/). For a detailed per-version change log, see the [Ontology Versions Summary](./ontology-files/generated/readme.md#ontology-versions-summary) in the generated files readme.

| Version | Directory |
| ------- | --------- |
| 0.5 | [`generated/archived/version-0.5/`](./ontology-files/generated/archived/version-0.5/) |
| 0.5.1 | [`generated/archived/version-0.5.1/`](./ontology-files/generated/archived/version-0.5.1/) |
| 0.7 | [`generated/archived/version-0.7/`](./ontology-files/generated/archived/version-0.7/) |
| 0.7.1 | [`generated/archived/version-0.7.1/`](./ontology-files/generated/archived/version-0.7.1/) |
| 1.0.0 | [`generated/archived/version-1.0.0/`](./ontology-files/generated/archived/version-1.0.0/) |
