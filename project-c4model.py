#!/usr/bin/env python3
"""
Project a C4 Structurizr DSL workspace from a C4 ESML event stream.

Fixes:
- Uses Structurizr DSL identifier assignment syntax: id = person/container/etc.
- Sanitizes ESML ids into DSL-safe ids.
- Does NOT emit "include a -> b" (illegal in Structurizr basic views).
- Emits styles inside views { styles { ... } } (required by DSL).
- ESML parsing supports JSON objects concatenated without commas.
"""

import argparse
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


# =====================================================================
#   ESML PARSER — Reads sequential JSON objects without commas
# =====================================================================

def read_esml_events(text: str):
    dec = json.JSONDecoder()
    i = 0
    n = len(text)
    while i < n:
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            break
        obj, next_i = dec.raw_decode(text, i)
        yield obj
        i = next_i


# =====================================================================
#   DATA STRUCTURES
# =====================================================================

@dataclass
class Workspace:
    workspace_id: str
    name: str = ""
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    themes: List[str] = field(default_factory=list)
    branding: Dict[str, Any] = field(default_factory=dict)
    terminology: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Element:
    element_id: str
    kind: str
    name: str
    description: str = ""
    technology: str = ""
    parent_id: Optional[str] = None
    tags: Set[str] = field(default_factory=set)
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Relationship:
    relationship_id: str
    source_id: str
    destination_id: str
    description: str = ""
    technology: str = ""
    interaction_style: Optional[str] = None
    tags: Set[str] = field(default_factory=set)
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class View:
    view_id: str
    kind: str
    scope_element_id: Optional[str] = None
    key: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    include_elements: Set[str] = field(default_factory=set)
    include_relationships: Set[str] = field(default_factory=set)  # stored, not emitted
    auto_layout: Optional[Dict[str, Any]] = None


@dataclass
class Styles:
    element_styles: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    relationship_styles: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class C4State:
    workspace: Optional[Workspace] = None
    elements: Dict[str, Element] = field(default_factory=dict)
    relationships: Dict[str, Relationship] = field(default_factory=dict)
    views: Dict[str, View] = field(default_factory=dict)
    styles: Styles = field(default_factory=Styles)


# =====================================================================
#   ID SANITIZATION (for Structurizr DSL)
# =====================================================================

def dsl_id(raw: str) -> str:
    """
    Convert ESML ids into Structurizr DSL-safe identifiers.
    Allowed: letters, digits, underscore; must not start with digit.
    """
    s = re.sub(r"[^A-Za-z0-9_]", "_", raw)
    if re.match(r"^\d", s):
        s = "_" + s
    return s


def build_id_maps(state: C4State) -> Tuple[Dict[str, str], Dict[str, str]]:
    el_map = {eid: dsl_id(eid) for eid in state.elements.keys()}
    rel_map = {rid: dsl_id(rid) for rid in state.relationships.keys()}
    return el_map, rel_map


# =====================================================================
#   APPLY EVENTS
# =====================================================================

def apply_event(state: C4State, event: Dict[str, Any]):
    etype = event.get("type")
    data = event.get("data", {})

    if etype == "TypeDeclared":
        return

    # Workspace events
    if etype == "c4.WorkspaceStarted":
        state.workspace = Workspace(
            workspace_id=data["workspace_id"],
            name=data.get("name", ""),
            description=data.get("description", "")
        )
        return

    if etype == "c4.WorkspaceRenamed":
        ws = state.workspace
        if ws and ws.workspace_id == data["workspace_id"]:
            if "new_name" in data:
                ws.name = data["new_name"]
            if "new_description" in data:
                ws.description = data["new_description"]
        return

    if etype == "c4.WorkspacePropertySet":
        ws = state.workspace
        if ws and ws.workspace_id == data["workspace_id"]:
            ws.properties[data["key"]] = data.get("value")
        return

    if etype == "c4.WorkspacePropertyRemoved":
        ws = state.workspace
        if ws and ws.workspace_id == data["workspace_id"]:
            ws.properties.pop(data["key"], None)
        return

    if etype == "c4.ThemeAdded":
        ws = state.workspace
        if ws and ws.workspace_id == data["workspace_id"]:
            ws.themes.append(data["theme_url"])
        return

    if etype == "c4.BrandingConfigured":
        ws = state.workspace
        if ws and ws.workspace_id == data["workspace_id"]:
            ws.branding.update(data.get("branding", {}))
        return

    if etype == "c4.TerminologyCustomized":
        ws = state.workspace
        if ws and ws.workspace_id == data["workspace_id"]:
            ws.terminology.update(data.get("terms", {}))
        return

    # Element events
    if etype == "c4.ElementDeclared":
        eid = data["element_id"]
        state.elements[eid] = Element(
            element_id=eid,
            kind=data["kind"],
            name=data["name"],
            description=data.get("description", "") or "",
            technology=data.get("technology", "") or "",
            parent_id=data.get("parent_id"),
            tags=set(data.get("tags", []) or []),
            properties=dict(data.get("properties", {}) or {})
        )
        return

    if etype == "c4.ElementRemoved":
        eid = data["element_id"]
        state.elements.pop(eid, None)
        to_rm = [rid for rid, r in state.relationships.items()
                 if r.source_id == eid or r.destination_id == eid]
        for rid in to_rm:
            state.relationships.pop(rid, None)
        return

    if etype == "c4.ElementRenamed":
        el = state.elements.get(data["element_id"])
        if el:
            el.name = data.get("new_name", el.name)
        return

    if etype == "c4.ElementDescriptionChanged":
        el = state.elements.get(data["element_id"])
        if el:
            nd = data.get("new_description")
            nt = data.get("new_technology")
            if nd is not None:
                el.description = nd
            if nt is not None:
                el.technology = nt
        return

    if etype == "c4.ElementTagged":
        el = state.elements.get(data["element_id"])
        if el:
            el.tags.update(data.get("tags_added", []) or [])
        return

    if etype == "c4.ElementUntagged":
        el = state.elements.get(data["element_id"])
        if el:
            for t in (data.get("tags_removed", []) or []):
                el.tags.discard(t)
        return

    if etype == "c4.ElementPropertySet":
        el = state.elements.get(data["element_id"])
        if el:
            el.properties[data["key"]] = data.get("value")
        return

    # Relationship events
    if etype == "c4.RelationshipDeclared":
        rid = data["relationship_id"]
        state.relationships[rid] = Relationship(
            relationship_id=rid,
            source_id=data["source_id"],
            destination_id=data["destination_id"],
            description=data.get("description", "") or "",
            technology=data.get("technology", "") or "",
            interaction_style=data.get("interaction_style"),
            tags=set(data.get("tags", []) or []),
            properties=dict(data.get("properties", {}) or {})
        )
        return

    if etype == "c4.RelationshipDescriptionChanged":
        rel = state.relationships.get(data["relationship_id"])
        if rel:
            nd = data.get("new_description")
            nt = data.get("new_technology")
            if nd is not None:
                rel.description = nd
            if nt is not None:
                rel.technology = nt
        return

    if etype == "c4.RelationshipRemoved":
        state.relationships.pop(data["relationship_id"], None)
        return

    # Views
    if etype == "c4.ViewDeclared":
        vid = data["view_id"]
        state.views[vid] = View(
            view_id=vid,
            kind=data["kind"],
            scope_element_id=data.get("scope_element_id"),
            key=data.get("key"),
            title=data.get("title"),
            description=data.get("description"),
        )
        return

    if etype == "c4.ViewElementIncluded":
        v = state.views.get(data["view_id"])
        if v:
            v.include_elements.add(data["element_id"])
        return

    if etype == "c4.ViewRelationshipIncluded":
        v = state.views.get(data["view_id"])
        if v:
            v.include_relationships.add(data["relationship_id"])
        return

    if etype == "c4.ViewAutoLayoutConfigured":
        v = state.views.get(data["view_id"])
        if v:
            v.auto_layout = {
                "rank_direction": data.get("rank_direction"),
                "rank_separation": data.get("rank_separation"),
                "node_separation": data.get("node_separation"),
            }
        return

    # Styles
    if etype == "c4.ElementStyleDefined":
        state.styles.element_styles[data["tag"]] = dict(data.get("style", {}) or {})
        return

    if etype == "c4.RelationshipStyleDefined":
        state.styles.relationship_styles[data["tag"]] = dict(data.get("style", {}) or {})
        return


# =====================================================================
#   DSL RENDER HELPERS
# =====================================================================

def q(s: str) -> str:
    return '"' + str(s).replace('"', '\\"') + '"'


def render_properties(props: Dict[str, Any], indent: str) -> List[str]:
    if not props:
        return []
    lines = [f"{indent}properties {{"]
    for k in sorted(props.keys()):
        v = props[k]
        if isinstance(v, str):
            lines.append(f"{indent}  {q(k)} {q(v)}")
        else:
            lines.append(f"{indent}  {q(k)} {json.dumps(v)}")
    lines.append(f"{indent}}}")
    return lines


def render_tags(tags: Set[str]) -> Optional[str]:
    if not tags:
        return None
    return f"tags {q(','.join(sorted(tags)))}"


def render_element(el: Element, children: List[Element], indent: str, el_map: Dict[str, str]) -> List[str]:
    """
    Emit: <id> = <keyword> "Name" "Desc" ["Tech"] { ... }
    """
    lines: List[str] = []
    kind_kw = {
        "person": "person",
        "softwareSystem": "softwareSystem",
        "container": "container",
        "component": "component",
        "deploymentNode": "deploymentNode",
        "infrastructureNode": "infrastructureNode",
        "softwareSystemInstance": "softwareSystemInstance",
        "containerInstance": "containerInstance",
        "custom": "element"
    }.get(el.kind, "element")

    eid = el_map[el.element_id]
    header = f"{indent}{eid} = {kind_kw} {q(el.name)}"
    if el.description:
        header += f" {q(el.description)}"
    if el.technology and el.kind in ("container", "component", "infrastructureNode"):
        header += f" {q(el.technology)}"

    lines.append(header + " {")

    tline = render_tags(el.tags)
    if tline:
        lines.append(f"{indent}  {tline}")

    # ESML traceability
    lines.append(f"{indent}  properties {{")
    lines.append(f"{indent}    \"esml.id\" {q(el.element_id)}")
    lines.append(f"{indent}  }}")

    lines.extend(render_properties(el.properties, indent + "  "))

    for c in children:
        lines.extend(render_element(c, [], indent + "  ", el_map))

    lines.append(f"{indent}}}")
    return lines


def render_relationship(rel: Relationship, indent: str, el_map: Dict[str, str]) -> str:
    src = el_map[rel.source_id]
    dst = el_map[rel.destination_id]
    s = f"{indent}{src} -> {dst}"
    if rel.description:
        s += f" {q(rel.description)}"
    if rel.technology:
        s += f" {q(rel.technology)}"
    return s


def render_style_block(styles: Dict[str, Dict[str, Any]], kind_kw: str, indent: str) -> List[str]:
    lines: List[str] = []
    for tag in sorted(styles.keys()):
        style = styles[tag]
        lines.append(f"{indent}{kind_kw} {q(tag)} {{")
        for k in sorted(style.keys()):
            v = style[k]
            if isinstance(v, str):
                lines.append(f"{indent}  {k} {q(v)}")
            else:
                lines.append(f"{indent}  {k} {v}")
        lines.append(f"{indent}}}")
    return lines


def render_views(state: C4State, indent: str, el_map: Dict[str, str]) -> List[str]:
    """
    Basic views only include elements; relationships are implied automatically.
    We keep include_relationships in ESML state but DO NOT emit them.
    """
    lines: List[str] = []
    for vid in sorted(state.views.keys()):
        v = state.views[vid]

        header_parts = [indent + v.kind]
        if v.scope_element_id:
            header_parts.append(el_map[v.scope_element_id])
        if v.key:
            header_parts.append(v.key)

        lines.append(" ".join(header_parts) + " {")

        if v.title:
            lines.append(f"{indent}  title {q(v.title)}")
        if v.description:
            lines.append(f"{indent}  description {q(v.description)}")

        for eid in sorted(v.include_elements):
            lines.append(f"{indent}  include {el_map[eid]}")

        # NO relationship includes here (illegal syntax)

        if v.auto_layout and v.auto_layout.get("rank_direction"):
            rd = v.auto_layout["rank_direction"]
            rs = v.auto_layout.get("rank_separation")
            ns = v.auto_layout.get("node_separation")
            al = f"{indent}  autoLayout {rd}"
            if rs is not None:
                al += f" {rs}"
            if ns is not None:
                al += f" {ns}"
            lines.append(al)

        lines.append(f"{indent}}}")
    return lines


# =====================================================================
#   PROJECT-TO-DSL MAIN FUNCTION
# =====================================================================

def project_to_dsl(state: C4State) -> str:
    ws = state.workspace
    if not ws:
        return "// No workspace started."

    el_map, rel_map = build_id_maps(state)

    out: List[str] = []
    out.append(f"workspace {q(ws.name or ws.workspace_id)} {q(ws.description)} {{")

    # configuration
    if ws.properties or ws.themes or ws.branding or ws.terminology:
        out.append("  configuration {")
        if ws.properties:
            out.append("    properties {")
            for k in sorted(ws.properties.keys()):
                v = ws.properties[k]
                if isinstance(v, str):
                    out.append(f"      {q(k)} {q(v)}")
                else:
                    out.append(f"      {q(k)} {json.dumps(v)}")
            out.append("    }")
        for t in ws.themes:
            out.append(f"    theme {q(t)}")
        if ws.branding:
            out.append("    branding {")
            for k in sorted(ws.branding.keys()):
                v = ws.branding[k]
                out.append(f"      {k} {q(v) if isinstance(v,str) else json.dumps(v)}")
            out.append("    }")
        if ws.terminology:
            out.append("    terminology {")
            for k in sorted(ws.terminology.keys()):
                v = ws.terminology[k]
                out.append(f"      {k} {q(v) if isinstance(v,str) else json.dumps(v)}")
            out.append("    }")
        out.append("  }")

    # parent->children
    children_map: Dict[str, List[Element]] = {}
    roots: List[Element] = []
    for el in state.elements.values():
        if el.parent_id:
            children_map.setdefault(el.parent_id, []).append(el)
        else:
            roots.append(el)

    for k in children_map:
        children_map[k].sort(key=lambda e: (e.kind, e.element_id))
    roots.sort(key=lambda e: (e.kind, e.element_id))

    # model
    out.append("  model {")
    for el in roots:
        kids = children_map.get(el.element_id, [])
        out.extend(render_element(el, kids, "    ", el_map))

    for rid in sorted(state.relationships.keys()):
        out.append(render_relationship(state.relationships[rid], "    ", el_map))
    out.append("  }")

    # views + styles (styles must be nested here)
    out.append("  views {")
    out.extend(render_views(state, "    ", el_map))

    if state.styles.element_styles or state.styles.relationship_styles:
        out.append("    styles {")
        out.extend(render_style_block(state.styles.element_styles, "element", "      "))
        out.extend(render_style_block(state.styles.relationship_styles, "relationship", "      "))
        out.append("    }")

    out.append("  }")  # end views

    out.append("}")
    return "\n".join(out)


# =====================================================================
#   CLI
# =====================================================================

def main():
    ap = argparse.ArgumentParser(description="Project Structurizr DSL from C4 ESML.")
    ap.add_argument("esml_file", help="Path to .esml file")
    ap.add_argument("--max-events", type=int, default=None,
                    help="Replay only first N events")
    args = ap.parse_args()

    with open(args.esml_file, "r", encoding="utf-8") as f:
        text = f.read()

    state = C4State()
    count = 0
    for ev in read_esml_events(text):
        apply_event(state, ev)
        count += 1
        if args.max_events is not None and count >= args.max_events:
            break

    print(project_to_dsl(state))


if __name__ == "__main__":
    main()
