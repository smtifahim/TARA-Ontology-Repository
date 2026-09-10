# TARA Ontology Distribution

Released Turtle files, served by GitHub Pages and resolvable via PURL. Written by the header-stamping scripts in `ontology-generator/script/{ontology,kb}-generation/` and indexed by `ontology-generator/script/publish_distribution.py` (all run from`ontology-generator/run_all.sh`). Do not hand-edit anything here.

## Layout

```
distribution/
  index.html                         version index (both ontologies)
  ontology/version/
    latest.json                      { latest, versions[], versionIRIs{} }
    <VERSION>/
      asserted/acupoints.ttl         with BFO,  asserted axioms
      inferred/acupoints.ttl         with BFO,  HermiT closure
      no-bfo/asserted/acupoints.ttl  without BFO, asserted
      no-bfo/inferred/acupoints.ttl  without BFO, HermiT closure   <- canonical
  kb/version/
    latest.json
    <VERSION>/…/articles-kb.ttl      same four variants
```

A `<VERSION>/` folder is an **immutable snapshot** - once published it is never
rewritten. Release versions come from `ontology-generator/script/versions.py`.

## Identifiers


| kind                         | example                                                                   | resolves to                          |
| ---------------------------- | ------------------------------------------------------------------------- | ------------------------------------ |
| ontology IRI (always latest) | `http://purl.org/tara/ontology/acupoints.owl`                             | the current release's canonical file |
| version IRI (pinned)         | `http://purl.org/tara/ontology/release/<V>/no-bfo/inferred/acupoints.ttl` | that exact snapshot                  |
| KB ontology IRI              | `http://purl.org/tara/ontology/kb/articles-kb.ttl`                        | current KB release                   |
| KB version IRI               | `http://purl.org/tara/ontology/kb/release/<V>/…/articles-kb.ttl`         | that snapshot                        |

Each `.ttl` carries its own `owl:versionIRI` matching the table above.

## PURL (purl.archive.org)

Partial redirects, most-specific wins:


| pattern                             | type    | target                                                                     |
| ----------------------------------- | ------- | -------------------------------------------------------------------------- |
| `/tara/ontology/release/`           | partial | `…/TARA-Ontology-Repository/distribution/ontology/version/`               |
| `/tara/ontology/kb/release/`        | partial | `…/TARA-Ontology-Repository/distribution/kb/version/`                     |
| `/tara/ontology/acupoints.owl`      | 302     | `…/distribution/ontology/version/<CURRENT>/no-bfo/inferred/acupoints.ttl` |
| `/tara/ontology/kb/articles-kb.ttl` | 302     | `…/distribution/kb/version/<CURRENT>/no-bfo/inferred/articles-kb.ttl`     |
| `/tara/ontology/TARA_`              | partial | the ontology browser (term IRIs)                                           |

The two 302s are the "always latest" links - retarget the `<CURRENT>` segment
(one line each) when cutting a release. The `release/` -> `version/` path
difference is handled by the partial redirect; the segments after the matched
prefix are appended verbatim.
