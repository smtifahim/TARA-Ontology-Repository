#!/usr/bin/env python3
"""Generate an interactive HTML ontology browser for tara-articles-kb-core.ttl.

Parses the ttl directly with rdflib (no manifest step) and emits a single
self-contained index.html (embedded CSS, JS, and a JSON data payload; no
external libraries or CDN dependencies) with:
  - a left sidebar showing the tara-kb:hasTARAArticlesMetadata property tree
    and the owl:Class hierarchy, both expandable/collapsible
  - a top search box with autocomplete over rdfs:label, skos:altLabel, and
    tara-ap:hasSynonym for both classes and properties, which filters the
    tree down to matching nodes (plus their ancestor path)
  - a right detail panel showing the selected node's full metadata, with
    domain/range/parent/children rendered as clickable cross-links

Output is intended to be served by GitHub Pages from the repo-root docs/
folder (docs/articles-kb-core/index.html by default) - this file is
entirely generated and should never be hand-edited; re-run this script
instead.

Usage:
    python3 generate_html_docs.py
    python3 generate_html_docs.py --ttl path/to/file.ttl --out path/to/output.html

Requires: rdflib (pip install rdflib)
"""

import argparse
import json
from pathlib import Path

import rdflib
from rdflib import Namespace, RDF, RDFS, OWL
from rdflib.namespace import SKOS

TARA = Namespace("http://www.acupunctureresearch.org/tara/ontology/")
TARA_KB = Namespace("http://www.acupunctureresearch.org/tara/ontology/kb/")
TARA_AP = Namespace("http://www.acupunctureresearch.org/tara/ontology/annotation-property/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
OBO = Namespace("http://purl.obolibrary.org/obo/")
IAO_EXAMPLE = OBO["IAO_0000112"]

ROOT_PROPERTY = TARA_KB.hasTARAArticlesMetadata

# generate_html_docs.py -> doc-generator -> artifacts-generator -> articles-kb-core
CORE_DIR = Path(__file__).resolve().parents[2]
# articles-kb-core -> articles-kb -> base -> ontology-files -> repo root
REPO_ROOT = Path(__file__).resolve().parents[6]

DEFAULT_TTL = CORE_DIR / "tara-articles-kb-core.ttl"
DEFAULT_OUT = REPO_ROOT / "docs" / "articles-kb-core" / "index.html"


# ---------------------------------------------------------------------------
# rdflib helpers
# ---------------------------------------------------------------------------

def label_of(g, uri):
    lbl = g.value(uri, RDFS.label)
    if lbl:
        return str(lbl)
    s = str(uri)
    return s.split("#")[-1] if "#" in s else s.rsplit("/", 1)[-1]


def qname_of(g, uri):
    try:
        return g.qname(uri)
    except Exception:
        return str(uri)


def text_of(g, s, p):
    v = g.value(s, p)
    return str(v) if v is not None else None


def list_of(g, s, p):
    return sorted({str(o) for o in g.objects(s, p)})


def is_grouping(g, uri):
    return any(str(t).endswith("grouping") for t in g.objects(uri, DCTERMS.type))


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def extract_classes(g):
    classes = {}
    for s in g.subjects(RDF.type, OWL.Class):
        if not (isinstance(s, rdflib.URIRef) and str(s).startswith(str(TARA))):
            continue
        qn = qname_of(g, s)
        parent = g.value(s, RDFS.subClassOf)
        classes[qn] = {
            "id": qn,
            "kind": "class",
            "label": label_of(g, s),
            "uri": str(s),
            "description": text_of(g, s, DCTERMS.description),
            "parent": qname_of(g, parent) if parent is not None else None,
            "children": [],
            "synonyms": list_of(g, s, TARA_AP.hasSynonym),
            "altLabels": list_of(g, s, SKOS.altLabel),
            "propertiesWithThisDomain": [],
        }
    for qn, c in classes.items():
        if c["parent"] and c["parent"] in classes:
            classes[c["parent"]]["children"].append(qn)
    for c in classes.values():
        c["children"].sort(key=lambda cid: classes[cid]["label"])
    return classes


def format_range(g, rng):
    if rng is None:
        return {"kind": None, "id": None, "label": None}
    if str(rng).startswith(str(rdflib.XSD)):
        return {"kind": "literal", "id": None, "label": qname_of(g, rng)}
    if rng == RDF.JSON:
        return {"kind": "literal", "id": None, "label": "rdf:JSON"}
    if str(rng).startswith(str(TARA)):
        # could be an owl:Class (linkable) or a custom rdfs:Datatype (not linkable)
        if (rng, RDF.type, OWL.Class) in g:
            return {"kind": "class", "id": qname_of(g, rng), "label": label_of(g, rng)}
        return {"kind": "literal", "id": None, "label": label_of(g, rng)}
    return {"kind": "literal", "id": None, "label": qname_of(g, rng)}


def extract_properties(g, classes):
    properties = {}
    children_of = {}  # parent URI -> [child URI, ...]
    for s, _, o in g.triples((None, RDFS.subPropertyOf, None)):
        if str(s).startswith(str(TARA_KB)):
            children_of.setdefault(o, []).append(s)

    def walk(uri, parent_qn, visited):
        # parent_qn is the tara-kb parent that reached this node during the walk -
        # NOT g.value(uri, RDFS.subPropertyOf), since several properties carry a
        # second, unrelated rdfs:subPropertyOf (e.g. dcterms:description) and
        # g.value() would pick one of the two non-deterministically.
        qn = qname_of(g, uri)
        if qn in visited:
            return
        visited.add(qn)
        dom = g.value(uri, RDFS.domain)
        dom_qn = qname_of(g, dom) if dom is not None else None
        rng = format_range(g, g.value(uri, RDFS.range))
        properties[qn] = {
            "id": qn,
            "kind": "property",
            "label": label_of(g, uri),
            "altLabel": text_of(g, uri, SKOS.altLabel),
            "uri": str(uri),
            "description": text_of(g, uri, DCTERMS.description),
            "comment": " / ".join(list_of(g, uri, RDFS.comment)) or None,
            "examples": list_of(g, uri, IAO_EXAMPLE),
            "grouping": is_grouping(g, uri),
            "domain": dom_qn,
            "domainLabel": label_of(g, dom) if dom is not None else None,
            "range": rng,
            "parent": parent_qn,
            "children": [qname_of(g, c) for c in children_of.get(uri, [])],
            "synonyms": list_of(g, uri, TARA_AP.hasSynonym),
        }
        if dom_qn and dom_qn in classes:
            classes[dom_qn]["propertiesWithThisDomain"].append(qn)
        for child_uri in children_of.get(uri, []):
            walk(child_uri, qn, visited)

    walk(ROOT_PROPERTY, None, set())
    for c in classes.values():
        c["propertiesWithThisDomain"].sort()
    # sort children by label for stable display
    for p in properties.values():
        p["children"].sort(key=lambda cid: properties[cid]["label"])
    return properties


def build_payload(g):
    classes = extract_classes(g)
    properties = extract_properties(g, classes)
    class_roots = sorted(
        (qn for qn, c in classes.items() if not c["parent"] or c["parent"] not in classes),
        key=lambda qn: classes[qn]["label"],
    )
    return {
        "classes": classes,
        "properties": properties,
        "propertyRoot": qname_of(g, ROOT_PROPERTY),
        "classRoots": class_roots,
    }


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

CSS_FILENAME = "styles.css"

CSS_TEMPLATE = """:root {
  --bg: #ffffff;
  --panel-bg: #f7f8fa;
  --border: #dfe2e6;
  --text: #1a1f27;
  --text-muted: #5b6472;
  --accent: #4472c4;
  --accent-bg: #e8f0ff;
  --grouping-bg: #eeeeee;
  --grouping-border: #999999;
  --chip-bg: #eef1f6;
  --highlight-bg: #fff3b0;
  --guide: #a9c2ea;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #14171c;
    --panel-bg: #1b1f26;
    --border: #2d333d;
    --text: #e6e9ef;
    --text-muted: #9aa4b2;
    --accent: #7fa4e8;
    --accent-bg: #1e2a44;
    --grouping-bg: #23272e;
    --grouping-border: #555c66;
    --chip-bg: #232833;
    --highlight-bg: #4a4322;
    --guide: #3a5480;
  }
}
* { box-sizing: border-box; }
html, body { height: 100%; margin: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  display: flex;
  flex-direction: column;
}
header {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}
header h1 { font-size: 1.05rem; margin: 0; white-space: nowrap; }
header .sub { color: var(--text-muted); font-size: 0.8rem; }
.search-wrap { position: relative; flex: 1; min-width: 220px; max-width: 480px; }
#search {
  width: 100%;
  padding: 0.45rem 0.7rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--panel-bg);
  color: var(--text);
  font-size: 0.9rem;
}
#autocomplete {
  position: absolute;
  top: 100%; left: 0; right: 0;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  margin-top: 4px;
  max-height: 320px;
  overflow-y: auto;
  z-index: 20;
  display: none;
  box-shadow: 0 6px 18px rgba(0,0,0,0.15);
}
#autocomplete .ac-item {
  padding: 0.4rem 0.7rem;
  cursor: pointer;
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  font-size: 0.85rem;
}
#autocomplete .ac-item:hover, #autocomplete .ac-item.active { background: var(--accent-bg); }
#autocomplete .ac-badge {
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--text-muted);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0.05rem 0.3rem;
}
main { display: flex; flex: 1; min-height: 0; }
#sidebar {
  width: 340px;
  min-width: 220px;
  border-right: 1px solid var(--border);
  overflow-y: auto;
  padding: 0.5rem 0;
  flex-shrink: 0;
}
#splitter {
  width: 6px;
  flex-shrink: 0;
  cursor: col-resize;
  background: var(--border);
}
#splitter:hover, #splitter.dragging { background: var(--accent); }
.tab-bar { display: flex; border-bottom: 1px solid var(--border); }
.tab-btn {
  flex: 1;
  padding: 0.5rem;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.85rem;
}
.tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
.tree { padding: 0.4rem 0.4rem 1rem 0.4rem; }
.tree ul { list-style: none; margin: 0; padding-left: 1.15rem; }
.tree > ul { padding-left: 0.2rem; }
.tree li > ul { border-left: 1px dotted var(--guide); margin-left: 0.55rem; }
.node-row {
  display: flex;
  align-items: baseline;
  gap: 0.35rem;
  padding: 0.15rem 0.3rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
}
.node-row:hover { background: var(--panel-bg); }
.node-row.selected { background: var(--accent-bg); color: var(--accent); font-weight: 600; }
.node-row.grouping .node-label { font-style: italic; color: var(--text-muted); }
.node-row.connector { opacity: 0.55; cursor: help; }
.domain-tree { margin-top: 0.2rem; }
.toggle {
  width: 1.1rem;
  text-align: center;
  color: var(--accent);
  font-size: 1.05rem;
  font-weight: 700;
  user-select: none;
  flex-shrink: 0;
}
.toggle.leaf { color: var(--text-muted); font-weight: 400; font-size: 0.95rem; }
.node-label { overflow-wrap: anywhere; }
li.hidden-by-filter { display: none; }
#content { flex: 1; overflow-y: auto; padding: 1.25rem 1.75rem; }
#content .placeholder { color: var(--text-muted); }
#content h2 { margin-top: 0; }
.qname-badge {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.85rem;
  background: var(--chip-bg);
  padding: 0.15rem 0.45rem;
  border-radius: 5px;
  color: var(--text-muted);
}
.type-badge {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0.1rem 0.4rem;
  color: var(--text-muted);
}
.field-label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-muted); margin: 1.1rem 0 0.3rem; }
.field-label:first-of-type { margin-top: 1.4rem; }
.prose { white-space: pre-wrap; line-height: 1.5; }
.chip-row { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.chip {
  display: inline-block;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  background: var(--chip-bg);
  border: 1px solid var(--border);
  font-size: 0.82rem;
  cursor: default;
}
.chip.link { cursor: pointer; color: var(--accent); border-color: var(--accent); }
.chip.link:hover { background: var(--accent-bg); }
.example-block {
  background: var(--panel-bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.6rem 0.8rem;
  margin-bottom: 0.5rem;
  font-size: 0.85rem;
  white-space: pre-wrap;
}
.flash { animation: flash-anim 1.4s ease; }
@keyframes flash-anim { 0%, 40% { background: var(--highlight-bg); } 100% { background: transparent; } }
footer { padding: 0.5rem 1rem; border-top: 1px solid var(--border); color: var(--text-muted); font-size: 0.75rem; }
"""

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TARA Articles KB &mdash; Core Metadata Browser</title>
<link rel="stylesheet" href="__CSS_FILENAME__">
</head>
<body>
<header>
  <div>
    <h1>TARA Articles KB &mdash; Core Metadata Browser</h1>
    <div class="sub">tara-articles-kb-core.ttl</div>
  </div>
  <div class="search-wrap">
    <input id="search" type="text" placeholder="Search or click to browse&hellip;" autocomplete="off">
    <div id="autocomplete"></div>
  </div>
</header>
<main>
  <div id="sidebar">
    <div class="tab-bar">
      <button class="tab-btn active" data-tab="properties">Properties</button>
      <button class="tab-btn" data-tab="classes">Classes</button>
    </div>
    <div id="tree-properties" class="tree"></div>
    <div id="tree-classes" class="tree" style="display:none"></div>
  </div>
  <div id="splitter" title="Drag to resize"></div>
  <div id="content"><p class="placeholder">Select a class or property from the left, or search above.</p></div>
</main>
<footer>Auto-generated from <code>tara-articles-kb-core.ttl</code> by <code>artifacts-generator/doc-generator/generate_html_docs.py</code>. Do not hand-edit &mdash; re-run the script instead.</footer>

<script id="tara-data" type="application/json">
__DATA_JSON__
</script>
<script>
(function () {
  const DATA = JSON.parse(document.getElementById('tara-data').textContent);
  const CLASSES = DATA.classes;
  const PROPERTIES = DATA.properties;

  function recordOf(id) { return PROPERTIES[id] || CLASSES[id] || null; }
  function kindOf(id) { return PROPERTIES[id] ? 'properties' : 'classes'; }

  // ---- sidebar tabs ----
  const tabBtns = document.querySelectorAll('.tab-btn');
  tabBtns.forEach(btn => btn.addEventListener('click', () => {
    tabBtns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tree-properties').style.display = btn.dataset.tab === 'properties' ? '' : 'none';
    document.getElementById('tree-classes').style.display = btn.dataset.tab === 'classes' ? '' : 'none';
  }));
  function activateTab(tab) {
    tabBtns.forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
    document.getElementById('tree-properties').style.display = tab === 'properties' ? '' : 'none';
    document.getElementById('tree-classes').style.display = tab === 'classes' ? '' : 'none';
  }

  // ---- resizable splitter (sidebar width, capped at 35% of page width) ----
  const sidebarEl = document.getElementById('sidebar');
  const splitterEl = document.getElementById('splitter');
  const SIDEBAR_MIN_WIDTH = 220;
  let splitterDragging = false;

  splitterEl.addEventListener('mousedown', (e) => {
    splitterDragging = true;
    splitterEl.classList.add('dragging');
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });
  document.addEventListener('mousemove', (e) => {
    if (!splitterDragging) return;
    const maxWidth = window.innerWidth * 0.35;
    const newWidth = Math.min(Math.max(e.clientX, SIDEBAR_MIN_WIDTH), maxWidth);
    sidebarEl.style.width = newWidth + 'px';
  });
  document.addEventListener('mouseup', () => {
    if (!splitterDragging) return;
    splitterDragging = false;
    splitterEl.classList.remove('dragging');
    document.body.style.userSelect = '';
  });

  // ---- tree rendering ----
  const TOGGLE_COLLAPSED = '▶'; // ▶
  const TOGGLE_EXPANDED = '▼'; // ▼
  const DEFAULT_EXPANDED_DEPTH = 2; // 0-indexed: depths 0 and 1 start expanded, so levels 1-3 are visible by default

  function buildNode(id, store, depth) {
    depth = depth || 0;
    const rec = store[id];
    const li = document.createElement('li');
    li.dataset.id = id;

    const row = document.createElement('div');
    row.className = 'node-row' + (rec.grouping ? ' grouping' : '');
    row.dataset.id = id;

    const hasChildren = rec.children && rec.children.length > 0;
    const toggle = document.createElement('span');
    toggle.className = 'toggle' + (hasChildren ? '' : ' leaf');
    toggle.textContent = hasChildren ? TOGGLE_COLLAPSED : '-';
    row.appendChild(toggle);

    const label = document.createElement('span');
    label.className = 'node-label';
    label.textContent = rec.label;
    row.appendChild(label);

    li.appendChild(row);

    let childUl = null;
    if (hasChildren) {
      const startExpanded = depth < DEFAULT_EXPANDED_DEPTH;
      childUl = document.createElement('ul');
      childUl.style.display = startExpanded ? '' : 'none';
      toggle.textContent = startExpanded ? TOGGLE_EXPANDED : TOGGLE_COLLAPSED;
      rec.children.forEach(cid => childUl.appendChild(buildNode(cid, store, depth + 1)));
      li.appendChild(childUl);

      toggle.addEventListener('click', (e) => {
        e.stopPropagation();
        const open = childUl.style.display !== 'none';
        childUl.style.display = open ? 'none' : '';
        toggle.textContent = open ? TOGGLE_COLLAPSED : TOGGLE_EXPANDED;
      });
    }

    row.addEventListener('click', () => selectNode(id));
    return li;
  }

  function renderTree(containerId, rootIds, store) {
    const container = document.getElementById(containerId);
    container.innerHTML = '';
    const ul = document.createElement('ul');
    rootIds.forEach(rid => ul.appendChild(buildNode(rid, store, 0)));
    container.appendChild(ul);
  }

  renderTree('tree-properties', [DATA.propertyRoot], PROPERTIES);
  renderTree('tree-classes', DATA.classRoots, CLASSES);

  function expandAncestors(id) {
    const rec = recordOf(id);
    if (!rec) return;
    let cur = rec.parent;
    const store = PROPERTIES[id] ? PROPERTIES : CLASSES;
    while (cur) {
      const row = document.querySelector('.node-row[data-id="' + cur + '"]');
      if (row) {
        const li = row.parentElement;
        const ul = li.querySelector(':scope > ul');
        if (ul) {
          ul.style.display = '';
          const t = row.querySelector('.toggle');
          if (t && !t.classList.contains('leaf')) t.textContent = TOGGLE_EXPANDED;
        }
      }
      cur = store[cur] ? store[cur].parent : null;
    }
  }

  // ---- selection & detail panel ----
  let selectedId = null;

  function selectNode(id, opts) {
    opts = opts || {};
    selectedId = id;
    document.querySelectorAll('.node-row.selected').forEach(el => el.classList.remove('selected'));
    if (opts.switchTab !== false) activateTab(kindOf(id));
    expandAncestors(id);
    const row = document.querySelector('.node-row[data-id="' + id + '"]');
    if (row) {
      row.classList.add('selected');
      row.scrollIntoView({ block: 'center' });
      row.parentElement.classList.add('flash');
      setTimeout(() => row.parentElement.classList.remove('flash'), 1400);
    }
    renderDetail(id);
    // record this selection as a browser-history entry (deep-linkable via '#id' too),
    // so the browser's native Back/Forward buttons step through past selections -
    // skipped when we're the ones restoring a state FROM a popstate/deep-link, to
    // avoid pushing a duplicate entry on top of the one already being navigated to.
    if (opts.pushHistory !== false) {
      history.pushState({ id: id }, '', '#' + id);
    }
  }

  function clearSelection() {
    selectedId = null;
    document.querySelectorAll('.node-row.selected').forEach(el => el.classList.remove('selected'));
    document.getElementById('content').innerHTML =
      '<p class="placeholder">Select a class or property from the left, or search above.</p>';
  }

  window.addEventListener('popstate', (e) => {
    const id = e.state && e.state.id;
    if (id && recordOf(id)) {
      selectNode(id, { pushHistory: false });
    } else {
      clearSelection();
    }
  });

  // restore a selection from a deep-linked URL (e.g. .../articles-kb-core/#tara-kb:hasBlindingQualityScore)
  (function restoreFromHash() {
    const initial = location.hash.slice(1);
    if (initial && recordOf(initial)) {
      selectNode(initial, { pushHistory: false });
    }
  })();

  function chip(text, onClick) {
    const el = document.createElement('span');
    el.className = 'chip' + (onClick ? ' link' : '');
    el.textContent = text;
    if (onClick) el.addEventListener('click', onClick);
    return el;
  }

  function fieldLabel(text) {
    const el = document.createElement('div');
    el.className = 'field-label';
    el.textContent = text;
    return el;
  }

  function prose(text) {
    const el = document.createElement('div');
    el.className = 'prose';
    el.textContent = text;
    return el;
  }

  // Renders propIds (a flat list of property ids sharing one domain class) as a
  // nested tree following tara-kb:hasTARAArticlesMetadata structure, instead of
  // one flat chip list - grouping properties (e.g. "Category B: ...") show their
  // members nested underneath instead of as unrelated siblings. An ancestor that
  // isn't itself in propIds (its own domain differs or is unset) is still shown,
  // dimmed, purely as structural connective tissue to the nearest visible root.
  function buildDomainTree(propIds) {
    const include = new Set(propIds);
    const connectors = new Set();
    include.forEach(id => {
      let cur = PROPERTIES[id] ? PROPERTIES[id].parent : null;
      while (cur && !include.has(cur) && !connectors.has(cur)) {
        connectors.add(cur);
        cur = PROPERTIES[cur] ? PROPERTIES[cur].parent : null;
      }
    });
    const all = new Set([...include, ...connectors]);
    const roots = [...all]
      .filter(id => { const p = PROPERTIES[id].parent; return !p || !all.has(p); })
      .sort((a, b) => PROPERTIES[a].label.localeCompare(PROPERTIES[b].label));

    function renderNode(id) {
      const rec = PROPERTIES[id];
      const li = document.createElement('li');
      const row = document.createElement('div');
      row.className = 'node-row' + (rec.grouping ? ' grouping' : '') + (connectors.has(id) ? ' connector' : '');
      row.dataset.id = id;
      if (connectors.has(id)) row.title = 'Shown for structure only — its own domain differs from this class';
      const bullet = document.createElement('span');
      bullet.className = 'toggle leaf';
      bullet.textContent = '-';
      row.appendChild(bullet);
      const label = document.createElement('span');
      label.className = 'node-label';
      label.textContent = rec.label;
      row.appendChild(label);
      row.addEventListener('click', () => selectNode(id));
      li.appendChild(row);

      const children = (rec.children || [])
        .filter(cid => all.has(cid))
        .sort((a, b) => PROPERTIES[a].label.localeCompare(PROPERTIES[b].label));
      if (children.length) {
        const ul = document.createElement('ul');
        children.forEach(cid => ul.appendChild(renderNode(cid)));
        li.appendChild(ul);
      }
      return li;
    }

    const container = document.createElement('div');
    container.className = 'tree domain-tree';
    const ul = document.createElement('ul');
    roots.forEach(rid => ul.appendChild(renderNode(rid)));
    container.appendChild(ul);
    return container;
  }

  function renderDetail(id) {
    const content = document.getElementById('content');
    content.innerHTML = '';
    const rec = recordOf(id);
    if (!rec) { content.innerHTML = '<p class="placeholder">Not found.</p>'; return; }

    const h = document.createElement('h2');
    h.textContent = rec.label;
    content.appendChild(h);

    const badgeRow = document.createElement('div');
    badgeRow.className = 'chip-row';
    const kindBadge = document.createElement('span');
    kindBadge.className = 'type-badge';
    kindBadge.textContent = rec.kind === 'property' ? (rec.grouping ? 'Grouping Property' : 'Property') : 'Class';
    badgeRow.appendChild(kindBadge);
    const qBadge = document.createElement('span');
    qBadge.className = 'qname-badge';
    qBadge.textContent = rec.id;
    badgeRow.appendChild(qBadge);
    content.appendChild(badgeRow);

    if (rec.altLabel) {
      content.appendChild(fieldLabel('Alt Label (skos:altLabel)'));
      content.appendChild(prose(rec.altLabel));
    }

    if (rec.description) {
      content.appendChild(fieldLabel('Description'));
      content.appendChild(prose(rec.description));
    }

    if (rec.comment) {
      content.appendChild(fieldLabel('Comment / Normalization Rules'));
      content.appendChild(prose(rec.comment));
    }

    if (rec.kind === 'property') {
      if (rec.domain || rec.range.label) {
        content.appendChild(fieldLabel('Domain · Range'));
        const row = document.createElement('div');
        row.className = 'chip-row';
        if (rec.domain) {
          row.appendChild(chip('Domain: ' + rec.domainLabel, () => selectNode(rec.domain)));
        } else {
          row.appendChild(chip('Domain: not specified'));
        }
        if (rec.range.kind === 'class') {
          row.appendChild(chip('Range: ' + rec.range.label, () => selectNode(rec.range.id)));
        } else if (rec.range.label) {
          row.appendChild(chip('Range: ' + rec.range.label));
        } else {
          row.appendChild(chip('Range: not specified'));
        }
        content.appendChild(row);
      }

      if (rec.examples && rec.examples.length) {
        content.appendChild(fieldLabel('Examples (obo:IAO_0000112)'));
        rec.examples.forEach(ex => {
          const block = document.createElement('div');
          block.className = 'example-block';
          block.textContent = ex;
          content.appendChild(block);
        });
      }
    }

    if (rec.kind === 'class' && rec.propertiesWithThisDomain && rec.propertiesWithThisDomain.length) {
      content.appendChild(fieldLabel('Properties with this Domain'));
      content.appendChild(buildDomainTree(rec.propertiesWithThisDomain));
    }

    if (rec.synonyms && rec.synonyms.length) {
      content.appendChild(fieldLabel('Synonyms'));
      const row = document.createElement('div');
      row.className = 'chip-row';
      rec.synonyms.forEach(s => row.appendChild(chip(s)));
      content.appendChild(row);
    }

    if (rec.altLabels && rec.altLabels.length) {
      content.appendChild(fieldLabel('Alt Labels'));
      const row = document.createElement('div');
      row.className = 'chip-row';
      rec.altLabels.forEach(s => row.appendChild(chip(s)));
      content.appendChild(row);
    }

    if (rec.parent) {
      const store = rec.kind === 'property' ? PROPERTIES : CLASSES;
      const parentRec = store[rec.parent];
      if (parentRec) {
        content.appendChild(fieldLabel(rec.kind === 'property' ? 'Parent Property' : 'Superclass'));
        const row = document.createElement('div');
        row.className = 'chip-row';
        row.appendChild(chip(parentRec.label, () => selectNode(rec.parent)));
        content.appendChild(row);
      }
    }

    if (rec.children && rec.children.length) {
      const store = rec.kind === 'property' ? PROPERTIES : CLASSES;
      content.appendChild(fieldLabel(rec.kind === 'property' ? 'Sub-properties' : 'Subclasses'));
      const row = document.createElement('div');
      row.className = 'chip-row';
      rec.children.forEach(cid => row.appendChild(chip(store[cid].label, () => selectNode(cid))));
      content.appendChild(row);
    }
  }

  // ---- search / autocomplete / filter ----
  const searchInput = document.getElementById('search');
  const autocompleteEl = document.getElementById('autocomplete');
  let acItems = [];
  let acActiveIndex = -1;

  function searchableText(rec) {
    return [rec.label, rec.altLabel].concat(rec.synonyms || [], rec.altLabels || [])
      .filter(Boolean).join(' • ').toLowerCase();
  }

  function allEntries() {
    const all = Object.values(PROPERTIES).concat(Object.values(CLASSES));
    all.sort((a, b) => a.label.localeCompare(b.label));
    return all;
  }

  function matchIds(query) {
    const q = query.trim().toLowerCase();
    if (!q) return allEntries(); // empty query -> full pulldown of everything, browsable
    const results = [];
    Object.values(PROPERTIES).forEach(rec => { if (searchableText(rec).includes(q)) results.push(rec); });
    Object.values(CLASSES).forEach(rec => { if (searchableText(rec).includes(q)) results.push(rec); });
    results.sort((a, b) => a.label.localeCompare(b.label));
    return results;
  }

  function ancestorChain(id) {
    const chain = [];
    const store = PROPERTIES[id] ? PROPERTIES : CLASSES;
    let cur = store[id] ? store[id].parent : null;
    while (cur) { chain.push(cur); cur = store[cur] ? store[cur].parent : null; }
    return chain;
  }

  function applyFilter(query) {
    const matches = matchIds(query);
    const allTreeItems = document.querySelectorAll('#tree-properties li, #tree-classes li');
    if (!query.trim()) {
      allTreeItems.forEach(li => li.classList.remove('hidden-by-filter'));
      return;
    }
    const keep = new Set();
    matches.forEach(rec => { keep.add(rec.id); ancestorChain(rec.id).forEach(a => keep.add(a)); });
    allTreeItems.forEach(li => {
      li.classList.toggle('hidden-by-filter', !keep.has(li.dataset.id));
    });
    // auto-expand branches that contain a visible match
    keep.forEach(id => {
      const row = document.querySelector('.node-row[data-id="' + id + '"]');
      if (row) {
        const ul = row.parentElement.querySelector(':scope > ul');
        if (ul) {
          ul.style.display = '';
          const t = row.querySelector('.toggle');
          if (t && !t.classList.contains('leaf')) t.textContent = TOGGLE_EXPANDED;
        }
      }
    });
  }

  function renderAutocomplete(query) {
    acItems = matchIds(query).slice(0, 60);
    acActiveIndex = -1;
    autocompleteEl.innerHTML = '';
    if (acItems.length === 0) {
      autocompleteEl.style.display = 'none';
      return;
    }
    acItems.forEach((rec, i) => {
      const item = document.createElement('div');
      item.className = 'ac-item';
      item.dataset.index = i;
      const badge = document.createElement('span');
      badge.className = 'ac-badge';
      badge.textContent = rec.kind === 'property' ? 'Prop' : 'Class';
      item.appendChild(badge);
      const label = document.createElement('span');
      label.textContent = rec.label;
      item.appendChild(label);
      item.addEventListener('mousedown', (e) => { e.preventDefault(); chooseAutocomplete(i); });
      autocompleteEl.appendChild(item);
    });
    // #autocomplete's stylesheet rule defaults to display:none, so clearing the
    // inline style here (display = '') would fall back to that and stay hidden -
    // must set an explicit visible value instead.
    autocompleteEl.style.display = 'block';
  }

  function chooseAutocomplete(i) {
    const rec = acItems[i];
    if (!rec) return;
    searchInput.value = rec.label;
    autocompleteEl.style.display = 'none';
    applyFilter('');
    selectNode(rec.id);
  }

  searchInput.addEventListener('input', () => {
    applyFilter(searchInput.value);
    renderAutocomplete(searchInput.value);
  });

  searchInput.addEventListener('focus', () => renderAutocomplete(searchInput.value));
  searchInput.addEventListener('click', () => renderAutocomplete(searchInput.value));

  searchInput.addEventListener('keydown', (e) => {
    if (autocompleteEl.style.display === 'none') return;
    const rows = autocompleteEl.querySelectorAll('.ac-item');
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      acActiveIndex = Math.min(acActiveIndex + 1, rows.length - 1);
      rows.forEach((r, i) => r.classList.toggle('active', i === acActiveIndex));
      rows[acActiveIndex] && rows[acActiveIndex].scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      acActiveIndex = Math.max(acActiveIndex - 1, 0);
      rows.forEach((r, i) => r.classList.toggle('active', i === acActiveIndex));
      rows[acActiveIndex] && rows[acActiveIndex].scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'Enter') {
      e.preventDefault();
      chooseAutocomplete(acActiveIndex >= 0 ? acActiveIndex : 0);
    } else if (e.key === 'Escape') {
      autocompleteEl.style.display = 'none';
    }
  });

  document.addEventListener('click', (e) => {
    if (!autocompleteEl.contains(e.target) && e.target !== searchInput) {
      autocompleteEl.style.display = 'none';
    }
  });
})();
</script>
</body>
</html>
"""


def generate(ttl_path: Path) -> str:
    g = rdflib.Graph()
    g.bind("tara", TARA)
    g.bind("tara-kb", TARA_KB)
    g.bind("tara-ap", TARA_AP)
    g.parse(str(ttl_path), format="turtle")

    payload = build_payload(g)
    data_json = json.dumps(payload, indent=2, ensure_ascii=False)
    # defend against a ttl field ever containing a literal "</script>", which
    # would otherwise prematurely close the embedded <script> tag
    data_json = data_json.replace("</", "<\\/")
    html = PAGE_TEMPLATE.replace("__CSS_FILENAME__", CSS_FILENAME)
    return html.replace("__DATA_JSON__", data_json)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ttl", type=Path, default=DEFAULT_TTL, help="Path to tara-articles-kb-core.ttl")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Path to write the generated index.html")
    args = parser.parse_args()

    html = generate(args.ttl)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    css_path = args.out.parent / CSS_FILENAME
    css_path.write_text(CSS_TEMPLATE, encoding="utf-8")
    print(f"Wrote {args.out}")
    print(f"Wrote {css_path}")


if __name__ == "__main__":
    main()
