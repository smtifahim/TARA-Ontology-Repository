#!/usr/bin/env python3
"""Generate the TARA <-> SCKAN acupoint innervation-pathway viewer.

This is NOT an ontology browser. It reads two cached SPARQL result files and
renders a searchable page that draws, per acupoint, the combined axonal pathway
(soma -> axon -> axon terminal -> collapsed "Target organ(s)" node) of every
SCKAN neuron the acupoint's related nerves fall on (via ilxtr:hasAxonLocation).

Inputs (resources/):
    tara-sckan-mapping.json        acupoint <-> neuron join (+ related nerve,
                                   meridian, phenotype). SPARQL SELECT JSON.
    tara-skan-partial-order.json   per-neuron hasNextNode adjacency list
                                   (V1 -> V2, with location types + IsSynapse +
                                   Target_Organ). SPARQL SELECT JSON.

Output (docs/tara-sckan/):
    index.html                     the viewer (self-contained bar styles.css)
    styles.css
    diagrams/*.svg  (only with --renderer graphviz|both, needs the `dot` binary)

Two renderers:
    interactive  Cytoscape.js + dagre, laid out in the browser from an embedded
                 JSON model. Per-acupoint and merged views, LR/TB, phenotype
                 filter, isolate-neuron, PNG export.
    graphviz     `dot` pre-renders an SVG per view (per acupoint and per facet
                 value) in each layout (TB + LR). `strict digraph`, so parallel
                 edges collapse. The page toggles between the two renderers.

Usage:
    python3 generate_tara_sckan_html.py
    python3 generate_tara_sckan_html.py --renderer cytoscape
    python3 generate_tara_sckan_html.py --out /some/dir --renderer both

This generator is standalone - the release pipeline does NOT call it.

Author: Fahim Imam
"""

import argparse
import datetime
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESOURCES_DIR = HERE / "resources"
# tara-sckan-html -> acupoints-ontology-html -> docs-generator -> ontology-generator -> repo root
REPO_ROOT = HERE.parents[3]
DEFAULT_OUT = REPO_ROOT / "docs" / "tara-sckan"

MAPPING_JSON = RESOURCES_DIR / "tara-sckan-mapping.json"
PARTIAL_ORDER_JSON = RESOURCES_DIR / "tara-skan-partial-order.json"

SCKAN_EXPLORER = "https://services.scicrunch.io/sckan/explorer/?neuron="
ACUPOINTS_BROWSER = "http://purl.org/tara/ontology"  # sibling TARA acupoints browser

# CURIE prefixes. Order matters only in that the longest-matching IRI wins;
# _iri_to_curie sorts by descending IRI length before matching.
PREFIX_IRI_MAPPING = [
    ("mmset1:", "http://uri.interlex.org/tgbugs/uris/readable/sparc-nlp/mmset1/"),
    ("mmset2cn:", "http://uri.interlex.org/tgbugs/uris/readable/sparc-nlp/mmset2cn/"),
    ("mmset4:", "http://uri.interlex.org/tgbugs/uris/readable/sparc-nlp/mmset4/"),
    ("semves:", "http://uri.interlex.org/tgbugs/uris/readable/sparc-nlp/semves/"),
    ("femrep:", "http://uri.interlex.org/tgbugs/uris/readable/sparc-nlp/femrep/"),
    ("prostate:", "http://uri.interlex.org/tgbugs/uris/readable/sparc-nlp/prostate/"),
    ("kidney:", "http://uri.interlex.org/tgbugs/uris/readable/sparc-nlp/kidney/"),
    ("liver:", "http://uri.interlex.org/tgbugs/uris/readable/sparc-nlp/liver/"),
    ("senmot:", "http://uri.interlex.org/tgbugs/uris/readable/sparc-nlp/senmot/"),
    ("swglnd:", "http://uri.interlex.org/tgbugs/uris/readable/sparc-nlp/swglnd/"),
    ("gastint:", "http://uri.interlex.org/composer/uris/set/gastint/"),
    ("portal:", "http://uri.interlex.org/composer/uris/set/portal/"),
    ("pain1:", "http://uri.interlex.org/composer/uris/set/pain1/"),
    ("ilxtr:", "http://uri.interlex.org/tgbugs/uris/readable/"),
    # anatomy / misc - for node IRIs coming out of the partial order
    ("UBERON:", "http://purl.obolibrary.org/obo/UBERON_"),
    ("ILX:", "http://uri.interlex.org/base/ilx_"),
    ("FMA:", "http://purl.org/sig/ont/fma/fma"),
    ("obo:", "http://purl.obolibrary.org/obo/"),
]
_PREFIXES_BY_LEN = sorted(PREFIX_IRI_MAPPING, key=lambda kv: len(kv[1]), reverse=True)

# V*_Type (a location-phenotype label) -> our node role.
ROLE_BY_TYPE = {
    "hasSomaLocation": "soma",
    "hasAxonLocation": "axon",
    "hasAxonTerminalLocation": "terminal",
    "hasAxonSensoryLocation": "sensory",
    "hasAxonToSensoryTerminal": "sensory",
    "hasAxonLeadingToSensoryTerminal": "sensory",
}

PHENOTYPE_COLORS = {
    "parasympathetic": "#2e7d32",
    "sympathetic": "#c62828",
    "sensory": "#1565c0",
    "motor": "#6a1b9a",
    "other": "#455a64",
}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _load_sparql(path):
    """Flatten a SPARQL SELECT JSON result to a list of {var: str} dicts."""
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    out = []
    for b in doc["results"]["bindings"]:
        out.append({k: v["value"] for k, v in b.items()})
    return out


def _clean_iri(iri):
    """A handful of partial-order rows carry a comma-joined double IRI
    (data corruption upstream). Keep the first."""
    if iri and "," in iri:
        iri = iri.split(",", 1)[0]
    return iri


def _iri_to_curie(iri):
    iri = _clean_iri(iri)
    for prefix, base in _PREFIXES_BY_LEN:
        if iri.startswith(base):
            return prefix + iri[len(base):]
    return iri


def _norm_phenotype(text):
    t = (text or "").lower()
    if "para" in t and "sympath" in t:
        return "parasympathetic"
    if "sympath" in t:
        return "sympathetic"
    if "sensory" in t:
        return "sensory"
    if "motor" in t:
        return "motor"
    return "other"


# --------------------------------------------------------------------------- #
# model
# --------------------------------------------------------------------------- #
def build_model():
    mapping = _load_sparql(MAPPING_JSON)
    partial = _load_sparql(PARTIAL_ORDER_JSON)

    # ----- neurons from the partial order (the only ones with a drawable path)
    neurons = {}
    for r in partial:
        niri = r["Neuron_Connected"]
        n = neurons.get(niri)
        if n is None:
            n = neurons[niri] = {
                "iri": niri,
                "curie": _iri_to_curie(niri),
                "explorerUrl": SCKAN_EXPLORER + _iri_to_curie(niri),
                "label": r.get("Neuron_Label", ""),
                "phenotype": _norm_phenotype(r.get("Target_Neuron_Phenotype")),
                "phenotypeLabel": r.get("Target_Neuron_Phenotype", ""),
                "organs": {},   # label -> IRI (Target_Organ_IRI)
                "_nodes": {},
                "_edges": {},
            }
        if not n["label"] and r.get("Neuron_Label"):
            n["label"] = r["Neuron_Label"]
        if r.get("Target_Organ"):
            n["organs"].setdefault(r["Target_Organ"], _clean_iri(r.get("Target_Organ_IRI", "")) or None)

        for side in ("1", "2"):
            nid = _clean_iri(r[f"V{side}_ID"])
            typ = r[f"V{side}_Type"]
            role = ROLE_BY_TYPE.get(typ, "axon")
            syn = side == "2" and r.get("IsSynapse") == "YES"
            existing = n["_nodes"].get(nid)
            if existing is None:
                n["_nodes"][nid] = {
                    "id": nid,
                    "curie": _iri_to_curie(nid),
                    "iri": nid,
                    "label": r[f"V{side}_Collapsed"],
                    "role": role,
                    "synapse": syn,
                }
            else:
                if syn:
                    existing["synapse"] = True
                # soma/terminal beat a plain axon label if types disagree
                if existing["role"] == "axon" and role in ("soma", "terminal", "sensory"):
                    existing["role"] = role
        e_key = (_clean_iri(r["V1_ID"]), _clean_iri(r["V2_ID"]))
        ee = n["_edges"].get(e_key)
        syn2 = r.get("IsSynapse") == "YES"
        if ee is None:
            n["_edges"][e_key] = {"from": e_key[0], "to": e_key[1], "synapse": syn2}
        elif syn2:
            ee["synapse"] = True

    for n in neurons.values():
        n["nodes"] = list(n["_nodes"].values())
        n["edges"] = list(n["_edges"].values())
        n["organs"] = [{"label": k, "iri": v} for k, v in sorted(n["organs"].items())]
        del n["_nodes"], n["_edges"]

    # ----- acupoints from the mapping (the full set; some have no pathway)
    acupoints = {}
    for r in mapping:
        airi = r["acupoint_iri"]
        a = acupoints.get(airi)
        if a is None:
            a = acupoints[airi] = {
                "iri": airi,
                "url": airi,  # purl.org IRI, per spec
                "code": r["acupoint"],
                "meridian": r.get("meridian", ""),
                "meridianUrl": r.get("meridian_iri", ""),
                "_nerves": {},
                "_neurons": {},
                "anchors": {},        # neuronIri -> [related nerve IRIs that are path nodes]
            }
        nlabel = r.get("related_nerve", "")
        niri = r.get("related_nerve_iri", "")
        if niri:
            a["_nerves"].setdefault(niri, {"iri": niri, "label": nlabel, "curie": _iri_to_curie(niri)})
        neu_iri = r["neuron"]
        neu = a["_neurons"].get(neu_iri)
        if neu is None:
            path_n = neurons.get(neu_iri)
            neu = a["_neurons"][neu_iri] = {
                "iri": neu_iri,
                "curie": _iri_to_curie(neu_iri),
                "explorerUrl": SCKAN_EXPLORER + _iri_to_curie(neu_iri),
                "label": (path_n or {}).get("label", ""),
                "phenotype": r.get("neuron_phenotype", ""),
                "phenotypeKind": _norm_phenotype(r.get("neuron_phenotype")),
                "hasPathway": neu_iri in neurons,
            }
        # record the anchor: the related-nerve node the acupoint attaches to
        if niri and neu_iri in neurons:
            node_ids = {nd["id"] for nd in neurons[neu_iri]["nodes"]}
            if niri in node_ids:
                a["anchors"].setdefault(neu_iri, [])
                if niri not in a["anchors"][neu_iri]:
                    a["anchors"][neu_iri].append(niri)

    for a in acupoints.values():
        a["nerves"] = sorted(a["_nerves"].values(), key=lambda x: x["label"].lower())
        a["neurons"] = sorted(a["_neurons"].values(), key=lambda x: (not x["hasPathway"], x["curie"]))
        a["pathwayNeurons"] = [n["iri"] for n in a["neurons"] if n["hasPathway"]]
        a["hasPathway"] = bool(a["pathwayNeurons"])
        # terminal entities (axon-terminal nodes) + end organs (label + IRI)
        terms, coarse = {}, {}
        for niri in a["pathwayNeurons"]:
            pn = neurons[niri]
            for o in pn["organs"]:
                if o["label"] not in coarse or (o["iri"] and not coarse[o["label"]]):
                    coarse[o["label"]] = o["iri"]
            for nd in pn["nodes"]:
                if nd["role"] in ("terminal", "sensory"):
                    terms.setdefault(nd["id"], {"iri": nd["iri"], "curie": nd["curie"], "label": nd["label"]})
        a["terminals"] = sorted(terms.values(), key=lambda x: x["label"].lower())
        a["coarseOrgans"] = [{"label": k, "iri": v} for k, v in sorted(coarse.items())]
        del a["_nerves"], a["_neurons"]

    # ----- search facets
    facets = {"meridian": {}, "nerve": {}, "neuron": {}, "organ": {}, "phenotype": {}}
    for a in acupoints.values():
        if a["meridian"]:
            facets["meridian"].setdefault(a["meridian"], set()).add(a["iri"])
        for nv in a["nerves"]:
            facets["nerve"].setdefault(nv["label"], set()).add(a["iri"])
        for nu in a["neurons"]:
            facets["neuron"].setdefault(nu["curie"], set()).add(a["iri"])
        for org in a["coarseOrgans"]:
            facets["organ"].setdefault(org["label"], set()).add(a["iri"])
        for niri in a["pathwayNeurons"]:
            facets["phenotype"].setdefault(neurons[niri]["phenotype"].capitalize(), set()).add(a["iri"])
    facets = {
        kind: {k: sorted(v) for k, v in vals.items()}
        for kind, vals in facets.items()
    }

    ordered_acu = sorted(acupoints.values(), key=lambda a: _natkey(a["code"]))
    stats = {
        "acupoints": len(acupoints),
        "withPathway": sum(1 for a in acupoints.values() if a["hasPathway"]),
        "mappingNeurons": len({n["iri"] for a in acupoints.values() for n in a["neurons"]}),
        "pathwayNeurons": len(neurons),
    }
    return {
        "generated": datetime.date.today().isoformat(),
        "explorerBase": SCKAN_EXPLORER,
        "acupointsBrowser": ACUPOINTS_BROWSER,
        "stats": stats,
        "phenotypeColors": PHENOTYPE_COLORS,
        "neurons": neurons,
        "acupoints": ordered_acu,
        "acupointsByIri": {a["iri"]: a for a in ordered_acu},
        "facets": facets,
    }


def _natkey(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s or "")]


# --------------------------------------------------------------------------- #
# Graphviz static rendering
# --------------------------------------------------------------------------- #
_NODE_STYLE = {
    "soma": 'shape=box, style="rounded,filled", color="#43a047", fillcolor="#e8f5e9"',
    "axon": 'shape=box, style="rounded,filled,dashed", color="#5c6bc0", fillcolor="#e8eaf6"',
    "terminal": 'shape=box, style="filled", color="#e53935", fillcolor="#ffebee"',
    "sensory": 'shape=box, style="rounded,filled", color="#8d6e63", fillcolor="#efebe9"',
}
_SYNAPSE_STYLE = 'shape=box, style="rounded,filled", color="#2e7d32", fillcolor="#e8f5e9", peripheries=2'
_ACU_STYLE = 'shape=box, style="rounded,filled", color="#fb8c00", fillcolor="#fff3e0", penwidth=2'
_ORGAN_STYLE = 'shape=box, style="filled", color="#607d8b", fillcolor="#eceff1", penwidth=1.5'


def _dot_escape(text):
    return (text or "").replace("\\", "\\\\").replace('"', '\\"')


def _dot_label(text, width=26):
    """Escape for a DOT quoted string, then soft-wrap on real \\n line breaks."""
    safe = _dot_escape(text or "")
    words, lines, cur = safe.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return "\\n".join(lines) or safe


def build_dot(model, acu_iris, layout="TB"):
    """DOT for one view: the combined pathway of every pathway-neuron of every
    acupoint in `acu_iris`, each acupoint its own anchor node, all terminals
    funnelling into one collapsed 'Target organ(s)' node."""
    neurons = model["neurons"]
    by_iri = model["acupointsByIri"]
    acus = [by_iri[i] for i in acu_iris if i in by_iri and by_iri[i]["hasPathway"]]
    if not acus:
        return None

    lines = [
        # `strict` collapses the parallel edges two neurons can create between
        # the same ordered pair of nodes into a single edge
        "strict digraph pathway {",
        f'  rankdir={layout};',
        '  graph [bgcolor="transparent", nodesep=0.35, ranksep=0.55];',
        '  node  [fontname="Helvetica", fontsize=10, margin="0.12,0.07"];',
        '  edge  [fontname="Helvetica", fontsize=9, arrowsize=0.8];',
    ]

    drawn_neurons = []
    seen_n = set()
    for a in acus:
        for niri in a["pathwayNeurons"]:
            if niri not in seen_n:
                seen_n.add(niri)
                drawn_neurons.append(niri)

    # shared pathway nodes (union by id across drawn neurons)
    nodes = {}
    for niri in drawn_neurons:
        for nd in neurons[niri]["nodes"]:
            cur = nodes.get(nd["id"])
            if cur is None:
                nodes[nd["id"]] = dict(nd)
            else:
                if nd["synapse"]:
                    cur["synapse"] = True
                if cur["role"] == "axon" and nd["role"] in ("soma", "terminal", "sensory"):
                    cur["role"] = nd["role"]

    def nid(x):
        return '"n_' + re.sub(r"[^A-Za-z0-9]", "_", x) + '"'

    for x, nd in nodes.items():
        style = _SYNAPSE_STYLE if nd["synapse"] else _NODE_STYLE.get(nd["role"], _NODE_STYLE["axon"])
        url = html.escape(nd["iri"], quote=True)
        # synapse nodes get an id="syn__..." so the static view can toggle them
        gid = f'id="syn__{re.sub(r"[^A-Za-z0-9]", "_", x)}", ' if nd["synapse"] else ""
        # node shows the plain label only; the CURIE is just the link-out target
        lines.append(f'  {nid(x)} [{gid}label="{_dot_label(nd["label"])}", {style}, '
                     f'URL="{url}", target="_blank", '
                     f'tooltip="{_dot_escape(nd["curie"] + " — " + nd["label"])}"];')

    # collapsed target-organ node - labelled with the actual end organ(s)
    organs = {}
    for a in acus:
        for o in a["coarseOrgans"]:
            organs.setdefault(o["label"], o["iri"])
    org_names = sorted(organs)
    org_label = ", ".join(org_names) if org_names else "target organ(s)"
    org_url = ""
    if len(org_names) == 1 and organs[org_names[0]]:
        org_url = f', URL="{html.escape(organs[org_names[0]], quote=True)}", target="_blank"'
    lines.append(f'  "organ" [label="{_dot_label(org_label, width=30)}", {_ORGAN_STYLE}{org_url}];')

    # pathway edges: ONE edge per ordered node pair (parallel edges from
    # different neurons are collapsed - `strict` also enforces this at parse
    # time). Colour = the phenotype if all contributing neurons agree, else grey.
    edge_phenos = {}
    for niri in drawn_neurons:
        ph = neurons[niri]["phenotype"]
        for e in neurons[niri]["edges"]:
            edge_phenos.setdefault((e["from"], e["to"]), set()).add(ph)
    for (frm, to), phs in edge_phenos.items():
        color = PHENOTYPE_COLORS.get(next(iter(phs)), PHENOTYPE_COLORS["other"]) \
            if len(phs) == 1 else PHENOTYPE_COLORS["other"]
        lines.append(f'  {nid(frm)} -> {nid(to)} [color="{color}"];')

    # terminals -> organ
    for x, nd in nodes.items():
        if nd["role"] in ("terminal", "sensory"):
            lines.append(f'  {nid(x)} -> "organ" [color="#607d8b", style=solid];')

    # acupoint anchors
    for a in acus:
        an = 'acu_' + re.sub(r"[^A-Za-z0-9]", "_", a["iri"])
        lines.append(f'  "{an}" [label="{_dot_escape(a["code"])}", {_ACU_STYLE}, '
                     f'URL="{html.escape(a["url"], quote=True)}", target="_blank"];')
        targets = []
        for niri in a["pathwayNeurons"]:
            targets += a["anchors"].get(niri, [])
        if not targets:  # fall back: attach to that neuron's soma nodes
            for niri in a["pathwayNeurons"]:
                targets += [nd["id"] for nd in neurons[niri]["nodes"] if nd["role"] == "soma"]
        for t in dict.fromkeys(targets):
            if t in nodes:
                lines.append(f'  "{an}" -> {nid(t)} [style=dashed, color="#fb8c00"];')

    lines.append("}")
    return "\n".join(lines)


def render_svg(dot_src):
    try:
        proc = subprocess.run(
            ["dot", "-Tsvg"], input=dot_src.encode("utf-8"),
            capture_output=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"graphviz `dot` failed: {exc}") from exc
    svg = proc.stdout.decode("utf-8")
    svg = re.sub(r"^.*?(<svg\b)", r"\1", svg, count=1, flags=re.S)  # drop xml/doctype prolog
    svg = svg.replace("<svg ", '<svg class="pathway-svg" ', 1)
    return svg


def build_all_svgs(model, layouts=("TB",)):
    """Every view the search can land on -> SVG string, keyed 'kind::key::layout'."""
    out = {}

    def add(key, acu_iris):
        for lay in layouts:
            dot_src = build_dot(model, acu_iris, layout=lay)
            if dot_src is None:
                continue
            try:
                out[f"{key}::{lay}"] = render_svg(dot_src)
            except RuntimeError as exc:
                print(f"  WARNING: {key} ({lay}): {exc}")

    for a in model["acupoints"]:
        if a["hasPathway"]:
            add(f"acupoint::{a['iri']}", [a["iri"]])
    for kind, vals in model["facets"].items():
        for k, iris in vals.items():
            if any(model["acupointsByIri"][i]["hasPathway"] for i in iris):
                add(f"{kind}::{k}", iris)
    return out


# --------------------------------------------------------------------------- #
# page assembly
# --------------------------------------------------------------------------- #
CSS = r"""
:root{
  --bg:#ffffff;--panel:#f7f8fa;--border:#dfe2e6;--text:#1a1f27;--muted:#5b6472;
  --accent:#4472c4;--accent-weak:#eaf0fb;--highlight:#fff3c4;
  --pill-bg:#e6f2fb;--pill-border:#b7d9ee;
}
@media(prefers-color-scheme:dark){:root{
  --bg:#14171c;--panel:#1b1f26;--border:#2d333d;--text:#e6e9ef;--muted:#9aa4b2;
  --accent:#7fa4e8;--accent-weak:#233047;--highlight:#4d431f;
  --pill-bg:#1e2c3b;--pill-border:#33506b;
}}
*{box-sizing:border-box}
body{margin:0;padding:0;background:var(--bg);color:var(--text);line-height:1.5;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
a{color:var(--accent)}
main{max-width:1180px;margin:0 auto;padding:2rem 1.4rem 4rem}
h1{font-size:1.35rem;margin:0 0 .3rem}
.lede{color:var(--muted);margin:0 0 1.4rem;font-size:.95rem;max-width:70ch}
.lede code{font-size:.85em}

.controls{display:flex;flex-wrap:wrap;gap:.7rem;align-items:center;
  padding:.85rem 1rem;background:var(--panel);border:1px solid var(--border);border-radius:10px}
.controls label{font-size:.8rem;color:var(--muted);text-transform:uppercase;letter-spacing:.03em}
.controls select,.controls input[type=text]{font:inherit;padding:.4rem .55rem;
  border:1px solid var(--border);border-radius:7px;background:var(--bg);color:var(--text)}
.controls .search-wrap{position:relative;flex:1 1 22rem;min-width:14rem}
.controls input[type=text]{width:100%}
.ac-list{position:absolute;z-index:20;left:0;right:0;top:calc(100% + 3px);max-height:16rem;
  overflow:auto;background:var(--bg);border:1px solid var(--border);border-radius:8px;
  box-shadow:0 6px 24px rgba(0,0,0,.14);display:none}
.ac-list.open{display:block}
.ac-item{padding:.4rem .6rem;cursor:pointer;display:flex;gap:.5rem;align-items:baseline}
.ac-item.active,.ac-item:hover{background:var(--accent-weak)}
.ac-item .k{font-size:.68rem;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);
  border:1px solid var(--border);border-radius:4px;padding:0 .3rem}
.renderer-toggle{margin-left:auto;display:flex;gap:.3rem;align-items:center}
.renderer-toggle button{font:inherit;font-size:.82rem;padding:.35rem .6rem;border:1px solid var(--border);
  background:var(--bg);color:var(--text);border-radius:7px;cursor:pointer}
.renderer-toggle button.on{background:var(--accent);border-color:var(--accent);color:#fff}
.renderer-toggle button:disabled{opacity:.4;cursor:not-allowed}

#results{margin-top:1.6rem;display:flex;flex-direction:column;gap:2rem}
.result-block{border:1px solid var(--border);border-radius:12px;overflow:hidden}
.result-head{padding:.9rem 1.1rem;background:var(--panel);border-bottom:1px solid var(--border)}
.result-head h2{margin:0;font-size:1.05rem}
.result-head .summary{margin:.3rem 0 0;color:var(--muted);font-size:.9rem;max-width:70ch}
/* don't let a long pill row or summary line dictate the card width */
.result-block .pill-row{max-width:min(100%, 68rem)}
.result-body{padding:1.1rem}

.pill-row{display:flex;flex-wrap:wrap;align-items:center;gap:.35rem .4rem;margin:.35rem 0}
.pill-row .lbl{font-size:.72rem;text-transform:uppercase;letter-spacing:.03em;color:var(--muted);
  align-self:center;margin:0 .1rem 0 .55rem;font-weight:700}
.pill-row .lbl:first-child{margin-left:0}
.chip{display:inline-flex;align-items:center;gap:.3rem;background:var(--pill-bg);border:1px solid var(--pill-border);
  border-radius:5px;padding:.14rem .5rem;font-size:.82rem;text-decoration:none;color:var(--text)}
a.chip:hover{border-color:var(--accent);color:var(--accent)}
.chip .sub{color:var(--muted);font-size:.75rem}

.neuron-list{margin:.6rem 0 0;display:flex;flex-direction:column;gap:.35rem}
.neuron-row{display:flex;flex-wrap:wrap;gap:.5rem;align-items:baseline;font-size:.85rem}
.neuron-row .pheno{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.03em}
.neuron-row .nlabel{color:var(--muted)}
.no-pathway{margin:.8rem 0 0;padding:.6rem .8rem;border-left:3px solid var(--border);
  color:var(--muted);font-size:.88rem;background:var(--panel)}

/* no nested panel - the diagram + its controls sit directly in the result body */
.diagram-block{margin-top:1.1rem}
.diagram-controls{display:flex;flex-wrap:wrap;gap:.5rem .9rem;align-items:center;
  margin-bottom:.75rem;font-size:.82rem}
.diagram-controls .grp{display:flex;gap:.35rem;align-items:center}
.diagram-controls .grp>span:first-child{color:var(--muted);text-transform:uppercase;
  letter-spacing:.03em;font-size:.72rem;font-weight:700}
.diagram-controls button{font:inherit;font-size:.8rem;padding:.28rem .55rem;border:1px solid var(--border);
  background:var(--bg);color:var(--text);border-radius:6px;cursor:pointer}
.diagram-controls button.on{background:var(--accent);border-color:var(--accent);color:#fff}
.diagram-controls button:disabled{opacity:.4;cursor:not-allowed}
.diagram-controls label.chk{display:flex;gap:.3rem;align-items:center;color:var(--text);
  text-transform:none;letter-spacing:0}
.diagram-controls select{font:inherit;font-size:.8rem;padding:.24rem .4rem;border:1px solid var(--border);
  border-radius:6px;background:var(--bg);color:var(--text)}
.diagram-info{padding:0 0 .5rem}
.diagram-info:empty{display:none}
/* the host shrink-wraps the diagram (both axes), capped at the panel width:
   static -> the SVG's own size; interactive -> set inline from the laid-out
   graph's bounding box. Anything larger scrolls inside the host. */
.diagram-host{position:relative;box-sizing:border-box;min-width:260px;max-width:100%;
  min-height:150px;overflow:auto;background:var(--bg);border:1px solid var(--border);border-radius:8px}
.diagram-host.static{width:fit-content;padding:.8rem;min-height:0;max-height:85vh}
.pathway-svg{max-width:none;height:auto;display:block}
.cy-canvas{position:absolute;inset:0}

.legend{display:flex;flex-wrap:wrap;gap:.5rem 1rem;margin-top:.7rem;padding:.1rem 0;
  font-size:.76rem;color:var(--muted);align-items:center}
.legend .k{display:inline-flex;gap:.35rem;align-items:center}
.legend .sw{width:20px;height:14px;border-radius:4px;display:inline-block;border:1.5px solid}
.sw-soma{background:#e8f5e9;border-color:#43a047}
.sw-axon{background:#e8eaf6;border-color:#5c6bc0;border-style:dashed}
.sw-terminal{background:#ffebee;border-color:#e53935}
.sw-sensory{background:#efebe9;border-color:#8d6e63}
.sw-synapse{background:#e8f5e9;border-color:#2e7d32;box-shadow:0 0 0 2px #fff,0 0 0 3.5px #2e7d32}
.legend .ph{display:inline-flex;gap:.3rem;align-items:center}
.legend .ph i{width:16px;height:3px;display:inline-block;border-radius:2px}

.caption-table{border-collapse:collapse;font-size:.82rem;margin-top:.8rem}
.caption-table th,.caption-table td{text-align:left;padding:.4rem .6rem;border-bottom:1px solid var(--border);vertical-align:top}
.caption-table th{color:var(--muted);font-weight:600}
.caption-table td:last-child{max-width:34rem;white-space:normal;overflow-wrap:anywhere}
.caption-table tr:last-child td{border-bottom:0}
/* keep long SCKAN labels from stretching the (shrink-wrapping) card */
.neuron-row{max-width:44rem}
.neuron-row .nlabel{overflow-wrap:anywhere}

.disclosure-controls{display:flex;flex-wrap:wrap;gap:.3rem 1rem;margin-top:.8rem}
.disclosure-controls:empty{display:none}
.disclosure-btn{background:none;border:0;padding:.2rem 0;color:var(--accent);font:inherit;font-size:.85rem;cursor:pointer}
.disclosure-btn:hover{text-decoration:underline}
.disclosure-hidden{display:none!important}

.result-body h3{font-size:.95rem;margin:1.6rem 0 .4rem}
.result-body h4{font-size:.88rem;margin:0 0 .3rem;color:var(--muted)}
.hint{color:var(--muted);font-size:.9rem}
.stat-pills{display:flex;flex-wrap:wrap;gap:.5rem;margin:.6rem 0 0}
.stat-pills .chip{cursor:default}
footer{margin-top:3rem;color:var(--muted);font-size:.8rem;border-top:1px solid var(--border);padding-top:1rem}
"""


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TARA Acupoint Innervation Pathways</title>
<link rel="stylesheet" href="styles.css">
</head>
<body>
<main>
<h1>TARA Acupoint Innervation Pathways</h1>
<p class="lede">Axonal pathways of the SCKAN neurons whose course
(<code>ilxtr:hasAxonLocation</code>) passes through an acupoint's related nerves,
drawn from soma &rarr; axon &rarr; axon terminal into a collapsed
<em>Target organ(s)</em> node. Acupoint and meridian names link to the
<a href="__BROWSER__">TARA Acupoints Ontology</a>; neuron names link to the
SCKAN Explorer.</p>

<div class="controls">
  <label for="by">Search by</label>
  <select id="by">
    <option value="acupoint">Acupoint</option>
    <option value="meridian">Meridian</option>
    <option value="nerve">Related nerve</option>
    <option value="neuron">Mapping neuron</option>
    <option value="organ">Target organ</option>
    <option value="phenotype">Phenotype</option>
  </select>
  <div class="search-wrap">
    <input type="text" id="q" autocomplete="off" spellcheck="false" placeholder="Start typing&hellip;">
    <div class="ac-list" id="ac"></div>
  </div>
  <div class="renderer-toggle" id="renderer">
    <span>View</span>
    <button data-r="interactive" class="on">Interactive</button>
    <button data-r="graphviz">Static</button>
  </div>
</div>

<div id="results"></div>

<footer>
  Generated __GENERATED__ &middot;
  <a href="https://github.com/SciCrunch/TARA-Ontology-Repository">SciCrunch/TARA-Ontology-Repository</a>
</footer>
</main>

<script id="tara-sckan-data" type="application/json">__DATA_JSON__</script>
<script src="https://cdn.jsdelivr.net/npm/cytoscape@3.30.2/dist/cytoscape.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/dagre@0.8.5/dist/dagre.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/cytoscape-dagre@2.5.0/cytoscape-dagre.min.js"></script>
<script>
__APP_JS__
</script>
</body>
</html>
"""


APP_JS = r"""
(function () {
  "use strict";
  var DATA = JSON.parse(document.getElementById("tara-sckan-data").textContent);
  var SVGS = DATA.svg || {};
  var HAS_STATIC = Object.keys(SVGS).length > 0;
  var STATIC_LAYOUTS = DATA.svgLayouts || ["TB"];
  var PH = DATA.phenotypeColors;
  var byIri = {};
  DATA.acupoints.forEach(function (a) { byIri[a.iri] = a; });
  if (window.cytoscape && window.cytoscapeDagre) { cytoscape.use(window.cytoscapeDagre); }

  var renderer = "interactive";
  if (!window.cytoscape) { renderer = HAS_STATIC ? "graphviz" : "interactive"; }

  // ---------- small helpers ----------
  function el(tag, cls, txt) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt != null) e.textContent = txt;
    return e;
  }
  function chip(text, href, sub) {
    var e = el(href ? "a" : "span", "chip");
    e.appendChild(document.createTextNode(text));
    if (sub) { var s = el("span", "sub", sub); e.appendChild(s); }
    if (href) { e.href = href; e.target = "_blank"; e.rel = "noopener"; }
    return e;
  }
  function natkey(s) {
    return (s || "").split(/(\d+)/).map(function (t) { return /^\d+$/.test(t) ? parseInt(t, 10) : t.toLowerCase(); });
  }
  function natcmp(a, b) {
    var x = natkey(a), y = natkey(b);
    for (var i = 0; i < Math.max(x.length, y.length); i++) {
      var p = x[i], q = y[i];
      if (p === undefined) return -1;
      if (q === undefined) return 1;
      if (p < q) return -1;
      if (p > q) return 1;
    }
    return 0;
  }
  function attachDisclosure(items, host, base, step) {
    base = Math.min(base, items.length); step = step || 5;
    var shown = base;
    var ctr = el("div", "disclosure-controls");
    host.appendChild(ctr);
    function mk(label, fn) { var b = el("button", "disclosure-btn", label); b.type = "button"; b.onclick = fn; ctr.appendChild(b); }
    function apply() {
      items.forEach(function (it, i) { it.classList.toggle("disclosure-hidden", i >= shown); });
      ctr.innerHTML = "";
      if (shown < items.length) {
        mk("Show " + Math.min(step, items.length - shown) + " more", function () { shown = Math.min(shown + step, items.length); apply(); });
        mk("Show all " + items.length, function () { shown = items.length; apply(); });
      }
      if (shown > base) mk("Collapse", function () { shown = base; apply(); });
    }
    apply();
  }

  // ---------- combined graph model (used by cytoscape) ----------
  function combinedGraph(acuList) {
    var nodes = {}, edges = {}, drawnNeurons = [], seen = {};
    acuList.forEach(function (a) {
      (a.pathwayNeurons || []).forEach(function (niri) {
        if (!seen[niri]) { seen[niri] = 1; drawnNeurons.push(niri); }
      });
    });
    drawnNeurons.forEach(function (niri) {
      var pn = DATA.neurons[niri];
      pn.nodes.forEach(function (nd) {
        var cur = nodes[nd.id];
        if (!cur) { nodes[nd.id] = { id: nd.id, curie: nd.curie, iri: nd.iri, label: nd.label, role: nd.role, synapse: nd.synapse }; }
        else {
          if (nd.synapse) cur.synapse = true;
          if (cur.role === "axon" && (nd.role === "soma" || nd.role === "terminal" || nd.role === "sensory")) cur.role = nd.role;
        }
      });
      pn.edges.forEach(function (e) {
        // one entry per ordered node pair; parallel edges from different
        // neurons collapse (matches the static `strict digraph`)
        var k = e.from + " || " + e.to;
        var cur = edges[k];
        if (!cur) { cur = edges[k] = { from: e.from, to: e.to, phenos: {}, neurons: {}, synapse: e.synapse }; }
        if (e.synapse) cur.synapse = true;
        cur.phenos[pn.phenotype] = 1;
        cur.neurons[niri] = 1;
      });
    });
    return { nodes: nodes, edges: edges, drawnNeurons: drawnNeurons };
  }

  function safeId(prefix, x) { return prefix + String(x).replace(/[^A-Za-z0-9]/g, "_"); }

  function cyElements(acuList) {
    var g = combinedGraph(acuList);
    var els = [];
    Object.keys(g.nodes).forEach(function (id) {
      var nd = g.nodes[id];
      els.push({ data: { id: safeId("n_", id), label: nd.label, curie: nd.curie, role: nd.synapse ? "synapse" : nd.role, iri: nd.iri } });
    });
    var orgMap = {};
    acuList.forEach(function (a) {
      (a.coarseOrgans || []).forEach(function (o) { if (!(o.label in orgMap)) orgMap[o.label] = o.iri || null; });
    });
    var orgNames = Object.keys(orgMap).sort();
    els.push({ data: {
      id: "organ", role: "organ",
      label: orgNames.length ? orgNames.join(", ") : "target organ(s)",
      iri: orgNames.length === 1 ? orgMap[orgNames[0]] : null
    } });
    Object.keys(g.edges).forEach(function (k) {
      var e = g.edges[k];
      var phs = Object.keys(e.phenos);
      els.push({ data: {
        id: safeId("e_", k),
        source: safeId("n_", e.from), target: safeId("n_", e.to),
        color: phs.length === 1 ? (PH[phs[0]] || PH.other) : PH.other,
        kind: "path", phenos: phs, neurons: Object.keys(e.neurons) } });
    });
    Object.keys(g.nodes).forEach(function (id) {
      var nd = g.nodes[id];
      if (nd.role === "terminal" || nd.role === "sensory") {
        els.push({ data: { id: safeId("eo_", id), source: safeId("n_", id), target: "organ", color: "#607d8b", kind: "organ" } });
      }
    });
    acuList.forEach(function (a) {
      var aid = safeId("acu_", a.iri);
      els.push({ data: { id: aid, label: a.code, role: "acupoint", iri: a.url } });
      var targets = [];
      (a.pathwayNeurons || []).forEach(function (niri) {
        targets = targets.concat((a.anchors && a.anchors[niri]) || []);
      });
      if (!targets.length) {
        (a.pathwayNeurons || []).forEach(function (niri) {
          DATA.neurons[niri].nodes.forEach(function (nd) { if (nd.role === "soma") targets.push(nd.id); });
        });
      }
      targets.filter(function (v, i, s) { return s.indexOf(v) === i; }).forEach(function (t) {
        if (g.nodes[t]) els.push({ data: { id: safeId("ea_", aid + "_" + t), source: aid, target: safeId("n_", t), color: "#fb8c00", kind: "anchor" } });
      });
    });
    return { els: els, drawnNeurons: g.drawnNeurons };
  }

  var CY_STYLE = [
    { selector: "node", style: {
        "label": "data(label)", "text-wrap": "wrap", "text-max-width": 150,
        "text-valign": "center", "text-halign": "center", "font-size": 10,
        "shape": "round-rectangle", "background-color": "#eef1f5", "border-width": 1.5,
        "border-color": "#9aa4b2", "padding": "6px", "width": "label", "height": "label" } },
    { selector: 'node[role="soma"]', style: { "background-color": "#e8f5e9", "border-color": "#43a047" } },
    { selector: 'node[role="axon"]', style: { "background-color": "#e8eaf6", "border-color": "#5c6bc0", "border-style": "dashed" } },
    { selector: 'node[role="terminal"]', style: { "background-color": "#ffebee", "border-color": "#e53935" } },
    { selector: 'node[role="sensory"]', style: { "background-color": "#efebe9", "border-color": "#8d6e63" } },
    { selector: 'node[role="synapse"]', style: { "background-color": "#e8f5e9", "border-color": "#2e7d32", "border-width": 3 } },
    { selector: 'node[role="acupoint"]', style: { "background-color": "#fff3e0", "border-color": "#fb8c00", "border-width": 2, "font-weight": "bold" } },
    { selector: 'node[role="organ"]', style: { "background-color": "#eceff1", "border-color": "#607d8b", "border-width": 1.5 } },
    { selector: "edge", style: {
        "curve-style": "bezier", "target-arrow-shape": "triangle", "width": 1.5,
        "line-color": "data(color)", "target-arrow-color": "data(color)", "arrow-scale": 0.9 } },
    { selector: 'edge[kind="anchor"]', style: { "line-style": "dashed" } },
    { selector: ".dim", style: { "opacity": 0.12 } }
  ];

  // ---------- diagram block ----------
  function legend(phenos) {
    var l = el("div", "legend");
    [["soma", "Soma location"], ["axon", "Axon location"], ["terminal", "Axon terminal"],
     ["sensory", "Sensory terminal"], ["synapse", "Synapse location"]].forEach(function (p) {
      var k = el("span", "k");
      k.appendChild(el("span", "sw sw-" + p[0]));
      k.appendChild(document.createTextNode(p[1]));
      l.appendChild(k);
    });
    Object.keys(phenos).forEach(function (ph) {
      var k = el("span", "ph");
      var i = el("i"); i.style.background = PH[ph] || PH.other; k.appendChild(i);
      k.appendChild(document.createTextNode(ph.charAt(0).toUpperCase() + ph.slice(1)));
      l.appendChild(k);
    });
    return l;
  }

  function neuronCaption(drawnNeurons) {
    var t = el("table", "caption-table");
    var thead = el("thead");
    thead.innerHTML = "<tr><th>Neuron</th><th>Phenotype</th><th>Population label (SCKAN)</th></tr>";
    t.appendChild(thead);
    var tb = el("tbody");
    drawnNeurons.map(function (i) { return DATA.neurons[i]; })
      .sort(function (a, b) { return natcmp(a.curie, b.curie); })
      .forEach(function (n) {
        var tr = el("tr");
        var td1 = el("td");
        td1.appendChild(chip(n.curie, n.explorerUrl));
        tr.appendChild(td1);
        tr.appendChild(el("td", null, n.phenotypeLabel || "—"));
        tr.appendChild(el("td", null, n.label || "—"));
        tb.appendChild(tr);
      });
    t.appendChild(tb);
    return t;
  }

  function diagramBlock(acuList, opts) {
    opts = opts || {};
    var viewKey = opts.viewKey;                    // 'acupoint::<iri>' | 'meridian::x' ...
    var block = el("div", "diagram-block");

    var g = combinedGraph(acuList);
    var phenos = {};
    g.drawnNeurons.forEach(function (i) { phenos[DATA.neurons[i].phenotype] = 1; });

    var ctrls = el("div", "diagram-controls");
    var state = { layout: "TB", synapse: true, isolate: "", phenoOff: {} };

    // layout
    var gL = el("div", "grp");
    gL.appendChild(el("span", null, "Layout"));
    var bTB = el("button", "on", "Top→Bottom"); bTB.type = "button";
    var bLR = el("button", null, "Left→Right"); bLR.type = "button";
    gL.appendChild(bTB); gL.appendChild(bLR);
    ctrls.appendChild(gL);

    // synapse
    var lS = el("label", "chk");
    var cS = document.createElement("input"); cS.type = "checkbox"; cS.checked = true;
    lS.appendChild(cS); lS.appendChild(document.createTextNode("Show synaptic connections"));
    ctrls.appendChild(lS);

    // phenotype filter
    var gP = el("div", "grp");
    gP.appendChild(el("span", null, "Phenotype"));
    Object.keys(phenos).forEach(function (ph) {
      var b = el("button", "on", ph.charAt(0).toUpperCase() + ph.slice(1)); b.type = "button";
      b.style.borderColor = PH[ph] || PH.other;
      b.onclick = function () {
        state.phenoOff[ph] = !state.phenoOff[ph];
        b.classList.toggle("on", !state.phenoOff[ph]);
        redraw();
      };
      gP.appendChild(b);
    });
    if (Object.keys(phenos).length > 1) ctrls.appendChild(gP);

    // isolate: whole view, one acupoint, or one neuron
    var gI = el("div", "grp");
    gI.appendChild(el("span", null, "Isolate"));
    var sel = document.createElement("select");
    sel.appendChild(new Option("Show all", ""));
    if (acuList.length > 1) {
      var og1 = document.createElement("optgroup"); og1.label = "Acupoint";
      acuList.slice().sort(function (a, b) { return natcmp(a.code, b.code); })
        .forEach(function (a) { og1.appendChild(new Option(a.code, "acu:" + a.iri)); });
      sel.appendChild(og1);
    }
    var og2 = document.createElement("optgroup"); og2.label = "Neuron";
    g.drawnNeurons.map(function (i) { return DATA.neurons[i]; })
      .sort(function (a, b) { return natcmp(a.curie, b.curie); })
      .forEach(function (n) { og2.appendChild(new Option(n.curie, "neu:" + n.iri)); });
    sel.appendChild(og2);
    sel.onchange = function () { state.isolate = sel.value; redraw(); };
    gI.appendChild(sel);
    ctrls.appendChild(gI);

    // export
    var bX = el("button", null, "Export PNG"); bX.type = "button";
    ctrls.appendChild(bX);

    block.appendChild(ctrls);

    var infoSlot = el("div", "diagram-info");
    block.appendChild(infoSlot);
    function refreshInfo() {
      infoSlot.innerHTML = "";
      if (state.isolate.indexOf("acu:") === 0) {
        var a = byIri[state.isolate.slice(4)];
        if (a) infoSlot.appendChild(acuInfo(a));
      }
    }

    var host = el("div", "diagram-host");
    block.appendChild(host);
    block.appendChild(legend(phenos));
    block.appendChild(neuronCaption(g.drawnNeurons));

    var cy = null;

    function setStaticControlsEnabled(on) {
      // Layout / synapse / isolate / export work in both renderers. Only the
      // phenotype filter needs the live graph (a pre-rendered SVG can't refilter).
      var layoutOk = on || STATIC_LAYOUTS.length > 1;
      [bTB, bLR].forEach(function (n) { n.disabled = !layoutOk; n.title = layoutOk ? "" : "Needs both layouts pre-rendered"; });
      [cS, sel, bX].forEach(function (n) { n.disabled = false; n.title = ""; });
      Array.prototype.forEach.call(gP.querySelectorAll("button"), function (b) {
        b.disabled = !on; b.title = on ? "" : "Interactive view only";
      });
    }

    function redraw() {
      refreshInfo();
      if (renderer === "graphviz") { drawStatic(); return; }
      drawCy();
    }

    function staticKey() {
      var lay = STATIC_LAYOUTS.indexOf(state.layout) >= 0 ? state.layout : STATIC_LAYOUTS[0];
      var iso = state.isolate;
      if (iso.indexOf("acu:") === 0) return "acupoint::" + iso.slice(4) + "::" + lay;
      if (iso.indexOf("neu:") === 0) {
        var n = DATA.neurons[iso.slice(4)];
        return n ? "neuron::" + n.curie + "::" + lay : null;
      }
      return viewKey + "::" + lay;
    }

    function applyStaticSynapse() {
      var on = cS.checked;
      var syn = host.querySelectorAll('g[id^="syn__"]');
      Array.prototype.forEach.call(syn, function (gEl) { gEl.style.opacity = on ? "" : "0.12"; });
    }

    function drawStatic() {
      host.className = "diagram-host static";
      host.style.height = "";   // CSS width:fit-content + the SVG's own size drive it
      host.style.width = "";
      setStaticControlsEnabled(false);
      var svg = SVGS[staticKey()] || SVGS[viewKey + "::" + STATIC_LAYOUTS[0]];
      host.innerHTML = svg || '<p class="hint" style="padding:1rem">No static diagram for this selection.</p>';
      applyStaticSynapse();
    }

    function drawCy() {
      host.className = "diagram-host";
      setStaticControlsEnabled(true);
      var isoNeuron = state.isolate.indexOf("neu:") === 0 ? state.isolate.slice(4) : null;
      var acuUse = acuList;
      if (state.isolate.indexOf("acu:") === 0) {
        var only = state.isolate.slice(4);
        acuUse = acuList.filter(function (a) { return a.iri === only; });
      }
      var built = cyElements(acuUse);
      var nodeEls = built.els.filter(function (x) { return !x.data.source; });
      var edgeEls = built.els.filter(function (x) { return x.data.source; });

      // 1. keep path edges allowed by the phenotype / isolate filters
      var pathEdges = edgeEls.filter(function (x) {
        var d = x.data;
        if (d.kind !== "path") return false;
        // drop only if every contributing phenotype is toggled off
        if (d.phenos.every(function (p) { return state.phenoOff[p]; })) return false;
        if (isoNeuron && d.neurons.indexOf(isoNeuron) < 0) return false;
        return true;
      });
      var live = {};
      pathEdges.forEach(function (x) { live[x.data.source] = 1; live[x.data.target] = 1; });

      // 2. organ + anchor edges survive only if their pathway endpoint is live
      var organEdges = edgeEls.filter(function (x) { return x.data.kind === "organ" && live[x.data.source]; });
      var anchorEdges = edgeEls.filter(function (x) { return x.data.kind === "anchor" && live[x.data.target]; });
      organEdges.forEach(function (x) { live[x.data.target] = 1; });   // 'organ'
      anchorEdges.forEach(function (x) { live[x.data.source] = 1; });  // acupoint node

      var els = nodeEls.filter(function (x) { return live[x.data.id]; })
        .concat(pathEdges, organEdges, anchorEdges);

      if (!pathEdges.length) {
        host.style.height = ""; host.style.width = "";
        host.innerHTML = '<p class="hint" style="padding:1rem">Nothing to show for the current filters.</p>';
        if (cy) { cy.destroy(); cy = null; }
        return;
      }

      if (cy) { cy.destroy(); cy = null; }
      host.innerHTML = "";
      var mount = el("div", "cy-canvas");
      host.appendChild(mount);
      cy = cytoscape({
        container: mount,
        elements: els,
        style: CY_STYLE,
        layout: { name: "dagre", rankDir: state.layout === "LR" ? "LR" : "TB", nodeSep: 22, rankSep: 55, edgeSep: 12 },
        wheelSensitivity: 0.2
      });
      cy.on("tap", "node", function (evt) {
        var iri = evt.target.data("iri");
        if (iri) window.open(iri, "_blank", "noopener");
      });
      cy.on("mouseover", "node", function (evt) {
        var d = evt.target.data();
        host.title = d.curie ? d.curie + (d.iri ? "  (click to open)" : "") : "";
      });
      cy.on("mouseout", "node", function () { host.title = ""; });
      if (!cS.checked) cy.nodes('[role="synapse"]').addClass("dim");
      // shrink-wrap the panel to the laid-out graph on BOTH axes (capped at the
      // available panel width and a sane max height), then fit the graph in.
      // rAF: the block may not be attached / measured yet on first paint.
      requestAnimationFrame(function () {
        if (!cy) return;
        var bb = cy.elements().boundingBox();
        var pad = 28;
        // measure against the page column, not the (shrink-wrapping) card
        var avail = (results.clientWidth || 900) - 40;
        var gw = Math.ceil(bb.w) + pad, gh = Math.ceil(bb.h) + pad;
        var w, h;
        if (gw <= avail) { w = Math.max(gw, 300); h = gh; }
        else { w = avail; h = gh * (avail / gw); }          // keep the graph's aspect
        h = Math.min(Math.max(h, 220), 900);
        host.style.width = Math.round(w) + "px";
        host.style.height = Math.round(h) + "px";
        cy.resize();
        cy.fit(undefined, 12);
      });
    }

    bTB.onclick = function () { state.layout = "TB"; bTB.classList.add("on"); bLR.classList.remove("on"); redraw(); };
    bLR.onclick = function () { state.layout = "LR"; bLR.classList.add("on"); bTB.classList.remove("on"); redraw(); };
    cS.onchange = function () {
      state.synapse = cS.checked;
      if (renderer === "graphviz") { applyStaticSynapse(); return; }
      if (cy) {
        if (cS.checked) cy.nodes('[role="synapse"]').removeClass("dim");
        else cy.nodes('[role="synapse"]').addClass("dim");
      }
    };

    function pngName() {
      return (staticKey() || viewKey).replace(/[^A-Za-z0-9]+/g, "_");
    }
    function downloadDataUrl(url) {
      var a = el("a"); a.href = url; a.download = pngName() + ".png"; a.click();
    }
    function exportStaticPng() {
      var svgEl = host.querySelector("svg");
      if (!svgEl) return;
      var vb = svgEl.viewBox && svgEl.viewBox.baseVal;
      var w = (vb && vb.width) || svgEl.clientWidth || 1200;
      var h = (vb && vb.height) || svgEl.clientHeight || 800;
      var xml = new XMLSerializer().serializeToString(svgEl);
      var src = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(xml)));
      var img = new Image();
      img.onload = function () {
        var scale = 2;
        var c = document.createElement("canvas");
        c.width = Math.ceil(w * scale); c.height = Math.ceil(h * scale);
        var ctx = c.getContext("2d");
        ctx.fillStyle = getComputedStyle(document.body).backgroundColor || "#ffffff";
        ctx.fillRect(0, 0, c.width, c.height);
        ctx.setTransform(scale, 0, 0, scale, 0, 0);
        ctx.drawImage(img, 0, 0, w, h);
        downloadDataUrl(c.toDataURL("image/png"));
      };
      img.onerror = function () { downloadDataUrl(src); };  // fall back to the SVG
      img.src = src;
    }
    bX.onclick = function () {
      if (renderer === "graphviz") { exportStaticPng(); return; }
      if (!cy) return;
      downloadDataUrl(cy.png({ full: true, scale: 2, bg: getComputedStyle(document.body).backgroundColor }));
    };

    block._redraw = redraw;
    // defer: caller still has to append `block` to the document, and cytoscape
    // needs the host to have a measured size before it lays out
    setTimeout(redraw, 0);
    return block;
  }

  // ---------- results ----------
  var results = document.getElementById("results");

  function acuNoPathwayNote(a) {
    return el("div", "no-pathway",
      "No axonal pathway available for " + a.code + " in the current SCKAN partial-order set.");
  }

  function acuInfo(a) {
    var wrap = el("div");
    // one line: acupoint · meridian · related nerve(s) · target organ(s)
    var pr = el("div", "pill-row");
    pr.appendChild(chip(a.code, a.url));
    if (a.meridian) pr.appendChild(chip(a.meridian, a.meridianUrl));
    if (a.nerves.length) {
      pr.appendChild(el("span", "lbl", "Related nerve" + (a.nerves.length > 1 ? "s" : "")));
      a.nerves.forEach(function (n) { pr.appendChild(chip(n.label, n.iri)); });
    }
    if (a.coarseOrgans.length) {
      pr.appendChild(el("span", "lbl", "Target organ" + (a.coarseOrgans.length > 1 ? "s" : "")));
      a.coarseOrgans.forEach(function (o) { pr.appendChild(chip(o.label, o.iri || null)); });
    }
    wrap.appendChild(pr);
    if (a.neurons.length) {
      var nl = el("div", "neuron-list");
      a.neurons.forEach(function (n) {
        var row = el("div", "neuron-row");
        row.appendChild(chip(n.curie, n.explorerUrl));
        row.appendChild(el("span", "pheno", n.phenotype || "—"));
        row.appendChild(el("span", "nlabel", n.label || (n.hasPathway ? "" : "(no pathway)")));
        nl.appendChild(row);
      });
      wrap.appendChild(nl);
    }
    return wrap;
  }

  function resultBlock(title, summary) {
    var b = el("div", "result-block");
    var h = el("div", "result-head");
    h.appendChild(el("h2", null, title));
    if (summary) h.appendChild(el("p", "summary", summary));
    b.appendChild(h);
    var body = el("div", "result-body");
    b.appendChild(body);
    return { block: b, body: body };
  }

  function phenoSummary(acuList) {
    var withP = acuList.filter(function (a) { return a.hasPathway; });
    var neurons = {}, meridians = {};
    withP.forEach(function (a) {
      a.pathwayNeurons.forEach(function (n) { neurons[n] = 1; });
      if (a.meridian) meridians[a.meridian] = 1;
    });
    var parts = [];
    parts.push(acuList.length + " acupoint" + (acuList.length === 1 ? "" : "s"));
    parts.push(withP.length + " with a drawable pathway");
    var nn = Object.keys(neurons).length, mm = Object.keys(meridians).length;
    if (nn) parts.push(nn + " SCKAN neuron" + (nn === 1 ? "" : "s"));
    if (mm > 1) parts.push("across " + mm + " meridians");
    return parts.join(" · ");
  }

  function renderAcupoint(a) {
    results.innerHTML = "";
    var rb = resultBlock(a.code + (a.meridian ? "  —  " + a.meridian : ""), phenoSummary([a]));
    rb.body.appendChild(acuInfo(a));
    if (a.hasPathway) {
      rb.body.appendChild(diagramBlock([a], { viewKey: "acupoint::" + a.iri }));
    } else {
      rb.body.appendChild(acuNoPathwayNote(a));
    }
    results.appendChild(rb.block);
  }

  function renderFacet(kind, key, iris) {
    results.innerHTML = "";
    var acuList = iris.map(function (i) { return byIri[i]; }).filter(Boolean)
      .sort(function (x, y) { return natcmp(x.code, y.code); });
    var withP = acuList.filter(function (a) { return a.hasPathway; });
    var label = { meridian: "Meridian", nerve: "Related nerve", neuron: "Mapping neuron",
                  organ: "Target organ", phenotype: "Phenotype" }[kind] || kind;

    var rb = resultBlock(label + ": " + key, phenoSummary(acuList));

    var pr = el("div", "pill-row");
    pr.appendChild(el("span", "lbl", "Acupoints"));
    acuList.forEach(function (a) {
      var c = chip(a.code, null);
      c.style.cursor = "pointer";
      c.onclick = function () { setQuery("acupoint", a.code); };
      if (!a.hasPathway) c.style.opacity = ".55";
      pr.appendChild(c);
    });
    rb.body.appendChild(pr);

    if (withP.length) {
      // one merged diagram; use the Isolate control to drill to one acupoint / neuron
      rb.body.appendChild(diagramBlock(withP, { viewKey: kind + "::" + key }));
    }

    var noP = acuList.filter(function (a) { return !a.hasPathway; });
    if (noP.length) {
      rb.body.appendChild(el("div", "no-pathway",
        noP.length + " mapped acupoint" + (noP.length === 1 ? "" : "s") +
        " with no pathway in the current SCKAN partial-order set: " +
        noP.map(function (a) { return a.code; }).join(", ")));
    }
    results.appendChild(rb.block);
  }

  function renderHome() {
    results.innerHTML = "";
    var s = DATA.stats;
    var rb = resultBlock("Overview",
      s.acupoints + " mapped acupoints · " + s.withPathway + " with drawable pathways · " +
      s.pathwayNeurons + " SCKAN neurons in the partial order (" + s.mappingNeurons + " mapped in total)");
    rb.body.appendChild(el("p", "hint", "Pick a search mode above and start typing, or choose a meridian:"));
    var pr = el("div", "stat-pills");
    Object.keys(DATA.facets.meridian).sort().forEach(function (m) {
      var c = chip(m + " (" + DATA.facets.meridian[m].length + ")", null);
      c.style.cursor = "pointer";
      c.onclick = function () { setQuery("meridian", m); };
      pr.appendChild(c);
    });
    rb.body.appendChild(pr);
    results.appendChild(rb.block);
  }

  // ---------- search / autocomplete ----------
  var bySel = document.getElementById("by");
  var qIn = document.getElementById("q");
  var acList = document.getElementById("ac");
  var acItems = [], acActive = -1;

  function candidates(kind) {
    if (kind === "acupoint") {
      return DATA.acupoints.map(function (a) { return { kind: "acupoint", label: a.code, key: a.iri, sub: a.meridian }; });
    }
    return Object.keys(DATA.facets[kind]).sort(natcmp).map(function (k) {
      return { kind: kind, label: k, key: k, sub: DATA.facets[kind][k].length + " acupoints" };
    });
  }

  function refreshAutocomplete() {
    var kind = bySel.value;
    var term = qIn.value.trim().toLowerCase();
    var pool = candidates(kind);
    acItems = pool.filter(function (c) { return !term || c.label.toLowerCase().indexOf(term) >= 0; }).slice(0, 40);
    acActive = -1;
    acList.innerHTML = "";
    if (!acItems.length) { acList.classList.remove("open"); return; }
    acItems.forEach(function (c, i) {
      var it = el("div", "ac-item");
      it.appendChild(el("span", "k", c.kind));
      it.appendChild(el("span", "t", c.label));
      if (c.sub) it.appendChild(el("span", "sub", "— " + c.sub));
      it.onmousedown = function (e) { e.preventDefault(); choose(i); };
      acList.appendChild(it);
    });
    acList.classList.add("open");
  }
  function highlight() {
    Array.prototype.forEach.call(acList.children, function (c, i) { c.classList.toggle("active", i === acActive); });
  }
  function choose(i) {
    var c = acItems[i];
    if (!c) return;
    acList.classList.remove("open");
    qIn.value = c.label;
    setQuery(c.kind, c.label);
  }

  qIn.addEventListener("input", refreshAutocomplete);
  qIn.addEventListener("focus", refreshAutocomplete);
  qIn.addEventListener("blur", function () { setTimeout(function () { acList.classList.remove("open"); }, 120); });
  qIn.addEventListener("keydown", function (e) {
    if (!acList.classList.contains("open")) return;
    if (e.key === "ArrowDown") { acActive = Math.min(acActive + 1, acItems.length - 1); highlight(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { acActive = Math.max(acActive - 1, 0); highlight(); e.preventDefault(); }
    else if (e.key === "Enter") { if (acActive >= 0) choose(acActive); else if (acItems.length === 1) choose(0); e.preventDefault(); }
    else if (e.key === "Escape") { acList.classList.remove("open"); }
  });
  bySel.addEventListener("change", function () { qIn.value = ""; qIn.focus(); refreshAutocomplete(); });

  // ---------- routing ----------
  function setQuery(kind, label, push) {
    var hash = "#by=" + encodeURIComponent(kind) + "&q=" + encodeURIComponent(label);
    if (push !== false && location.hash !== hash) history.pushState(null, "", hash);
    route();
  }
  function route() {
    var vm = /(?:^|&)view=(static|interactive)/.exec(location.hash || "");
    if (vm && vm[1] !== renderer) {
      var wanted = vm[1] === "static" ? "graphviz" : "interactive";
      if (!(wanted === "graphviz" && !HAS_STATIC) && !(wanted === "interactive" && !window.cytoscape)) {
        renderer = wanted;
        Array.prototype.forEach.call(rt.querySelectorAll("button"), function (x) {
          x.classList.toggle("on", x.dataset.r === renderer);
        });
      }
    }
    var m = /by=([^&]*)&q=([^&]*)/.exec(location.hash || "");
    if (!m) { renderHome(); return; }
    var kind = decodeURIComponent(m[1]), label = decodeURIComponent(m[2]);
    bySel.value = ({ acupoint: 1, meridian: 1, nerve: 1, neuron: 1, organ: 1, phenotype: 1 }[kind]) ? kind : "acupoint";
    qIn.value = label;
    if (kind === "acupoint") {
      var a = DATA.acupoints.filter(function (x) { return x.code === label; })[0];
      if (a) { renderAcupoint(a); return; }
    }
    var vals = DATA.facets[kind] || {};
    if (vals[label]) { renderFacet(kind, label, vals[label]); return; }
    renderHome();
  }
  window.addEventListener("popstate", route);

  // ---------- renderer toggle ----------
  var rt = document.getElementById("renderer");
  Array.prototype.forEach.call(rt.querySelectorAll("button"), function (b) {
    if (b.dataset.r === "graphviz" && !HAS_STATIC) { b.disabled = true; b.title = "Build with --renderer graphviz"; }
    if (b.dataset.r === "interactive" && !window.cytoscape) { b.disabled = true; b.title = "Cytoscape failed to load"; }
    b.onclick = function () {
      if (b.disabled) return;
      renderer = b.dataset.r;
      Array.prototype.forEach.call(rt.querySelectorAll("button"), function (x) { x.classList.toggle("on", x === b); });
      var h = (location.hash || "").replace(/&view=(static|interactive)/g, "");
      if (h.indexOf("by=") >= 0) {
        try { history.replaceState(null, "", h + "&view=" + (renderer === "graphviz" ? "static" : "interactive")); } catch (e) {}
      }
      route();
    };
  });
  Array.prototype.forEach.call(rt.querySelectorAll("button"), function (x) { x.classList.toggle("on", x.dataset.r === renderer); });

  route();
})();
"""


def build_page(model, include_svgs):
    payload = {
        "generated": model["generated"],
        "explorerBase": model["explorerBase"],
        "acupointsBrowser": model["acupointsBrowser"],
        "stats": model["stats"],
        "phenotypeColors": model["phenotypeColors"],
        "neurons": model["neurons"],
        "acupoints": model["acupoints"],
        "facets": model["facets"],
    }
    if include_svgs:
        payload["svg"] = include_svgs["map"]
        payload["svgLayouts"] = include_svgs["layouts"]

    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    data_json = data_json.replace("</", "<\\/")  # keep </script> literals safe

    html_doc = (PAGE
                .replace("__BROWSER__", html.escape(model["acupointsBrowser"], quote=True))
                .replace("__GENERATED__", html.escape(model["generated"]))
                .replace("__DATA_JSON__", data_json)
                .replace("__APP_JS__", APP_JS))
    return html_doc


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory (default: docs/tara-sckan/)")
    ap.add_argument("--renderer", choices=["cytoscape", "graphviz", "both"], default="both",
                    help="which renderer(s) to build (default: both)")
    ap.add_argument("--layouts", default="TB,LR",
                    help="comma list of static layouts to pre-render (default: TB,LR)")
    args = ap.parse_args(argv)

    for p in (MAPPING_JSON, PARTIAL_ORDER_JSON):
        if not p.is_file():
            sys.exit(f"missing input: {p}")

    print("Building model from SPARQL results...")
    model = build_model()
    s = model["stats"]
    print(f"  {s['acupoints']} acupoints ({s['withPathway']} with a pathway), "
          f"{s['pathwayNeurons']} pathway neurons, {s['mappingNeurons']} mapped neurons")

    svg_bundle = None
    want_graphviz = args.renderer in ("graphviz", "both")
    if want_graphviz:
        if shutil.which("dot") is None:
            if args.renderer == "graphviz":
                sys.exit("`dot` (graphviz) not on PATH - install it or use --renderer cytoscape")
            print("  `dot` not found - skipping static SVGs (interactive only)")
        else:
            layouts = tuple(x.strip().upper() for x in args.layouts.split(",") if x.strip())
            print(f"  rendering static SVGs with graphviz (layouts: {', '.join(layouts)})...")
            svg_map = build_all_svgs(model, layouts=layouts)
            print(f"  {len(svg_map)} SVG views")
            svg_bundle = {"map": svg_map, "layouts": list(layouts)}

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "styles.css").write_text(CSS, encoding="utf-8")
    (out / "index.html").write_text(build_page(model, svg_bundle), encoding="utf-8")
    size = (out / "index.html").stat().st_size
    print(f"Wrote {out/'index.html'} ({size/1024:.0f} KB) and {out/'styles.css'}")


if __name__ == "__main__":
    main()
