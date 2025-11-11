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


# ------------- helpers for line/col reporting -------------


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


# ------------- type tag parsing (name@version) -------------


_TYPE_TAG_RE = re.compile(r"^(?P<name>[^@]+)(?:@(?P<ver>.+))?$")


def parse_type_tag(tag: str) -> Tuple[str, Optional[str]]:
    m = _TYPE_TAG_RE.match(tag)
    if not m:
        raise ValueError(f"invalid type tag: {tag}")
    return m.group("name"), m.group("ver")


# ------------- error type -------------


class ESMLValidationError(Exception):
    def __init__(self, message: str, line: int, col: int, event_index: int):
        super().__init__(f"line {line}, col {col}, event {event_index}: {message}")
        self.line = line
        self.col = col
        self.event_index = event_index
        self.reason = message


# ------------- main validator -------------


class ESMLValidator:
    """
    EventStoreML validator.

    Key points:
    - built-in TypeDeclared is hard-coded
    - first file-declared TypeDeclared must match built-in (log ignored)
    - later undeclared TypeDeclared (no @) is forbidden
    - other types may be redeclared: last one wins
    - versions are taken ONLY from name via "name@something"
    """

    BUILTIN_TYPEDECLARED_SCHEMA: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "log": {"type": "string"},
            "schema": {"type": "object"},
        },
        "required": ["name", "schema"],
        "additionalProperties": False,
    }

    def __init__(self, collect_summary: bool = False) -> None:
        # registry[name][version] = schema
        self.registry: Dict[str, Dict[Optional[str], Dict[str, Any]]] = {}
        # declarers we know about (name, ver)
        self.declarator_candidates: Set[Tuple[str, Optional[str]]] = set()

        # summary
        self.collect_summary = collect_summary
        self.event_count = 0
        self.declarer_event_count = 0
        self.normal_event_count = 0
        self.declared_types: List[Tuple[str, Optional[str]]] = []
        self.event_type_counts: Dict[Tuple[str, Optional[str]], int] = {}

        # bootstrap: hard-code TypeDeclared@None
        self.registry.setdefault("TypeDeclared", {})[None] = self.BUILTIN_TYPEDECLARED_SCHEMA
        self.declarator_candidates.add(("TypeDeclared", None))

    # -------- public API --------

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

        while idx < n:
            # skip whitespace/newlines between JSON objects
            while idx < n and text[idx].isspace():
                idx += 1
            if idx >= n:
                break

            obj, end = decoder.raw_decode(text, idx)
            line, col = _pos_to_linecol(line_starts, idx)

            self._validate_event(obj, event_index, line, col)

            idx = end
            event_index += 1
            self.event_count += 1

    def get_summary(self) -> str:
        # build type sets
        # self.declared_types is collected only when collect_summary=True
        # it's a list of (name, version) tuples, so make it unique
        all_types = set(self.declared_types)
        declarer_types = set(self.declarator_candidates)
        non_declarer_types = all_types - declarer_types

        lines: List[str] = []

        # 1) events
        lines.append(f"Total events: {self.event_count}")
        lines.append(f"  Type-declaring events: {self.declarer_event_count}")
        lines.append(f"  Non-type-declaring events: {self.normal_event_count}")
        lines.append("")

        # 2) types
        lines.append(f"Total types (unique): {len(all_types)}")
        lines.append(f"  Type-declaring-capable types (unique): {len(declarer_types)}")
        lines.append(f"  Non-type-declaring-capable types (unique): {len(non_declarer_types)}")
        lines.append("")

        # 3) list of type-declaring-capable types
        lines.append("Type-declaring-capable types:")
        for name, ver in sorted(declarer_types):
            tname = name if ver is None else f"{name}@{ver}"
            lines.append(f"  - {tname}")
        lines.append("")

        # 4) list of non-type-declaring-capable types
        lines.append("Non-type-declaring-capable types:")
        for name, ver in sorted(non_declarer_types):
            tname = name if ver is None else f"{name}@{ver}"
            lines.append(f"  - {tname}")
        lines.append("")

        # 5) event counts by event type
        lines.append("Event counts by type:")
        for (name, ver), cnt in sorted(self.event_type_counts.items()):
            tname = name if ver is None else f"{name}@{ver}"
            lines.append(f"  - {tname}: {cnt}")

        return "\n".join(lines)


    # -------- internals --------

    def _inc_event_type(self, name: str, ver: Optional[str]) -> None:
        key = (name, ver)
        self.event_type_counts[key] = self.event_type_counts.get(key, 0) + 1

    def _validate_event(self, obj: Any, event_index: int, line: int, col: int) -> None:
        if not isinstance(obj, dict):
            raise ESMLValidationError("event must be an object", line, col, event_index)
        if "type" not in obj:
            raise ESMLValidationError("event missing 'type'", line, col, event_index)
        if "data" not in obj:
            raise ESMLValidationError("event missing 'data'", line, col, event_index)

        t = obj["type"]
        if not isinstance(t, str):
            raise ESMLValidationError("'type' must be a string", line, col, event_index)

        name, ver = parse_type_tag(t)
        payload = obj["data"]

        if self.collect_summary:
            self._inc_event_type(name, ver)

        # is this a declarer event?
        if (name, ver) in self.declarator_candidates:
            if self.collect_summary:
                self.declarer_event_count += 1
            self._handle_declarer_event(name, ver, payload, line, col, event_index)
            return

        # normal event: we must have already declared this type
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

        self._validate_json(payload, schema, line, col, event_index, ctx=name)

    def _same_typedeclared_schema(self, file_schema: Dict[str, Any]) -> bool:
        """
        Compare file's TypeDeclared to our built-in one, ignoring language-dependent 'log'.
        """
        builtin = self.BUILTIN_TYPEDECLARED_SCHEMA

        def normalize(s: Dict[str, Any]) -> Dict[str, Any]:
            s = dict(s)
            props = dict(s.get("properties", {}))
            if "log" in props:
                props.pop("log")
            s["properties"] = props
            return s

        return normalize(file_schema) == normalize(builtin)

    def _handle_declarer_event(
        self,
        declarer_name: str,
        declarer_ver: Optional[str],
        payload: Dict[str, Any],
        line: int,
        col: int,
        event_index: int,
    ) -> None:
        # find the declarer schema
        decl_schema = self.registry.get(declarer_name, {}).get(declarer_ver)
        if decl_schema is None:
            raise ESMLValidationError(
                f"declarer {declarer_name}" + ("" if declarer_ver is None else f"@{declarer_ver}") + " not registered",
                line,
                col,
                event_index,
            )

        # validate declarer event itself
        self._validate_json(payload, decl_schema, line, col, event_index, ctx=declarer_name)

        raw_name = payload.get("name")
        dschema = payload.get("schema")

        if not isinstance(raw_name, str):
            raise ESMLValidationError("declared 'name' must be string", line, col, event_index)
        if not isinstance(dschema, dict):
            raise ESMLValidationError("'schema' must be object", line, col, event_index)

        # split declared name into base + optional @version
        dname, dver = parse_type_tag(raw_name)

        # --- special case: TypeDeclared (no version) may only appear once and must match ---
        if dname == "TypeDeclared" and dver is None:
            # have we already seen a file-declared TypeDeclared?
            if ("TypeDeclared", None) in self.declared_types:
                raise ESMLValidationError(
                    "TypeDeclared may only be declared once (the self-declaration)",
                    line,
                    col,
                    event_index,
                )
            # and it must match builtin (except for 'log')
            if not self._same_typedeclared_schema(dschema):
                raise ESMLValidationError(
                    "file attempts to redefine TypeDeclared with a different shape",
                    line,
                    col,
                    event_index,
                )

        # register (for all other types, last one wins)
        self.registry.setdefault(dname, {})[dver] = dschema

        if self.collect_summary:
            self.declared_types.append((dname, dver))

        # if the newly declared type itself looks like a declarer, remember it
        if self._schema_looks_like_declarer(dschema):
            self.declarator_candidates.add((dname, dver))

    def _schema_looks_like_declarer(self, schema: Dict[str, Any]) -> bool:
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

    # -------- JSON validation (small subset + $ref) --------

    def _validate_json(
        self,
        value: Any,
        schema: Dict[str, Any],
        line: int,
        col: int,
        event_index: int,
        ctx: str,
    ) -> None:
        # $ref to previously declared type
        if "$ref" in schema:
            ref = schema["$ref"]
            if not (isinstance(ref, str) and ref.startswith("#/$defs/")):
                raise ESMLValidationError(f"{ctx}: unsupported $ref '{ref}'", line, col, event_index)
            tag = ref[len("#/$defs/"):]
            rname, rver = parse_type_tag(tag)
            target = self.registry.get(rname, {}).get(rver)
            if target is None:
                raise ESMLValidationError(f"{ctx}: $ref '{ref}' not found", line, col, event_index)
            self._validate_json(value, target, line, col, event_index, ctx=ctx)
            return

        t = schema.get("type")

        if t == "object":
            if not isinstance(value, dict):
                raise ESMLValidationError(f"{ctx}: expected object", line, col, event_index)

            props = schema.get("properties") or {}
            required = schema.get("required") or []

            # required props
            for req in required:
                if req not in value:
                    raise ESMLValidationError(
                        f"{ctx}: missing required property '{req}'",
                        line,
                        col,
                        event_index,
                    )

            # validate present props
            for k, subschema in props.items():
                if k in value:
                    self._validate_json(value[k], subschema, line, col, event_index, ctx=f"{ctx}.{k}")

            # additionalProperties
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
            elif isinstance(ap, dict):
                # schema for additional props
                for k in value:
                    if k not in props:
                        self._validate_json(value[k], ap, line, col, event_index, ctx=f"{ctx}.{k}")

        elif t == "array":
            if not isinstance(value, list):
                raise ESMLValidationError(f"{ctx}: expected array", line, col, event_index)
            item_schema = schema.get("items")
            if item_schema is not None:
                for i, item in enumerate(value):
                    self._validate_json(item, item_schema, line, col, event_index, ctx=f"{ctx}[{i}]")

        elif t == "string":
            if not isinstance(value, str):
                raise ESMLValidationError(f"{ctx}: expected string", line, col, event_index)

        elif t == "integer":
            # make sure bools don't pass
            if not (isinstance(value, int) and not isinstance(value, bool)):
                raise ESMLValidationError(f"{ctx}: expected integer", line, col, event_index)

        elif t == "number":
            if not (isinstance(value, int) or isinstance(value, float)) or isinstance(value, bool):
                raise ESMLValidationError(f"{ctx}: expected number", line, col, event_index)

        elif t == "boolean":
            if not isinstance(value, bool):
                raise ESMLValidationError(f"{ctx}: expected boolean", line, col, event_index)

        elif t is None:
            # no type specified: accept anything
            return

        else:
            raise ESMLValidationError(f"{ctx}: unsupported type '{t}'", line, col, event_index)


# ------------- CLI -------------


def export_jsonl(path: str) -> None:
    """Read ESML and emit each JSON object as a single line to stdout."""
    import json, sys
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    decoder = json.JSONDecoder()
    idx = 0
    n = len(text)
    while idx < n:
        while idx < n and text[idx].isspace():
            idx += 1
        if idx >= n:
            break
        obj, end = decoder.raw_decode(text, idx)
        sys.stdout.write(json.dumps(obj, separators=(',', ':')) + '\n')
        idx = end

def main() -> None:
    if len(sys.argv) < 2:
        print("EventStoreML — ESML validator")
        print("Usage: python eventstoreml.py [--summary|--jsonl] <file.esml>")
        sys.exit(1)

    args = sys.argv[1:]
    collect_summary = False
    export_jsonl_flag = False
    if args and args[0] in ('--summary', '--jsonl'):
        if args[0] == '--summary':
            collect_summary = True
        else:
            export_jsonl_flag = True
        args = args[1:]

    if not args:
        print("missing file")
        sys.exit(1)

    path = args[0]

    if export_jsonl_flag:
        export_jsonl(path)
        return
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