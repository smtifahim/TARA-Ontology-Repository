"""
generate_ontology.py — TARA Acupoints Ontology Generator

Reads curated CSV files from ../curated-data/, transforms their contents into RDF graphs,
and produces a set of merged Turtle ontology files under ../ontology-files/generated/ttl/.

The central class, AcupointsOntologyAdapter, provides methods for parsing each CSV file
and populating the corresponding OWL-DL constructs (classes, object properties, annotations,
and restrictions) into an RDFLib graph. After all CSV data is incorporated, the intermediate
graphs are merged with the base ontology files to produce the final output.

Input CSV files:   ../curated-data/acupoints/   (meridians, acupoints, special points, etc.)
Base ontology:     ../ontology-files/base/
Generated output:  ../ontology-files/generated/ttl/

Run directly or via run_all.sh (which also invokes fetch_curated_data.py and hermit_reasoner.py).

Author: Fahim Imam
Last updated: July 8, 2026
"""

import csv, os, subprocess, sys
from rdflib import Graph, Namespace, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, OWL
from rdflib.collection import Collection
from lib.convert_class_iris import convert_iri_suffixes_to_numeric
from lib.ontology_merger import merge_ontologies

## Declaration of global variables

# Defined namespace prefixes for the URIs in a dictionary
namespaces = {
                "IAO"       :     "http://purl.obolibrary.org/obo/IAO_",
                "RO"        :     "http://purl.obolibrary.org/obo/RO_",
                "BFO"       :     "http://purl.obolibrary.org/obo/BFO_",
                "partOf"    :     "http://purl.obolibrary.org/obo/BFO_0000050",
                "obo"       :     "http://purl.obolibrary.org/obo/",
                "tara"      :     "http://www.acupunctureresearch.org/tara/ontology/",
                "tara-kb"   :     "http://www.acupunctureresearch.org/tara/ontology/kb/",
                "TARA"      :     "http://www.acupunctureresearch.org/tara/ontology/",
                "tara-op"   :     "http://www.acupunctureresearch.org/tara/ontology/object-property/",
                "UBERON"    :     "http://purl.obolibrary.org/obo/UBERON_",
                "OboInOwl"  :     "http://www.geneontology.org/formats/oboInOwl#",
                "swrl"      :     "http://www.w3.org/2003/11/swrl#",
                "dcterms"   :     "http://purl.org/dc/terms/",
                "dc"        :     "http://purl.org/dc/elements/1.1/",
                "ILX"       :     "http://uri.interlex.org/base/ilx_",
                "ilxtr"     :     "http://uri.interlex.org/tgbugs/uris/readable/",
                "ilxr"      :     "http://uri.interlex.org/base/readable/",
                "NIFRID"    :     "http://uri.neuinfo.org/nif/nifstd/readable/",
                "FMA"       :     "http://purl.org/sig/ont/fma/fma",
                "HP"        :     "http://purl.obolibrary.org/obo/HP_",
                "MONDO"     :     "http://purl.obolibrary.org/obo/MONDO_",    
                "mondons"   :     "http://purl.obolibrary.org/obo/mondo#",
                "protege"   :     "http://protege.stanford.edu/plugins/owl/protege#"
             }

ONT_BASE_DIR = "../ontology-files/base/"
ONT_GEN_DIR = "../ontology-files/generated/temp-files/ttl/"

# Ontology files and their relative paths
ontology_files = {
                   "tara-acupoints-upper.ttl"              : ONT_BASE_DIR + "tara-acupoints-upper.ttl",                      # Input location for upper acupoints ontology
                   "tara-acupoints-core.ttl"               : ONT_BASE_DIR + "tara-acupoints-core.ttl",                       # Input location for core acupoints ontology
                   "tara-upper-bridge.ttl"                 : ONT_BASE_DIR + "bridge-files/tara-upper-bridge.ttl",            # Input location for upper bridge ontology
                   "tara-imported-anatomical-terms.ttl"    : ONT_BASE_DIR + "tara-imported-anatomical-terms.ttl",            # Input location for imported anatomical terms ontology
                   "tara-metadata-properties.ttl"          : ONT_BASE_DIR + "tara-metadata-properties.ttl",                 # Input location for metadata properties ontology
                   "tara-acupoints-temp.ttl"               : ONT_GEN_DIR + "tmp/tara-acupoints-temp.ttl",          # Temporary location for acupoints ontology
                   "tara-articles-kb-temp.ttl"             : ONT_GEN_DIR + "tmp/tara-articles-kb-temp.ttl",        # Temporary location for articles KB ontology
                   "tara-acupoints-no-upper.ttl"           : ONT_GEN_DIR + "no-upper/tara-acupoints.ttl",          # Output location for acupoints ontology without upper ontology
                   "tara-acupoints-no-upper-inferred.ttl"  : ONT_GEN_DIR + "no-upper/tara-acupoints-inferred.ttl", # Output location for inferred (HermiT) acupoints ontology without upper ontology
                   "tara-acupoints.ttl"                    : ONT_GEN_DIR + "tara-acupoints.ttl",                   # Output location for acupoints ontology with upper ontology
                   "tara-acupoints-inferred.ttl"           : ONT_GEN_DIR + "tara-acupoints-inferred.ttl",           # Output location for inferred (HermiT) acupoints ontology with upper ontology
                 }

# CSV input files and their relative paths
CURATED_DATA_DIR = "../curated-data/ontology-curation-sheet/acupoints/"
csv_files =  {
                "meridians.csv"                 : CURATED_DATA_DIR + "meridians.csv",
                "acupoints-category.csv"        : CURATED_DATA_DIR + "acupoints-category.csv",
                "acupoints.csv"                 : CURATED_DATA_DIR + "acupoints.csv",
                "extra-acupoints.csv"           : CURATED_DATA_DIR + "extra-acupoints.csv",
                "special-points.csv"            : CURATED_DATA_DIR + "special-points.csv",
                "acupoints-locations.csv"       : CURATED_DATA_DIR + "acupoints-locations.csv",
                "special-points-association.csv": CURATED_DATA_DIR + "special-points-association.csv",
                "acupoints-nerves.csv"          : CURATED_DATA_DIR + "acupoints-nerves.csv",
                "acupoints-veins-arteries.csv"  : CURATED_DATA_DIR + "acupoints-veins-arteries.csv"
             }

# Serialization namespaces: split the single TARA prefix into two so that
# class IRIs (…/TARA_NNNNNNN) serialize as TARA:NNNNNNN and property IRIs
# (…/hasSynonym etc.) serialize as tara:hasSynonym.  The main `namespaces`
# dict is kept unchanged so curie_to_iri() continues to work correctly.
serialisation_namespaces = {**namespaces,
                             "TARA": "http://www.acupunctureresearch.org/tara/ontology/TARA_",
                             "tara": "http://www.acupunctureresearch.org/tara/ontology/",
                             "tara-op": "http://www.acupunctureresearch.org/tara/ontology/object-property/",}

# Defined frequently used namespaces
TARA = Namespace(namespaces["tara"])
TARA_OP = Namespace(namespaces["tara-op"])
TARA_KB = Namespace(namespaces["tara-kb"])

UBERON = Namespace(namespaces["UBERON"])
IAO = Namespace(namespaces["IAO"])
ILX = Namespace(namespaces["ILX"])
DC = Namespace(namespaces["dc"])
DCMI = Namespace(namespaces["dcterms"])
partOf = URIRef(namespaces["partOf"])

# Utility functions

# Return a full URI from a given CURIE using the namespaces above.
def curie_to_iri(curie):
    if ':' not in curie:
        raise ValueError("Invalid CURIE format. No prefix found.")
    
    prefix, local_part = curie.split(':', 1)
    
    if prefix in namespaces:
        return namespaces[prefix] + local_part
    else:
        raise ValueError(f"Prefix '{prefix}' not found in the namespace dictionary.")

# Function to create URI from the text string in the csv cell
def create_uri(text_string):
    return TARA[text_string.replace(" ", "_")]
 
class AcupointsOntologyAdapter:
    def __init__(self):
        self.onology_graph = Graph() # Instantiate an empty ontology graph.
        self.setNamespacePrefixes (serialisation_namespaces) # Set the namespaces.
        
    
    # Load the base ontology from file
    def addBaseOntology(self, file_path):
        print("\n> Adding Base Ontology from: " + file_path)
        self.onology_graph.parse(file_path, format='ttl')
        # Remove owl:versionIRI — it belongs in the merged/released files only,
        # not in the intermediate generated tara-acupoints.ttl.
        self.onology_graph.remove((None, OWL.versionIRI, None))
        print ("  Base Ontology Added Successfully.")
    
    def addGraph(self, g):
        self.onology_graph = self.onology_graph + g 
    
    def setNamespacePrefixes (self, namespaces):
        # Binding namespaces to prefixes
        # print ("\nBinding Namespace prefixes is done.")
        for prefix, uri in namespaces.items():
            self.onology_graph.bind(prefix, Namespace(uri))
    
    def saveUpdatedOntology(self, file_path):
        print("\n> Saving Updated Ontology at: " + file_path)
        
        # Serialize the updated graph to a file in turtle format
        self.setNamespacePrefixes (serialisation_namespaces) #important to respecify the namespaces
        self.onology_graph.serialize(destination=file_path, format='turtle')        
        print ("  Gerenerated Turtle File Location: " + file_path + "\n")
    
    # Add meridians from the corresponding CSV file
    def addMeridians(self, file_path):
        g = Graph()
        print("\n> Adding Meridians from: " + file_path)
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if not any(row.values()): # Skip empty rows
                    continue
                
                meridian, organ, superclass = row['Meridian'], row['Associated Organ'], row['Superclass']
                label, synonyms, abbreviations, reference = row['Label'], row['Synonym'], row['Abbreviation'], row['Reference']
                chinese_label = row['Chinese Label']
                # Create the URI for the meridian
                meridian_uri = create_uri(meridian)

                # Add the meridian
                g.add((meridian_uri, RDF.type, OWL.Class))
                g.add((meridian_uri, RDFS.label, Literal(label)))

                # Add each synonym and abbreviation as an annotation property
                if synonyms:
                    for synonym in synonyms.split(','):
                        g.add((meridian_uri, TARA.hasSynonym, Literal(synonym.strip())))
                
                if abbreviations:
                    for abbrev in abbreviations.split(','):
                        g.add((meridian_uri, TARA.hasAbbreviation, Literal(abbrev.strip())))
                        
                if reference:
                    g.add((meridian_uri, DCMI.bibliographicCitation, Literal(reference)))
                    
                if chinese_label:
                    g.add((meridian_uri, TARA.hasChineseLabel, Literal(chinese_label)))
                
                # Add the superclass relationship. No need as it will be added as part of the OWL axiom.
                # if superclass:
                #     g.add((meridian_uri, RDFS.subClassOf, URIRef(curie_to_iri(superclass))))    
            
                if organ:
                    # First, add organ entity as an annotation property
                    g.add((meridian_uri, TARA.hasAssociatedOrgan, URIRef(curie_to_iri(organ))))
                    
                    # Then, add OWL restriction for the relation between the meridian category and associated organ.
                    g = g + (self.getOWLAxiom(meridian_uri, RDFS.subClassOf, URIRef(curie_to_iri(superclass)), 
                                            TARA_OP.hasAssociatedOrgan, URIRef(curie_to_iri(organ))))
                
                # If no organ association found eg., for Du Channel and Rn Channel, simply add the superclass
                if not organ:
                    g.add((meridian_uri, RDFS.subClassOf, URIRef(curie_to_iri(superclass))))
                    
        
        self.addGraph(g)
        print ("  Meridians Added Successfully.")
    
    # Add acupoints category from the corresponding CSV file
    def addAcupointsCategory(self, file_path):
        g = Graph()
        print("\n> Adding Acupoint Categories from: " + file_path)
        
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if not any(row.values()):
                    continue
                acupoint, label, synonyms = row['Acupoints'], row['Label'], row['Synonym']
                meridian = row['Meridian']
                description, reference = row['Description'], row['Reference']

                # Create the URI for the acupoint category
                acupoint_uri = URIRef(create_uri(acupoint))
                # Create the URI for the meridian
                meridian_uri = URIRef(create_uri(meridian))

                # Add the meridian
                g.add((acupoint_uri, RDF.type, OWL.Class))
                g.add((acupoint_uri, RDFS.label, Literal(label)))
                #  g.add ((acupoint_uri, RDFS.subClassOf, TARA.Meridian_Acupoint))

                # Add each synonym as an annotation property
                if synonyms:
                    for synonym in synonyms.split(','):
                        g.add((acupoint_uri, TARA.hasSynonym, Literal(synonym.strip())))            
            
                if meridian:
                    g.add((acupoint_uri, TARA.isLocatedOnMeridian, meridian_uri))
                    
                    # Then, add OWL restriction for acupoint category and associated meridian.
                    g = g + self.getOWLAxiom(acupoint_uri, OWL.equivalentClass, TARA.Meridian_Acupoint, 
                                             TARA_OP.isLocatedOnMeridian, meridian_uri)
        
                if description:
                    g.add((acupoint_uri, DCMI.description, Literal(description)))
                if reference:
                    g.add((acupoint_uri, DCMI.bibliographicCitation, Literal(reference)))
        self.addGraph(g)
        print ("  Acupoints Categories Added Successfully.")
        
    # Add acupoints from the corresponding CSV file
    # TODO: try to see if the annotations can be rendered in the exact sequence they added. e.g. lable, pinyin label, chinese label, meridian, location, indications, method, vasculature, innervation, synonyms, refernces. 
    def addAcupoints(self, file_path):
        g = Graph()
        print("\n> Adding Acupoints from: " + file_path)
        
        # Read the CSV file
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if not any(row.values()):
                    continue
                
                acupoint, label, meridian, superclass = row['Acupoint'], row['Label'], row['Meridian'], row['Superclass']
                synonyms, chinese_names = row['Synonym'], row['Pinyin Label']
                location_info, reference, indications = row['WHO Location'], row['Reference-WHO'], row ['Indications']
                method, vasculature, innervation = row['Acupuncture Method'], row['Vasculature'], row['Innervation']
                chinese_label = row['Chinese Label']
                reference_cam = row['Reference-CAM']
                # Create the URI for the acupoint
                acupoint_uri = URIRef(create_uri(acupoint))
                
                # Create the URI for the meridian
                meridian_uri = URIRef(create_uri(meridian))

                # Add the acupoint
                g.add((acupoint_uri, RDF.type, OWL.Class))
                g.add((acupoint_uri, RDFS.label, Literal(label)))
                # g.add ((acupoint_uri, RDFS.subClassOf, TARA.Meridian_Acupoint))

                # Add superclass of the acupoint if any.
                if superclass:
                    superclass_uri = URIRef(create_uri(superclass))
                    g.add ((acupoint_uri, RDFS.subClassOf, superclass_uri))
                
                # Add each synonym and abbreviation as an annotation property
                if synonyms:
                    for synonym in synonyms.split(','):
                        g.add((acupoint_uri, TARA.hasSynonym, Literal(synonym.strip())))
                
                if chinese_names:
                    for chinese_name in chinese_names.split(','):
                        g.add((acupoint_uri, TARA.hasPinyinLabel, Literal(chinese_name.strip())))
                
                if location_info:
                    g.add((acupoint_uri, TARA.hasLocationalDescription, Literal(location_info)))
                
                if reference:
                    g.add((acupoint_uri, DCMI.bibliographicCitation, Literal(reference)))
                
                if reference_cam:
                    g.add((acupoint_uri, DCMI.bibliographicCitation, Literal(reference_cam)))
                
                if method:
                    g.add((acupoint_uri, TARA.hasMethodDescription, Literal(method)))
                
                if indications:
                    g.add((acupoint_uri, TARA.hasListedIndications, Literal(indications))) 
                
                if vasculature:
                    g.add((acupoint_uri, TARA.hasVasculatureInformation, Literal(vasculature)))
                
                if innervation:
                    g.add((acupoint_uri, TARA.hasInnervationInformation, Literal(innervation)))
                
                if chinese_label:
                    g.add((acupoint_uri, TARA.hasChineseLabel, Literal(chinese_label)))
                
                if meridian:
                    # First add meridian entity as an annotation property
                    g.add((acupoint_uri, TARA.isLocatedOnMeridian, meridian_uri))
                    
                    # Add the inverse relationship for the meridian location
                    g.add((meridian_uri, TARA.isMeridianLocationOf, acupoint_uri))

                                        
                    if not superclass:
                        g = g + self.getOWLAxiom(acupoint_uri, RDFS.subClassOf, TARA.Meridian_Acupoint,
                                                  TARA_OP.isLocatedOnMeridian, meridian_uri)
                        
                        self.addSimpleOWLRestriction(g, meridian_uri, TARA_OP.isMeridianLocationOf, acupoint_uri)

                    
                    # Then add OWL restriction to associate the acupoint with corresponding meridan
                    # g = g + self.getOWLAxiom(acupoint_uri, RDFS.subClassOf, TARA.Meridian_Acupoint, 
                    #      TARA.isMemberAcupointOf, meridian_uri)

        self.addGraph(g)
        print ("  Acupoints Added Successfully.")
        
    # Add extra acupoints from the corresponding CSV file
    def addExtraAcupoints(self, file_path):
        g = Graph()
        print("\n> Adding Extra Acupoints from: " + file_path)
        
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if not any(row.values()):
                    continue
                
                acupoint, superclass, label , synonyms = row['Acupoint'], row['Superclass'], row['Label'], row['Synonym']
                location, indications, method = row['Location'], row['Indications'], row['Acupuncture Method']
                reference = row ['Reference']
                synonyms = row['Synonym']
                reference_syn = row['Reference-Synonym']
              
                # Create the URI for the acupoint category
                acupoint_uri = URIRef(create_uri(acupoint))
                
                # Add the acupoint
                g.add((acupoint_uri, RDF.type, OWL.Class))
                g.add((acupoint_uri, RDFS.label, Literal(label)))
                
                if superclass:
                    if superclass == "TARA:Extra_Acupoint":
                        g.add ((acupoint_uri, RDFS.subClassOf, TARA.Extra_Acupoint))
                    else:
                        g.add ((acupoint_uri, RDFS.subClassOf, URIRef(create_uri(superclass))))


                # Add each synonym as an annotation property
                if synonyms:
                    for synonym in synonyms.split(','):
                        g.add((acupoint_uri, TARA.hasSynonym, Literal(synonym.strip())))            
                
                if location:
                    g.add ((acupoint_uri, TARA.hasLocationalDescription, Literal(location)))
                
                if indications:
                    g.add ((acupoint_uri, TARA.hasListedIndications, Literal(indications)))
                
                if method:
                    g.add ((acupoint_uri, TARA.hasMethodDescription, Literal(method)))
                
                if reference:
                    g.add((acupoint_uri, DCMI.bibliographicCitation, Literal(reference)))
                if reference_syn:
                    g.add((acupoint_uri, DCMI.bibliographicCitation, Literal(reference_syn)))
                   
        self.addGraph(g)
        print ("  Extra Acupoints Added Successfully.")
    
    
    # Add special points from the corresponding CSV file
    def addSpecialPoints(self, file_path):
        g = Graph()
        print("\n> Adding Special Points from: " + file_path)
        
        # g = g + self.getOWLAxiom (TARA.Special_Point, OWL.equivalentClass, TARA.Acupoint, 
        #                           TARA.hasSpecialPointRole, TARA.Special_Point_Role)
        
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if not any(row.values()):
                    continue
                
                special_point, label, superclass = row['Special Point'], row['Label'], row['Superclass']
                description, reference = row['Description'], row['Reference']
                                
                # Create the URI for the special point
                special_point_uri = URIRef(create_uri(special_point))

                # Add the special point as an OWL class
                g.add((special_point_uri, RDF.type, OWL.Class))
                g.add((special_point_uri, RDFS.label, Literal(label)))
                
                # Add the corresponding special point role as a class
                special_point_role = special_point + " Role"
                special_point_role_uri = URIRef(create_uri(special_point_role))
                
                g.add((special_point_role_uri, RDF.type, OWL.Class))
                g.add((special_point_role_uri, RDFS.label, Literal(special_point_role)))
                
                # Add special point role to the special point as an annotation
                g.add((special_point_uri, TARA.hasSpecialPointRole, special_point_role_uri))
                
                if description:
                    g.add ((special_point_uri, DCMI.description, Literal(description)))
                
                if reference:
                    g.add ((special_point_uri, DCMI.bibliographicCitation, Literal(reference)))
                
                if superclass:
                    # If the TARA class is specified with namespace TARA:Special_Point
                    
                    if superclass == "TARA:Special_Point":
                        # g.add ((special_point_uri, RDFS.subClassOf, TARA.Special_Point))
                        # Add OWL restriction for the special point using OWL equivalent axiom to classify the meridan acupoints
                        g = g + self.getOWLAxiom(special_point_uri, OWL.equivalentClass, TARA.Special_Point, 
                                                 TARA_OP.hasSpecialPointRole, special_point_role_uri)        
                        # Add superclass of the special point role
                        g.add ((special_point_role_uri, RDFS.subClassOf, TARA.Special_Acupoint_Role))
                    else:
                        superclass_uri = URIRef(create_uri(superclass))
                        superclass_role_uri = URIRef(create_uri(superclass + " Role"))
                        # g.add ((special_point_uri, RDFS.subClassOf, superclass_uri))
                        # Add OWL restriction for the special point using OWL equivalent axiom to classify the meridan acupoints
                        g = g + self.getOWLAxiom(special_point_uri, OWL.equivalentClass, superclass_uri, 
                                                 TARA_OP.hasSpecialPointRole, special_point_role_uri)
                        # Add superclass of the special point role
                        g.add ((special_point_role_uri, RDFS.subClassOf, superclass_role_uri))
        
        self.addGraph(g)
        print ("  Special Points Added Successfully.")
    
    # Add special points association from the corresponding CSV file
    def addSpecialPointsAssociation(self, file_path):
        g = Graph()
        print("\n> Adding Special Points Association from: " + file_path)
       
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if not any(row.values()):
                    continue
                acupoint = row['Acupoint']
                special_point_1 = row["Special-Point-1"]
                special_point_2 = row["Special-Point-2"]
                special_point_3 = row["Special-Point-3"]
                
                # Create the URI for the acupoint
                acupoint_uri = URIRef(create_uri(acupoint))

                # Add the acupoint as an OWL class
            #    g.add((acupoint_uri, RDF.type, OWL.Class))
            #    g.add((acupoint_uri, RDFS.label, Literal(acupoint))) # acupoint class created already as part of addAcupoints() function
                
                if special_point_1:
                    special_point_1_role = special_point_1 + " Role"
                    special_point_1_role_uri = URIRef(create_uri(special_point_1_role))
                    g.add((special_point_1_role_uri, RDF.type, OWL.Class))
                    g.add((acupoint_uri, TARA.hasSpecialPointRole, URIRef(create_uri(special_point_1)))) # Add annotation
                    
                    # g = g + self.getOWLAxiom(acupoint_uri, RDFS.subClassOf, TARA.Special_Point, 
                    #                              TARA.hasSpecialPointRole, special_point_1_role_uri)
                    
                    self.addSimpleOWLRestriction(g, acupoint_uri, TARA_OP.hasSpecialPointRole, special_point_1_role_uri )
                
                if special_point_2:
                    special_point_2_role = special_point_2 + " Role"
                    special_point_2_role_uri = URIRef(create_uri(special_point_2_role))
                    g.add((special_point_2_role_uri, RDF.type, OWL.Class))
                    g.add((acupoint_uri, TARA.hasSpecialPointRole, URIRef(create_uri(special_point_2)))) # Add annotation
                    
                    # g = g + self.getOWLAxiom(acupoint_uri, RDFS.subClassOf, TARA.Special_Point, 
                    #                              TARA.hasSpecialPointRole, special_point_2_role_uri)
                    
                    self.addSimpleOWLRestriction(g, acupoint_uri, TARA_OP.hasSpecialPointRole, special_point_2_role_uri )
                
                if special_point_3:
                    special_point_3_role = special_point_3 + " Role"
                    special_point_3_role_uri = URIRef(create_uri(special_point_3_role))
                    g.add((special_point_3_role_uri, RDF.type, OWL.Class))
                    g.add((acupoint_uri, TARA.hasSpecialPointRole, URIRef(create_uri(special_point_3)))) # Add annotation
                    
                    # g = g + self.getOWLAxiom(acupoint_uri, RDFS.subClassOf, TARA.Special_Point, 
                    #                              TARA.hasSpecialPointRole, special_point_3_role_uri)
                    
                    self.addSimpleOWLRestriction(g, acupoint_uri, TARA_OP.hasSpecialPointRole, special_point_3_role_uri )
        
        self.addGraph(g)
        print ("  Special Points Association Added Successfully.")

 # Add surface location associated with each acupoint from the corresponding CSV file
    def addSurfaceLocations(self, file_path):
        g = Graph()
        print("\n> Adding Surface Locations for the Acupoints from: " + file_path)
       
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if not any(row.values()):
                    continue
                acupoint = row['Acupoint']
                acupoint_location = row['Identified Locations URI']
                locational_relation = row ['Relation']                
                # Create the URI for the acupoint
                acupoint_uri = URIRef(create_uri(acupoint))
             
                if acupoint_location:
                    # Only use the locations from ILX or UBERON. 
                    # Exclude FMA for now as they will have corresponding ILX URI in the future.
                    if  'fma' not in acupoint_location:
                        acupoint_location_uri = URIRef(acupoint_location)
                        g.add((acupoint_location_uri, RDF.type, OWL.Class))
                                        
                        if locational_relation == "TARA:locatedOnTheSurfaceOf":
                            g.add ((acupoint_uri, TARA.hasGeneralSurfaceLocation, acupoint_location_uri)) # Add annotation

                        if locational_relation == "TARA:locatedInRelationTo":
                            g.add ((acupoint_uri, TARA.hasSpecificReferenceLocation, acupoint_location_uri)) # Add annotation
                        
                        if locational_relation == "TARA:locatedOnTheSurfaceOf":
                            # locatedOnTheSurfaceOf some (partOf some acupoint_location_uri)
                            inner_restriction = BNode()
                            g.add((inner_restriction, RDF.type, OWL.Restriction))
                            g.add((inner_restriction, OWL.onProperty, partOf))
                            g.add((inner_restriction, OWL.someValuesFrom, acupoint_location_uri))
                            self.addSimpleOWLRestriction(g, acupoint_uri, TARA_OP.hasGeneralSurfaceLocation, inner_restriction)
                        elif locational_relation == "TARA:locatedInRelationTo":
                            # locatedInRelationTo some (partOf some acupoint_location_uri)
                            inner_restriction = BNode()
                            g.add((inner_restriction, RDF.type, OWL.Restriction))
                            g.add((inner_restriction, OWL.onProperty, partOf))
                            g.add((inner_restriction, OWL.someValuesFrom, acupoint_location_uri))
                            self.addSimpleOWLRestriction(g, acupoint_uri, TARA_OP.hasSpecificReferenceLocation, inner_restriction)
                        else:
                            self.addSimpleOWLRestriction(g, acupoint_uri, URIRef(curie_to_iri(locational_relation)), acupoint_location_uri)
    
        self.addGraph(g)
        print ("  Surface Locations for the Acupoints Added Successfully.")    
    
    # Add innervation (nerve locations) associated with each acupoint from the corresponding CSV file
    def addInnervation(self, file_path):
        g = Graph()
        print("\n> Adding Innervation for the Acupoints from: " + file_path)

        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if not any(row.values()):
                    continue

                acupoint          = row['Acupoint']
                nerve_location    = row['Nerve Location URI']
                nerve_relation    = row['Nerve Relation']

                # Create the URI for the acupoint
                acupoint_uri = URIRef(create_uri(acupoint))

                if nerve_location:
                    nerve_location_uri = URIRef(nerve_location)

                    # Annotation: TARA.hasRelatedNerve with the nerve location URI
                    g.add((acupoint_uri, TARA.hasRelatedNerve, nerve_location_uri))

                    # OWL axiom: subClassOf restriction using TARA_OP.hasRelatedNerve
                    if nerve_relation:
                        self.addSimpleOWLRestriction(g, acupoint_uri,
                                                     TARA_OP.hasRelatedNerve,
                                                     nerve_location_uri)

        self.addGraph(g)
        print ("  Innervation for the Acupoints Added Successfully.")

    # Add vasculature (veins and arteries) associated with each acupoint from the corresponding CSV file
    def addVasculature(self, file_path):
        g = Graph()
        print("\n> Adding Vasculature for the Acupoints from: " + file_path)

        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if not any(row.values()):
                    continue

                acupoint            = row['Acupoint']
                vasculature_uri_str = row['Vasculature URI']
                vasculature_relation = row['Vasculature Relation']

                # Create the URI for the acupoint
                acupoint_uri = URIRef(create_uri(acupoint))

                if vasculature_uri_str:
                    vasculature_uri = URIRef(vasculature_uri_str)

                    if vasculature_relation == "TARA:hasRelatedVein":
                        # Annotation
                        g.add((acupoint_uri, TARA.hasRelatedVein, vasculature_uri))
                        # OWL axiom
                        self.addSimpleOWLRestriction(g, acupoint_uri,
                                                     TARA_OP.hasRelatedVein,
                                                     vasculature_uri)

                    elif vasculature_relation == "TARA:hasRelatedArtery":
                        # Annotation
                        g.add((acupoint_uri, TARA.hasRelatedArtery, vasculature_uri))
                        # OWL axiom
                        self.addSimpleOWLRestriction(g, acupoint_uri,
                                                     TARA_OP.hasRelatedArtery,
                                                     vasculature_uri)

        self.addGraph(g)
        print ("  Vasculature for the Acupoints Added Successfully.")

    
    # To add a restriction like :class_x isEquivalentTo (:y and :hasProperty some :z) to the graph
    # To add a restriction like :class_x isSubClassOf (:y and :hasProperty some :z) to the graph
    # Note: restriction_type must be one of OWL.equivalentClass or RDFS.isSubclussOf
    def getOWLAxiom(self, class_x, restriction_type, genus_class, hasProperty, restriction_value):
        r_graph = Graph() # restriction subgraph.
        
        # Create blank nodes
        anonymous_class_bnode = BNode()
        intersection_bnode = BNode()
        restriction_bnode = BNode()
        
        # class_uri = genus_class
        # property_uri = hasProperty
        # restriction_uri = restriction_value

        # Add triples for a given class_x
        r_graph.add((class_x, RDF.type, OWL.Class))
        
        if (restriction_type == OWL.equivalentClass):
            r_graph.add((class_x, OWL.equivalentClass, anonymous_class_bnode))
        if (restriction_type == RDFS.subClassOf):
            r_graph.add((class_x, RDFS.subClassOf, anonymous_class_bnode))

        # Add triples for the equivalent class and intersection
        r_graph.add((anonymous_class_bnode, RDF.type, OWL.Class))
        r_graph.add((anonymous_class_bnode, OWL.intersectionOf, intersection_bnode))

        # Create the RDF collection for owl:intersectionOf
        intersection_list = [genus_class, restriction_bnode]
        Collection(r_graph, intersection_bnode, intersection_list)

        # Define the restriction
        r_graph.add((restriction_bnode, RDF.type, OWL.Restriction))
        r_graph.add((restriction_bnode, OWL.onProperty, hasProperty))
        r_graph.add((restriction_bnode, OWL.someValuesFrom, restriction_value))
        return r_graph
    
    # To add OWL restrictions without intersecting with genus. 
    # Example :a :hasProperty some :x
    def addSimpleOWLRestriction (self, g, sub, property, obj):
        # First, create a blank node for the restriction
        restriction_node = BNode()
        # Then, add triples for the restriction
        g.add((restriction_node, RDF.type, OWL.Restriction))
        g.add((restriction_node, OWL.onProperty, property))
        g.add((restriction_node, OWL.someValuesFrom, obj))

        # Add the restriction to the special point class
        g.add((sub, RDFS.subClassOf, restriction_node))
        
        #return g

def main():
        # Instantiate the Adepter       
        a = AcupointsOntologyAdapter()
        
        a.addBaseOntology (ontology_files.get("tara-acupoints-core.ttl"))
        # a.saveUpdatedOntology(ontology_files.get("tara-acupoints.ttl"))

        a.addMeridians (csv_files.get("meridians.csv"))
        #  a.saveUpdatedOntology(ontology_files.get("tara-acupoints.ttl"))
        
        a.addAcupointsCategory (csv_files.get("acupoints-category.csv"))
        #  a.saveUpdatedOntology(ontology_files.get("tara-acupoints.ttl"))
        
        a.addAcupoints (csv_files.get("acupoints.csv"))
        #  a.saveUpdatedOntology(ontology_files.get("tara-acupoints.ttl"))
        
        a.addExtraAcupoints (csv_files.get("extra-acupoints.csv"))
        #  a.saveUpdatedOntology(ontology_files.get("tara-acupoints.ttl"))
        
        a.addSpecialPoints (csv_files.get("special-points.csv"))
        #  a.saveUpdatedOntology(ontology_files.get("tara-acupoints.ttl"))
        
        a.addSpecialPointsAssociation (csv_files.get("special-points-association.csv"))
        #  a.saveUpdatedOntology(ontology_files.get("tara-acupoints.ttl"))
        
        a.addSurfaceLocations (csv_files.get("acupoints-locations.csv"))
        #  a.saveUpdatedOntology(ontology_files.get("tara-acupoints.ttl"))

        a.addInnervation (csv_files.get("acupoints-nerves.csv"))
        #  a.saveUpdatedOntology(ontology_files.get("tara-acupoints.ttl"))

        a.addVasculature (csv_files.get("acupoints-veins-arteries.csv"))
        #  a.saveUpdatedOntology(ontology_files.get("tara-acupoints.ttl"))
        
        a.saveUpdatedOntology(ontology_files.get("tara-acupoints-temp.ttl"))
        
        # Path to the Turtle files for IRI conversions
        input_ttl_file = ontology_files.get("tara-acupoints-temp.ttl")
        output_ttl_file = ontology_files.get("tara-acupoints-temp.ttl") # saving the output in the same input ttl
        
        print ("> Converting Textual IRI Suffixes into Numeric Values for: " +  input_ttl_file)  
        convert_iri_suffixes_to_numeric(input_ttl_file, output_ttl_file)
        
        print ("\n Generating TARA Acupoints Ontology with no upper-level ontology classes...")
        print ("\n> Merging Generated Ontology with Imported Anatomical Terms from: " + ontology_files.get("tara-imported-anatomical-terms.ttl"))
        merge_ontologies (output_ttl_file, ontology_files.get("tara-imported-anatomical-terms.ttl"),
                          ontology_files.get("tara-acupoints-no-upper.ttl"), serialisation_namespaces)
        merge_ontologies (ontology_files.get("tara-acupoints-no-upper.ttl"), ontology_files.get("tara-metadata-properties.ttl"),
                                  ontology_files.get("tara-acupoints-no-upper.ttl"), serialisation_namespaces)
        print ("\n Saved TARA Acupoints Ontology with No Upper-Level Classes At: " + ontology_files.get("tara-acupoints-no-upper.ttl"))

        print ("\n> Running HermiT Reasoner on: " + ontology_files.get("tara-acupoints-no-upper.ttl"))
        subprocess.run(
            [sys.executable, "lib/hermit_reasoner.py",
             ontology_files.get("tara-acupoints-no-upper.ttl"),
             ontology_files.get("tara-acupoints-no-upper-inferred.ttl")],
            check=True
        )
        print ("\n Saved Inferred TARA Acupoints Ontology At: " + ontology_files.get("tara-acupoints-no-upper-inferred.ttl"))


        
        print ("\n> Merging Generated Ontology with Upper Ontology from: " + ontology_files.get("tara-acupoints-upper.ttl"))
        merge_ontologies (output_ttl_file, ontology_files.get("tara-acupoints-upper.ttl"),
                          ontology_files.get("tara-acupoints.ttl"), serialisation_namespaces)
        
        # Merge tara-upper-levelbridge ontology next
        merge_ontologies (ontology_files.get("tara-acupoints.ttl"), ontology_files.get("tara-upper-bridge.ttl"),
                                  ontology_files.get("tara-acupoints.ttl"), serialisation_namespaces)
        
        print ("\n> Merging Generated Ontology with Imported Anatomical Terms from: " + ontology_files.get("tara-imported-anatomical-terms.ttl"))
        merge_ontologies (ontology_files.get("tara-acupoints.ttl"), ontology_files.get("tara-imported-anatomical-terms.ttl"),
                          ontology_files.get("tara-acupoints.ttl"), serialisation_namespaces)
        
        print ("\n> Running HermiT Reasoner on: " + ontology_files.get("tara-acupoints.ttl"))
        subprocess.run(
            [sys.executable, "lib/hermit_reasoner.py",
             ontology_files.get("tara-acupoints.ttl"),
             ontology_files.get("tara-acupoints-inferred.ttl")],
            check=True)
        print ("\n Saved Inferred TARA Acupoints Ontology At: " + ontology_files.get("tara-acupoints-inferred.ttl"))   
        print ("\n> End of Program Execution. All Steps Executed Succussfully.\n")

if __name__ == "__main__":
    main()