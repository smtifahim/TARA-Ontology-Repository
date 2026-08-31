# TARA Articles KB Metadata — Core Ontology

### [Click here to browse this ontology interactively](https://smtifahim.github.io/TARA-Ontology-Repository/articles-kb-core/)

## Purpose

`tara-articles-kb-core.ttl` is the single source of truth for the metadata schema used to capture extracted information from acupuncture clinical trial publications. It exists to solve a recurring ETL problem: metadata extracted via AI tools (Elicit, Gemini, etc.) arrived with inconsistent column names and prompting from batch to batch, which forced the ingestion/transformation scripts to be rewritten every time, and no standardized database schema existed to load into.

This ttl is designed to drive three things directly, so extraction, transformation, and load all stay consistent with one another:

1. **Extraction** — a data dictionary precise enough to generate standardized extraction instructions (prompts) per metadata element for the AI extraction step.
2. **Transformation** — consistent CSV/Excel headers and SPARQL query templates, generated from the ontology rather than hand-maintained.
3. **Load** — a relational database schema derived from the same property definitions used in the RDF graph, so the graph and relational representations never drift apart.

Every annotation property carries `rdfs:label` (human name), `skos:altLabel` (machine-safe column/field name), `dcterms:description` (formal definition), `obo:IAO_0000112` (worked examples), `rdfs:comment` (normalization rules), `rdfs:domain`/`rdfs:range` (owning class / expected value type), and `dcterms:type tara-kb:grouping` where the property is purely organizational and never holds a value itself.

**Status note:** the `obo:IAO_0000112` example values and OCSI scoring rubrics currently in the file are a preliminary starting point and have not yet been verified as authoritative — treat them as draft until reviewed. See also the [LLM Extraction Prompt](#llm-extraction-prompt) section below.

## ETL Architecture

`tara-articles-kb-core.ttl` is not just documentation of the schema — it is the single generation source every downstream artifact is built from. Rather than each ETL stage (extraction prompts, CSV headers, SPARQL, DB schema) hand-maintaining its own copy of "what the fields are," a generator reads the ttl once into a canonical field manifest, and every artifact is derived from that manifest. Adding or renaming a field happens in one place instead of four.

```mermaid
flowchart TB
    classDef core fill:#e8f0ff,stroke:#4472c4,stroke-width:2px,color:#1a3a6b
    classDef gen fill:#eee,stroke:#999,color:#333
    classDef artifact fill:#ffffff,stroke:#333,color:#111
    classDef stage fill:#fef6e0,stroke:#c9960c,color:#5c4400

    TTL["<b>tara-articles-kb-core.ttl</b><br/>single source of truth:<br/>fields, labels, definitions, <br/>examples, normalization rules, types"]:::core

    subgraph BUILD["artifacts-generator/ — generated once per ontology change"]
        REFLECT["ontology_manifest.py<br/>(one SPARQL reflection query)"]:::gen
        MANIFEST["field-manifest.json<br/>(canonical intermediate)"]:::artifact
        PROMPT_GEN["generate_llm_prompts.py"]:::gen
        CSV_GEN["generate_csv_template.py"]:::gen
        SPARQL_GEN["generate_sparql_templates.py"]:::gen
        DB_GEN["generate_db_schema.py"]:::gen

        PROMPTS["extraction-prompts.json"]:::artifact
        CSV["articles-kb-extraction-template.xlsx<br/>(headers = skos:altLabel)"]:::artifact
        SPARQL["select_article_metadata.rq"]:::artifact
        DDL["articles_kb_schema.sql"]:::artifact

        REFLECT --> MANIFEST
        MANIFEST --> PROMPT_GEN --> PROMPTS
        MANIFEST --> CSV_GEN --> CSV
        MANIFEST --> SPARQL_GEN --> SPARQL
        MANIFEST --> DB_GEN --> DDL
    end

    TTL --> REFLECT

    subgraph RUN["ETL Pipeline — runs every extraction batch"]
        direction LR
        EXTRACT["<b>Extract</b><br/>Elicit / Gemini reads full-text<br/>articles per field-level prompt"]:::stage
        RAW["Raw Excel<br/>(one row per study)"]:::stage
        TRANSFORM["<b>Transform</b><br/>ingestion scripts map columns<br/>to ontology properties"]:::stage
        LOADG["<b>Load</b><br/>RDF graph<br/>(tara-articles-kb.ttl instances)"]:::stage
        LOADD["<b>Load</b><br/>Relational DB<br/>(Publication / Study / OCSI tables)"]:::stage
    end

    PROMPTS -. "same prompt,<br/>every batch" .-> EXTRACT
    EXTRACT --> RAW
    CSV -. "defines column<br/>headers for" .-> RAW
    RAW --> TRANSFORM
    SPARQL -. "used to validate/<br/>query result" .-> LOADG
    TTL -. "defines classes &<br/>properties asserted by" .-> TRANSFORM
    TRANSFORM --> LOADG
    TRANSFORM --> LOADD
    DDL -. "defines table/column<br/>schema for" .-> LOADD
```

**Why this fixes the original ETL problem:** the ttl's `skos:altLabel` becomes the column name used by both the CSV template *and* the extraction output, so there's no separate mapping step and no drift between the field the LLM was asked for and the field the transform script expects. The `dcterms:description` / `obo:IAO_0000112` / `rdfs:comment` on each property become the extraction prompt and its scoring rubric, injected verbatim every run instead of re-written by whoever is prompting that batch — the direct fix for inconsistent OCSI scores. And `rdfs:range` / `rdfs:domain` drive the DB column types and table assignment, so the relational schema and the RDF graph are generated from the same definitions and can't drift apart.

## Contents

- **`tara-articles-kb-core.ttl`** — the canonical, hand-authored ontology.
- **`tara-articles-kb-core-draft.ttl`** — working draft / staging area for property changes before they're promoted into the core file.
- **`artifacts-generator/`** — generator scripts, one subdirectory per artifact type, each producing the correspondingly-named folder under `generated-artifacts/`. Each script parses `tara-articles-kb-core.ttl` directly with `rdflib`; introduce a shared `ontology_manifest.py` reflection step once more than one generator needs the same field-level traversal. (`docs-generator/` used to live here but has moved — see below — since it's generic across ontologies rather than specific to this one.)
  - `manifest/` — *(not yet implemented)* will hold `ontology_manifest.py`, the intended canonical field-reflection generator other scripts can share.
  - `csv-templates/` — *(not yet implemented)* will hold the CSV/Excel extraction-template generator.
  - `db-schema/` — *(not yet implemented)* will hold the relational DDL generator.
  - `sparql-templates/` — *(not yet implemented)* will hold the canned SPARQL query-template generator.
  - `llm-prompts/` — *(not yet implemented)* will hold the per-field LLM extraction-prompt generator.
  - `queries/` — *(not yet populated)* reusable SPARQL (`.rq`) query files shared across the generator scripts above.
- Documentation generators now live at repo root in **`ontology-generator/docs-generator/`** (shared across ontologies, not just this one): `generate_documentation.py` (writes `tara-articles-kb-core-doc.md` alongside it — class hierarchy, full `tara-kb:hasTARAArticlesMetadata` property tree with domain/range, and a computed Data Quality Notes section) and `generate_articles_kb_core_html.py` (a thin per-ontology config on top of the shared `lib/ttl_to_html.py` engine, which writes the interactive HTML ontology browser — search/pulldown-autocomplete, expandable trees with a resizable sidebar, browser-history navigation — as `index.html` + `styles.css` to `docs/articles-kb-core/` at the repo root by default, served by GitHub Pages). A future ontology gets its own `generate_<ontology>_html.py` calling into the same `lib/ttl_to_html.py`. Run either with `python3 ontology-generator/docs-generator/<script>.py [--ttl PATH] [--out PATH]`.
- **`generated-artifacts/`** — build output only; never hand-edited; regenerated from `artifacts-generator/`.
  - `manifest/` — the canonical intermediate field manifest (compact URI, column name, definition, example, range, domain, parent grouping) that every other generated artifact is built from.
  - `csv-templates/` — generated Excel/CSV extraction templates.
  - `db-schema/` — generated relational DDL.
  - `sparql-templates/` — generated canned SPARQL query templates.
  - `llm-prompts/` — generated per-field LLM extraction prompt payloads.

## Metadata Structure

Under `tara-kb:hasTARAArticlesMetadata`, extracted metadata is organized into branches aligned with three core classes: `Acupuncture Study Publication`, `Acupuncture Research Study`, and `Acupuncture Study OCSI Appraisal`.

```mermaid
flowchart
style INSTANCES stroke:transparent
    subgraph INSTANCES["<b>Cross-Linked Entity Instances</b>"]
        PUB_ENT[["<b>[Class Instance]</b><br>Acupuncture<br>Study Publication"]]
        STUDY_ENT[["<b>[Class Instance]</b><br>Acupuncture<br>Research Study"]]
        OCSI_ENT[["<b>[Class Instance]</b><br>Acupuncture Study<br>OCSI Appraisal"]]
  
        %% Connections keep these horizontal naturally
        PUB_ENT -- hasReportedStudyID --> STUDY_ENT
        STUDY_ENT -- hasOCSIAppraisalID --> OCSI_ENT
        OCSI_ENT -- hasOCSIInputStudyID --> STUDY_ENT
        STUDY_ENT -- hasReportingPublicationID --> PUB_ENT
    end

```

In each diagram below,

* A dashed node is a pure grouping property (organizational only, never holds a value)
* A solid node holds an actual extracted value (some solid nodes are also parents of more granular sub-properties)
* A double-bordered node on the left represents an instance of a TARA-KB class (see above)
* See [Entity Relationships](#entity-relationships) below for the full picture with cardinality.

```mermaid
flowchart LR
 subgraph LEGENDS["Diagram Legend"]
        L[["Class Instance"]]
        G["Grouping Only<br>(no value)"]
        F["Can Hold Value"]
  end

     L:::linked
     G:::group
     F:::field
    classDef group fill:#eee,stroke:#999,stroke-dasharray: 3 3,color:#555
    classDef field fill:#ffffff,stroke:#333,color:#111
    classDef linked fill:#e8f0ff,stroke:#4472c4,stroke-dasharray: 2 2,color:#1a3a6b
    style LEGENDS stroke:transparent
```

### 1. Acupuncture Study Publication

Bibliographic metadata about an instnace of an Acupuncture Study Publication (e.g., a journal article) reporting a study.

```mermaid
flowchart LR
    classDef group fill:#eee,stroke:#999,stroke-dasharray: 3 3,color:#555
    classDef field fill:#ffffff,stroke:#333,color:#111
    classDef linked fill:#e8f0ff,stroke:#4472c4,stroke-dasharray: 2 2,color:#1a3a6b
    style BIB_FIELDS stroke:none

    PUB[["Acupuncture<br>Study Publication"]]:::linked
    BIB["hasBibliographicMetadata<br/>(Bibliographic Metadata)"]:::field

    subgraph BIB_FIELDS ["<b>Bibliographic Metadata</b>"]
        TITLE["hasArticleTitle<br/>(Article Title)"]:::field
        ATYPE["hasArticleType<br/>(Article Type)"]:::field
        AUTH["hasListedAuthors<br/>(Listed Author(s))"]:::field
        PVENUE["hasPublicationVenue<br/>(Publication Venue)"]:::field
        PDATE["hasPublicationDate<br/>(Publication Date)"]:::field
        LINK["hasPublicationLink<br/>(Publication Link)"]:::field
  
        PYEAR["hasPublicationYear<br/>(Publication Year)"]:::field
        DOI["hasDOILink<br/>(DOI Link)"]:::field
        OTHER["hasOtherLink<br/>(Other Link)"]:::field
        PUBMED["hasPubMedLink<br/>(PubMed Link)"]:::field
    end

    PUB --> BIB
    BIB --> ATYPE
    BIB --> TITLE
    BIB --> AUTH
    BIB --> PDATE --> PYEAR
    BIB --> PVENUE

    BIB --> LINK
            LINK --> DOI
            LINK --> OTHER
            LINK --> PUBMED
```

### 2. Acupuncture Research Study

Everything about an instance of an Acupuncture Research Study ; i.e., how the trial was actually conducted as reported in the publication: intervention protocol, design, conditions studied, findings, and study location.

```mermaid
flowchart LR
    classDef group fill:#eee,stroke:#999,stroke-dasharray: 3 3,color:#555
    classDef field fill:#ffffff,stroke:#333,color:#111
    classDef linked fill:#e8f0ff,stroke:#4472c4,stroke-dasharray: 2 2,color:#1a3a6b

    STUDY[["Acupuncture<br/>Research Study"]]:::linked
    ROOT["hasAcupunctureStudyMetadata<br/>(Acupuncture Study Metadata)"]:::group
    STUDY --> ROOT

    ROOT --> PROT
    ROOT --> LIST
    ROOT --> DLINK
    ROOT --> SCOND
    ROOT --> SDES
    ROOT --> SFIND
    ROOT --> SLOC

    subgraph PROTO ["<b>Acupuncture Protocol</b>"]
        direction LR
        PROT["hasAcupunctureProtocol<br/>(Acupuncture Protocol)"]:::linked

        ASELGROUP["hasAcupointSelectionAndGrouping<br/>(Point Selection and Grouping)"]:::field
        GRP["hasAcupointGrouping<br/>(Acupoint Grouping)"]:::field
        SEL["hasAcupointSelection<br/>(Acupoint Selection)"]:::field
        NEEDLE["hasNeedlingDetails<br/>(Needling Details)"]:::field
        SHAM["hasShamAcupunctureDetails<br/>(Sham Acupuncture Details)"]:::field
        SHAMUSED["hasShamAcupunctureUsed<br/>(Sham Acupuncture Used)"]:::field
        STIM["hasStimulationTypeDetails<br/>(Stimulation Type Details)"]:::field

        PROT --> ASELGROUP
        ASELGROUP --> GRP
        ASELGROUP --> SEL
        PROT --> NEEDLE
        PROT --> SHAM
        PROT --> SHAMUSED
        PROT --> STIM
    end

    subgraph LISTED ["<b>Listed Acupoints</b>"]
        direction LR
        LIST["hasListedAcupoints<br/>(Listed Acupoint(s))"]:::field
        LMAP["hasListedAcupointsMapped<br/>(Listed Acupoint(s) Mapped)"]:::field
        LCURIE["hasListedAcupointsMappedCurie<br/>(Listed Acupoint(s) Mapped Curie)"]:::field
        LUNMAP["hasListedAcupointsUnmappable<br/>(Listed Acupoint(s) Unmappable)"]:::field

        LIST --> LMAP
        LIST --> LCURIE
        LIST --> LUNMAP
    end

    subgraph DLK ["Dataset Link"]
        direction LR
        DLINK["hasDatasetLink<br/>(Dataset Link)"]:::field
    end

    subgraph COND ["<b>Studied Condition</b>"]
        direction LR
        SCOND["hasStudiedCondition<br/>(Studied Condition)"]:::group
        TCM["hasStudiedTCMCondition<br/>(Studied Condition (TCM))"]:::field
        TCMMAP["hasMappedTCMCondition<br/>(Mapped Condition (TCM))"]:::field
        WEST["hasStudiedWesternCondition<br/>(Studied Condition (Western))"]:::field
        WESTMAP["hasMappedWesternCondition<br/>(Mapped Condition (Western))"]:::field

        SCOND --> TCM --> TCMMAP
        SCOND --> WEST --> WESTMAP
    end

    subgraph DESIGN ["<b>Study Design Metadata</b>"]
        direction LR
        SDES["hasStudyDesignMetadata<br/>(Study Design Metadata)"]:::group
        CTRL["hasControlGroupsDetails<br/>(Control Groups Details)"]:::field
        SAMP["hasSampleSizeDetails<br/>(Sample Size Details)"]:::field
        OUT["hasStudyOutcomesMeasure<br/>(Study Outcomes Measure)"]:::field
        POUT["hasPrimaryOutcomeMeasure<br/>(Primary Outcome Measure)"]:::field
        SOUT["hasSecondaryOutcomeMeasure<br/>(Secondary Outcome Measure)"]:::field
        STYPE["hasStudyType<br/>(Study Design Category)"]:::field
        TDF["hasTreatmentDurationAndFrequency<br/>(Treatment Duration and Frequency)"]:::field
        TDUR["hasTreatmentDuration<br/>(Treatment Duration)"]:::field
        TFREQ["hasTreatmentFrequency<br/>(Treatment Frequency)"]:::field

        SDES --> CTRL
        SDES --> SAMP
        SDES --> OUT
        OUT --> POUT
        OUT --> SOUT
        SDES --> STYPE
        SDES --> TDF
        TDF --> TDUR
        TDF --> TFREQ
    end

    subgraph FINDINGS ["<b>Study Findings</b>"]
        direction LR
        SFIND["hasStudyFindings<br/>(Study Findings)"]:::field
        COMP["hasComparativeFindings<br/>(Comparative Findings)"]:::field
        MECH["hasProposedMechanism<br/>(Proposed Mechanism)"]:::field
        CONCL["hasStudyConclusions<br/>(Study Conclusions)"]:::field
        EFFECT["hasStudyEffectiveness<br/>(Study Effectiveness)"]:::field
        RESULTS["hasStudyResults<br/>(Study Results)"]:::field

        SFIND --> COMP
        SFIND --> MECH
        SFIND --> CONCL
        SFIND --> EFFECT
        SFIND --> RESULTS
    end

    subgraph LOC ["<b>Study Location</b>"]
        direction LR
        SLOC["hasStudyLocation<br/>(Study Location)"]:::field
        COUNTRY["hasCountryOfStudy<br/>(Country of Study)"]:::field
        SLOC --> COUNTRY
    end
```

### 3. Acupuncture Study OCSI Assessment

Everything about an instance of an Acupuncture Study OCSI Assessment based on a reported study. Each instance contains  structured quality appraisal of trial reporting, based on the Oregon CONSORT/STRICTA Instrument (OCSI), organized into five scoring categories (A–E) covering 27 numbered items.

```mermaid
flowchart LR
    classDef group fill:#eee,stroke:#999,stroke-dasharray: 3 3,color:#555
    classDef field fill:#ffffff,stroke:#333,color:#111
    classDef linked fill:#e8f0ff,stroke:#4472c4,stroke-dasharray: 2 2,color:#1a3a6b

    OCSI[["Acupuncture Study<br/>OCSI Assessment"]]:::linked
    %% ROOT["hasStudyQualityAssessmentMetadata<br/>(Study Assessment Metadata)"]:::group
    ITEM["hasOCSIItemScoringMetadata<br/>(OCSI Item Scoring Metadata)"]:::group
    TOTPCT["hasOCSITotalPercentage<br/>(OCSI Total Percentage)"]:::field
    %% OCSI --> ROOT
    OCSI --> ITEM
    ITEM --> TOTPCT

    subgraph A ["<b>Category A: Study Rationale & Scope Metrics</b>"]
        direction LR
        CATA["hasStudyRationaleAndScopeMetrics"]:::group
        A1["hasParticipantsRandomizationStatementScore<br/>((1) Participants Randomization Statement)"]:::field
        A2["hasScientificBackgroundRationaleScore<br/>((2) Scientific Background & Rationale)"]:::field
        A3["hasParticipantsEligibilityAndStudySettingsScore<br/>((3) Participants Eligibility & Study Settings)"]:::field
        A10["hasSpecificObjectivesHypothesesScore<br/>((10) Specific Objectives & Hypotheses)"]:::field

        CATA --> A1
        CATA --> A2
        CATA --> A3
        CATA --> A10
    end

    subgraph B ["<b>Category B: Acupuncture Intervention Metrics</b>"]
        direction LR
        CATB["hasAcupunctureInterventionMetrics"]:::group
        B4["hasAcupunctureStyleAndSelectionScore<br/>((4) Acupuncture Style & Acupoints Selection)"]:::field
        B5["hasAcupunctureNeedlingParametersScore<br/>((5) Acupuncture Needling Parameters)"]:::field
        B6["hasTreatmentsDurationAndFrequencyScore<br/>((6) Treatments Duration & Frequency)"]:::field
        B7["hasAcupunctureCointerventionsScore<br/>((7) Acupuncture Group Cointervention(s))"]:::field
        B8["hasPractitionerTrainingExpertiseScore<br/>((8) Practitioner Training & Expertise)"]:::field
        B9["hasControlGroupsInterventionScore<br/>((9) Control Groups Intervention)"]:::field

        CATB --> B4
        CATB --> B5
        CATB --> B6
        CATB --> B7
        CATB --> B8
        CATB --> B9
    end

    subgraph C ["<b>Category C: Study Design & Analysis Metrics</b>"]
        direction LR
        CATC["hasStudyDesignAndAnalysisMetrics"]:::group
        C11["hasOutcomesMeasureDefinitionsScore<br/>((11) Outcomes Measure Definitions)"]:::field
        C12["hasSampleSizeDeterminationScore<br/>((12) Sample Size Determination)"]:::field
        C13["hasRandomAllocationSequencingScore<br/>((13) Random Allocation Sequencing)"]:::field
        C14["hasRandomAllocationConcealmentScore<br/>((14) Random Allocation Concealment)"]:::field
        C15["hasRandomAllocationPersonnelScore<br/>((15) Random Allocation Personnel)"]:::field
        C16["hasBlindingStatementsQualityScore<br/>((16) Blinding Statements Quality)"]:::field
        C17["hasStatisticalMethodsForOutcomesScore<br/>((17) Statistical Methods for Outcomes)"]:::field

        CATC --> C11
        CATC --> C12
        CATC --> C13
        CATC --> C14
        CATC --> C15
        CATC --> C16
        CATC --> C17
    end

    subgraph D ["<b>Category D: Results & Outcomes Metrics</b>"]
        direction LR
        CATD["hasResultsAndOutcomesMetrics"]:::group
        D18["hasParticipantsFlowAndDeviationScore<br/>((18) Participants Flow & Deviation)"]:::field
        D19["hasParticipantsRecruitmentFollowupScore<br/>((19) Participants Recruitment & Followup)"]:::field
        D20["hasGroupDemographicsCharacteristicsScore<br/>((20) Group Demographics & Characteristics)"]:::field
        D21["hasParticipantsIntentionToTreatScore<br/>((21) Participants & Intention to Treat Analysis)"]:::field
        D22["hasStudyOutcomesAndEffectSizeScore<br/>((22) Study Outcomes & Effect Size)"]:::field
        D23["hasSubgroupAdjustedAnalysesScore<br/>((23) Subgroup & Adjusted Analyses)"]:::field
        D24["hasAdverseEventsSideEffectsScore<br/>((24) Adverse Events & Side Effects)"]:::field

        CATD --> D18
        CATD --> D19
        CATD --> D20
        CATD --> D21
        CATD --> D22
        CATD --> D23
        CATD --> D24
    end

    subgraph E ["<b>Category E: Results Discussion Metrics</b>"]
        direction LR
        CATE["hasResultsDiscussionMetrics"]:::group
        E25["hasTrialStrengthsLimitationsScore<br/>((25) Trial Strengths & Limitations)"]:::field
        E26["hasTrialGeneralizabilityScore<br/>((26) Trial Findings Generalizability)"]:::field
        E27["hasInterpretationOfResultsScore<br/>((27) Interpretation of Results)"]:::field

        CATE --> E25
        CATE --> E26
        CATE --> E27
    end

    ITEM --> CATA
    ITEM --> CATB
    ITEM --> CATC
    ITEM --> CATD
    ITEM --> CATE
```

## Entity Relationships

The three core classes are cross-linked by dedicated annotation properties rather than a single owning hierarchy, forming a triangle: a Publication reports a Study, a Study is reported by a Publication and appraised by an OCSI record, and an OCSI record traces back to both its input Study and its reporting Publication.

```mermaid
erDiagram
    PUBLICATION ||--o| STUDY : hasReportedStudyID
    STUDY ||--o| PUBLICATION : hasReportingPublicationID
    STUDY ||--o| OCSI_APPRAISAL : hasOCSIAppraisalID
    OCSI_APPRAISAL ||--o| STUDY : hasOCSIInputStudyID
    PUBLICATION ||--o| OCSI_APPRAISAL : hasOCSIAppraisalID
    OCSI_APPRAISAL ||--o| PUBLICATION : hasReportingPublicationID

    PUBLICATION {
        string dc_identifier "e.g. tara-kb:A-112625-612"
        string Article_Title
        string Article_Type
        string Publication_Venue
        string Publication_Date
        string DOI_Link
    }
    STUDY {
        string dc_identifier "e.g. tara-kb:S-112625-612"
        string Acupuncture_Protocol
        string Study_Type
        string Country_Of_Study
        string Study_Results
    }
    OCSI_APPRAISAL {
        string dc_identifier "e.g. tara-kb:O-112625-612"
        integer Eligibility_Score
        integer Blinding_Quality_Score
        float OCSI_Total_Percentage
    }
```

**Class hierarchy:** `Acupuncture Study Publication` is a subclass of `Research Study Publication`; `Acupuncture Research Study` is a subclass of `Research Study`; `Acupuncture Study OCSI Appraisal` is a subclass of `Acupuncture Study Qualty Appraisal`, itself a subclass of `Study Quality Appraisal`.

**Cardinality note:** the `||--o|` (one-to-zero-or-one) cardinality above reflects current pipeline convention — each source spreadsheet row produces exactly one Publication, one Study, and one OCSI Appraisal individual, linked 1:1. This is not an OWL constraint enforced by the ontology (none of these are declared `owl:FunctionalProperty`), so a future scenario such as one Publication reporting multiple Studies (e.g. a multi-arm trial or meta-analysis) is not structurally prevented — just not what the current extraction pipeline produces.

## LLM Extraction Prompt

Work in Progress
