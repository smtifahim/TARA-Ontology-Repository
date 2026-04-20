# Curated Data for the TARA Acupoints Ontology

This directory contains all the curated CSV files used by the [ontology generator](../ontology-generator) to generate the TARA Acupoints Ontology. The files are sourced from the [Official TARA Ontology Curation Google Sheet](https://docs.google.com/spreadsheets/d/1hvUcTrw-b9ly8Yn1P706px22li0vsjslukYhxkTDlA8/) maintained by the TARA ontology curation team. To download the latest version of each file from the Google Sheet, run [`fetch_curated_data.py`](../ontology-generator/fetch_curated_data.py) from the `ontology-generator/` directory.

## Contents

1. [Data Sources](#data-sources)
2. [Curated Data Files](#curated-data-files)

## Data Sources

The acupoint knowledge curated in these files is drawn primarily from the following two authoritative reference works:

- World Health Organization. *WHO Standard Acupuncture Point Locations in the Western Pacific Region*. WHO Regional Office for the Western Pacific, 2008. ISBN 978-92-9061-248-7. [Available online](https://iris.who.int/handle/10665/353407).
- D. Liangyue, G. Yijun, H. Shuhui, et al. *Chinese Acupuncture and Moxibustion*. Revised ed. Foreign Languages Press, Beijing, 1999. ISBN 978-7-119-01758-7.

## Curated Data Files

The table below summarizes each CSV file, its columns, and the content it contributes to the ontology.


| File                                                               | Key Columns                                                                                                                                                                          | Description                                                                                                                                                                                   |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`meridians.csv`](#meridianscsv)                                   | Meridian, Associated Organ, Superclass, Label, Synonym, Abbreviation, Chinese Label, Description                                                                                     | Defines the 14 meridians (12 main + 2 extra) as OWL classes with labels, synonyms, abbreviations, Chinese names, and associated UBERON organ terms                                            |
| [`acupoints-category.csv`](#acupoints-categorycsv)                 | Acupoints, Label, Meridian, Synonym, Description                                                                                                                                     | Defines one named category class per meridian (e.g., "Acupoint of the Lung Meridian") with labels, synonyms, and textual descriptions                                                         |
| [`acupoints.csv`](#acupointscsv)                                   | Acupoint, Label, Synonym, Meridian, Pinyin Label, Chinese Label, English Name, Location, WHO Location, Indications, Acupuncture Method, Vasculature, Innervation                     | Main acupoint data — defines 361 meridian acupoints with full metadata including WHO standard locations, Chinese names, clinical indications, needling methods, and anatomical relationships |
| [`extra-acupoints.csv`](#extra-acupointscsv)                       | Acupoint, Superclass, Label, Synonym, Location, Indications, Acupuncture Method, Vasculature, Innervation                                                                            | Defines extra acupoints (outside the 14 standard meridians) with the same metadata structure as the main acupoints file                                                                       |
| [`special-points.csv`](#special-pointscsv)                         | Special Point, Label, Superclass, Description                                                                                                                                        | Defines the special point category classes and roles (e.g., Xi-Cleft Point, Yuan-Source Point, Five-Shu Points) with descriptions and hierarchical structure                                  |
| [`special-points-association.csv`](#special-points-associationcsv) | Acupoint, Special-Point-1, Special-Point-2, Special-Point-3                                                                                                                          | Associates individual acupoints with their special point designations; supports multiple designations per acupoint                                                                            |
| [`acupoints-locations.csv`](#acupoints-locationscsv)               | Acupoint, WHO Location, Identified Locations, Identified Locations URI, Relation                                                                                                     | Maps acupoints to their anatomical surface locations using URIs from UBERON and InterLex (ILX); specifies the locational relation (`locatedOnTheSurfaceOf` or `locatedInRelationTo`)          |
| [`pain-related-articles.csv`](#pain-related-articlescsv)           | Title, Authors, Venue, DOI, Year, Trial Type, Acupuncture Modality, Stimulation Type, Needling Info, Sample Size, Controls, Country, Acupoints Used, Condition Treated, Condition ID | Metadata for peer-reviewed articles studying acupuncture for pain-related conditions; acupoints and conditions are mapped to TARA, MONDO, and HP identifiers                                  |

### meridians.csv

Defines the 14 meridians as OWL classes. Each row specifies the meridian's label, standard abbreviation (e.g., `LU`, `ST`), associated organ from UBERON (where applicable), synonyms including the traditional Chinese meridian name, Chinese-script label, and a textual description of the meridian's course and acupoint count.

### acupoints-category.csv

Defines one superclass per meridian representing the category of acupoints belonging to that meridian (e.g., "Acupoint of the Lung Meridian"). Each row includes the class IRI, label, parent meridian, synonyms, and a textual description of the meridian course used for the category definition.

### acupoints.csv

The primary acupoint data file. Each row defines one of the 361 standard meridian acupoints with:

- **Identification**: WHO standard label (e.g., `LU 1`), synonyms, Pinyin name, Chinese characters
- **Classification**: parent meridian, optional UMLS CUI
- **Location**: textual location description and the WHO standard location text
- **Clinical metadata**: indications, acupuncture method, vasculature, innervation
- **Provenance**: reference to the WHO or Chinese Acupuncture and Moxibustion source

### extra-acupoints.csv

Defines extra acupoints — standardized acupoints that do not belong to the 14 main meridians. Uses the same column structure as `acupoints.csv`, with the addition of a `Superclass` column to specify the appropriate OWL parent class (e.g., `TARA:Extra_Acupoint`).

### special-points.csv

Defines the special point roles and category classes used in the ontology (e.g., Xi-Cleft Points, Yuan-Source Points, Luo-Connecting Points, Five-Shu Points, Eight Confluent Points). Each row specifies the class IRI, label, parent class, and a textual description with provenance.

### special-points-association.csv

Associates individual acupoints with their special point designations. Each row maps one acupoint to up to three special point roles. This file drives the `hasSpecialPointDesignation` axioms in the generated ontology and the defined class equivalences for named special point categories.

### acupoints-locations.csv

Maps acupoints to their anatomical surface locations using external ontology URIs. Each row specifies:

- **WHO Location**: the verbatim WHO standard surface location text
- **Identified Locations URI**: the UBERON or ILX URI for the matched anatomical term
- **Relation**: either `TARA:locatedOnTheSurfaceOf` (general surface region) or `TARA:locatedInRelationTo` (proximal landmark)

FMA-only locations are excluded pending their replacement with ILX equivalents.

### pain-related-articles.csv

Metadata for peer-reviewed articles on acupuncture treatment of pain-related conditions. Each row captures one article with full bibliographic information, study methodology (trial type, modality, stimulation type, needling details, sample size, controls, country), the list of acupoints used (both textual and mapped to TARA IDs), and the studied conditions mapped to MONDO and HP identifiers.
