# TARA Acupoints Ontology Adapter

The python script `acupoints_ontology_adapter.py` automates the CSV to OWL transformation process for the TARA Acupoints Ontology Project. The script automatically extracts information from a set of [CSV files relevant to the project](../csv-files) and transforms the information into an intergated OWL-DL ontology. After running the script the generated ontology file `tara-acupoints.ttl` will be saved under `../ontology-files/generated` directory.  Observing the [Sample Execution](#sample-execution) of the script should provide an understanding of the overall transformation process.

## Prerequisites

* Set your Python interpreter to `Python 3.8.X` or higher
* Install [RDFLib 7.0.0 from PyPi](https://pypi.org/project/rdflib/): `$ pip install rdflib`
* The script assumes that you have all the necessary input files available as follows:
  * All the input CSV files under [../csv_files](csv-files) directory
  * All the ontology files (.ttl files) under [../ontology_files](ontology-files) directory

## Sample Execution

```
csv-adapter-script % python acupoints_ontology_adapter.py

> Adding Base Ontology From: ../ontology-files/tara-acupoints-core.ttl
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

> Saving Updated Ontology At: ../ontology-files/generated/tara-acupoints.ttl
  Gerenerated Turtle File Location: ../ontology-files/generated/tara-acupoints.ttl
```

---
