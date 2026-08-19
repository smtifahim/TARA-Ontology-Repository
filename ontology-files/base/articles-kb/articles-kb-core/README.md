# TARA Articles KB — Core Ontology

## Purpose

`tara-articles-kb-core.ttl` is the single source of truth for the metadata schema used to capture extracted information from acupuncture clinical trial publications. It exists to solve a recurring ETL problem: metadata extracted via AI tools (Elicit, Gemini, etc.) arrived with inconsistent column names and prompting from batch to batch, which forced the ingestion/transformation scripts to be rewritten every time, and no standardized database schema existed to load into.

This ttl is designed to drive three things directly, so extraction, transformation, and load all stay consistent with one another:

1. **Extraction** — a data dictionary precise enough to generate standardized extraction instructions (prompts) per metadata element for the AI extraction step.
2. **Transformation** — consistent CSV/Excel headers and SPARQL query templates, generated from the ontology rather than hand-maintained.
3. **Load** — a relational database schema derived from the same property definitions used in the RDF graph, so the graph and relational representations never drift apart.

Every annotation property carries `rdfs:label` (human name), `skos:altLabel` (machine-safe column/field name), `dcterms:description` (formal definition), `obo:IAO_0000112` (worked examples), `rdfs:comment` (normalization rules), `rdfs:domain`/`rdfs:range` (owning class / expected value type), and `dcterms:type tara-kb:grouping` where the property is purely organizational and never holds a value itself.

**Status note:** the `obo:IAO_0000112` example values and OCSI scoring rubrics currently in the file are a preliminary starting point and have not yet been verified as authoritative — treat them as draft until reviewed. See also the [LLM Extraction Prompt](#llm-extraction-prompt) section below.

## Contents

- **`tara-articles-kb-core.ttl`** — the canonical, hand-authored ontology.
- **`tara-articles-kb-core-draft.ttl`** — working draft / staging area for property changes before they're promoted into the core file.
- **`schema-tools/`** — *(scaffolding only, not yet implemented)* scripts that will read the core ttl and generate the derived artifacts below (CSV/Excel templates, DB schema, SPARQL templates, LLM prompt manifests) from a single ontology-reflection query, so every downstream format is regenerated from one source instead of hand-maintained separately.
  - `queries/` — reusable SPARQL (`.rq`) query files used by the generator scripts.
- **`generated-artifacts/`** — *(empty scaffolding, populated by `schema-tools/` once implemented)* build output only; never hand-edited.
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

    ROOT --> SLOC
    ROOT --> SDES
    ROOT --> SCOND
    ROOT --> PROT
    ROOT --> SFIND
    ROOT --> DLINK

    subgraph DLK ["Dataset Link"]
        direction LR
        DLINK["hasDatasetLink<br/>(Dataset Link)"]:::field
    end

    subgraph FINDINGS ["<b>Study Findings</b>"]
        direction LR
        SFIND["hasStudyFindings<br/>(Study Findings)"]:::field
        COMP["hasComparativeFindings<br/>(Comparative Findings)"]:::field
        MECH["hasProposedMechanism<br/>(Proposed Mechanism)"]:::field
        CONCL["hasStudyConclusions<br/>(Study Conclusions)"]:::field
        EFFECT["hasStudyEffectiveness<br/>(Study Effectiveness)"]:::field
        RESULTS["hasStudyResults<br/>(Study Results)"]:::field

        SFIND --> RESULTS
        SFIND --> CONCL
        SFIND --> EFFECT
        SFIND --> COMP
        SFIND --> MECH
    
    end
  
  
    subgraph PROTO ["<b>Acupuncture Protocol</b>"]
        direction LR
        PROT["hasAcupunctureProtocol<br/>(Acupuncture Protocol)"]:::linked
    
        LIST["hasListedAcupoints<br/>(Listed Acupoint(s))"]:::field
        LMAP["hasListedAcupointsMapped<br/>(Listed Acupoint(s) Mapped)"]:::field
        LCURIE["hasListedAcupointsMappedCurie<br/>(Listed Acupoint(s) Mapped Curie)"]:::field
        LUNMAP["hasListedAcupointsUnmappable<br/>(Listed Acupoint(s) Unmappable)"]:::field
        NEEDLE["hasNeedlingDetails<br/>(Needling Details)"]:::field
        SHAM["hasShamAcupunctureDetails<br/>(Sham Acupuncture Details)"]:::field
        STIM["hasStimulationTypeDetails<br/>(Stimulation Type Details)"]:::field

        ASELGROUP["hasAcupointSelectionAndGrouping<br/>(Point Selection and Grouping)"]:::field
        GRP["hasAcupointGrouping<br/>(Acupoint Grouping)"]:::field
        SEL["hasAcupointSelection<br/>(Acupoint Selection)"]:::field
    

        PROT --> ASELGROUP
        ASELGROUP --> GRP
        ASELGROUP --> SEL
        PROT --> NEEDLE
        PROT --> LIST
        LIST --> LMAP
        LIST --> LCURIE
        LIST --> LUNMAP    
        PROT --> STIM
        PROT --> SHAM

    
    end
  
    subgraph DESIGN ["<b>Study Design Metadata</b>"]
        direction LR
        SDES["hasStudyDesignMetadata<br/>(Study Design Metadata)"]:::group
        CTRL["hasControlGroupsDetails<br/>(Control Groups Details)"]:::field
        SAMP["hasSampleSizeDetails<br/>(Sample Size Details)"]:::field
        OUT["hasStudyOutcomesMeasure<br/>(Study Outcomes Measure)"]:::field
        POUT["hasPrimaryOutcomeMeasure<br/>(Primary Outcome Measure)"]:::field
        SOUT["hasSecondaryOutcomeMeasure<br/>(Secondary Outcome Measure)"]:::field
        STYPE["hasStudyType<br/>(Study Type)"]:::field
        CTYPE["hasClinicalTrialType<br/>(Clinical Trial Type)"]:::field
        TDF["hasTreatmentDurationAndFrequency<br/>(Treatment Duration and Frequency)"]:::field
        TDUR["hasTreatmentDuration<br/>(Treatment Duration)"]:::field
        TFREQ["hasTreatmentFrequency<br/>(Treatment Frequency)"]:::field

        SDES --> STYPE --> CTYPE
        SDES --> CTRL
        SDES --> OUT
        SDES --> SAMP
    
        OUT --> POUT
        OUT --> SOUT
        SDES --> TDF
        TDF --> TDUR
        TDF --> TFREQ
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

    subgraph LOC ["<b>Study Location</b>"]
        direction LR
        SLOC["hasStudyLocation<br/>(Study Location)"]:::field
        COUNTRY["hasCountryOfStudy<br/>(Country of Study)"]:::field
        SLOC --> COUNTRY
    end
```

### 3. Acupuncture Study OCSI Appraisal

Everything about an instance of an Acupuncture Study OCSI Appraisal based on a reported study. Each instance contains  structured quality appraisal of trial reporting, based on the Oregon CONSORT/STRICTA Instrument (OCSI), organized into four scoring categories.

```mermaid
flowchart LR
    classDef group fill:#eee,stroke:#999,stroke-dasharray: 3 3,color:#555
    classDef field fill:#ffffff,stroke:#333,color:#111
    classDef linked fill:#e8f0ff,stroke:#4472c4,stroke-dasharray: 2 2,color:#1a3a6b

    OCSI[["Acupuncture Study<br/>OCSI Appraisal"]]:::linked
    ROOT["hasOCSIScoreMetadata<br/>(OCSI Score Metadata)"]:::group
    OCSI --> ROOT

    subgraph D ["<b>Category D: Evaluative Results and Global Metrics</b>"]
        direction LR
        CATD["hasEvaluativeResultsAndGlobalMetrics"]:::group
        TOTPCT["hasOCSITotalPercentage<br/>(OCSI Total Percentage)"]:::field
        X2["hasOutcomesMeasureX2Score<br/>(Outcomes Measure X2 Score)"]:::field
        RESOUT["hasResultsOutcomesScore<br/>(Results Outcomes Score)"]:::field
        CATD --> TOTPCT
        CATD --> X2
        CATD --> RESOUT
    end

    subgraph C ["<b>Category C: Methodological and Statistical Allocation Metrics</b>"]
        direction LR
        SUBG["hasSubgroupScore<br/>(Subgroup Score)"]:::field
        BLIND["hasBlindingQualityScore<br/>(Blinding Quality Score)"]:::field
        CATC["hasMethodologicalAndStatisticalAllocationMetrics"]:::group
        ADV["hasAdverseEffectsScore<br/>(Adverse Effects Score)"]:::field
        RAND["hasRandomAllocationScore<br/>(Random Allocation Score)"]:::field
    
        CATC --> SUBG
        CATC --> BLIND
        CATC --> ADV
        CATC --> RAND
    end
  
    subgraph B ["<b>Category B: Technical Intervention Quality Metrics</b>"]
        direction LR
        CATB["hasTechnicalInterventionQualityMetrics"]:::group
        ACUDET["hasAcupunctureDetailsScore<br/>(Acupuncture Details Score)"]:::field
        CTRLSC["hasControlGroupsScore<br/>(Control Groups Score)"]:::field
        COINT["hasCointerventionsScore<br/>(Cointerventions Score)"]:::field
        NEEDLESC["hasNeedlingParametersScore<br/>(Needling Parameters Score)"]:::field
        PRACSAMP["hasPractitionerAndSampleSizeScore<br/>(Practitioner and Sample Size Score)"]:::field
        PRACSC["hasPractitionerScore<br/>(Practitioner Score)"]:::field

        SAMPSC["hasSampleSizeScore<br/>(Sample Size Score)"]:::field
        SHAMSC["hasShamDetailsScore<br/>(Sham Controls Score)"]:::field
        FREQSC["hasFrequencyOfTreatmentScore<br/>(Treatment Frequency Score)"]:::field

        CATB --> ACUDET
        CATB --> CTRLSC
        CATB --> COINT
        CATB --> PRACSAMP
                 PRACSAMP --> SAMPSC
                 PRACSAMP --> PRACSC
        CATB --> NEEDLESC
        CATB --> SHAMSC
        CATB --> FREQSC
    end

    subgraph A ["<b>Category A: Study Foundation and Background Metrics</b>"]
        direction LR
        CATA["hasStudyFoundationAndBackgroundMetrics"]:::group
        INTRO["hasIntroductionAndHypothesisScore<br/>(Introduction and Hypothesis Score)"]:::field
        ELIG["hasEligibilityScore<br/>(Eligibility Score)"]:::field
        LIMIT["hasLimitationsScore<br/>(Limitations Score)"]:::field
        PART["hasParticipantsScore<br/>(Participants Score)"]:::field
        CATA --> INTRO
        CATA --> ELIG
        CATA --> LIMIT
        CATA --> PART
    end

    ROOT --> CATA
    ROOT --> CATB
    ROOT --> CATC
    ROOT --> CATD
  
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
