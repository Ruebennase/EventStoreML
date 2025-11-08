#!/usr/bin/env python3

#
# CAREFUL for now truly vibecoded hack. Just a proof of concept.
# CAREFUL for now truly vibecoded hack. Just a proof of concept.
# CAREFUL for now truly vibecoded hack. Just a proof of concept.
# CAREFUL for now truly vibecoded hack. Just a proof of concept.
#

import sys
import json
import bisect
import re
from typing import Any, Dict, List, Tuple, Optional, Set


# ------------ helpers for line/col reporting ------------

def _line_starts(text: str) -> List[int]:
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def _pos_to_linecol(starts: List[int], pos: int) -> Tuple[int, int]:
    line_idx = bisect.bisect_right(starts, pos) - 1
    line_start = starts[line_idx]
    return line_idx + 1, (pos - line_start) + 1


# ------------ type tag parsing ------------

# versions are optional + arbitrary strings now
_TYPE_TAG_RE = re.compile(r"^(?P<name>[^@]+)(?:@(?P<ver>.+))?$")


def parse_type_tag(tag: str) -> Tuple[str, Optional[str]]:
    m = _TYPE_TAG_RE.match(tag)
    if not m:
        raise ValueError(f"invalid type tag: {tag}")
    name = m.group("name")
    ver = m.group("ver")
    return name, ver  # ver can be None


# ------------ error type ------------

class ESMLValidationError(Exception):
    def __init__(self, message: str, line: int, col: int, event_index: int):
        super().__init__(f"line {line}, col {col}, event {event_index}: {message}")
        self.line = line
        self.col = col
        self.event_index = event_index
        self.reason = message


# ------------ main validator ------------

class ESMLValidator:
    """
    ESML validator that:
    - knows built-in TypeDeclared
    - learns further declarers by shape (requires name + schema)
    - validates all later events
    - resolves $ref to declared types
    - supports optional, non-numeric versions
    - can produce a summary that separates:
        * declarer events
        * normal events
        * declared types
    """

    BUILTIN_TYPEDECLARED_SCHEMA: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "name":   {"type": "string"},
            "log":    {"type": "string"},
            "schema": {"type": "object"},
            "version": {"type": "string"},  # optional, non-numeric
        },
        "required": ["name", "schema"],
        "additionalProperties": False,
    }

    def __init__(self, collect_summary: bool = False) -> None:
        # registry[name][version] = schema
        self.registry: Dict[str, Dict[Optional[str], Dict[str, Any]]] = {}
        # types that look like declarers (name, version)
        self.declarator_candidates: Set[Tuple[str, Optional[str]]] = set()

        # summary counters
        self.collect_summary = collect_summary
        self.event_count = 0
        self.declarer_event_count = 0
        self.normal_event_count = 0
        self.declared_types: List[Tuple[str, Optional[str]]] = []
        self.event_type_counts: Dict[Tuple[str, Optional[str]], int] = {}

        # bootstrap
        self.registry.setdefault("TypeDeclared", {})[None] = self.BUILTIN_TYPEDECLARED_SCHEMA
        self.declarator_candidates.add(("TypeDeclared", None))

    # ---------- public API ----------

    def validate_file(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        self.validate_text(text)

    def validate_text(self, text: str) -> None:
        line_starts = _line_starts(text)
        decoder = json.JSONDecoder()
        idx = 0
        n = len(text)
        event_index = 0

        while True:
            # skip whitespace between events
            while idx < n and text[idx].isspace():
                idx += 1
            if idx >= n:
                break

            event_start = idx
            try:
                obj, end = decoder.raw_decode(text, idx)
            except json.JSONDecodeError as e:
                line, col = _pos_to_linecol(line_starts, e.pos)
                raise ESMLValidationError(f"invalid JSON: {e.msg}", line, col, event_index)
            line, col = _pos_to_linecol(line_starts, event_start)

            self._validate_event(obj, event_index, line, col)
            idx = end
            event_index += 1
            self.event_count += 1

    def get_summary(self) -> str:
        lines: List[str] = []
        lines.append(f"Total events: {self.event_count}")
        lines.append(f"Type-declaring events: {self.declarer_event_count}")
        lines.append(f"Normal events: {self.normal_event_count}")
        lines.append(f"Declared types (unique): {len(self.declared_types)}")
        if self.declarator_candidates:
            lines.append("Declarer-capable types:")
            for name, ver in sorted(self.declarator_candidates):
                tname = name if ver is None else f"{name}@{ver}"
                lines.append(f"  - {tname}")
        if self.event_type_counts:
            lines.append("Event counts by type:")
            for (name, ver), cnt in sorted(self.event_type_counts.items()):
                tname = name if ver is None else f"{name}@{ver}"
                lines.append(f"  - {tname}: {cnt}")
        return "\n".join(lines)

    # ---------- internals ----------

    def _inc_event_type(self, name: str, ver: Optional[str]) -> None:
        key = (name, ver)
        self.event_type_counts[key] = self.event_type_counts.get(key, 0) + 1

    def _validate_event(self, obj: Any, event_index: int, line: int, col: int) -> None:
        if not isinstance(obj, dict):
            raise ESMLValidationError("each event must be a JSON object", line, col, event_index)

        if "type" not in obj or "data" not in obj:
            raise ESMLValidationError("event must have 'type' and 'data'", line, col, event_index)

        t = obj["type"]
        if not isinstance(t, str):
            raise ESMLValidationError("'type' must be a string", line, col, event_index)

        name, ver = parse_type_tag(t)
        payload = obj["data"]

        # summary counting
        if self.collect_summary:
            self._inc_event_type(name, ver)

        # declarer-like?
        if (name, ver) in self.declarator_candidates:
            if self.collect_summary:
                self.declarer_event_count += 1
            self._handle_declarer_event(name, ver, payload, line, col, event_index)
            return

        # otherwise must have been declared already
        schema = self.registry.get(name, {}).get(ver)
        if schema is None:
            raise ESMLValidationError(
                f"type {name}" + ("" if ver is None else f"@{ver}") + " used before declaration",
                line,
                col,
                event_index,
            )

        if self.collect_summary:
            self.normal_event_count += 1

        ctx_name = name if ver is None else f"{name}@{ver}"
        self._validate_json(payload, schema, line, col, event_index, ctx=ctx_name)

    def _handle_declarer_event(
        self,
        declarer_name: str,
        declarer_version: Optional[str],
        payload: Any,
        line: int,
        col: int,
        event_index: int,
    ) -> None:
        # get the schema of this declarer
        decl_schema = self.registry.get(declarer_name, {}).get(declarer_version)
        if decl_schema is None:
            raise ESMLValidationError(
                f"unknown declarer {declarer_name}" + ("" if declarer_version is None else f"@{declarer_version}"),
                line,
                col,
                event_index,
            )

        # validate the declarer event itself
        self._validate_json(payload, decl_schema, line, col, event_index, ctx=declarer_name)

        # extract new type info
        dname = payload.get("name")
        dver = payload.get("version", None)  # optional + arbitrary
        dschema = payload.get("schema")

        if not isinstance(dname, str):
            raise ESMLValidationError("declared 'name' must be string", line, col, event_index)
        if dver is not None and not isinstance(dver, str):
            raise ESMLValidationError("declared 'version' must be string when present", line, col, event_index)
        if not isinstance(dschema, dict):
            raise ESMLValidationError("'schema' must be object", line, col, event_index)

        # register
        self.registry.setdefault(dname, {})[dver] = dschema
        if self.collect_summary:
            self.declared_types.append((dname, dver))

        # if the newly declared type itself looks like a declarer, remember that
        if self._schema_looks_like_declarer(dschema):
            self.declarator_candidates.add((dname, dver))

    def _schema_looks_like_declarer(self, schema: Dict[str, Any]) -> bool:
        """
        Heuristic: consider a declared type "declarer-capable" if:
        - type: object
        - has properties
        - requires both 'name' and 'schema'
        """
        if not isinstance(schema, dict):
            return False
        if schema.get("type") != "object":
            return False
        props = schema.get("properties")
        if not isinstance(props, dict):
            return False
        if "name" not in props or "schema" not in props:
            return False
        req = schema.get("required", [])
        if not isinstance(req, list):
            return False
        return "name" in req and "schema" in req

    # ---------- JSON Schema subset with $ref to registry ----------

    def _validate_json(
        self,
        value: Any,
        schema: Dict[str, Any],
        line: int,
        col: int,
        event_index: int,
        ctx: str,
    ) -> None:
        # $ref: "#/$defs/TypeName" or "#/$defs/TypeName@ver"
        if "$ref" in schema:
            ref = schema["$ref"]
            if not (isinstance(ref, str) and ref.startswith("#/$defs/")):
                raise ESMLValidationError(f"{ctx}: unsupported $ref '{ref}'", line, col, event_index)
            tag = ref[len("#/$defs/"):]
            rname, rver = parse_type_tag(tag)
            target = self.registry.get(rname, {}).get(rver)
            if target is None:
                raise ESMLValidationError(f"{ctx}: $ref target {tag} not declared", line, col, event_index)
            self._validate_json(value, target, line, col, event_index, ctx=f"{ctx} -> {tag}")
            return

        t = schema.get("type")
        if t is None:
            return

        if t == "object":
            if not isinstance(value, dict):
                raise ESMLValidationError(f"{ctx}: expected object", line, col, event_index)
            props = schema.get("properties") or {}
            required = schema.get("required") or []

            for req in required:
                if req not in value:
                    raise ESMLValidationError(
                        f"{ctx}: missing required property '{req}'",
                        line,
                        col,
                        event_index,
                    )

            for k, subschema in props.items():
                if k in value:
                    self._validate_json(value[k], subschema, line, col, event_index, ctx=f"{ctx}.{k}")

            ap = schema.get("additionalProperties", True)
            if ap is False:
                for k in value:
                    if k not in props:
                        raise ESMLValidationError(
                            f"{ctx}: additional property '{k}' not allowed",
                            line,
                            col,
                            event_index,
                        )

        elif t == "array":
            if not isinstance(value, list):
                raise ESMLValidationError(f"{ctx}: expected array", line, col, event_index)
            items = schema.get("items")
            if isinstance(items, dict):
                for i, it in enumerate(value):
                    self._validate_json(it, items, line, col, event_index, ctx=f"{ctx}[{i}]")

        elif t == "string":
            if not isinstance(value, str):
                raise ESMLValidationError(f"{ctx}: expected string", line, col, event_index)

        elif t == "integer":
            if not (isinstance(value, int) and not isinstance(value, bool)):
                raise ESMLValidationError(f"{ctx}: expected integer", line, col, event_index)

        elif t == "number":
            if not (isinstance(value, (int, float)) and not isinstance(value, bool)):
                raise ESMLValidationError(f"{ctx}: expected number", line, col, event_index)

        elif t == "boolean":
            if not isinstance(value, bool):
                raise ESMLValidationError(f"{ctx}: expected boolean", line, col, event_index)

        else:
            raise ESMLValidationError(f"{ctx}: unsupported type '{t}'", line, col, event_index)


# ------------ CLI ------------

def main() -> None:
    if len(sys.argv) < 2:
        print("EventStoreML — ESML validator")
        print("Usage: python eventstoreml.py [--summary] <file.esml>")
        sys.exit(1)

    args = sys.argv[1:]
    collect_summary = False
    if args[0] == "--summary":
        collect_summary = True
        args = args[1:]

    if not args:
        print("Usage: python eventstoreml.py [--summary] <file.esml>")
        sys.exit(1)

    path = args[0]
    validator = ESMLValidator(collect_summary=collect_summary)
    try:
        validator.validate_file(path)
    except ESMLValidationError as e:
        print(f"ERROR: {e}")
        sys.exit(2)

    print("OK")
    if collect_summary:
        print()
        print(validator.get_summary())


if __name__ == "__main__":
    main()
