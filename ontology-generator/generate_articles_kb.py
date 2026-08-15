"""
generate_articles_kb.py — TARA Articles Knowledge-Base Generator

Converts the hand-authored articles-kb core ontology into a numeric-IRI
Turtle file, merges it with the imported MONDO/HP disease-condition terms
and the TARA acupoints ontology, and populates it with article, study, and
OCSI-score individuals sourced from the curated TARA-KB source spreadsheet.
Produces both a "no-upper" and a "with-upper" ontology variant, each with
its own HermiT-reasoned inferred closure.

Base ontology:     ../ontology-files/base/articles-kb/articles-kb-core/tara-articles-kb-core.ttl
Curated source:    ../curated-data/kb-curation-sheets/sources/
Generated output:  ../ontology-files/generated/temp-files/ttl/

Author: Fahim Imam
"""

import json
import math
import os
import subprocess
import sys

import openpyxl
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DC, OWL, RDF, RDFS
from tqdm import tqdm

from lib.ontology_merger import merge_ontologies

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_ontology import AcupointsOntologyAdapter, serialisation_namespaces, TARA, TARA_KB

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)

# --- Base ontology & source file locations ---------------------------------
ARTICLES_KB_BASE_DIR = os.path.join(REPO_ROOT, "ontology-files/base/articles-kb")
ONTOLOGY_BASE_DIR = os.path.join(REPO_ROOT, "ontology-files/base")

ARTICLES_KB_CORE_TTL = os.path.join(ARTICLES_KB_BASE_DIR, "articles-kb-core/tara-articles-kb-core.ttl")
IMPORTED_MONDO_HP_TTL = os.path.join(ARTICLES_KB_BASE_DIR, "imported-conditions/imported-tara-kb-mondo-hp-terms.ttl")
MONDO_HP_BRIDGE_TTL = os.path.join(ARTICLES_KB_BASE_DIR, "imported-conditions/tara-kb-mondo-hp-bridge.ttl")
COLUMN_MAPPING_TTL = os.path.join(ARTICLES_KB_BASE_DIR, "kb-src-column-mappings/tara-kb-src-column-mapping.ttl")
TARA_KB_UPPER_BRIDGE_TTL = os.path.join(ONTOLOGY_BASE_DIR, "bridge-files/tara-kb-upper-bridge.ttl")

# --- Generated output locations ---------------------------------------------
OUTPUT_DIR = os.path.join(REPO_ROOT, "ontology-files/generated/temp-files/ttl")

ARTICLES_KB_OUTPUT_TTL = os.path.join(OUTPUT_DIR, "no-upper/kb/tara-articles-kb.ttl")
KB_NO_UPPER_INFERRED_TTL = os.path.join(OUTPUT_DIR, "no-upper/kb/tara-articles-kb-no-upper-inferred.ttl")

TARA_ONTOLOGY_NO_UPPER_TTL = os.path.join(OUTPUT_DIR, "no-upper/tara-acupoints.ttl")
TARA_ONTOLOGY_WITH_UPPER_TTL = os.path.join(OUTPUT_DIR, "tara-acupoints.ttl")

ARTICLES_KB_WITH_UPPER_TTL = os.path.join(OUTPUT_DIR, "kb/tara-articles-kb-with-upper.ttl")
KB_WITH_UPPER_INFERRED_TTL = os.path.join(OUTPUT_DIR, "kb/tara-articles-kb-inferred.ttl")

# --- Source spreadsheet ------------------------------------------------------
XLSX_SOURCE_FILE = os.path.join(REPO_ROOT, "curated-data/kb-curation-sheets/sources/TARA-KB-Source-112625-Final.xlsx")
XLSX_SHEET_NAME = "All-Articles"
XLSX_SHEET_ACUPOINTS = "Acupoints-List-Mapped"
XLSX_SHEET_TCM_CONDITIONS = "TCM-Conditions-Normalized"
XLSX_SHEET_WESTERN_CONDITIONS = "Western-Conditions-Mapped"

ARTICLE_ID_COLUMN = "TARA-KB:Article_ID"
STUDY_ID_COLUMN = "TARA-KB:Study_ID"
OCSI_ID_COLUMN = "TARA-KB:OCSI_Set_ID"
TITLE_COLUMN = "Title"

ARTICLE_CLASS_LABEL = "Acupuncture Study Publication"
STUDY_CLASS_LABEL = "Acupuncture Research Study"
OCSI_CLASS_LABEL = "Acupuncture Study OCSI Appraisal"

STUDY_METADATA_EXCLUDED_COLUMNS = {
    "Acupoint List",
    "Disease/ Condition (Western)",
    "Disease/ Condition (TCM)",
}

HAS_SOURCE_SHEET_COLUMN_LABEL = TARA["hasSourceSheetColumnLabel"]

# TARA class IRIs use the "TARA_" suffixed namespace (e.g. TARA:5363236 ->
# http://www.acupunctureresearch.org/tara/ontology/TARA_5363236), distinct
# from the "tara:" property namespace bound to TARA_KB above.
TARA_ID = Namespace(serialisation_namespaces["TARA"])


# =============================================================================
#  Console Output Helpers
# =============================================================================

TOTAL_STEPS = 9


def print_step(step_number, description):
    """Prints a banner announcing the start of a top-level pipeline step."""
    banner = "=" * 70
    print(f"\n{banner}\nSTEP {step_number}/{TOTAL_STEPS}: {description}\n{banner}")


# =============================================================================
#  General Helpers
# =============================================================================

def is_blank(value):
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def to_literal(value):
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    elif isinstance(value, str):
        value = value.strip()
    return Literal(value)


def split_values(value, separator=","):
    if is_blank(value):
        return []
    return [v.strip() for v in str(value).split(separator) if v.strip()]


def curie_to_tara_uri(curie):
    """
    Converts a "TARA:<id>" CURIE into its full TARA_<id> class IRI.
    Values that are already full IRIs (e.g. MONDO/HP term URIs) are
    passed through unchanged.
    """
    prefix, separator, local = curie.partition(":")
    if separator and prefix.strip() == "TARA":
        return TARA_ID[local.strip()]
    return URIRef(curie.strip())


def get_columns_between(columns, start_label, end_label, exclude=None):
    """Returns the slice of `columns` from `start_label` to `end_label` (inclusive)."""
    exclude = exclude or set()
    start_idx = columns.index(start_label)
    end_idx = columns.index(end_label)
    return [c for c in columns[start_idx:end_idx + 1] if c not in exclude]


def find_class_uri_by_label(graph, label):
    """
    Resolves a class URI by its rdfs:label, since classes in the merged
    base ontology are keyed by numeric TARA_ identifiers rather than
    their original textual IRI suffixes.
    """
    for subject, object_ in graph.subject_objects(RDFS.label):
        if str(object_) == label:
            return subject
    raise ValueError(f"No class found with rdfs:label {label!r}")


def load_column_property_mapping(mapping_file):
    """
    Parses tara-kb-src-column-mapping.ttl and builds a dict mapping each
    source spreadsheet column header to the tara-kb: annotation property
    that it should be populated into.
    """
    g = Graph()
    g.parse(mapping_file, format="turtle")

    mapping = {}
    for prop, _, column_label in g.triples((None, HAS_SOURCE_SHEET_COLUMN_LABEL, None)):
        for label in str(column_label).split(","):
            mapping[label.strip()] = prop

    return mapping


def read_articles_sheet(xlsx_file, sheet_name):
    """
    Loads every row of `sheet_name` from `xlsx_file` into a list of
    {column_header: cell_value} record dicts, keyed by the header row.
    """
    print(f"\n> Reading Sheet: {sheet_name}")

    workbook = openpyxl.load_workbook(xlsx_file, data_only=True)
    worksheet = workbook[sheet_name]

    rows = worksheet.iter_rows(values_only=True)
    headers = list(next(rows))
    records = [dict(zip(headers, row)) for row in rows]

    print(f"  Read {len(records)} Rows From Sheet: {sheet_name}")
    return headers, records


# =============================================================================
#  Metadata Population
# =============================================================================

def add_publication_metadata(g, records, column_property_mapping, publication_columns, article_class_uri):
    """
    Adds one 'Acupuncture Study Journal Article' named individual per row,
    populated with the article-level columns from Title up to Other_Link.
    """
    print("\n> Adding Publication Metadata...")

    for record in tqdm(records, desc="  Publication Metadata", unit="row"):
        article_id = record.get(ARTICLE_ID_COLUMN)
        study_id = record.get(STUDY_ID_COLUMN)

        if is_blank(article_id):
            continue

        article_uri = TARA_KB[str(article_id).strip()]
        g.add((article_uri, RDF.type, OWL.NamedIndividual))
        g.add((article_uri, RDF.type, article_class_uri))

        if not is_blank(study_id):
            study_uri = TARA_KB[str(study_id).strip()]
            g.add((article_uri, TARA_KB.hasReportedStudy, study_uri))

        for column in publication_columns:
            prop = column_property_mapping.get(column)
            value = record.get(column)
            if prop is None or is_blank(value):
                continue
            g.add((article_uri, prop, to_literal(value)))

    print("  Publication Metadata Added Successfully.")


def add_study_metadata(g, records, column_property_mapping, study_columns, study_class_uri):
    """
    Adds one 'Acupuncture Research Study' named individual per row, tags it
    with a dcterms:title (from the Title column), links it to its reporting
    'Acupuncture Study Journal Article' via tara-kb:hasReportingPublication,
    and populates the study-level columns from Country to Results/Conclusion
    (excluding the acupoint/condition columns handled elsewhere).
    """
    print("\n> Adding Study Metadata...")

    for record in tqdm(records, desc="  Study Metadata", unit="row"):
        study_id = record.get(STUDY_ID_COLUMN)
        article_id = record.get(ARTICLE_ID_COLUMN)
        ocsi_id = record.get(OCSI_ID_COLUMN)

        if is_blank(study_id):
            continue

        study_uri = TARA_KB[str(study_id).strip()]
        g.add((study_uri, RDF.type, OWL.NamedIndividual))
        g.add((study_uri, RDF.type, study_class_uri))

        title = record.get(TITLE_COLUMN)
        if not is_blank(title):
            g.add((study_uri, DC.title, to_literal(title)))

        if not is_blank(article_id):
            article_uri = TARA_KB[str(article_id).strip()]
            g.add((study_uri, TARA_KB.hasReportingPublication, article_uri))
            g.add((article_uri, TARA_KB.hasReportedStudy, study_uri))

        if not is_blank(ocsi_id):
            ocsi_uri = TARA_KB[str(ocsi_id).strip()]
            g.add((study_uri, TARA_KB.hasOCSIAppraisal, ocsi_uri))

        for column in study_columns:
            prop = column_property_mapping.get(column)
            value = record.get(column)
            if prop is None or is_blank(value):
                continue
            g.add((study_uri, prop, to_literal(value)))

    print("  Study Metadata Added Successfully.")


def add_ocsi_score(g, records, column_property_mapping, ocsi_columns, ocsi_class_uri):
    """
    Adds one 'Acupuncture Study OCSI Appraisal' named individual per row,
    tags it with a dcterms:title (from the Title column), and populates
    the OCSI (Oregon CONSORT/STRICTA-based) scoring columns, from
    Introduction and Hypothesis Score through TOTAL %.
    """
    print("\n> Adding OCSI Scores...")

    for record in tqdm(records, desc="  OCSI Scores", unit="row"):
        ocsi_id = record.get(OCSI_ID_COLUMN)
        if is_blank(ocsi_id):
            continue

        ocsi_uri = TARA_KB[str(ocsi_id).strip()]
        g.add((ocsi_uri, RDF.type, OWL.NamedIndividual))
        g.add((ocsi_uri, RDF.type, ocsi_class_uri))

        title = record.get(TITLE_COLUMN)
        if not is_blank(title):
            g.add((ocsi_uri, DC.title, to_literal(title)))

        study_id = record.get(STUDY_ID_COLUMN)
        if not is_blank(study_id):
            article_uri = TARA_KB[str(record.get(ARTICLE_ID_COLUMN)).strip()]
            study_uri = TARA_KB[str(study_id).strip()]
            g.add((ocsi_uri, TARA_KB.hasOCSIInputStudy, study_uri))
            g.add((ocsi_uri, TARA_KB.hasReportingPublication, article_uri))

        for column in ocsi_columns:
            prop = column_property_mapping.get(column)
            value = record.get(column)
            if prop is None or is_blank(value):
                continue
            g.add((ocsi_uri, prop, to_literal(value)))

    print("  OCSI Scores Added Successfully.")


def add_listed_acupoints(g, records):
    """
    From the Acupoints-List-Mapped sheet, populates each study's listed,
    mapped, and unmappable acupoint annotations, along with a JSON
    CURIE-to-label lookup map (hasListedAcupointMap).
    """
    print("\n> Adding Listed Acupoints...")

    for record in tqdm(records, desc="  Listed Acupoints", unit="row"):
        study_id = record.get(STUDY_ID_COLUMN)
        if is_blank(study_id):
            continue

        study_uri = TARA_KB[str(study_id).strip()]

        normalized_acupoints = record.get("Acupoints-Normalized")
        if not is_blank(normalized_acupoints):
            g.add((study_uri, TARA_KB.hasListedAcupoint, Literal(str(normalized_acupoints).strip())))

        mapped_curies = split_values(record.get("Acupoints_TARA_IDs"))
        for curie in mapped_curies:
            g.add((study_uri, TARA_KB.hasMappedAcupoint, curie_to_tara_uri(curie)))

        mapped_labels = split_values(record.get("Acupoints-Mapped"))
        if mapped_curies and mapped_labels:
            acupoint_map = dict(zip(mapped_curies, mapped_labels))
            g.add((study_uri, TARA_KB.hasListedAcupointMap, Literal(json.dumps(acupoint_map), datatype=RDF.JSON)))

        unmappable_acupoints = record.get("Acupoints-Unmappable")
        if not is_blank(unmappable_acupoints):
            g.add((study_uri, TARA_KB.hasUnmappableAcupoint, Literal(str(unmappable_acupoints).strip())))

    print("  Listed Acupoints Added Successfully.")


def add_tcm_conditions(g, records):
    """
    From the TCM-Conditions-Normalized sheet, populates each study's
    hasStudiedTCMCondition annotation from the Normalized-Condition-TCM
    column.
    """
    print("\n> Adding TCM Conditions...")

    for record in tqdm(records, desc="  TCM Conditions", unit="row"):
        study_id = record.get(STUDY_ID_COLUMN)
        condition = record.get("Normalized-Condition-TCM")
        if is_blank(study_id) or is_blank(condition):
            continue

        study_uri = TARA_KB[str(study_id).strip()]
        g.add((study_uri, TARA_KB.hasStudiedTCMCondition, Literal(str(condition).strip())))

    print("  TCM Conditions Added Successfully.")


def add_western_conditions(g, records):
    """
    From the Western-Conditions-Mapped sheet, populates each study's
    hasStudiedWesternCondition annotation from Condition-Extracted-Western
    and hasMappedWesternCondition annotations (one per comma-separated
    URI) from MONDO-OR-HP-Term-URI.
    """
    print("\n> Adding Western Conditions...")

    for record in tqdm(records, desc="  Western Conditions", unit="row"):
        study_id = record.get(STUDY_ID_COLUMN)
        if is_blank(study_id):
            continue

        study_uri = TARA_KB[str(study_id).strip()]

        extracted_condition = record.get("Condition-Extracted-Western")
        if not is_blank(extracted_condition):
            g.add((study_uri, TARA_KB.hasStudiedWesternCondition, Literal(str(extracted_condition).strip())))

        for term_uri in split_values(record.get("MONDO-OR-HP-Term-URI")):
            g.add((study_uri, TARA_KB.hasMappedWesternCondition, URIRef(term_uri)))

    print("  Western Conditions Added Successfully.")


# =============================================================================
#  Reasoning
# =============================================================================

def generate_inferred_ontology(asserted_ttl, inferred_ttl):
    """Runs the HermiT reasoner on `asserted_ttl` and saves its inferred closure to `inferred_ttl`."""
    print(f"\n> Running HermiT Reasoner on: {asserted_ttl}")
    subprocess.run(
        [sys.executable, "lib/hermit_reasoner.py", asserted_ttl, inferred_ttl],
        check=True,
    )
    print(f"  Saved Inferred Ontology At: {inferred_ttl}")


# =============================================================================
#  Main Pipeline
# =============================================================================

def main():
    os.makedirs(os.path.dirname(ARTICLES_KB_OUTPUT_TTL), exist_ok=True)

    print_step(1, "Merging Core Ontology With MONDO/HP Bridge")
    merge_ontologies(MONDO_HP_BRIDGE_TTL, ARTICLES_KB_CORE_TTL, ARTICLES_KB_OUTPUT_TTL, serialisation_namespaces)

    print_step(2, "Loading Base Ontology And Resolving Class URIs")
    adapter = AcupointsOntologyAdapter()
    adapter.addBaseOntology(ARTICLES_KB_OUTPUT_TTL)

    article_class_uri = find_class_uri_by_label(adapter.onology_graph, ARTICLE_CLASS_LABEL)
    study_class_uri = find_class_uri_by_label(adapter.onology_graph, STUDY_CLASS_LABEL)
    ocsi_class_uri = find_class_uri_by_label(adapter.onology_graph, OCSI_CLASS_LABEL)

    print_step(3, "Reading Source Spreadsheet")
    print("  Source File: " + XLSX_SOURCE_FILE)
    headers, records = read_articles_sheet(XLSX_SOURCE_FILE, XLSX_SHEET_NAME)
    column_property_mapping = load_column_property_mapping(COLUMN_MAPPING_TTL)

    publication_columns = get_columns_between(headers, TITLE_COLUMN, "Other_Link")
    study_columns = get_columns_between(
        headers, "Country", "Results/Conclusion", exclude=STUDY_METADATA_EXCLUDED_COLUMNS
    )
    ocsi_columns = get_columns_between(headers, "Introduction and Hypothesis Score", "TOTAL %")

    print_step(4, "Populating Publication, Study, And OCSI-Score Metadata")
    g = Graph()
    add_publication_metadata(g, records, column_property_mapping, publication_columns, article_class_uri)
    add_study_metadata(g, records, column_property_mapping, study_columns, study_class_uri)
    add_ocsi_score(g, records, column_property_mapping, ocsi_columns, ocsi_class_uri)

    print_step(5, "Populating Acupoint And Condition Metadata")
    _, acupoint_records = read_articles_sheet(XLSX_SOURCE_FILE, XLSX_SHEET_ACUPOINTS)
    _, tcm_condition_records = read_articles_sheet(XLSX_SOURCE_FILE, XLSX_SHEET_TCM_CONDITIONS)
    _, western_condition_records = read_articles_sheet(XLSX_SOURCE_FILE, XLSX_SHEET_WESTERN_CONDITIONS)

    add_listed_acupoints(g, acupoint_records)
    add_tcm_conditions(g, tcm_condition_records)
    add_western_conditions(g, western_condition_records)

    print_step(6, "Saving Populated Knowledge Base")
    adapter.addGraph(g)
    adapter.saveUpdatedOntology(ARTICLES_KB_OUTPUT_TTL)

    print_step(7, "Merging KB With Imported MONDO/HP Disease-Condition Terms")
    merge_ontologies(ARTICLES_KB_OUTPUT_TTL, IMPORTED_MONDO_HP_TTL, ARTICLES_KB_OUTPUT_TTL, serialisation_namespaces)

    print_step(8, "Merging KB With TARA Ontology (No Upper) And Running Inference")
    merge_ontologies(
        ARTICLES_KB_OUTPUT_TTL, TARA_ONTOLOGY_NO_UPPER_TTL, ARTICLES_KB_OUTPUT_TTL, serialisation_namespaces
    )
    generate_inferred_ontology(ARTICLES_KB_OUTPUT_TTL, KB_NO_UPPER_INFERRED_TTL)

    print_step(9, "Merging KB With Upper Ontology And Running Inference")
    merge_ontologies(
        ARTICLES_KB_OUTPUT_TTL, TARA_KB_UPPER_BRIDGE_TTL, ARTICLES_KB_WITH_UPPER_TTL, serialisation_namespaces
    )
    merge_ontologies(
        ARTICLES_KB_WITH_UPPER_TTL, TARA_ONTOLOGY_WITH_UPPER_TTL, ARTICLES_KB_WITH_UPPER_TTL, serialisation_namespaces
    )
    generate_inferred_ontology(ARTICLES_KB_WITH_UPPER_TTL, KB_WITH_UPPER_INFERRED_TTL)

    print("\n> End Of Program Execution — All Steps Completed Successfully.\n")


if __name__ == "__main__":
    main()
