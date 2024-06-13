# TARA Acupoints Ontology

The TARA Acupoints Ontology is an ontology being developed as part of the [Topological Atlas and Repository for Acupoint Research (TARA)](https://www.acupunctureresearch.org/tara) project funded by the National Institute of Health (NIH). The goal of the project is to establish a new comprehensive resource for the acupuncture research and clinician community. The ontology will be used to support semantic search and annotations for anatomical maps, atlases, and data sets relevant to the TARA project. The ontology takes into account both Eastern and Western nomenclature for acupuncture points. The current scope of the ontology is to develop the semantic modelling of the anatomical and physiological aspects associated with different acupoints located in the main meridians.

Closely following the [Open Biomedical Ontology Foundry](https://obofoundry.org/principles/fp-000-summary.html) (OBO Foundry) principles, the TARA Acupoints Ontology is being developed to support the best practices recommeded by the FAIR principles. These practices include utilizing existing community ontologies where possible, e.g., the Foundational Model of Anatomy (FMA) or UBERON for common anatomical structures, and the use of upper level ontologies like [Basic Formal Ontology (BFO)](https://basic-formal-ontology.org/) and [Relation Ontology (RO)](https://obofoundry.org/ontology/ro.html) ensuring maximum interoperability with other ontologies in biomedical domain.

## Versions Summary

This section will be updated periodically based on the release of the newer versions of the ontology.

### Version 0.5 (June 4, 2024)

* Classes representing the Meridians
  * Includes 12 main meridians and 2 extra meridinas (Du Channel and Ren Channel)
  * Includes associated organs from UBERON for 11 main meridians
* Classification of the Meridian Acupoints
  * Classed representing acupoints located in each of the 14 meridians (Total: 361)
* Classes representing with Extra Acupoints (Extra points)
  * Includes 40 Extra points
* Classes representing the Special Points
  * Classification of Special Points
  * Association of Meridian Acupoints with Special Points
  * Classification of Meridian Acupoints based on Special Point roles
* Associated metadata such as labels, synonyms, abbreviations, Chinese names
  * Also includes textual descriptions for the acupoint locations and special points

## Exploring the Ontology

Download the ontology from [this link](https://raw.githubusercontent.com/smtifahim/TARA-Ontology-Repository/master/ontology-files/generated/tara-acupoints.ttl) and load it in Protege.


## Basic Model of Relationships

![1718304880191](image/readme/1718304880191.png)

The diagram above provides a high-level depiction of relationships for Acupoints in TARA Acupoints Ontology (Version 0.5).

## DL Query Examples
