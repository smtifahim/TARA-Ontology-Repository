# TARA Acupoints Ontology

1. [About TARA Acupoints Ontology](#about-tara-acupoints-ontology)
2. [Ontology Versions Summary](#ontology-versions-summary)
   + [Version 0.5.1 (July 10, 2024)](#exploring-the-ontology-in-webprotégé)
   + [Version 0.5 (June 4, 2024)](#ontology-versions-summary)
3. [Accessing and Exploring the Ontology](#accessing-and-exploring-the-ontology)
   + [Loading the Ontology in Protégé Desktop](#loading-the-ontology-in-protégé-desktop)
   + [Exploring the Ontology in WebProtégé](#exploring-the-ontology-in-webprotégé)
4. [Examples of the Basic Hierarchies](#examples-of-the-basic-hierarchies)
    + [Hierarchy of the Meridians](#hierarchy-of-the-meridians)
    + [Hierarchy of the Meridian Acupoints](#hierarchy-of-the-meridian-acupoints)
    + [Classification of the Special Acupoints](#classification-of-the-special-acupoints)
    + [Inferred Subclasses of a Special Point](#inferred-subclasses-of-a-special-point)
4. [Basic Model of Relationships](#basic-model-of-relationships)
5. [DL Query Examples](#dl-query-examples)

## About TARA Acupoints Ontology

The TARA Acupoints Ontology is an ontology being developed as part of the [Topological Atlas and Repository for Acupoint Research (TARA)](https://www.acupunctureresearch.org/tara) project funded by the National Institute of Health (NIH). The goal of the project is to establish a new comprehensive resource for the acupuncture research and clinician community. The ontology will be used to support semantic search and annotations for anatomical maps, atlases, and data sets relevant to the TARA project. The ontology takes into account both Eastern and Western nomenclature for acupuncture points. The current scope of the ontology is to develop the semantic modelling of the anatomical and physiological aspects associated with different acupoints located in the main meridians.

Closely following the [Open Biomedical Ontology Foundry](https://obofoundry.org/principles/fp-000-summary.html) (OBO Foundry) principles, the TARA Acupoints Ontology is being developed to support the best practices recommeded by the FAIR principles. These practices include utilizing existing community ontologies where possible, e.g., the Foundational Model of Anatomy (FMA) or UBERON for common anatomical structures, and the use of upper level ontologies like [Basic Formal Ontology (BFO)](https://basic-formal-ontology.org/) and [Relation Ontology (RO)](https://obofoundry.org/ontology/ro.html) ensuring maximum interoperability with other ontologies in biomedical domain. [Navigate to this page](../) to know more about the upper level layers of the TARA Acupoints Ontology.

## Ontology Versions Summary

This section will be updated periodically based on the release of the newer versions of the ontology.

### Version 0.5.1 (July 10, 2024)

* All the textual IRI suffixes of the class IRIs are automatically converted to numeric suffixes.
  * Example: the OWL class `TARA:Meridian_Acupoint` is converted to `TARA:TARA_5151019`

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

The most recent version of the TARA Acupoints Ontology is [linked here](https://raw.githubusercontent.com/smtifahim/TARA-Ontology-Repository/master/ontology-files/generated/tara-acupoints.ttl). The easiest way to explore the ontology is to load it in **Protégé**. Protégé is a free, open-source ontology editor which you can download from [this link](https://protege.stanford.edu/software.php#desktop-protege).

### Loading the Ontology in Protégé Desktop

* Make sure to download the Protégé Desktop Version 5.5.X or higher. If you are not familiar with the Protégé interface there is a "Getting Started" document [linked here](https://protegeproject.github.io/protege/getting-started/).
* Click `File > Open From URL..` in Protégé and copy/paste the [**TARA Acupoints Ontology Link**](https://raw.githubusercontent.com/smtifahim/TARA-Ontology-Repository/master/ontology-files/generated/tara-acupoints.ttl) under the `URI` field. Clicking the `OK` button will load the ontology in Protege.

![1718383103389](image/readme/1718383103389.png)

The screenshot above is from TARA Acupoints Ontology Version 0.5.

### Exploring the Ontology in WebProtégé

The inferred version of the TARA Acupoints Ontology is available explore via the **WebProtégé**. WebProtégé is an open source, lightweight, web-based ontology viewer and editor. The ontology is available in WebProtégé *only for viewing and commenting*. The idea is to gather feedback from acupoint experts.

* If you don't have an account in WebProtégé, [create an account using this link](https://webprotege.stanford.edu/#accounts/new).
* Simply navigate to the following link: [TARA Acupoints Ontology in WebProtege](https://webprotege.stanford.edu/#projects/7c97eaa5-7c13-4a73-ab3c-5cb6eeec4fb4/edit/Classes?selection=Class(%3Chttp://www.acupunctureresearch.org/tara/ontology/acupoints.owl%23TARA_5151019%3E))
* If you are new to WebProtégé, please visit the [WebProtégé User Guide]().

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
