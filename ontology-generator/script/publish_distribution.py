"""
================================================================================
publish_distribution.py - version index for the published TARA ontology distribution
================================================================================
The header-stamping scripts write the versioned Turtle files into

    docs/distribution/ontology/version/<VERSION>/<variant>/acupoints.ttl
    docs/distribution/kb/version/<VERSION>/<variant>/articles-kb.ttl

This script, run last in the pipeline, does not touch those files; it only
derives the "what's current / what exists" metadata from script/versions.py and
whatever version folders are present:

    docs/distribution/ontology/version/latest.json
    docs/distribution/kb/version/latest.json
    docs/distribution/index.html          (human-browsable version index)

The version-less ontology IRIs
(http://purl.org/tara/ontology/acupoints.owl, .../kb/articles-kb.ttl) are the
"always latest" links; a PURL 302 points each at the current version's file -
one target to bump per release. latest.json is the machine-readable equivalent.

Author: Fahim Imam
================================================================================
"""

import datetime
import html
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
sys.path.insert(0, SCRIPT_DIR)
from versions import ACUPOINTS_VERSION, KB_VERSION  # noqa: E402

DIST_ROOT = os.path.join(REPO_ROOT, "docs", "distribution")

# Combined / gradual release notes (all versions), rendered on GitHub.
RELEASE_NOTES_URL = (
    "https://github.com/SciCrunch/TARA-Ontology-Repository/blob/master/"
    "ontology-files/generated/distribution/readme.md#ontology-versions-summary"
)

# Version-less ontology IRI - browses the latest no-BFO inferred ontology.
BROWSE_URL = "http://purl.org/tara/ontology"

# Major releases of the full BFO-compliant inferred acupoints ontology.
BIOPORTAL_URL = "https://purl.bioontology.org/ontology/TARA"

# Each variant is (display label, on-disk / IRI path segment). "BFO" is the
# default build, so its files live directly under <version>/asserted and
# <version>/inferred (no "bfo/" directory) - the label still reads "BFO/..."
# but the link points at the bare path. Canonical (version-less-IRI target)
# listed first.
VARIANTS = [
    ("No-BFO/Asserted", "no-bfo/asserted"),
    ("No-BFO/Inferred", "no-bfo/inferred"),
    ("BFO/Asserted", "asserted"),
    ("BFO/Inferred", "inferred"),
]
CANONICAL_LABEL = "No-BFO/Inferred"
CANONICAL_PATH = "no-bfo/inferred"

ONTOLOGIES = [
    {
        "key": "ontology",
        "title": "TARA Acupoints Ontology",
        "current": ACUPOINTS_VERSION,
        "file": "acupoints.ttl",
        "iri_base": "http://purl.org/tara/ontology/release/",
        "ontology_iri": "http://purl.org/tara/ontology/acupoints.owl",
    },
    {
        "key": "kb",
        "title": "TARA Articles Knowledge Base",
        "current": KB_VERSION,
        "file": "articles-kb.ttl",
        "iri_base": "http://purl.org/tara/ontology/kb/release/",
        "ontology_iri": "http://purl.org/tara/ontology/kb/articles-kb.ttl",
    },
]


def _version_key(v):
    try:
        return tuple(int(p) for p in v.split("."))
    except ValueError:
        return (0,)


def discover_versions(version_dir):
    if not os.path.isdir(version_dir):
        return []
    names = [
        n for n in os.listdir(version_dir)
        if n[:1].isdigit() and os.path.isdir(os.path.join(version_dir, n))
    ]
    return sorted(names, key=_version_key, reverse=True)


def variant_url(iri_base, version, variant, file_name):
    return f"{iri_base}{version}/{variant}/{file_name}"


def build_latest_json(ont, versions):
    current = ont["current"]
    return {
        "id": ont["key"],
        "title": ont["title"],
        "ontologyIRI": ont["ontology_iri"],
        "latest": current,
        "versions": versions,
        "canonicalVariant": CANONICAL_PATH,
        "versionIRIs": {
            path: variant_url(ont["iri_base"], current, path, ont["file"])
            for _label, path in VARIANTS
        },
        "generated": datetime.date.today().isoformat(),
    }


_INDEX_CSS = """
:root{--bg:#fff;--panel:#f7f8fa;--border:#dfe2e6;--text:#1a1f27;--muted:#5b6472;--accent:#4472c4}
@media(prefers-color-scheme:dark){:root{--bg:#14171c;--panel:#1b1f26;--border:#2d333d;--text:#e6e9ef;--muted:#9aa4b2;--accent:#7fa4e8}}
*{box-sizing:border-box}body{margin:0;padding:2.5rem 1.5rem;background:var(--bg);color:var(--text);
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;line-height:1.5}
main{max-width:900px;margin:0 auto}h1{font-size:1.4rem;margin:0 0 .25rem}
/* title, then a subtitle line, then a row with the logo on the left stretched
   to the height of the bullet list beside it (object-fit keeps the aspect) */
.page-head{margin-bottom:2rem}
.page-head h1{margin:0 0 .5rem}
.subtitle{color:var(--muted);margin:0 0 1rem}
.page-head .sub-row{display:flex;align-items:stretch;gap:1.5rem}
ul.sub-text{flex:0 1 42rem;min-width:0;margin:0;padding-left:1.1rem;color:var(--muted);font-size:.95rem;overflow-wrap:anywhere}
ul.sub-text li{margin:.2rem 0}
.page-logo{flex:0 0 auto;align-self:stretch;height:100%;width:auto;max-width:300px;object-fit:contain}
@media(max-width:640px){.page-head .sub-row{flex-wrap:wrap}.page-logo{height:auto;width:180px}}
section{border:1px solid var(--border);border-radius:8px;background:var(--panel);padding:1rem 1.2rem;margin-bottom:1.4rem}
h2{font-size:1.05rem;margin:0 0 .2rem}
.latest{margin:.2rem 0 .9rem;font-size:.95rem}
.latest a{font-weight:600}
code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.85em;color:var(--muted)}
table{border-collapse:collapse;width:100%;font-size:.85rem}
th,td{text-align:left;padding:.35rem .6rem;border-bottom:1px solid var(--border)}
th{color:var(--muted);font-weight:600}
tr:last-child td{border-bottom:none}
a{color:var(--accent)}
footer{color:var(--muted);font-size:.8rem;margin-top:2rem}
"""


def build_index_html(sections_html):
    today = datetime.date.today().isoformat()
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>TARA Acupoints Ontology & Knowledge Base Distribution</title>\n"
        f"<style>{_INDEX_CSS}</style>\n</head>\n<body>\n<main>\n"
        "<header class=\"page-head\">\n"
        "<h1>TARA Acupoints Ontology &amp; Knowledge Base Distribution</h1>\n"
        "<p class=\"subtitle\">Released Turtle files. The version-less ontology IRI "
        "always resolves to the latest release. Each <code>version/&lt;v&gt;/</code> "
        "file is an immutable snapshot. See the "
        f"<a href=\"{RELEASE_NOTES_URL}\">release notes</a> for what changed "
        "in each version.</p>\n"
        "<div class=\"sub-row\">\n"
        "<img class=\"page-logo\" src=\"tara-logo.png\" alt=\"TARA\">\n"
        "<ul class=\"sub-text\">\n"
        "<li>To browse the latest, inferred version of the ontology (excluding BFO "
        f"Top-Level): <a href=\"{BROWSE_URL}\" target=\"_blank\" rel=\"noopener\">{BROWSE_URL}</a></li>\n"
        "<li>Major releases of the full, BFO-compliant, inferred version of the TARA "
        "Acupoints Ontology are published in BioPortal: "
        f"<a href=\"{BIOPORTAL_URL}\" target=\"_blank\" rel=\"noopener\">{BIOPORTAL_URL}</a></li>\n"
        "</ul>\n"
        "</div>\n"
        "</header>\n"
        + sections_html +
        f"<footer>Generated {today} &middot; "
        "<a href=\"https://github.com/SciCrunch/TARA-Ontology-Repository\">SciCrunch/TARA-Ontology-Repository</a>"
        "</footer>\n</main>\n</body>\n</html>\n"
    )


def section_html(ont, versions):
    e = html.escape
    current = ont["current"]
    rel = f"{ont['key']}/version"
    rows = []
    rows.append("<tr><th>Version</th>" + "".join(f"<th>{e(label)}</th>" for label, _p in VARIANTS) + "</tr>")
    for v in versions:
        cells = [f"<td><strong>{e(v)}</strong>{' &middot; latest' if v == current else ''}</td>"]
        for label, path in VARIANTS:
            href = f"{rel}/{e(v)}/{path}/{e(ont['file'])}"
            cells.append(f"<td><a href=\"{href}\">{e(label)}</a></td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    canon_href = f"{rel}/{e(current)}/{CANONICAL_PATH}/{e(ont['file'])}"
    return (
        f"<section>\n<h2>{e(ont['title'])}</h2>\n"
        f"<div class=\"latest\">Latest: <a href=\"{canon_href}\">{e(current)} "
        f"({e(CANONICAL_LABEL)})</a> &middot; ontology IRI "
        f"<code>{e(ont['ontology_iri'])}</code></div>\n"
        f"<table>\n{chr(10).join(rows)}\n</table>\n</section>\n"
    )


def main():
    if not os.path.isdir(DIST_ROOT):
        raise SystemExit(f"Nothing to publish - {os.path.relpath(DIST_ROOT)} does not exist. "
                         f"Run the header-stamping scripts first.")

    for p_root, _dirs, files in os.walk(DIST_ROOT):
        for f in files:
            if f == ".DS_Store":
                os.remove(os.path.join(p_root, f))

    sections = []
    for ont in ONTOLOGIES:
        version_dir = os.path.join(DIST_ROOT, ont["key"], "version")
        versions = discover_versions(version_dir)
        if not versions:
            print(f"  WARNING: no version folders under {os.path.relpath(version_dir)} - skipping {ont['key']}")
            continue
        if ont["current"] not in versions:
            print(f"  WARNING: script/versions.py says {ont['key']} is {ont['current']} "
                  f"but that folder is missing (found: {', '.join(versions)})")

        latest_path = os.path.join(version_dir, "latest.json")
        with open(latest_path, "w", encoding="utf-8") as fh:
            json.dump(build_latest_json(ont, versions), fh, indent=2)
            fh.write("\n")
        print(f"  wrote {os.path.relpath(latest_path)}  (latest={ont['current']}, versions={', '.join(versions)})")

        sections.append(section_html(ont, versions))

    if sections:
        index_path = os.path.join(DIST_ROOT, "index.html")
        with open(index_path, "w", encoding="utf-8") as fh:
            fh.write(build_index_html("".join(sections)))
        print(f"  wrote {os.path.relpath(index_path)}")

    print("\nDone.")


if __name__ == "__main__":
    main()
