#!/usr/bin/env python3
import argparse
import json
import sys

try:
    import yaml  # PyYAML
except ImportError:
    yaml = None


def iter_esml_events(text: str):
    """
    Yield JSON objects from an ESML file where the format is:
      { ... } <whitespace> { ... } ...
    Objects may be pretty-printed or single-line.
    """
    decoder = json.JSONDecoder()
    i = 0
    n = len(text)
    while i < n:
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            break
        obj, j = decoder.raw_decode(text, i)
        yield obj
        i = j


def ensure_components(doc):
    if "components" not in doc or not isinstance(doc["components"], dict):
        doc["components"] = {}
    comps = doc["components"]
    comps.setdefault("schemas", {})
    comps.setdefault("parameters", {})
    comps.setdefault("responses", {})
    comps.setdefault("requestBodies", {})
    comps.setdefault("securitySchemes", {})
    return comps


def get_spec_id_from_event(data: dict):
    # allow for naming drift
    return data.get("spec_id") or data.get("id")


def project_openapi(esml_path: str, target_spec_id: str = None, debug: bool = False):
    with open(esml_path, "r", encoding="utf-8") as f:
        raw = f.read()

    doc = {
        "openapi": "3.1.0",
        "info": {
            "title": "API",
            "version": "1.0.0"
        },
        "paths": {}
    }
    servers = []
    doc["servers"] = servers

    for event in iter_esml_events(raw):
        evt_type = event.get("type")
        data = event.get("data", {})

        event_spec_id = get_spec_id_from_event(data)
        if target_spec_id is not None and event_spec_id is not None and event_spec_id != target_spec_id:
            continue

        # 1. root
        if evt_type == "openapi.ApiSpecificationDeclared":
            if "openapi_version" in data:
                doc["openapi"] = data["openapi_version"]
            info = doc.setdefault("info", {})
            if "title" in data:
                info["title"] = data["title"]
            if "version" in data:
                info["version"] = data["version"]
            if "description" in data:
                info["description"] = data["description"]
            continue

        # 2. servers
        if evt_type == "openapi.ServerAdded":
            server = {"url": data["url"]}
            if "description" in data:
                server["description"] = data["description"]
            servers.append(server)
            continue

        # 3. schemas
        if evt_type == "openapi.SchemaDeclared":
            comps = ensure_components(doc)
            schema_name = data.get("schema_name") or data.get("name")
            schema_def = data.get("schema")
            if not schema_name or schema_def is None:
                if debug:
                    print(f"[debug] openapi.SchemaDeclared missing schema name or schema: {data}", file=sys.stderr)
                continue
            comps["schemas"][schema_name] = schema_def
            continue

        # 4. paths
        if evt_type == "openapi.PathAdded":
            path_obj = doc["paths"].setdefault(data["path"], {})
            if "summary" in data:
                path_obj["summary"] = data["summary"]
            if "description" in data:
                path_obj["description"] = data["description"]
            continue

        # 5. operations
        if evt_type == "openapi.OperationAdded":
            path = data["path"]
            method = data["method"].lower()
            path_obj = doc["paths"].setdefault(path, {})
            op_obj = path_obj.setdefault(method, {})
            op_obj["operationId"] = data["operation_id"]
            if "summary" in data:
                op_obj["summary"] = data["summary"]
            if "description" in data:
                op_obj["description"] = data["description"]
            if "tags" in data:
                op_obj["tags"] = data["tags"]
            continue

        # 6. parameters
        if evt_type == "openapi.OperationParameterAdded":
            path = data["path"]
            method = data["method"].lower()
            op_obj = doc["paths"].setdefault(path, {}).setdefault(method, {})
            params = op_obj.setdefault("parameters", [])

            param_obj = {
                "name": data["name"],
                "in": data["in"]
            }
            if "required" in data:
                param_obj["required"] = data["required"]
            if "description" in data:
                param_obj["description"] = data["description"]
            if data.get("schema"):
                param_obj["schema"] = data["schema"]
            elif data.get("ref"):
                param_obj["$ref"] = data["ref"]

            params.append(param_obj)
            continue

        # 7. requestBody
        if evt_type == "openapi.OperationRequestSet":
            path = data["path"]
            method = data["method"].lower()
            op_obj = doc["paths"].setdefault(path, {}).setdefault(method, {})
            op_obj["requestBody"] = data["request_body"]
            continue

        # 8. responses
        if evt_type == "openapi.OperationResponseAdded":
            path = data["path"]
            method = data["method"].lower()
            status = data["status_code"]
            op_obj = doc["paths"].setdefault(path, {}).setdefault(method, {})
            responses = op_obj.setdefault("responses", {})
            resp_obj = {"description": data["description"]}
            if data.get("content"):
                resp_obj["content"] = data["content"]
            responses[status] = resp_obj
            continue

        # 9. deprecation
        if evt_type == "openapi.OperationDeprecatedSet":
            path = data["path"]
            method = data["method"].lower()
            op_obj = doc["paths"].setdefault(path, {}).setdefault(method, {})
            op_obj["deprecated"] = bool(data.get("deprecated", True))
            continue

        # unknown
        if debug:
            print(f"[debug] ignoring event type: {evt_type} data={data}", file=sys.stderr)

    if not servers:
        doc.pop("servers", None)

    return doc


def main():
    parser = argparse.ArgumentParser(
        description="Project an OpenAPI document from an ESML file (YAML by default)."
    )
    parser.add_argument("esml_file", help="Path to the .esml file")
    parser.add_argument(
        "--spec-id",
        help="If the ESML contains multiple specs, project only this spec_id.",
        default=None,
    )
    parser.add_argument(
        "--debug",
        help="Print info about ignored/unknown events to stderr.",
        action="store_true",
    )
    parser.add_argument(
        "--json",
        help="Output JSON instead of YAML.",
        action="store_true",
    )
    args = parser.parse_args()

    doc = project_openapi(args.esml_file, args.spec_id, args.debug)

    if args.json:
        json.dump(doc, sys.stdout, indent=2)
        print()
    else:
        if yaml is None:
            # fallback to JSON if PyYAML isn't installed
            print("# yaml not available, falling back to JSON", file=sys.stderr)
            json.dump(doc, sys.stdout, indent=2)
            print()
        else:
            # default YAML output, nice and readable
            yaml.safe_dump(doc, sys.stdout, sort_keys=False)


if __name__ == "__main__":
    main()

