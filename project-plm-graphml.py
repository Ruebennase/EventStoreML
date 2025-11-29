import sys
import json
from typing import Optional
from xml.sax.saxutils import escape


def iter_esml_events(text: str):
    """
    Incrementally parse a sequence of JSON objects (ESML) from a string.
    Works even if objects are not one-per-line.
    """
    decoder = json.JSONDecoder()
    idx = 0
    length = len(text)
    while idx < length:
        # Skip whitespace
        while idx < length and text[idx].isspace():
            idx += 1
        if idx >= length:
            break
        obj, next_idx = decoder.raw_decode(text, idx)
        yield obj
        idx = next_idx


def project_esml_to_graphml(esml_path: str, graphml_path: str):
    with open(esml_path, "r", encoding="utf-8") as f:
        content = f.read()

    nodes = {}  # id -> {"id": ..., "kind": ..., "label": ...}
    edges = []  # {"source": ..., "target": ..., "label": ..., "type": ...}

    def ensure_node(node_id: str, kind: str = "unknown", label: Optional[str] = None):
        if node_id not in nodes:
            nodes[node_id] = {
                "id": node_id,
                "kind": kind,
                "label": label or node_id,
            }
        else:
            if kind != "unknown" and nodes[node_id].get("kind") in (None, "unknown"):
                nodes[node_id]["kind"] = kind
            if label and (
                not nodes[node_id].get("label")
                or nodes[node_id]["label"] == nodes[node_id]["id"]
            ):
                nodes[node_id]["label"] = label

    # --- Build nodes & edges from ESML events ---

    for event in iter_esml_events(content):
        etype = event.get("type")
        data = event.get("data", {})

        if etype == "plm.ConfigurationDefined":
            cid = data["config_id"]
            ensure_node(
                cid,
                kind=data.get("kind", "configuration"),
                label=data.get("label", cid),
            )

        elif etype == "plm.ConfigurationPropertySet":
            cid = data["config_id"]
            ensure_node(cid, kind="configuration")
            nodes[cid].setdefault("properties", {})[data["key"]] = data["value"]

        elif etype == "plm.ConfigurationSpecialisedAs":
            child = data["more_specific_id"]
            parent = data["more_general_id"]
            ensure_node(child, kind="configuration")
            ensure_node(parent, kind="configuration")
            edges.append(
                {"source": child, "target": parent,
                 "label": "specialises", "type": "specialises"}
            )

        elif etype == "plm.ConfigurationPartOf":
            whole = data["whole_id"]
            part = data["part_id"]
            ensure_node(whole, kind="configuration")
            ensure_node(part, kind="configuration")
            # Arrow should point: part  →  whole
            edges.append(
                {"source": part, "target": whole,
                 "label": "part-of", "type": "part-of"}
            )

        elif etype == "plm.ConfigurationSupersededBy":
            old_id = data["old_config_id"]
            new_id = data["new_config_id"]
            ensure_node(old_id, kind="configuration")
            ensure_node(new_id, kind="configuration")
            edges.append(
                {"source": old_id, "target": new_id,
                 "label": "superseded-by", "type": "supersedes"}
            )

        elif etype == "plm.FunctionDefined":
            fid = data["function_id"]
            ensure_node(fid, kind="function", label=data.get("label", fid))

        elif etype == "plm.ConfigurationImplementsFunction":
            cid = data["config_id"]
            fid = data["function_id"]
            ensure_node(cid, kind="configuration")
            ensure_node(fid, kind="function")
            edges.append(
                {"source": cid, "target": fid,
                 "label": "implements", "type": "implements"}
            )

        elif etype == "plm.RequirementDefined":
            rid = data["requirement_id"]
            ensure_node(rid, kind="requirement", label=data.get("label", rid))

        elif etype == "plm.ConfigurationFulfillsRequirement":
            cid = data["config_id"]
            rid = data["requirement_id"]
            ensure_node(cid, kind="configuration")
            ensure_node(rid, kind="requirement")
            edges.append(
                {"source": cid, "target": rid,
                 "label": "fulfills", "type": "fulfills"}
            )

        elif etype == "plm.ConstraintDefined":
            cid = data["constraint_id"]
            ensure_node(cid, kind="constraint", label=data.get("label", cid))

        elif etype == "plm.ConfigurationSatisfiesConstraint":
            cfg = data["config_id"]
            con = data["constraint_id"]
            ensure_node(cfg, kind="configuration")
            ensure_node(con, kind="constraint")
            label = "satisfies({})".format(data.get("status", "unknown"))
            edges.append(
                {"source": cfg, "target": con,
                 "label": label, "type": "satisfies"}
            )

        elif etype == "plm.ProcessDefined":
            pid = data["process_id"]
            ensure_node(pid, kind="process", label=data.get("label", pid))

        elif etype == "plm.ConfigurationDerivedFrom":
            derived = data["derived_config_id"]
            source = data["source_config_id"]
            ensure_node(derived, kind="configuration")
            ensure_node(source, kind="configuration")
            edges.append(
                {"source": derived, "target": source,
                 "label": "derived-from", "type": "derived-from"}
            )

        elif etype == "plm.ConfigurationStateAtTimeRecorded":
            sid = data["state_id"]
            cfg = data["config_id"]
            ensure_node(cfg, kind="configuration")
            label = "{}@{}".format(cfg, data.get("timestamp"))
            ensure_node(sid, kind="state", label=label)
            edges.append(
                {"source": cfg, "target": sid,
                 "label": "state-at-time", "type": "state-at-time"}
            )

        elif etype == "plm.AssetDefined":
            aid = data["asset_id"]
            ensure_node(aid, kind="asset", label=data.get("label", aid))

        elif etype == "plm.ConfigurationRepresentsAsset":
            cfg = data["config_id"]
            aid = data["asset_id"]
            ensure_node(cfg, kind="configuration")
            ensure_node(aid, kind="asset")
            edges.append(
                {"source": cfg, "target": aid,
                 "label": "represents", "type": "represents"}
            )

        # Ignore TypeDeclared etc.

    # --- Write yEd-style GraphML, with color, size, arrows like your sample ---

    with open(graphml_path, "w", encoding="utf-8") as out:
        out.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        out.write('<graphml xmlns="http://graphml.graphdrawing.org/xmlns"\n')
        out.write('         xmlns:y="http://www.yworks.com/xml/graphml">\n')
        # use d6/d10 like your sample: node and edge graphics
        out.write('  <key id="d6" for="node" yfiles.type="nodegraphics"/>\n')
        out.write('  <key id="d10" for="edge" yfiles.type="edgegraphics"/>\n')
        out.write('  <graph id="G" edgedefault="directed">\n')

        # Nodes: ShapeNode, rounded rectangle, color+size like your style
        for node_id, props in nodes.items():
            label = escape(str(props.get("label", node_id)))
            out.write('    <node id="{}">\n'.format(escape(node_id)))
            out.write('      <data key="d6">\n')
            out.write('        <y:ShapeNode>\n')
            # size: close to 85x55 like your small boxes, x/y left to layout
            out.write('          <y:Geometry height="55.0" width="120.0" x="0.0" y="0.0"/>\n')
            out.write('          <y:Fill color="#CAECFF80" transparent="false"/>\n')
            out.write('          <y:BorderStyle color="#999999" type="line" width="1.0"/>\n')
            out.write('          <y:NodeLabel>{}</y:NodeLabel>\n'.format(label))
            out.write('          <y:Shape type="roundrectangle"/>\n')
            out.write('        </y:ShapeNode>\n')
            out.write('      </data>\n')
            out.write('    </node>\n')

        # Edges: PolyLine + LineStyle + Arrows + EdgeLabel
        for i, e in enumerate(edges):
            eid = "e{}".format(i)
            src = escape(e["source"])
            tgt = escape(e["target"])
            label = escape(e.get("label", ""))
            out.write('    <edge id="{0}" source="{1}" target="{2}">\n'
                      .format(eid, src, tgt))
            out.write('      <data key="d10">\n')
            out.write('        <y:PolyLineEdge>\n')
            out.write('          <y:Path sx="0.0" sy="0.0" tx="0.0" ty="0.0"/>\n')
            out.write('          <y:LineStyle color="#000000" type="line" width="1.0"/>\n')
            # arrows same style you had: none at source, standard at target
            out.write('          <y:Arrows source="none" target="standard"/>\n')
            if label:
                out.write('          <y:EdgeLabel>{}</y:EdgeLabel>\n'.format(label))
            out.write('        </y:PolyLineEdge>\n')
            out.write('      </data>\n')
            out.write('    </edge>\n')

        out.write('  </graph>\n')
        out.write('</graphml>\n')

    print("Wrote GraphML with {} nodes and {} edges to {}".format(
        len(nodes), len(edges), graphml_path
    ))


def main():
    if len(sys.argv) not in (2, 3):
        print("Usage: python project-plm-graphml.py INPUT.esml [OUTPUT.graphml]")
        sys.exit(1)

    esml_path = sys.argv[1]
    if len(sys.argv) == 3:
        graphml_path = sys.argv[2]
    else:
        base = esml_path.rsplit(".", 1)[0] if "." in esml_path else esml_path
        graphml_path = base + ".graphml"

    project_esml_to_graphml(esml_path, graphml_path)


if __name__ == "__main__":
    main()
