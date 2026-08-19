# TARA Articles KB: Core Ontology Documentation

Auto-generated from [`tara-articles-kb-core.ttl`](../../tara-articles-kb-core.ttl) by `artifacts-generator/doc-generator/generate_documentation.py`. Do not hand-edit — re-run the script instead.

## Core Classes

Classes defined in `tara-articles-kb-core.ttl`. Classes marked **(domain)** are used as `rdfs:domain` by at least one property under `tara-kb:hasTARAArticlesMetadata`; classes marked *(range only)* are referenced only as an `rdfs:range` target.

- **Acupuncture Point** — `TARA:1132428` *(range only)*
- **Disease or Condition** — `TARA:3448356`
  A broad ontology class representing any pathological process, abnormal state, or disruption of normal bodily structure or function manifested by a specific set of symptoms or signs.
  - **Disease or Condition (TCM)** — `TARA:6703917` *(range only)*
    A specialized subclass of 'Disease or Condition' representing health impairments conceptualized, diagnosed, and classified according to the principles of Traditional Chinese Medicine.
  - **Disease or Condition (Western)** — `TARA:1244992` *(range only)*
    A specialized subclass of 'Disease or Condition' representing health impairments conceptualized, diagnosed, and classified according to conventional Western biomedical science.
- **Research Study** — `TARA:7008377`
  A planned acupuncture research process consisting of a coordinated group of research activities, methodological designs, and data-gathering evaluations aimed at systematically investigating a scientific hypothesis or clinical question.
  - **Acupuncture Research Study** — `TARA:6701896` **(domain)**
    A specialized study process wherein the primary intervention under investigation involves acupuncture therapeutics, including needle insertion, point selection logic, needle manipulation methods, and stimulation protocols (manual, electrical, or thermal).
- **Research Study Publication** — `TARA:3677977`
  An abstract ontology class representing any formal written, digital, or multimedia artifact that documents, describes, or reports on a research study.
  - **Acupuncture Study Publication** — `TARA:8223728` **(domain)**
    A specialized subclass of 'Research Study Publication' representing any formal written, digital, or multimedia artifact that documents, describes, or reports on an acupuncture research study.
    - **Acupuncture Study Journal Article** — `TARA:2894731` *(range only)*
      A specialized subclass of 'Acupuncture Study Publication' representing a peer-reviewed paper published within a periodic scientific journal.
- **Study Quality Appraisal** — `TARA:7227329` **(domain)**
  A data item consisting of a structured collection of metrics, scores, or evaluations generated during a systematic process to assess the methodological rigor, risk of bias, validity, or reporting completeness of a scientific study or clinical trial.
  - **Acupuncture Study Qualty Appraisal** — `TARA:9542913`
    A study quality appraisal data item specifically designed or adapted to evaluate the methodological rigor and reporting completeness of clinical trials or systematic reviews evaluating acupuncture interventions, capturing specific operational variables unique to needle-based therapeutics.
    - **Acupuncture Study OCSI Appraisal** — `TARA:2825659` **(domain)**
      An acupuncture study quality appraisal data item that captures, organizes, and structures the specific multi-item compliance metrics and qualitative evaluation scores defined by the Oregon CONSORT STRICTA Instrument (OCSI) for assessing the reporting quality of acupuncture clinical trials.

**Custom datatype(s):**
- `TARA:6560239` ("TARA_6560239") — To represent the total OCSI Score percentage between 0.0 to 100.0.
- `tara-kb:nonNegShortInt` ("nonNegShortInt") — To represent individual score for each OCSI Score Category between 0 and 10.

## Metadata Property Hierarchy

Full hierarchy of `tara-kb:hasTARAArticlesMetadata` and its `rdfs:subPropertyOf` descendants. A property tagged *(grouping — organizational only)* carries `dcterms:type tara-kb:grouping` and never holds an extracted value itself. `Domain`/`Range` of *not specified* means the property has no `rdfs:domain`/`rdfs:range` asserted in the file.

- **TARA-KB: Articles Metadata** — `tara-kb:hasTARAArticlesMetadata` *(grouping — organizational only)* — Domain: *not specified* · Range: *not specified*
  - **Extracted Article Metadata** — `tara-kb:hasExtractedArticleMetadata` *(grouping — organizational only)* — Domain: *not specified* · Range: *not specified*
    - **Acupuncture Study Metadata** — `tara-kb:hasAcupunctureStudyMetadata` *(grouping — organizational only)* — Domain: `Acupuncture Research Study` · Range: *not specified*
      - **Acupuncture Protocol** — `tara-kb:hasAcupunctureProtocol` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
        - **Listed Acupoint(s)** — `tara-kb:hasListedAcupoints` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
          - **Listed Acupoint(s) Mapped** — `tara-kb:hasListedAcupointsMapped` — Domain: `Acupuncture Research Study` · Range: `Acupuncture Point`
          - **Listed Acupoint(s) Mapped Curie** — `tara-kb:hasListedAcupointsMappedCurie` — Domain: `Acupuncture Research Study` · Range: `rdf:JSON`
          - **Listed Acupoint(s) Unmappable** — `tara-kb:hasListedAcupointsUnmappable` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
        - **Needling Details** — `tara-kb:hasNeedlingDetails` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
        - **Point Selection and Grouping** — `tara-kb:hasAcupointSelectionAndGrouping` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
          - **Acupoint Grouping** — `tara-kb:hasAcupointGrouping` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
          - **Acupoint Selection** — `tara-kb:hasAcupointSelection` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
        - **Sham Acupuncture Details** — `tara-kb:hasShamAcupunctureDetails` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
        - **Stimulation Type Details** — `tara-kb:hasStimulationTypeDetails` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
      - **Dataset Link** — `tara-kb:hasDatasetLink` — Domain: `Acupuncture Research Study` · Range: `xsd:anyURI`
      - **Studied Condition** — `tara-kb:hasStudiedCondition` *(grouping — organizational only)* — Domain: `Acupuncture Research Study` · Range: *not specified*
        - **Studied Condition (TCM)** — `tara-kb:hasStudiedTCMCondition` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
          - **Mapped Condition (TCM)** — `tara-kb:hasMappedTCMCondition` — Domain: `Acupuncture Research Study` · Range: `Disease or Condition (TCM)`
        - **Studied Condition (Western)** — `tara-kb:hasStudiedWesternCondition` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
          - **Mapped Condition (Western)** — `tara-kb:hasMappedWesternCondition` — Domain: `Acupuncture Research Study` · Range: `Disease or Condition (Western)`
      - **Study Design Metadata** — `tara-kb:hasStudyDesignMetadata` *(grouping — organizational only)* — Domain: `Acupuncture Research Study` · Range: *not specified*
        - **Control Groups Details** — `tara-kb:hasControlGroupsDetails` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
        - **Sample Size Details** — `tara-kb:hasSampleSizeDetails` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
        - **Study Outcomes Measure** — `tara-kb:hasStudyOutcomesMeasure` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
          - **Primary Outcome Measure** — `tara-kb:hasPrimaryOutcomeMeasure` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
          - **Secondary Outcome Measure** — `tara-kb:hasSecondaryOutcomeMeasure` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
        - **Study Type** — `tara-kb:hasStudyType` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
          - **Clinical Trial Type** — `tara-kb:hasClinicalTrialType` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
        - **Treatment Duration and Frequency** — `tara-kb:hasTreatmentDurationAndFrequency` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
          - **Treatment Duration** — `tara-kb:hasTreatmentDuration` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
          - **Treatment Frequency** — `tara-kb:hasTreatmentFrequency` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
      - **Study Findings** — `tara-kb:hasStudyFindings` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
        - **Comparative Findings** — `tara-kb:hasComparativeFindings` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
        - **Proposed Mechanism** — `tara-kb:hasProposedMechanism` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
        - **Study Conclusions** — `tara-kb:hasStudyConclusions` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
        - **Study Effectiveness** — `tara-kb:hasStudyEffectiveness` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
        - **Study Results** — `tara-kb:hasStudyResults` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
      - **Study Location** — `tara-kb:hasStudyLocation` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
        - **Country of Study** — `tara-kb:hasCountryOfStudy` — Domain: `Acupuncture Research Study` · Range: `xsd:string`
    - **Bibliographic Metadata** — `tara-kb:hasBibliographicMetadata` — Domain: `Acupuncture Study Publication` · Range: `xsd:string`
      - **Article Title** — `tara-kb:hasArticleTitle` — Domain: `Acupuncture Study Publication` · Range: `xsd:string`
      - **Article Type** — `tara-kb:hasArticleType` — Domain: `Acupuncture Study Publication` · Range: `xsd:string`
      - **Listed Author(s)** — `tara-kb:hasListedAuthors` — Domain: `Acupuncture Study Publication` · Range: `xsd:string`
      - **Publication Date** — `tara-kb:hasPublicationDate` — Domain: `Acupuncture Study Publication` · Range: `xsd:string`
        - **Publication Year** — `tara-kb:hasPublicationYear` — Domain: `Acupuncture Study Publication` · Range: `xsd:gYear`
      - **Publication Link** — `tara-kb:hasPublicationLink` — Domain: `Acupuncture Study Publication` · Range: `xsd:anyURI`
        - **DOI Link** — `tara-kb:hasDOILink` — Domain: `Acupuncture Study Publication` · Range: `xsd:anyURI`
        - **Other Link** — `tara-kb:hasOtherLink` — Domain: `Acupuncture Study Publication` · Range: `xsd:anyURI`
        - **PubMed Link** — `tara-kb:hasPubMedLink` — Domain: `Acupuncture Study Publication` · Range: `xsd:anyURI`
      - **Publication Venue** — `tara-kb:hasPublicationVenue` — Domain: `Acupuncture Study Publication` · Range: `xsd:string`
  - **LLM Extraction Prompt** — `tara-kb:hasLLMExtractionPrompt` — Domain: *not specified* · Range: `rdf:JSON`
    - **LLM System Prompt** — `tara-kb:hasLLMSystemPrompt` — Domain: *not specified* · Range: *not specified*
    - **LLM User Prompt** — `tara-kb:hasLLMUserPrompt` — Domain: *not specified* · Range: *not specified*
  - **Study Appraisal Metadata** — `tara-kb:hasStudyQualityAppraisalMetadata` *(grouping — organizational only)* — Domain: `Study Quality Appraisal` · Range: *not specified*
    - **OCSI Score Metadata** — `tara-kb:hasOCSIScoreMetadata` *(grouping — organizational only)* — Domain: `Acupuncture Study OCSI Appraisal` · Range: *not specified*
      - **Evaluative Results and Global Metrics** — `tara-kb:hasEvaluativeResultsAndGlobalMetrics` *(grouping — organizational only)* — Domain: `Acupuncture Study OCSI Appraisal` · Range: *not specified*
        - **OCSI Total Percentage** — `tara-kb:hasOCSITotalPercentage` — Domain: `Acupuncture Study OCSI Appraisal` · Range: `xsd:float`
        - **Outcomes Measure X2 Score** — `tara-kb:hasOutcomesMeasureX2Score` — Domain: `Acupuncture Study OCSI Appraisal` · Range: `nonNegShortInt`
        - **Results Outcomes Score** — `tara-kb:hasResultsOutcomesScore` — Domain: `Acupuncture Study OCSI Appraisal` · Range: `nonNegShortInt`
      - **Methodological and Statistical Allocation Metrics** — `tara-kb:hasMethodologicalAndStatisticalAllocationMetrics` *(grouping — organizational only)* — Domain: `Acupuncture Study OCSI Appraisal` · Range: *not specified*
        - **Adverse Effects Score** — `tara-kb:hasAdverseEffectsScore` — Domain: `Acupuncture Study OCSI Appraisal` · Range: `nonNegShortInt`
        - **Blinding Quality Score** — `tara-kb:hasBlindingQualityScore` — Domain: `Acupuncture Study OCSI Appraisal` · Range: `nonNegShortInt`
        - **Random Allocation Score** — `tara-kb:hasRandomAllocationScore` — Domain: `Acupuncture Study OCSI Appraisal` · Range: `nonNegShortInt`
        - **Subgroup Score** — `tara-kb:hasSubgroupScore` — Domain: `Acupuncture Study OCSI Appraisal` · Range: `nonNegShortInt`
      - **Study Foundation and Background Metrics** — `tara-kb:hasStudyFoundationAndBackgroundMetrics` *(grouping — organizational only)* — Domain: `Acupuncture Study OCSI Appraisal` · Range: *not specified*
        - **Eligibility Score** — `tara-kb:hasEligibilityScore` — Domain: `Acupuncture Study OCSI Appraisal` · Range: `nonNegShortInt`
        - **Introduction and Hypothesis Score** — `tara-kb:hasIntroductionAndHypothesisScore` — Domain: `Acupuncture Study OCSI Appraisal` · Range: `nonNegShortInt`
        - **Limitations Score** — `tara-kb:hasLimitationsScore` — Domain: `Acupuncture Study OCSI Appraisal` · Range: `nonNegShortInt`
        - **Participants Score** — `tara-kb:hasParticipantsScore` — Domain: `Acupuncture Study OCSI Appraisal` · Range: `nonNegShortInt`
      - **Technical Intervention Quality Metrics** — `tara-kb:hasTechnicalInterventionQualityMetrics` *(grouping — organizational only)* — Domain: `Acupuncture Study OCSI Appraisal` · Range: *not specified*
        - **Acupuncture Details Score** — `tara-kb:hasAcupunctureDetailsScore` — Domain: `Acupuncture Study OCSI Appraisal` · Range: `nonNegShortInt`
        - **Cointerventions Score** — `tara-kb:hasCointerventionsScore` — Domain: `Acupuncture Study OCSI Appraisal` · Range: `nonNegShortInt`
        - **Control Groups Score** — `tara-kb:hasControlGroupsScore` — Domain: `Acupuncture Study OCSI Appraisal` · Range: `nonNegShortInt`
        - **Needling Parameters Score** — `tara-kb:hasNeedlingParametersScore` — Domain: `Acupuncture Study OCSI Appraisal` · Range: `nonNegShortInt`
        - **Practitioner and Sample Size Score** — `tara-kb:hasPractitionerAndSampleSizeScore` — Domain: `Acupuncture Study OCSI Appraisal` · Range: `nonNegShortInt`
          - **Practitioner Score** — `tara-kb:hasPractitionerScore` — Domain: `Acupuncture Study OCSI Appraisal` · Range: `nonNegShortInt`
          - **Sample Size Score** — `tara-kb:hasSampleSizeScore` — Domain: `Acupuncture Study OCSI Appraisal` · Range: `nonNegShortInt`
        - **Sham Controls Score** — `tara-kb:hasShamDetailsScore` — Domain: `Acupuncture Study OCSI Appraisal` · Range: `nonNegShortInt`
        - **Treatment Frequency Score** — `tara-kb:hasFrequencyOfTreatmentScore` — Domain: `Acupuncture Study OCSI Appraisal` · Range: `nonNegShortInt`

## Data Quality Notes

Computed from the current file — re-run this script after edits to refresh:

- `tara-kb:hasLLMSystemPrompt` ("LLM System Prompt") holds a value (not a grouping property) but has no `rdfs:range` asserted.
- `tara-kb:hasLLMUserPrompt` ("LLM User Prompt") holds a value (not a grouping property) but has no `rdfs:range` asserted.
