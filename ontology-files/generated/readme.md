# TARA Acupoints Ontology

1. [About TARA Acupoints Ontology](#about-tara-acupoints-ontology)
2. [Ontology Versions Summary](#ontology-versions-summary)
   + [[Version 0.7 (March 15, 2025)](#version-07-march-15-2025)
   + [Version 0.6 (December 12, 2024)](#version-06-december-12-2024)
   + [Version 0.5.1 (July 12, 2024)](#version-051-july-12-2024)
   + [Version 0.5.1 (July 11, 2024)](#version-051-july-11-2024)
   + [Version 0.5 (June 4, 2024)](#version-05-june-4-2024)
3. [Accessing and Exploring the Ontology](#accessing-and-exploring-the-ontology)
   + [Loading the Ontology in Protégé Desktop](#loading-the-ontology-in-protégé-desktop)
   + [Exploring the Ontology in WebProtégé](#exploring-the-ontology-in-webprotégé)
4. [Examples of the Basic Hierarchies](#examples-of-the-basic-hierarchies)
   + [Hierarchy of the Meridians](#hierarchy-of-the-meridians)
   + [Hierarchy of the Meridian Acupoints](#hierarchy-of-the-meridian-acupoints)
   + [Classification of the Special Acupoints](#classification-of-the-special-acupoints)
   + [Inferred Subclasses of a Special Point](#inferred-subclasses-of-a-special-point)
5. [Basic Model of Relationships](#basic-model-of-relationships)
6. [DL Query Examples](#dl-query-examples)
7. [SPARQL Query Examples](#sparql-query-examples)

## About TARA Acupoints Ontology

The TARA Acupoints Ontology is an ontology being developed as part of the [Topological Atlas and Repository for Acupoint Research (TARA)](https://www.acupunctureresearch.org/tara) project funded by the National Institute of Health (NIH). The goal of the project is to establish a new comprehensive resource for the acupuncture research and clinician community. The ontology will be used to support semantic search and annotations for anatomical maps, atlases, and data sets relevant to the TARA project. The ontology takes into account both Eastern and Western nomenclature for acupuncture points. The current scope of the ontology is to develop the semantic modelling of the anatomical and physiological aspects associated with different acupoints located in the main meridians.

Closely following the [Open Biomedical Ontology Foundry](https://obofoundry.org/principles/fp-000-summary.html) (OBO Foundry) principles, the TARA Acupoints Ontology is being developed to support the best practices recommeded by the FAIR principles. These practices include utilizing existing community ontologies where possible, e.g., the Foundational Model of Anatomy (FMA) or UBERON for common anatomical structures, and the use of upper level ontologies like [Basic Formal Ontology (BFO)](https://basic-formal-ontology.org/) and [Relation Ontology (RO)](https://obofoundry.org/ontology/ro.html) ensuring maximum interoperability with other ontologies in biomedical domain. [Navigate to this page](../) to know more about the upper level layers of the TARA Acupoints Ontology.

## Ontology Versions Summary

This section will be updated periodically based on the release of the newer versions of the ontology.

### Version 0.7 (March 15, 2025)

* **Expanded Locational Axioms for Acupoints** :
  * Added 1,172 axioms associating acupoints with their surface locations, covering 262 unique locations.
  * Only 18 related surface locations remain to complete the locational axioms for all meridian acupoints. These locations have been identified in FMA and are pending expert review for inclusion in InterLeX.
* **Enhanced Terminology Coverage** :
  * Added additional synonyms for acupoints and meridians to improve semantic alignment and searchability.
* **Incorporated Acupuncture Research Metadata** :
  * Added metadata for 87 unique articles on acupuncture for pain-related conditions, including detailed provenance and study methodologies.
  * Standardized and mapped a major subset of acupoints extracted from the articles to TARA ontology's standard acupoints (113 unique acupoints across different meridians).
  * Mapped a major subset of extracted pain-related conditions studied in the articles to MONDO, HP, and ILX terms, integrating 28 unique conditions into the TARA ontology.
* **Added Annotation Properties for Acupoint-Specific Research Metadata** :
  * Added new properties to incorporate metadata from journal articles on acupuncture treatments for various conditions.
    * Added these properties to capture key details of acupuncture studies:
  * Annotation Properties by Domain and Range :
    * **Domain: Journal Article (DOI); Range: Free Text**
      * `TARA:hasTrialType`, `TARA:hasAcupunctureModality`, `TARA:hasStimulationType`
      * `TARA:hasNeedlingInformation`, `TARA:hasSampleSizeInformation`, `TARA:hasControlsInformation`
      * `TARA:hasListedAcupointsUsed`, `TARA:hasStudiedConditionNote`, `TARA:hasStudiedConditionContext`
      * `TARA:hasCountryInformation`
    * **Domain: Journal Article (DOI); Range: Controlled Term (MONDO/HPO)**
      * `TARA:hasStudiedCondition` – Links studied conditions to standardized MONDO and HPO terms.
    * **Domain: Controlled Term (TARA Acupoint); Range: Journal Article (DOI)**
      * `TARA:isStudiedInArticle` – Captures references to journal articles studying specific acupoints.

### Version 0.6 (December 12, 2024)

* **Updated Ontology** :
  * Included axioms associating the surface locations of acupoints.
  * Added two special properties: `TARA:locatedOnTheSurfaceOf` and `TARA:locatedInRelationTo`, to specify the surface anatomy for each acupoint.
    * `TARA:locatedOnTheSurfaceOf`: Defines the relationship between an acupoint and its general regional location on the body surface.
    * `TARA:locatedInRelationTo`: Defines the relationship between an acupoint and its related proximal location on the body surface.
* **Content Summary** :
  * This version includes all surface locations for the acupoints of the Lung (LU) and Large Intestine (LI) meridians, totaling 31 acupoints.
    * Anatomical terms associated with surface regions are drawn from UBERON (200+ terms) and InterLex (ILX). ILX terms are derived from the Foundational Model of Anatomy (FMA). A total of 55 ILX terms related to surface anatomy were created and imported into the ontology.
    * For the remaining meridian acupoints, this version includes only surface regions associated with UBERON and ILX terms. Regions associated with FMA have been excluded (to be replaced with ILX terms) pending a future release.

### Version 0.5.1 (July 12, 2024)

* Updated the labels for the acupoints of the Governor Vessel and the Conception Vessel
  * Du 1...Du N are udated to GV 1...GV N; Du X are kept as synonyms
  * RN 1...RN N are updated to CV 1...CV N; RN X are kept as synonyms

### Version 0.5.1 (July 11, 2024)

* All the textual IRI suffixes of the class IRIs are automatically converted to numeric suffixes.
  * Example: the OWL class `TARA:Meridian_Acupoint` is converted to `TARA:TARA_5151019`
* Updated preferred labels for `Du Channel` and `Ren Channel` to be `Governor Vessel` and `Conception Vessel` respectively
  * Du Channel and Ren Channel are kept as synonyms
* Updated preferred labels for `Acupoint of the Du Channel` and `Acupoint of the Ren Channel` to be `Acupoint of the Governor Vessel` and `Acupoint of the Conception Vessel` respectively
  * `Acupoint of the Du Channel` and `Acupoint of the Ren Channel` are kept as synonyms

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

The most recent version of the TARA Acupoints Ontology is [linked here](https://raw.githubusercontent.com/smtifahim/TARA-Ontology-Repository/refs/heads/master/ontology-files/generated/tara-acupoints-merged.ttl). The easiest way to explore the ontology is to load it in **Protégé**. Protégé is a free, open-source ontology editor which you can download from [this link](https://protege.stanford.edu/software.php#desktop-protege).

* The [inferred version of the ontology is linked here](https://raw.githubusercontent.com/smtifahim/TARA-Ontology-Repository/master/ontology-files/generated/tara-acupoints-inferred.ttl). This inferred ontology merges the asserted and inferred axioms of the acupoints ontology plus the upper ontology into a **single turtle file**.

### Loading the Ontology in Protégé Desktop

* Make sure to download the Protégé Desktop Version 5.5.X or higher. If you are not familiar with the Protégé interface there is a "Getting Started" document [linked here](https://protegeproject.github.io/protege/getting-started/).
* Click `File > Open From URL..` in Protégé and copy/paste the [**TARA Acupoints Ontology Link**](https://raw.githubusercontent.com/smtifahim/TARA-Ontology-Repository/refs/heads/master/ontology-files/generated/tara-acupoints-merged.ttl) under the `URI` field. Clicking the `OK` button will load the ontology in Protege.

![1718383103389](image/readme/1718383103389.png)

The screenshot above is from TARA Acupoints Ontology - Version 0.5.

### Exploring the Ontology in WebProtégé

The inferred version of the TARA Acupoints Ontology is available explore via the **WebProtégé**. WebProtégé is an open source, lightweight, web-based ontology viewer and editor. The ontology is available in WebProtégé *only for viewing and commenting*. The idea is to gather feedback from acupoint experts.

* If you don't have an account in WebProtégé, [create an account using this link](https://webprotege.stanford.edu/).
* Simply navigate to the following link: [TARA Acupoints Ontology in WebProtege](https://webprotege.stanford.edu/#projects/7c97eaa5-7c13-4a73-ab3c-5cb6eeec4fb4/edit/Classes?selection=Class(%3Chttp://www.acupunctureresearch.org/tara/ontology/acupoints.owl%23TARA_5151019%3E))
* If you are new to WebProtégé, please visit the [WebProtégé User Guide](https://protegewiki.stanford.edu/wiki/WebProtegeUsersGuide).

![1720703169244](image/readme/1720703169244.png)

## Examples of the Basic Hierarchies

This sections provides a set of Protégé screenshot examples of the basic hierarchies used in the TARA Acupoints Ontology.

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

[The DL Query tab](https://protegewiki.stanford.edu/wiki/DLQueryTab) in Protege provides a powerful feature for testing a classified ontology using class expressions in a standard Description Logic (DL) syntax called the Manchester OWL syntax.

* Before using the DL Query tab, make sure to run the reasoner by selecting `Reasoner > Select HermiT > Start reasoner` in Protege.

This section provides a set of example DL queries to test the basic classifications of the TARA Acupoints Ontology.

**Q: What are the acupuncture points in the Heart Meridan?**

```
'Meridian Acupoint' that isMemberAcupointOf some 'Heart Meridian'
```

Since we have a defined a named class called `'Acupoint of the Heart Meridian'` in the ontology that is equivalent to the class expression above, we can achieve the same result by simply typing the named class as the DL Query.

```
'Acupoint of the Heart Meridian' 
```

![1718430667694](image/readme/1718430667694.png)

**Q. What are the Xi-Cleft Points in the main meridians?**

```
'Meridian Acupoint' that hasSpecialPointDesignation some 'Xi-Cleft Point Role'
```

Again, since we have defined a named class called 'Xi-Cleft Point' in the ontology as equivalent to the class expression above, we can achive the same result by typing `'Meridian Acupoint' and 'Xi-Cleft Point'`.

![1718432154575](image/readme/1718432154575.png)

**Q: What are the Xi-Cleft Points on the Kidney Meridian?**

```
'Xi-Cleft Point' and isMemberAcupointOf some (Meridian 
                 and hasAssociatedOrgan some kidney)
```

We are essentially looking for the Xi-Cleft points in the Kidney Meridian; i.e., the acupoints of the kidney meridian that are considered Xi-Cleft points. Since we have a defined class called the 'Acupoint of the Kidney Meridian' as equivalent to the class expression `'Meridian Acupoint' and (isMemberAcupointOf some 'Kidney Meridian')` and we also have 'Kidney Meridan' specified as a subclass of the class expression `'Main Meridian'and (hasAssociatedOrgan some kidney)`, we can simply type the following expression to achieve the same query result.

```
'Xi-Cleft Point' and 'Acupoint of the Kidney Meridian'
```

![1719335980722](image/readme/1719335980722.png)

**Q. What are the 8 Confluent Points of the main meridians?**

```
'Confluent Point' and isMemberAcupointOf some 'Main Meridian'
```

Without using the defined class called 'Confluent Point', we would need to use the following expression to achieve the same result.

```
'Meridian Acupoint' and (hasSpecialPointDesignation some 'Confluent Point Role')
```

![1718434002421](image/readme/1718434002421.png)

**Q. What are the 15 Luo-Connecting Points of the meridians?**

```
'Meridian Acupoint' and 'Luo-Connecting Point'
```

Again, without using the defined class called 'Luo-Connecting Point' one would need to use the following expression.

```
'Meridian Acupoint' and hasSpecialPointDesignation some 'Luo-Connecting Point Role'
```

![1718435147757](image/readme/1718435147757.png)

### DL Queries Related to Surface Locations

**Q. What meridian acupoints can be located on the surface of the face?**

```
'Meridian Acupoint' and (locatedOnTheSurfaceOf some face)
```

![1734073357404](image/readme/1734073357404.png)

**Q. What meridian acupoints can be located on the surface of the chest?**

```
Acupoint and (locatedOnTheSurfaceOf some ('part of' some chest))
```

![1734073730688](image/readme/1734073730688.png)

Also try with different parts of the body surface like the following:

**Q. What acupoints are located on the surface of the legs?**

```
Acupoint and locatedInRelationTo some ('part of' some leg)
```

**Q: What acoupoints and located on the surface of the forearm?**

```
Acupoint and (locatedInRelationTo some 'forelimb zeugopod’)
```

## SPARQL Query Examples

### SPARQL Examples in Jupyter Notebook

A set of [example queries are available in a Jupyter Notebook](https://github.com/smtifahim/TARA-Ontology-Repository/blob/master/ontology-files/TARA%20SPARQL%20Query%20Examples.ipynb) to explore the TARA Acupoints Ontology.

**Q. List all the acupoints along with their meridians, special point role, and surface regions.**

```SPARQL
# List all the acupoints along with their meridians, special point role, and surface regions.

PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX TARA: <http://www.acupunctureresearch.org/tara/ontology/acupoints.owl#>

SELECT DISTINCT ?acupoint_iri ?acupoint ?meridian ?special_point_role ?surface_region
WHERE 
{
    # FILTER (?acupoint = 'LU 9').

    ?acupoint_iri TARA:hasMeridian/rdfs:label ?meridian.
    ?acupoint_iri rdfs:subClassOf/rdfs:label "Meridian Acupoint".

    OPTIONAL
    {
        ?acupoint_iri TARA:hasDesignatedSpecialPointRole/rdfs:label ?special_point_role.
    }

    OPTIONAL 
    {   
        ?acupoint_iri TARA:hasSurfaceLocation ?surface_region_iri.
        ?surface_region_iri rdfs:label ?surface_region.
    }

    # Exclude generic superclass like 'Acupoint of the X Meridian.
    FILTER (!regex(str(?acupoint), 'Acupoint of the'))
    ?acupoint_iri rdfs:label ?acupoint.
}
ORDER BY ?meridian ?acupoint
limit 1000
```

**Q. What surface regions are associated with a particular acupoint (e.g., LU 9)?**

```SPARQL
# What surface regions are associated with a particular acupoint (e.g., LU 9)?
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX TARA: <http://www.acupunctureresearch.org/tara/ontology/acupoints.owl#>

SELECT ?acupoint ?related_region ?related_region_iri ?surface_region ?surface_region_iri
WHERE 
{
    FILTER (?acupoint = 'LU 9'). 
    ?acupoint_iri TARA:hasRelatedLocation ?related_region_iri.
    ?acupoint_iri TARA:hasSurfaceLocation ?surface_region_iri.

    ?acupoint_iri rdfs:label ?acupoint.
    ?surface_region_iri rdfs:label ?surface_region.
    ?related_region_iri rdfs:label ?related_region.

}
ORDER BY ?acupoint
limit 10
```

### Query Result

| acupoint | related_region                  | related_region_iri | surface_region | surface_region_iri |
| -------- | ------------------------------- | ------------------ | -------------- | ------------------ |
| LU 9     | abductor pollicis longus tendon | ILX:0795335        | carpal region  | UBERON:0004452     |
| LU 9     | carpal region                   | UBERON:0004452     | carpal region  | UBERON:0004452     |
| LU 9     | palmar wrist crease             | ILX:0795334        | carpal region  | UBERON:0004452     |
| LU 9     | radiale                         | UBERON:0001427     | carpal region  | UBERON:0004452     |
| LU 9     | styloid process of radius       | UBERON:7500078     | carpal region  | UBERON:0004452     |
| LU 9     | radial artery                   | UBERON:0001404     | carpal region  | UBERON:0004452     |

**Q. What surface regions are connected by a given meridian (e.g., lung meridian)?**

```SPARQL
# What surface regions are connected by a given meridian (e.g., lung meridian)?

PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX TARA: <http://www.acupunctureresearch.org/tara/ontology/acupoints.owl#>

SELECT DISTINCT 
    ?meridian ?acupoint
    ?surface_region  ?surface_region_iri
    ?related_region  ?related_region_iri 

WHERE 
{
    FILTER (?meridian = 'Lung Meridian'). 
    # FILTER (?meridian = 'Liver Meridian').
  
    ?acupoint_iri TARA:hasMeridian ?meridian_iri.
    ?acupoint_iri TARA:hasRelatedLocation ?related_region_iri.
    ?acupoint_iri TARA:hasSurfaceLocation ?surface_region_iri.

    ?acupoint_iri rdfs:label ?acupoint.
    ?meridian_iri rdfs:label ?meridian.
    ?surface_region_iri rdfs:label ?surface_region.
    ?related_region_iri rdfs:label ?related_region.
  
    Filter (?related_region != ?surface_region)

}
ORDER BY ?meridian ?acupoint ?surface_region ?related_region
limit 30
```

### Query Result

| meridian      | acupoint | surface_region       | surface_region_iri | related_region                  | related_region_iri |
| ------------- | -------- | -------------------- | ------------------ | ------------------------------- | ------------------ |
| Lung Meridian | LU 1     | anterior chest       | UBERON:0016416     | anterior median line            | ILX:0795285        |
| Lung Meridian | LU 1     | anterior chest       | UBERON:0016416     | first intercostal space         | ILX:0795283        |
| Lung Meridian | LU 1     | anterior chest       | UBERON:0016416     | infraclavicular fossa           | ILX:0795284        |
| Lung Meridian | LU 10    | palmar part of manus | UBERON:0008878     | metacarpal bone of digit 1      | UBERON:0003645     |
| Lung Meridian | LU 11    | manual digit 1       | UBERON:0001463     | distal phalanx                  | UBERON:0004300     |
| Lung Meridian | LU 11    | manual digit 1       | UBERON:0001463     | nail of manual digit 1          | UBERON:0011273     |
| Lung Meridian | LU 2     | anterior chest       | UBERON:0016416     | anterior median line            | ILX:0795285        |
| Lung Meridian | LU 2     | anterior chest       | UBERON:0016416     | clavipectoral triangle          | ILX:0795286        |
| Lung Meridian | LU 2     | anterior chest       | UBERON:0016416     | coracoid process of scapula     | UBERON:0006633     |
| Lung Meridian | LU 2     | anterior chest       | UBERON:0016416     | infraclavicular fossa           | ILX:0795284        |
| Lung Meridian | LU 3     | arm                  | UBERON:0001460     | anterior axillary fold          | ILX:0795287        |
| Lung Meridian | LU 3     | arm                  | UBERON:0001460     | biceps brachii                  | UBERON:0001507     |
| Lung Meridian | LU 4     | arm                  | UBERON:0001460     | anterior axillary fold          | ILX:0795287        |
| Lung Meridian | LU 4     | arm                  | UBERON:0001460     | biceps brachii                  | UBERON:0001507     |
| Lung Meridian | LU 5     | elbow                | UBERON:0001461     | cubital crease                  | ILX:0795332        |
| Lung Meridian | LU 5     | elbow                | UBERON:0001461     | tendon of biceps brachii        | UBERON:0008188     |
| Lung Meridian | LU 6     | forelimb zeugopod    | UBERON:0002386     | carpal region                   | UBERON:0004452     |
| Lung Meridian | LU 6     | forelimb zeugopod    | UBERON:0002386     | palmar wrist crease             | ILX:0795334        |
| Lung Meridian | LU 7     | forelimb zeugopod    | UBERON:0002386     | abductor pollicis longus tendon | ILX:0795335        |
| Lung Meridian | LU 7     | forelimb zeugopod    | UBERON:0002386     | extensor pollicis brevis tendon | ILX:0795336        |
| Lung Meridian | LU 7     | forelimb zeugopod    | UBERON:0002386     | palmar wrist crease             | ILX:0795334        |
| Lung Meridian | LU 8     | forelimb zeugopod    | UBERON:0002386     | palmar wrist crease             | ILX:0795334        |
| Lung Meridian | LU 8     | forelimb zeugopod    | UBERON:0002386     | radial artery                   | UBERON:0001404     |
| Lung Meridian | LU 8     | forelimb zeugopod    | UBERON:0002386     | styloid process of radius       | UBERON:7500078     |
| Lung Meridian | LU 9     | carpal region        | UBERON:0004452     | abductor pollicis longus tendon | ILX:0795335        |
| Lung Meridian | LU 9     | carpal region        | UBERON:0004452     | palmar wrist crease             | ILX:0795334        |
| Lung Meridian | LU 9     | carpal region        | UBERON:0004452     | radial artery                   | UBERON:0001404     |
| Lung Meridian | LU 9     | carpal region        | UBERON:0004452     | radiale                         | UBERON:0001427     |
| Lung Meridian | LU 9     | carpal region        | UBERON:0004452     | styloid process of radius       | UBERON:7500078     |

**Additional example queries will be added based on the use cases of the TARA ontology as part of this section.**
