# TARA Acupoints Ontology

* [About TARA Acupoints Ontology](#about-tara-acupoints-ontology)
* [Ontology Versions Summary](#ontology-versions-summary)
  + [Version 0.5 (June 4, 2024)](#version-05--june-4--2024-)
* [Accessing and Exploring the Ontology](#accessing-and-exploring-the-ontology)
  + [Examples of the Basic Hierarchies](#examples-of-the-basic-hierarchies)
    - [Hierarchy of the Meridians](#hierarchy-of-the-meridians)
    - [Hierarchy of the Meridian Acupoints](#hierarchy-of-the-meridian-acupoints)
    - [Classification of the Special Acupoints](#classification-of-the-special-acupoints)
    - [Inferred Subclasses of a Special Point](#inferred-subclasses-of-a-special-point)
* [Basic Model of Relationships](#basic-model-of-relationships)
* [DL Query Examples](#dl-query-examples)

## About TARA Acupoints Ontology

The TARA Acupoints Ontology is an ontology being developed as part of the [Topological Atlas and Repository for Acupoint Research (TARA)](https://www.acupunctureresearch.org/tara) project funded by the National Institute of Health (NIH). The goal of the project is to establish a new comprehensive resource for the acupuncture research and clinician community. The ontology will be used to support semantic search and annotations for anatomical maps, atlases, and data sets relevant to the TARA project. The ontology takes into account both Eastern and Western nomenclature for acupuncture points. The current scope of the ontology is to develop the semantic modelling of the anatomical and physiological aspects associated with different acupoints located in the main meridians.

Closely following the [Open Biomedical Ontology Foundry](https://obofoundry.org/principles/fp-000-summary.html) (OBO Foundry) principles, the TARA Acupoints Ontology is being developed to support the best practices recommeded by the FAIR principles. These practices include utilizing existing community ontologies where possible, e.g., the Foundational Model of Anatomy (FMA) or UBERON for common anatomical structures, and the use of upper level ontologies like [Basic Formal Ontology (BFO)](https://basic-formal-ontology.org/) and [Relation Ontology (RO)](https://obofoundry.org/ontology/ro.html) ensuring maximum interoperability with other ontologies in biomedical domain. [Navigate to this page](../) to know more about the upper level layers of the TARA Acupoints Ontology.

## Ontology Versions Summary

This section will be updated periodically based on the release of the newer versions of the ontology.

### Version 0.5 (June 4, 2024)

* Classes representing the Meridians
  * Includes 12 main meridians and 2 extra meridians (Du Channel and Ren Channel)
  * Includes associated organs from UBERON for 11 main meridians
* Classification of the Meridian Acupoints
  * Classes representing acupoints located in each of the 14 meridians (Total: 361)
* Classes representing with Extra Acupoints (Extra points)
  * Includes 40 Extra points
* Classes representing the Special Points
  * Classification of Special Points
  * Association of Meridian Acupoints with Special Points
  * Classification of Meridian Acupoints based on Special Point roles
* Associated metadata such as labels, synonyms, abbreviations, Chinese names
  * Also includes textual descriptions for the acupoint locations and special points

## Accessing and Exploring the Ontology

The most recent version of the TARA Acupoints Ontology is [linked here](https://raw.githubusercontent.com/smtifahim/TARA-Ontology-Repository/master/ontology-files/generated/tara-acupoints.ttl). The easiest way to explore the ontology is to load it in Protege. Protege is a free, open-source ontology editor which you can download from [this link](https://protege.stanford.edu/software.php#desktop-protege).

* Make sure to download the Protege Desktop Version 5.5.X or higher. If you are not familiar with the Protege interface there is a "Getting Started" document [linked here](https://protegeproject.github.io/protege/getting-started/).
* Click `File > Open From URL..` in Protege and copy/paste the [**TARA Acupoints Ontology Link**](https://raw.githubusercontent.com/smtifahim/TARA-Ontology-Repository/master/ontology-files/generated/tara-acupoints.ttl) under the `URI` field. Clicking the `OK` button will load the ontology in Protege.

![1718383103389](image/readme/1718383103389.png)

### Examples of the Basic Hierarchies

This sections provides a set of Protege screenshot examples of the basic hierarchies used in the TARA Acupoints Ontology.

#### Hierarchy of the Meridians

![1718384992327](image/readme/1718384992327.png)

#### Hierarchy of the Meridian Acupoints

![1718385881339](image/readme/1718385881339.png)

#### Classification of the Special Acupoints

![1718386855618](image/readme/1718386855618.png)

#### Inferred Subclasses of a Special Point

The example shows the inferred subclasses of a special acupuncture point called the "Xi-Cleft Point". The subclasses are the acupoints of different meridans that are considered to be Xi-Cleft points.

![1718387153546](image/readme/1718387153546.png)

## Basic Model of Relationships

![1718304880191](image/readme/1718304880191.png)

The diagram above provides a high-level depiction of possible relationships for Acupoints in TARA Acupoints Ontology (Version 0.5). It should be noted that not all acupoints require the relationships with meridians as there are many acupoints that do not belong to the standard meridian system. Also, not all acupoints have the special point designations. Only the acupoints of the 12 main meridans and 2 extra meridians, namely the Du Channel and the Ren Channel, have some special point roles.

## DL Query Examples
