#!/usr/bin/env python3
import sys
import json
from typing import List, Dict, Any, Optional

# ------------------------------------------------------------
# ESML loader (same style as your validator)
# ------------------------------------------------------------
def load_esml(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    decoder = json.JSONDecoder()
    idx = 0
    n = len(text)
    events: List[Dict[str, Any]] = []

    while idx < n:
        while idx < n and text[idx].isspace():
            idx += 1
        if idx >= n:
            break
        obj, end = decoder.raw_decode(text, idx)
        events.append(obj)
        idx = end
    return events

# ------------------------------------------------------------
# BPMN in-memory model
# ------------------------------------------------------------
class BPMNProcess:
    def __init__(self, pid: str, name: Optional[str] = None):
        self.id = pid
        self.name = name
        self.elements: Dict[str, Dict[str, Any]] = {}
        self.sequence_flows: List[Dict[str, Any]] = []
        self.lane_assignments: List[tuple] = []  # (lane_id, element_id)

class BPMNDefinition:
    def __init__(self):
        self.processes: Dict[str, BPMNProcess] = {}
        self.pools: Dict[str, Dict[str, Any]] = {}
        self.lanes: Dict[str, Dict[str, Any]] = {}
        self.message_flows: List[Dict[str, Any]] = []

    def get_or_create_process(self, pid: str) -> BPMNProcess:
        if pid not in self.processes:
            self.processes[pid] = BPMNProcess(pid)
        return self.processes[pid]

# ------------------------------------------------------------
# Replay ESML → BPMN
# ------------------------------------------------------------
def replay_events(events: List[Dict[str, Any]]) -> BPMNDefinition:
    bpmn = BPMNDefinition()
    for ev in events:
        etype = ev.get("type")
        data = ev.get("data", {})

        if etype == "bpmn.ProcessDeclared":
            pid = data["process_id"]
            proc = bpmn.get_or_create_process(pid)
            proc.name = data.get("name", pid)

        elif etype == "bpmn.PoolDeclared":
            bpmn.pools[data["pool_id"]] = {
                "id": data["pool_id"],
                "name": data.get("name"),
                "process_id": data.get("process_id"),
            }

        elif etype == "bpmn.LaneDeclared":
            bpmn.lanes[data["lane_id"]] = {
                "id": data["lane_id"],
                "name": data.get("name"),
                "pool_id": data.get("pool_id"),
                "process_id": data.get("process_id"),
            }

        elif etype == "bpmn.ElementAssignedToLane":
            pid = data["process_id"]
            bpmn.get_or_create_process(pid).lane_assignments.append(
                (data["lane_id"], data["element_id"])
            )

        elif etype == "bpmn.StartEventDeclared":
            pid = data["process_id"]
            bpmn.get_or_create_process(pid).elements[data["element_id"]] = {
                "type": "startEvent",
                "name": data.get("name"),
            }

        elif etype == "bpmn.EndEventDeclared":
            pid = data["process_id"]
            bpmn.get_or_create_process(pid).elements[data["element_id"]] = {
                "type": "endEvent",
                "name": data.get("name"),
            }

        elif etype == "bpmn.IntermediateCatchEventDeclared":
            pid = data["process_id"]
            bpmn.get_or_create_process(pid).elements[data["element_id"]] = {
                "type": "intermediateCatchEvent",
                "name": data.get("name"),
                "event_def": data.get("event_def"),
            }

        elif etype == "bpmn.IntermediateThrowEventDeclared":
            pid = data["process_id"]
            bpmn.get_or_create_process(pid).elements[data["element_id"]] = {
                "type": "intermediateThrowEvent",
                "name": data.get("name"),
                "event_def": data.get("event_def"),
            }

        elif etype == "bpmn.TaskDeclared":
            pid = data["process_id"]
            bpmn.get_or_create_process(pid).elements[data["element_id"]] = {
                "type": "task",
                "name": data.get("name"),
            }

        elif etype == "bpmn.SubProcessDeclared":
            pid = data["process_id"]
            bpmn.get_or_create_process(pid).elements[data["element_id"]] = {
                "type": "subProcess",
                "name": data.get("name"),
            }

        elif etype == "bpmn.CallActivityDeclared":
            pid = data["process_id"]
            bpmn.get_or_create_process(pid).elements[data["element_id"]] = {
                "type": "callActivity",
                "name": data.get("name"),
                "called_process": data.get("called_process"),
            }

        elif etype == "bpmn.ExclusiveGatewayDeclared":
            pid = data["process_id"]
            bpmn.get_or_create_process(pid).elements[data["element_id"]] = {
                "type": "exclusiveGateway",
                "name": data.get("name"),
                "default_flow": data.get("default_flow"),
            }

        elif etype == "bpmn.ParallelGatewayDeclared":
            pid = data["process_id"]
            bpmn.get_or_create_process(pid).elements[data["element_id"]] = {
                "type": "parallelGateway",
                "name": data.get("name"),
            }

        elif etype == "bpmn.SequenceFlowDeclared":
            pid = data["process_id"]
            bpmn.get_or_create_process(pid).sequence_flows.append({
                "id": data["flow_id"],
                "sourceRef": data["source_id"],
                "targetRef": data["target_id"],
                "name": data.get("name"),
                "condition": data.get("condition"),
            })

        elif etype == "bpmn.MessageFlowDeclared":
            bpmn.message_flows.append({
                "id": data["message_flow_id"],
                "source": data["source_element_id"],
                "target": data["target_element_id"],
                "name": data.get("name"),
            })

        # ignore TypeDeclared etc.

    return bpmn

# ------------------------------------------------------------
# XML helpers
# ------------------------------------------------------------
def esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&apos;")
    )

# ------------------------------------------------------------
# Very simple layout
# ------------------------------------------------------------
def layout_process(proc: BPMNProcess, lanes: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    """
    Return a dict: element_id -> {x, y, w, h}
    We'll place nodes in the order we saw them.
    Lane height = 120.
    """
    positions: Dict[str, Dict[str, int]] = {}
    lane_y: Dict[str, int] = {}
    lane_height = 120

    # give lanes a y position
    ycursor = 80
    for lane_id, lane in lanes.items():
        if lane.get("process_id") == proc.id:
            lane_y[lane_id] = ycursor
            ycursor += lane_height

    # elements in deterministic order
    xcursor = 150
    for eid in proc.elements.keys():
        # default y
        y = 80
        # if assigned to a lane, use that lane's y center
        for (lid, elid) in proc.lane_assignments:
            if elid == eid and lid in lane_y:
                y = lane_y[lid] + 40
                break
        positions[eid] = {"x": xcursor, "y": y, "w": 100, "h": 80}
        xcursor += 180

    return positions

# ------------------------------------------------------------
# Render BPMN XML (with DI)
# ------------------------------------------------------------
def render_bpmn_xml(bpmn: BPMNDefinition) -> str:
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"')
    lines.append('             xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"')
    lines.append('             xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"')
    lines.append('             xmlns:di="http://www.omg.org/spec/DD/20100524/DI"')
    lines.append('             xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"')
    lines.append('             id="Definitions_1" targetNamespace="http://example.com/bpmn">')

    # processes
    for pid, proc in bpmn.processes.items():
        pname = esc(proc.name) if proc.name else pid
        lines.append(f'  <process id="{esc(pid)}" name="{pname}" isExecutable="false">')

        # laneSet
        proc_lanes = [l for l in bpmn.lanes.values() if l.get("process_id") == pid]
        if proc_lanes:
            lines.append('    <laneSet id="LaneSet_1">')
            for lane in proc_lanes:
                lid = esc(lane["id"])
                lname = esc(lane.get("name", lane["id"]))
                flow_nodes = [
                    eid for (lane_id, eid) in proc.lane_assignments
                    if lane_id == lane["id"]
                ]
                lines.append(f'      <lane id="{lid}" name="{lname}">')
                for eid in flow_nodes:
                    lines.append(f'        <flowNodeRef>{esc(eid)}</flowNodeRef>')
                lines.append('      </lane>')
            lines.append('    </laneSet>')

        # flow nodes
        for eid, el in proc.elements.items():
            etype = el["type"]
            ename = el.get("name")
            name_attr = f' name="{esc(ename)}"' if ename else ""
            if etype == "startEvent":
                lines.append(f'    <startEvent id="{esc(eid)}"{name_attr} />')
            elif etype == "endEvent":
                lines.append(f'    <endEvent id="{esc(eid)}"{name_attr} />')
            elif etype == "intermediateCatchEvent":
                lines.append(f'    <intermediateCatchEvent id="{esc(eid)}"{name_attr} />')
            elif etype == "intermediateThrowEvent":
                lines.append(f'    <intermediateThrowEvent id="{esc(eid)}"{name_attr} />')
            elif etype == "task":
                lines.append(f'    <task id="{esc(eid)}"{name_attr} />')
            elif etype == "subProcess":
                lines.append(f'    <subProcess id="{esc(eid)}"{name_attr} />')
            elif etype == "callActivity":
                called = el.get("called_process")
                if called:
                    lines.append(f'    <callActivity id="{esc(eid)}"{name_attr} calledElement="{esc(called)}" />')
                else:
                    lines.append(f'    <callActivity id="{esc(eid)}"{name_attr} />')
            elif etype == "exclusiveGateway":
                default_flow = el.get("default_flow")
                if default_flow:
                    lines.append(f'    <exclusiveGateway id="{esc(eid)}"{name_attr} default="{esc(default_flow)}" />')
                else:
                    lines.append(f'    <exclusiveGateway id="{esc(eid)}"{name_attr} />')
            elif etype == "parallelGateway":
                lines.append(f'    <parallelGateway id="{esc(eid)}"{name_attr} />')
            else:
                lines.append(f'    <task id="{esc(eid)}"{name_attr} />')

        # sequence flows
        for flow in proc.sequence_flows:
            fid = esc(flow["id"])
            src = esc(flow["sourceRef"])
            tgt = esc(flow["targetRef"])
            fname = flow.get("name")
            cond = flow.get("condition")
            name_attr = f' name="{esc(fname)}"' if fname else ""
            if cond:
                lines.append(f'    <sequenceFlow id="{fid}" sourceRef="{src}" targetRef="{tgt}"{name_attr}>')
                lines.append(f'      <conditionExpression xsi:type="tFormalExpression">{esc(cond)}</conditionExpression>')
                lines.append(f'    </sequenceFlow>')
            else:
                lines.append(f'    <sequenceFlow id="{fid}" sourceRef="{src}" targetRef="{tgt}"{name_attr} />')

        lines.append('  </process>')

    # collaboration
    if bpmn.pools or bpmn.message_flows:
        lines.append('  <collaboration id="Collab_1">')
        for pool_id, pool in bpmn.pools.items():
            pname = pool.get("name") or pool_id
            proc_ref = pool.get("process_id")
            if proc_ref:
                lines.append(f'    <participant id="{esc(pool_id)}" name="{esc(pname)}" processRef="{esc(proc_ref)}" />')
            else:
                lines.append(f'    <participant id="{esc(pool_id)}" name="{esc(pname)}" />')
        for mf in bpmn.message_flows:
            mid = esc(mf["id"])
            src = esc(mf["source"])
            tgt = esc(mf["target"])
            mname = mf.get("name")
            name_attr = f' name="{esc(mname)}"' if mname else ""
            lines.append(f'    <messageFlow id="{mid}" sourceRef="{src}" targetRef="{tgt}"{name_attr} />')
        lines.append('  </collaboration>')

    # --------------------------------------------------------
    # BPMN DI (one diagram, one plane for the first process)
    # --------------------------------------------------------
    # pick the first process for diagram
    if bpmn.processes:
        first_pid = list(bpmn.processes.keys())[0]
        proc = bpmn.processes[first_pid]
        positions = layout_process(proc, bpmn.lanes)

        lines.append('  <bpmndi:BPMNDiagram id="BPMNDiagram_1">')
        lines.append(f'    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="{esc(first_pid)}">')

        # shapes
        for eid, el in proc.elements.items():
            pos = positions[eid]
            lines.append(f'      <bpmndi:BPMNShape id="BPMNShape_{esc(eid)}" bpmnElement="{esc(eid)}">')
            lines.append(f'        <dc:Bounds x="{pos["x"]}" y="{pos["y"]}" width="{pos["w"]}" height="{pos["h"]}" />')
            lines.append(f'      </bpmndi:BPMNShape>')

        # edges
        for flow in proc.sequence_flows:
            src_pos = positions[flow["sourceRef"]]
            tgt_pos = positions[flow["targetRef"]]
            lines.append(f'      <bpmndi:BPMNEdge id="BPMNEdge_{esc(flow["id"])}" bpmnElement="{esc(flow["id"])}">')
            lines.append(f'        <di:waypoint x="{src_pos["x"] + src_pos["w"]}" y="{src_pos["y"] + src_pos["h"]//2}" />')
            lines.append(f'        <di:waypoint x="{tgt_pos["x"]}" y="{tgt_pos["y"] + tgt_pos["h"]//2}" />')
            lines.append(f'      </bpmndi:BPMNEdge>')

        lines.append('    </bpmndi:BPMNPlane>')
        lines.append('  </bpmndi:BPMNDiagram>')

    lines.append('</definitions>')
    return "\n".join(lines)

# ------------------------------------------------------------
def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} path/to/file.esml", file=sys.stderr)
        sys.exit(1)
    events = load_esml(sys.argv[1])
    bpmn = replay_events(events)
    xml = render_bpmn_xml(bpmn)
    sys.stdout.write(xml)

if __name__ == "__main__":
    main()
