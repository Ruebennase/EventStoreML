#!/usr/bin/env python3
"""
Project a Structurizr DSL workspace from a C4 ESML event stream.

Supports:
- Workspace evolution (properties/themes/branding/terminology/extends)
- Elements, relationships, and removals
- Groups/boundaries + membership add/remove
- Views, filtered views, auto-layout, animations
- Element/relationship styles
- Docs and ADRs/decisions blocks
- Deployment model kinds (via ElementDeclared kinds)

DSL compliance:
- Identifiers use assignment syntax: <id> = container/person/...
- ESML ids sanitized into DSL-safe identifiers
- Basic views only include elements; relationships are implied
- Styles emitted inside views { styles { ... } }
"""

import argparse
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


# =====================================================================
#   ESML PARSER (sequence of JSON objects without commas)
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
    extends: Optional[str] = None
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
    # animations: step -> (elements, relationships)
    animations: Dict[int, Dict[str, List[str]]] = field(default_factory=dict)


@dataclass
class Group:
    group_id: str
    name: str
    parent_group_id: Optional[str] = None
    element_ids: Set[str] = field(default_factory=set)


@dataclass
class Styles:
    element_styles: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    relationship_styles: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class DocsSection:
    workspace_id: str
    element_id: Optional[str]
    title: str
    format: str
    content_ref: str


@dataclass
class Adr:
    workspace_id: str
    adr_id: str
    title: str
    status: Optional[str] = None
    content_ref: Optional[str] = None


@dataclass
class C4State:
    workspace: Optional[Workspace] = None
    elements: Dict[str, Element] = field(default_factory=dict)
    relationships: Dict[str, Relationship] = field(default_factory=dict)
    views: Dict[str, View] = field(default_factory=dict)
    filtered_views: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # view_id -> spec
    groups: Dict[str, Group] = field(default_factory=dict)
    styles: Styles = field(default_factory=Styles)
    docs_sections: List[DocsSection] = field(default_factory=list)
    adrs: Dict[str, Adr] = field(default_factory=dict)


# =====================================================================
#   ID SANITIZATION
# =====================================================================

def dsl_id(raw: str) -> str:
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

    # ---------------- Workspace ----------------
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
            if data.get("new_name") is not None:
                ws.name = data["new_name"]
            if data.get("new_description") is not None:
                ws.description = data["new_description"]
        return

    if etype == "c4.WorkspaceExtended":
        ws = state.workspace
        if ws and ws.workspace_id == data["workspace_id"]:
            ws.extends = data.get("base_ref")
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

    if etype == "c4.ThemeRemoved":
        ws = state.workspace
        if ws and ws.workspace_id == data["workspace_id"]:
            try:
                ws.themes.remove(data["theme_url"])
            except ValueError:
                pass
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

    # ---------------- Elements ----------------
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

    if etype == "c4.ElementRenamed":
        el = state.elements.get(data["element_id"])
        if el and data.get("new_name") is not None:
            el.name = data["new_name"]
        return

    if etype == "c4.ElementDescriptionChanged":
        el = state.elements.get(data["element_id"])
        if el:
            if data.get("new_description") is not None:
                el.description = data["new_description"]
            if data.get("new_technology") is not None:
                el.technology = data["new_technology"]
        return

    if etype == "c4.ElementMoved":
        el = state.elements.get(data["element_id"])
        if el:
            el.parent_id = data.get("new_parent_id")
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

    if etype == "c4.ElementPropertyRemoved":
        el = state.elements.get(data["element_id"])
        if el:
            el.properties.pop(data["key"], None)
        return

    if etype == "c4.ElementRemoved":
        eid = data["element_id"]
        state.elements.pop(eid, None)

        # remove relationships referencing element
        to_rm = [rid for rid, r in state.relationships.items()
                 if r.source_id == eid or r.destination_id == eid]
        for rid in to_rm:
            state.relationships.pop(rid, None)

        # remove from groups
        for g in state.groups.values():
            g.element_ids.discard(eid)

        # remove from view includes
        for v in state.views.values():
            v.include_elements.discard(eid)
        return

    # ---------------- Groups / Boundaries ----------------
    if etype == "c4.GroupDeclared":
        gid = data["group_id"]
        state.groups[gid] = Group(
            group_id=gid,
            name=data["name"],
            parent_group_id=data.get("parent_group_id")
        )
        return

    if etype == "c4.GroupRenamed":
        g = state.groups.get(data["group_id"])
        if g and data.get("new_name"):
            g.name = data["new_name"]
        return

    if etype == "c4.GroupRemoved":
        state.groups.pop(data["group_id"], None)
        return

    if etype == "c4.ElementAddedToGroup":
        g = state.groups.get(data["group_id"])
        if g:
            g.element_ids.add(data["element_id"])
        return

    if etype == "c4.ElementRemovedFromGroup":
        g = state.groups.get(data["group_id"])
        if g:
            g.element_ids.discard(data["element_id"])
        return

    # ---------------- Relationships ----------------
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
            if data.get("new_description") is not None:
                rel.description = data["new_description"]
            if data.get("new_technology") is not None:
                rel.technology = data["new_technology"]
        return

    if etype == "c4.RelationshipTagged":
        rel = state.relationships.get(data["relationship_id"])
        if rel:
            rel.tags.update(data.get("tags_added", []) or [])
        return

    if etype == "c4.RelationshipUntagged":
        rel = state.relationships.get(data["relationship_id"])
        if rel:
            for t in (data.get("tags_removed", []) or []):
                rel.tags.discard(t)
        return

    if etype == "c4.RelationshipPropertySet":
        rel = state.relationships.get(data["relationship_id"])
        if rel:
            rel.properties[data["key"]] = data.get("value")
        return

    if etype == "c4.RelationshipPropertyRemoved":
        rel = state.relationships.get(data["relationship_id"])
        if rel:
            rel.properties.pop(data["key"], None)
        return

    if etype == "c4.RelationshipRemoved":
        state.relationships.pop(data["relationship_id"], None)
        return

    # ---------------- Views ----------------
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

    if etype == "c4.ViewRenamed":
        v = state.views.get(data["view_id"])
        if v:
            if data.get("new_key"): v.key = data["new_key"]
            if data.get("new_title"): v.title = data["new_title"]
        return

    if etype == "c4.ViewDescriptionChanged":
        v = state.views.get(data["view_id"])
        if v and data.get("new_description") is not None:
            v.description = data["new_description"]
        return

    if etype == "c4.ViewElementIncluded":
        v = state.views.get(data["view_id"])
        if v:
            v.include_elements.add(data["element_id"])
        return

    if etype == "c4.ViewElementExcluded":
        v = state.views.get(data["view_id"])
        if v:
            v.include_elements.discard(data["element_id"])
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

    if etype == "c4.ViewAutoLayoutCleared":
        v = state.views.get(data["view_id"])
        if v:
            v.auto_layout = None
        return

    if etype == "c4.ViewRemoved":
        state.views.pop(data["view_id"], None)
        return

    if etype == "c4.FilteredViewDeclared":
        # store spec; emitted later
        state.filtered_views[data["view_id"]] = {
            "base_view_key": data["base_view_key"],
            "filter_tag": data["filter_tag"],
            "mode": data["mode"],  # include/exclude
            "key": data.get("key") or data["view_id"],
            "title": data.get("title"),
            "description": data.get("description"),
        }
        return

    if etype == "c4.AnimationStepAdded":
        v = state.views.get(data["view_id"])
        if v:
            step = int(data["step_number"])
            v.animations[step] = {
                "elements": list(data.get("elements", []) or []),
                "relationships": list(data.get("relationships", []) or []),
            }
        return

    if etype == "c4.AnimationStepRemoved":
        v = state.views.get(data["view_id"])
        if v:
            v.animations.pop(int(data["step_number"]), None)
        return

    # ---------------- Styles ----------------
    if etype == "c4.ElementStyleDefined":
        state.styles.element_styles[data["tag"]] = dict(data.get("style", {}) or {})
        return

    if etype == "c4.ElementStyleRemoved":
        state.styles.element_styles.pop(data["tag"], None)
        return

    if etype == "c4.RelationshipStyleDefined":
        state.styles.relationship_styles[data["tag"]] = dict(data.get("style", {}) or {})
        return

    if etype == "c4.RelationshipStyleRemoved":
        state.styles.relationship_styles.pop(data["tag"], None)
        return

    # ---------------- Docs / ADRs ----------------
    if etype == "c4.DocumentationSectionAdded":
        state.docs_sections.append(DocsSection(
            workspace_id=data["workspace_id"],
            element_id=data.get("element_id"),
            title=data["section_title"],
            format=data["format"],
            content_ref=data.get("content_ref","")
        ))
        return

    if etype == "c4.DocumentationSectionUpdated":
        # naive update by title+element_id
        for s in state.docs_sections:
            if s.title == data["section_title"] and s.element_id == data.get("element_id"):
                if data.get("content_ref") is not None:
                    s.content_ref = data["content_ref"]
        return

    if etype == "c4.DocumentationSectionRemoved":
        state.docs_sections = [
            s for s in state.docs_sections
            if not (s.title == data["section_title"] and s.element_id == data.get("element_id"))
        ]
        return

    if etype == "c4.AdrAdded":
        state.adrs[data["adr_id"]] = Adr(
            workspace_id=data["workspace_id"],
            adr_id=data["adr_id"],
            title=data["title"],
            status=data.get("status"),
            content_ref=data.get("content_ref")
        )
        return

    if etype == "c4.AdrUpdated":
        a = state.adrs.get(data["adr_id"])
        if a:
            if data.get("title") is not None: a.title = data["title"]
            if data.get("status") is not None: a.status = data["status"]
            if data.get("content_ref") is not None: a.content_ref = data["content_ref"]
        return

    if etype == "c4.AdrRemoved":
        state.adrs.pop(data["adr_id"], None)
        return


# =====================================================================
#   DSL RENDER HELPERS
# =====================================================================

def q(s: str) -> str:
    return '"' + str(s).replace('"', '\\"') + '"'

def dsl_view_key(raw: str) -> str:
    """
    Structurizr view keys may only contain a-zA-Z0-9_-.
    Replace anything else (like dots) with underscore.
    """
    return re.sub(r"[^A-Za-z0-9_-]", "_", raw)

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


def element_keyword(kind: str) -> str:
    return {
        "person": "person",
        "softwareSystem": "softwareSystem",
        "container": "container",
        "component": "component",
        "deploymentEnvironment": "deploymentEnvironment",
        "deploymentNode": "deploymentNode",
        "infrastructureNode": "infrastructureNode",
        "softwareSystemInstance": "softwareSystemInstance",
        "containerInstance": "containerInstance",
        "custom": "element"
    }.get(kind, "element")


def render_element(el: Element, children: List[Element], indent: str, el_map: Dict[str, str]) -> List[str]:
    kw = element_keyword(el.kind)
    eid = el_map[el.element_id]

    header = f"{indent}{eid} = {kw} {q(el.name)}"
    if el.description:
        header += f" {q(el.description)}"
    if el.technology and el.kind in ("container", "component", "infrastructureNode"):
        header += f" {q(el.technology)}"

    lines = [header + " {"]

    tline = render_tags(el.tags)
    if tline:
        lines.append(f"{indent}  {tline}")

    # traceability
    lines.append(f"{indent}  properties {{")
    lines.append(f"{indent}    \"esml.id\" {q(el.element_id)}")
    lines.append(f"{indent}  }}")

    lines.extend(render_properties(el.properties, indent + "  "))

    for c in children:
        lines.extend(render_element(c, [], indent + "  ", el_map))

    lines.append(f"{indent}}}")
    return lines


def render_relationship(rel: Relationship, indent: str, el_map: Dict[str, str]) -> Optional[str]:
    if rel.source_id not in el_map or rel.destination_id not in el_map:
        return None
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


# ---------------- Groups rendering ----------------

def build_group_tree(groups: Dict[str, Group]) -> Tuple[List[str], Dict[str, List[str]]]:
    roots = []
    children = {}
    for gid, g in groups.items():
        if g.parent_group_id and g.parent_group_id in groups:
            children.setdefault(g.parent_group_id, []).append(gid)
        else:
            roots.append(gid)
    for k in children:
        children[k].sort()
    roots.sort()
    return roots, children


def render_groups_and_roots(
    state: C4State,
    roots: List[Element],
    children_map: Dict[str, List[Element]],
    el_map: Dict[str, str],
    indent: str
) -> List[str]:
    """
    Render root-level elements, grouping those assigned to groups.
    Note: groups are applied only to root elements (parent_id None).
    """
    lines: List[str] = []

    # Map element->group (only one group supported per root for now)
    elem_to_group: Dict[str, str] = {}
    for gid, g in state.groups.items():
        for eid in g.element_ids:
            elem_to_group[eid] = gid

    group_roots, group_children = build_group_tree(state.groups)

    # Which root elements are not in any group?
    grouped_root_ids = {eid for eid in elem_to_group.keys()}
    ungrouped_roots = [e for e in roots if e.element_id not in grouped_root_ids]

    # render groups recursively
    def render_group(gid: str, level_indent: str):
        g = state.groups[gid]
        lines.append(f'{level_indent}group {q(g.name)} {{')

        # elements in this group (root only)
        elems = [e for e in roots if elem_to_group.get(e.element_id) == gid]
        elems.sort(key=lambda e: (e.kind, e.element_id))
        for el in elems:
            kids = children_map.get(el.element_id, [])
            lines.extend(render_element(el, kids, level_indent + "  ", el_map))

        # child groups
        for child_gid in group_children.get(gid, []):
            render_group(child_gid, level_indent + "  ")

        lines.append(f"{level_indent}}}")

    for gid in group_roots:
        render_group(gid, indent)

    # render ungrouped roots after groups
    for el in ungrouped_roots:
        kids = children_map.get(el.element_id, [])
        lines.extend(render_element(el, kids, indent, el_map))

    return lines


# ---------------- Views rendering ----------------

def render_view_animation(v: View, indent: str, el_map: Dict[str, str]) -> List[str]:
    if not v.animations:
        return []
    lines = [f"{indent}  animation {{"]

    for step in sorted(v.animations.keys()):
        step_data = v.animations[step]
        elems = []
        for eid in step_data.get("elements", []):
            if eid in el_map:
                elems.append(el_map[eid])

        # if relationships are provided, pull in their endpoints too
        for rid in step_data.get("relationships", []):
            # Not listing relationships explicitly in animation; endpoints are enough
            pass

        if elems:
            lines.append(f"{indent}    " + " ".join(sorted(set(elems))))
        else:
            lines.append(f"{indent}    // step {step} had no remaining elements")

    lines.append(f"{indent}  }}")
    return lines


def render_views(state: C4State, indent: str, el_map: Dict[str, str]) -> List[str]:
    """
    Basic views include only elements. Relationships are implied automatically.
    Missing elements (removed later) are skipped safely.
    """
    lines: List[str] = []
    for vid in sorted(state.views.keys()):
        v = state.views[vid]

        header_parts = [indent + v.kind]
        if v.scope_element_id and v.scope_element_id in el_map:
            header_parts.append(el_map[v.scope_element_id])
        if v.key:
            header_parts.append(dsl_view_key(v.key))

        lines.append(" ".join(header_parts) + " {")

        if v.title:
            lines.append(f"{indent}  title {q(v.title)}")
        if v.description:
            lines.append(f"{indent}  description {q(v.description)}")

        for eid in sorted(v.include_elements):
            if eid in el_map:
                lines.append(f"{indent}  include {el_map[eid]}")

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

        # animation
        lines.extend(render_view_animation(v, indent, el_map))

        lines.append(f"{indent}}}")
    return lines


def render_filtered_views(state: C4State, indent: str) -> List[str]:
    """
    filtered <baseKey> <include|exclude> <tags> <key> ["description"] { ... }
    """
    lines: List[str] = []
    for vid in sorted(state.filtered_views.keys()):
        fv = state.filtered_views[vid]
        base_key = dsl_view_key(fv["base_view_key"])
        mode = fv["mode"]                  # include | exclude
        tags = fv["filter_tag"]
        key_raw = fv.get("key") or vid
        key = dsl_view_key(key_raw)
        desc = fv.get("description")

        header = f"{indent}filtered {base_key} {mode} {q(tags)} {key}"
        if desc:
            header += f" {q(desc)}"
        header += " {"
        lines.append(header)

        if fv.get("title"):
            lines.append(f"{indent}  title {q(fv['title'])}")

        lines.append(f"{indent}}}")
    return lines




# ---------------- Docs / Decisions rendering ----------------

def render_docs_and_adrs(state: C4State, indent: str) -> List[str]:
    lines: List[str] = []

    # Docs ARE allowed in all Structurizr editions
    if state.docs_sections:
        lines.append(f"{indent}!docs {{")
        for s in state.docs_sections:
            lines.append(f'{indent}  section {q(s.title)} {{')
            if s.element_id:
                lines.append(f'{indent}    element {q(s.element_id)}')
            lines.append(f'{indent}    format {s.format}')
            if s.content_ref:
                lines.append(f'{indent}    content {q(s.content_ref)}')
            lines.append(f"{indent}  }}")
        lines.append(f"{indent}}}")

    # Decisions (ADRs) are NOT emitted, to stay OSS-compatible
    # ADR events remain in ESML state but not projected to DSL.

    return lines


# =====================================================================
#   PROJECT-TO-DSL
# =====================================================================

def project_to_dsl(state: C4State) -> str:
    ws = state.workspace
    if not ws:
        return "// No workspace started."

    el_map, rel_map = build_id_maps(state)

    out: List[str] = []
    wname = ws.name or ws.workspace_id
    out.append(f"workspace {q(wname)} {q(ws.description)} {{")

    # docs + decisions (top-level, if present)
    out.extend(render_docs_and_adrs(state, "  "))

    # configuration
    if ws.extends or ws.properties or ws.themes or ws.branding or ws.terminology:
        out.append("  configuration {")

        if ws.extends:
            out.append(f"    extends {q(ws.extends)}")

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

    # parent->children map
    children_map: Dict[str, List[Element]] = {}
    roots: List[Element] = []
    for el in state.elements.values():
        if el.parent_id and el.parent_id in state.elements:
            children_map.setdefault(el.parent_id, []).append(el)
        else:
            roots.append(el)

    for pid in children_map:
        children_map[pid].sort(key=lambda e: (e.kind, e.element_id))
    roots.sort(key=lambda e: (e.kind, e.element_id))

    # model
    out.append("  model {")
    out.extend(render_groups_and_roots(state, roots, children_map, el_map, "    "))

    # relationships
    for rid in sorted(state.relationships.keys()):
        line = render_relationship(state.relationships[rid], "    ", el_map)
        if line:
            out.append(line)

    out.append("  }")

    # views
    out.append("  views {")
    out.extend(render_views(state, "    ", el_map))
    out.extend(render_filtered_views(state, "    "))

    # styles (inside views)
    if state.styles.element_styles or state.styles.relationship_styles:
        out.append("    styles {")
        out.extend(render_style_block(state.styles.element_styles, "element", "      "))
        out.extend(render_style_block(state.styles.relationship_styles, "relationship", "      "))
        out.append("    }")

    out.append("  }")
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
