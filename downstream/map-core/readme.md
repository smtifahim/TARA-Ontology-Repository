# TARA Acupoints Ontology Resource for MAP-CORE

This directory contains the code, SPARQL queries, and generated data based on the query results for MAP-CORE's use cases utilizing the [TARA Acupoints Ontology](https://github.com/SciCrunch/TARA-Ontology-Repository/blob/master/ontology-files/generated/readme.md).

## Directory Structure

- **acupoints-data-generator/**: Python scripts and SPARQL queries for extracting and processing ontology data.
  - `query-acupoints-data.py`: Main script to run SPARQL queries against the Stardog database and save results as JSON.
  - `sparql-queries/`: Contains SPARQL query files for metadata and location extraction.
- **data/**: Stores generated JSON files from query results.
- **map-core/**: This directory (overview, scripts, and generated data). See the [map-core readme](https://github.com/SciCrunch/TARA-Ontology-Repository/blob/master/downstream/map-core/readme.md).

## Python Environment & Dependencies

It is recommended to use Python 3.8 or newer. You can use a virtual environment (venv or conda) to manage dependencies.

Required Python packages:

- `stardog` (Stardog Python client)
- `python-dotenv` (for loading environment variables from a `.env` file)

To install dependencies, run:

```bash
pip install pystardog[cloud]
pip install python-dotenv
```

## Main Script Usage

To run the main data extraction script:

1. Ensure the Stardog server is running and accessible.
2. Set the required environment variables (e.g., `STARDOG_TARA_PASSWORD`).
3. Run `query-acupoints-data.py` in the `acupoints-data-generator` directory:
   ```bash
   python query-acupoints-data.py
   ```
4. The script will execute SPARQL queries and save results in the `data/json/` directory.

## Data Files

The generated JSON files contain metadata and location information for acupoints, supporting MAP-CORE applications.

## Contact

For questions or contributions, please contact the repository maintainer or open an issue in the main repository.
