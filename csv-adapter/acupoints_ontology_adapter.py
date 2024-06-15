"""
This purpose of this script is to read different CSV files relevant to TARA Acupoints ontology,
extract the csv contents, and transform the contents into generated TARA Acupoints Ontology.
The AcupointsOntologyAdapter is the class with member functions to parse and extract different 
csv files, and transform each of them into corresponding rdf graph, and subsequently merge the graphs 
into TARA Acupoints Ontology file in turtle format. 
- Fahim Imam
"""

import csv, os
from rdflib import Graph, Namespace, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, OWL
from rdflib.collection import Collection

## Declaration of global variables

# Defined namespace prefixes for the URIs in a dictionary
namespaces = {
                "IAO"       :     "http://purl.obolibrary.org/obo/IAO_",
                "RO"        :     "http://purl.obolibrary.org/obo/RO_",
                "BFO"       :     "http://purl.obolibrary.org/obo/BFO_",
                "TARA"      :     "http://www.acupunctureresearch.org/tara/ontology/acupoints.owl#",
                "UBERON"    :     "http://purl.obolibrary.org/obo/UBERON_",
                "OboInOwl"  :     "http://www.geneontology.org/formats/oboInOwl#",
                "swrl"      :     "http://www.w3.org/2003/11/swrl#",
                "dcterms"   :     "http://purl.org/dc/terms/",
                "dc"        :     "http://purl.org/dc/elements/1.1/",
                "protege"   :     "http://protege.stanford.edu/plugins/owl/protege#"
             }

# Ontology files and their relative paths
ontology_files = {
                   "tara-acupoints-upper.ttl"   : "../ontology-files/tara-acupoints-upper.ttl",
                   "tara-acupoints-core.ttl"    : "../ontology-files/tara-acupoints-core.ttl",
                   "tara-acupoints.ttl"         : "../ontology-files/generated/tara-acupoints.ttl" 
                 }

# CSV input files and their relative paths
csv_files =  {
                "meridians.csv"                 : "../csv-files/meridians.csv",
                "acupoints-category.csv"        : "../csv-files/acupoints-category.csv",
                "acupoints.csv"                 : "../csv-files/acupoints.csv",
                "extra-acupoints.csv"           : "../csv-files/extra-acupoints.csv",
                "special-points.csv"            : "../csv-files/special-points.csv",
                "special-points-association.csv": "../csv-files/special-points-association.csv"
             }

# Defined frequently used namespaces
TARA = Namespace(namespaces["TARA"])
UBERON = Namespace(namespaces["UBERON"])
DC = Namespace(namespaces["dc"])

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
        self.setNamespacePrefixes (namespaces) # Set the namespaces.
        
    
    # Load the base ontology from file
    def addBaseOntology(self, file_path):
        print("\n> Adding Base Ontology From: " + file_path)
        self.onology_graph.parse(file_path, format='ttl')
        print ("  Base Ontology Added Successfully.")
    
    def addGraph(self, g):
        self.onology_graph = self.onology_graph + g 
    
    def setNamespacePrefixes (self, namespaces):
        # Binding namespaces to prefixes
        # print ("\nBinding Namespace prefixes is done.")
        for prefix, uri in namespaces.items():
            self.onology_graph.bind(prefix, Namespace(uri))
    
    def saveUpdatedOntology(self, file_path):
        print("\n> Saving Updated Ontology At: " + file_path)
        
        # Serialize the updated graph to a file in turtle format
        self.setNamespacePrefixes (namespaces) #important to respecify the namespaces
        self.onology_graph.serialize(destination=file_path, format='turtle')        
        print ("  Gerenerated Turtle File Location: " + file_path + "\n")
    
    # Add meridians from the corresponding CSV file
    def addMeridians(self, file_path):
        g = Graph()
        print("\n> Adding Meridians From: " + file_path)
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if not any(row.values()): # Skip empty rows
                    continue
                
                meridian, organ, superclass = row['Meridian'], row['Associated Organ'], row['Superclass']
                synonyms, abbreviations = row['Synonym'], row['Abbreviation']
                
                # Create the URI for the meridian
                meridian_uri = create_uri(meridian)

                # Add the meridian
                g.add((meridian_uri, RDF.type, OWL.Class))
                g.add((meridian_uri, RDFS.label, Literal(meridian)))

                # Add each synonym and abbreviation as an annotation property
                if synonyms:
                    for synonym in synonyms.split(','):
                        g.add((meridian_uri, TARA.hasSynonym, Literal(synonym.strip())))
                
                if abbreviations:
                    for abbrev in abbreviations.split(','):
                        g.add((meridian_uri, TARA.hasAbbreviation, Literal(abbrev.strip())))

                # Add the superclass relationship. No need as it will be added as part of the OWL axiom.
                # if superclass:
                #     g.add((meridian_uri, RDFS.subClassOf, URIRef(curie_to_iri(superclass))))    
            
                if organ:
                    # First, add organ entity as an annotation property
                    g.add((meridian_uri, TARA.hasDesignatedOrgan, URIRef(curie_to_iri(organ))))
                    
                    # Then, add OWL restriction for the relation between the meridian category and associated organ.
                    g = g + (self.getOWLAxiom(meridian_uri, RDFS.subClassOf, URIRef(curie_to_iri(superclass)), 
                                            TARA.hasAssociatedOrgan, URIRef(curie_to_iri(organ))))
                
                # If no organ association found eg., for Du Channel and Rn Channel, simply add the superclass
                if not organ:
                    g.add((meridian_uri, RDFS.subClassOf, URIRef(curie_to_iri(superclass))))
        
        self.addGraph(g)
        print ("  Meridians Added Successfully.")
    
    # Add acupoints category from the corresponding CSV file
    def addAcupointsCategory(self, file_path):
        g = Graph()
        print("\n> Adding Acupoint Categories From: " + file_path)
        
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if not any(row.values()):
                    continue
                acupoint = row['Acupoints']
                meridian = row['Meridian']
                synonyms = row['Synonym']

                # Create the URI for the acupoint category
                acupoint_uri = URIRef(create_uri(acupoint))
                # Create the URI for the meridian
                meridian_uri = URIRef(create_uri(meridian))

                # Add the meridian
                g.add((acupoint_uri, RDF.type, OWL.Class))
                g.add((acupoint_uri, RDFS.label, Literal(acupoint)))
                #  g.add ((acupoint_uri, RDFS.subClassOf, TARA.Meridian_Acupoint))

                # Add each synonym as an annotation property
                if synonyms:
                    for synonym in synonyms.split(','):
                        g.add((acupoint_uri, TARA.hasSynonym, Literal(synonym.strip())))            
            
                if meridian:
                    g.add((acupoint_uri, TARA.hasMeridian, meridian_uri))
                    
                    # Then, add OWL restriction for acupoint category and associated meridian.
                    g = g + self.getOWLAxiom(acupoint_uri, OWL.equivalentClass, TARA.Meridian_Acupoint, 
                                             TARA.isMemberAcupointOf, meridian_uri)
        self.addGraph(g)
        print ("  Acupoints Categories Added Successfully.")
        
    # Add acupoints from the corresponding CSV file
    def addAcupoints(self, file_path):
        g = Graph()
        print("\n> Adding Acupoints From: " + file_path)
        
        # Read the CSV file
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if not any(row.values()):
                    continue
                
                acupoint, meridian = row['Acupoint'], row['Meridian']
                synonyms, chinese_names = row['Synonym'], row['Chinese Name']
                location_info, reference, indications = row['WHO Location'], row['Reference'], row ['Indications']
                method, vasculature, innervation = row['Acupuncture Method'], row['Vasculature'], row['Innervation']
               
                # Create the URI for the acupoint
                acupoint_uri = URIRef(create_uri(acupoint))
                
                # Create the URI for the meridian
                meridian_uri = URIRef(create_uri(meridian))

                # Add the meridian
                g.add((acupoint_uri, RDF.type, OWL.Class))
                g.add((acupoint_uri, RDFS.label, Literal(acupoint)))
                # g.add ((acupoint_uri, RDFS.subClassOf, TARA.Meridian_Acupoint))

                # Add each synonym and abbreviation as an annotation property
                if synonyms:
                    for synonym in synonyms.split(','):
                        g.add((acupoint_uri, TARA.hasSynonym, Literal(synonym.strip())))
                
                if chinese_names:
                    for chinese_name in chinese_names.split(','):
                        g.add((acupoint_uri, TARA.hasChineseName, Literal(chinese_name.strip())))
                
                if location_info:
                    g.add((acupoint_uri, TARA.hasLocationalDescription, Literal(location_info)))
                
                if reference:
                    g.add((acupoint_uri, TARA.hasReference, Literal(reference)))
                
                if method:
                    g.add((acupoint_uri, TARA.hasMethodDescription, Literal(method)))
                
                if indications:
                    g.add((acupoint_uri, TARA.hasIndicationsDescription, Literal(indications))) 
                
                if vasculature:
                    g.add((acupoint_uri, TARA.hasVasculatureDescription, Literal(vasculature)))
                
                if innervation:
                    g.add((acupoint_uri, TARA.hasInnervationDescription, Literal(innervation)))
                
                if meridian:
                    # First add meridian entity as an annotation property
                    g.add((acupoint_uri, TARA.hasMeridian, meridian_uri))     
                    
                    g.add ((acupoint_uri, RDFS.subClassOf, TARA.Meridian_Acupoint))
                    self.addSimpleOWLRestriction (g, acupoint_uri, TARA.isMemberAcupointOf, meridian_uri)
                    
                    # Then add OWL restriction to associate the acupoint with corresponding meridan
                    # g = g + self.getOWLAxiom(acupoint_uri, RDFS.subClassOf, TARA.Meridian_Acupoint, 
                    #      TARA.isMemberAcupointOf, meridian_uri)

        self.addGraph(g)
        print ("  Acupoints Added Successfully.")
        
    # Add extra acupoints from the corresponding CSV file
    def addExtraAcupoints(self, file_path):
        g = Graph()
        print("\n> Adding Extra Acupoints From: " + file_path)
        
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if not any(row.values()):
                    continue
                
                acupoint, superclass, synonyms = row['Acupoint'], row['Superclass'], row['Synonym']
                location, indications, method = row['Location'], row['Indications'], row['Acupuncture Method']
                reference = row ['Reference']
              
                # Create the URI for the acupoint category
                acupoint_uri = URIRef(create_uri(acupoint))
                
                # Add the acupoint
                g.add((acupoint_uri, RDF.type, OWL.Class))
                g.add((acupoint_uri, RDFS.label, Literal(acupoint)))
                
                if superclass:
                    g.add ((acupoint_uri, RDFS.subClassOf, TARA.Extra_Acupoint))

                # Add each synonym as an annotation property
                if synonyms:
                    for synonym in synonyms.split(','):
                        g.add((acupoint_uri, TARA.hasSynonym, Literal(synonym.strip())))            
                
                if location:
                    g.add ((acupoint_uri, TARA.hasLocationalDescription, Literal(location)))
                
                if indications:
                    g.add ((acupoint_uri, TARA.hasIndicationsDescription, Literal(indications)))
                
                if method:
                    g.add ((acupoint_uri, TARA.hasMethodDescription, Literal(method)))
                
                if reference:
                    g.add((acupoint_uri, TARA.hasReference, Literal(reference)))
                    
                   
        self.addGraph(g)
        print ("  Extra Acupoints Added Successfully.")
    
    
    # Add special points from the corresponding CSV file
    def addSpecialPoints(self, file_path):
        g = Graph()
        print("\n> Adding Special Points From: " + file_path)
        
        # g = g + self.getOWLAxiom (TARA.Special_Point, OWL.equivalentClass, TARA.Acupoint, 
        #                           TARA.hasSpecialPointDesignation, TARA.Special_Point_Role)
        
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if not any(row.values()):
                    continue
                
                special_point, superclass = row['Special Point'], row['Superclass']
                description, reference = row['Description'], row['Reference']
                                
                # Create the URI for the special point
                special_point_uri = URIRef(create_uri(special_point))

                # Add the special point as an OWL class
                g.add((special_point_uri, RDF.type, OWL.Class))
                g.add((special_point_uri, RDFS.label, Literal(special_point)))
                
                # Add the corresponding special point role as a class
                special_point_role = special_point + " Role"
                special_point_role_uri = URIRef(create_uri(special_point_role))
                
                g.add((special_point_role_uri, RDF.type, OWL.Class))
                g.add((special_point_role_uri, RDFS.label, Literal(special_point_role)))
                
                # Add special point role to the special point as an annotation
                g.add((special_point_uri, TARA.hasDesignatedSpecialPointRole, special_point_role_uri))
                
                if description:
                    g.add ((special_point_uri, DC.description, Literal(description)))
                
                if reference:
                    g.add ((special_point_uri, TARA.hasReference, Literal(reference)))
                
                if superclass:
                    # If the TARA class is specified with namespace TARA:Special_Point
                    
                    if superclass == "TARA:Special_Point":
                        # g.add ((special_point_uri, RDFS.subClassOf, TARA.Special_Point))
                        # Add OWL restriction for the special point using OWL equivalent axiom to classify the meridan acupoints
                        g = g + self.getOWLAxiom(special_point_uri, OWL.equivalentClass, TARA.Special_Point, 
                                                 TARA.hasSpecialPointDesignation, special_point_role_uri)        
                        # Add superclass of the special point role
                        g.add ((special_point_role_uri, RDFS.subClassOf, TARA.Special_Acupoint_Role))
                    else:
                        superclass_uri = URIRef(create_uri(superclass))
                        superclass_role_uri = URIRef(create_uri(superclass + " Role"))
                        # g.add ((special_point_uri, RDFS.subClassOf, superclass_uri))
                        # Add OWL restriction for the special point using OWL equivalent axiom to classify the meridan acupoints
                        g = g + self.getOWLAxiom(special_point_uri, OWL.equivalentClass, superclass_uri, 
                                                 TARA.hasSpecialPointDesignation, special_point_role_uri)
                        # Add superclass of the special point role
                        g.add ((special_point_role_uri, RDFS.subClassOf, superclass_role_uri))
        
        self.addGraph(g)
        print ("  Special Points Added Successfully.")
    
    # Add special points association from the corresponding CSV file
    def addSpecialPointsAssociation(self, file_path):
        g = Graph()
        print("\n> Adding Special Points Association From: " + file_path)
       
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
                g.add((acupoint_uri, RDF.type, OWL.Class))
                g.add((acupoint_uri, RDFS.label, Literal(acupoint)))
                
                if special_point_1:
                    special_point_1_role = special_point_1 + " Role"
                    special_point_1_role_uri = URIRef(create_uri(special_point_1_role))
                    g.add((special_point_1_role_uri, RDF.type, OWL.Class))
                    g.add((acupoint_uri, TARA.hasDesignatedSpecialPointRole, special_point_1_role_uri)) # Add annotation
                    
                    # g = g + self.getOWLAxiom(acupoint_uri, RDFS.subClassOf, TARA.Special_Point, 
                    #                              TARA.hasSpecialPointDesignation, special_point_1_role_uri)
                    
                    self.addSimpleOWLRestriction(g, acupoint_uri, TARA.hasSpecialPointDesignation, special_point_1_role_uri )
                
                if special_point_2:
                    special_point_2_role = special_point_2 + " Role"
                    special_point_2_role_uri = URIRef(create_uri(special_point_2_role))
                    g.add((special_point_2_role_uri, RDF.type, OWL.Class))
                    g.add((acupoint_uri, TARA.hasDesignatedSpecialPointRole, special_point_2_role_uri)) # Add annotation
                    
                    # g = g + self.getOWLAxiom(acupoint_uri, RDFS.subClassOf, TARA.Special_Point, 
                    #                              TARA.hasSpecialPointDesignation, special_point_2_role_uri)
                    
                    self.addSimpleOWLRestriction(g, acupoint_uri, TARA.hasSpecialPointDesignation, special_point_2_role_uri )
                
                if special_point_3:
                    special_point_3_role = special_point_3 + " Role"
                    special_point_3_role_uri = URIRef(create_uri(special_point_3_role))
                    g.add((special_point_3_role_uri, RDF.type, OWL.Class))
                    g.add((acupoint_uri, TARA.hasDesignatedSpecialPointRole, special_point_3_role_uri)) # Add annotation
                    
                    # g = g + self.getOWLAxiom(acupoint_uri, RDFS.subClassOf, TARA.Special_Point, 
                    #                              TARA.hasSpecialPointDesignation, special_point_3_role_uri)
                    
                    self.addSimpleOWLRestriction(g, acupoint_uri, TARA.hasSpecialPointDesignation, special_point_3_role_uri )
        
        self.addGraph(g)
        print ("  Special Points Association Added Successfully.")
    
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
        # a.saveUpdatedOntology(ontology_files.get("tara-acupoints-merged.ttl"))

        a.addMeridians (csv_files.get("meridians.csv"))
        #  a.saveUpdatedOntology(ontology_files.get("tara-acupoints-merged.ttl"))
        
        a.addAcupointsCategory (csv_files.get("acupoints-category.csv"))
        #  a.saveUpdatedOntology(ontology_files.get("tara-acupoints-merged.ttl"))
        
        a.addAcupoints (csv_files.get("acupoints.csv"))
        #  a.saveUpdatedOntology(ontology_files.get("tara-acupoints-merged.ttl"))
        
        a.addExtraAcupoints (csv_files.get("extra-acupoints.csv"))
        #  a.saveUpdatedOntology(ontology_files.get("tara-acupoints-merged.ttl"))
        
        a.addSpecialPoints (csv_files.get("special-points.csv"))
        #  a.saveUpdatedOntology(ontology_files.get("tara-acupoints-merged.ttl"))
        
        a.addSpecialPointsAssociation (csv_files.get("special-points-association.csv"))
        
        a.saveUpdatedOntology(ontology_files.get("tara-acupoints.ttl"))

if __name__ == "__main__":
    main()