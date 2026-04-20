# Downstream Consumers of the TARA Acupoints Ontology

This directory contains data extraction pipelines and generated datasets for external groups and projects that build on the [TARA Acupoints Ontology](https://github.com/SciCrunch/TARA-Ontology-Repository/blob/master/ontology-files/generated/readme.md). Each subdirectory is self-contained and represents the work of a specific downstream consumer — typically querying the ontology via a SPARQL endpoint and producing output data in formats suited to their application.

## Subdirectories

| Directory | Consumer | Description |
|-----------|----------|-------------|
| [`map-core/`](map-core/) | MAP-CORE | Scripts and generated JSON data for MAP-CORE applications. Queries the TARA ontology via the Stardog endpoint. See the [MAP-CORE readme](map-core/readme.md). |
| [`data-core/`](data-core/) | DATA-CORE | _(Placeholder — content coming soon)_ |

## Adding a New Consumer

To add a new downstream consumer, create a new subdirectory here (e.g., `downstream/<project-name>/`) with its own scripts, data output, and a `readme.md` describing its purpose, dependencies, and usage. Then add a row to the table above.
