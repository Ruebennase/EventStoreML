#!/usr/bin/env python3
import argparse
import json
import sys


def iter_esml_events(text: str):
    """
    Yield JSON objects from an ESML file where the format is:
    <json-object><whitespace><json-object><whitespace>...
    Objects may be pretty-printed or single-line.
    """
    decoder = json.JSONDecoder()
    i = 0
    n = len(text)

    while i < n:
        # skip whitespace between objects
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            break

        obj, j = decoder.raw_decode(text, i)
        yield obj
        i = j  # move past this object


def project_properties(esml_path: str, target_config_id: str = None):
    """
    Replays ESML config events and returns two dicts:
    - props: key -> string value
    - comments: key -> string comment (optional)
    """
    with open(esml_path, "r", encoding="utf-8") as f:
        raw = f.read()

    props = {}
    comments = {}

    for event in iter_esml_events(raw):
        evt_type = event.get("type")
        data = event.get("data", {})

        cfg_id = data.get("config_id")
        if target_config_id is not None and cfg_id is not None and cfg_id != target_config_id:
            # event is for a different config
            continue

        if evt_type == "config.PropertySet":
            key = data["key"]
            value = data["value"]
            comment = data.get("comment")

            # stringify non-strings so we don't lose info
            if isinstance(value, str):
                props[key] = value
            else:
                props[key] = json.dumps(value, ensure_ascii=False)

            if comment:
                comments[key] = comment
            else:
                # if we set a value without comment, we can choose to drop old comment
                comments.pop(key, None)

        elif evt_type == "config.PropertyRemoved":
            key = data["key"]
            props.pop(key, None)
            comments.pop(key, None)

        elif evt_type == "config.PropertyRenamed":
            old_key = data["old_key"]
            new_key = data["new_key"]
            if old_key in props:
                props[new_key] = props.pop(old_key)
            if old_key in comments:
                comments[new_key] = comments.pop(old_key)

        # ignore: TypeDeclared, PropertiesFileDeclared, NamespaceDeclared, etc.

    return props, comments


def main():
    parser = argparse.ArgumentParser(
        description="Project latest properties from an ESML file and print as key=value (with comments)."
    )
    parser.add_argument("esml_file", help="Path to the .esml file")
    parser.add_argument(
        "--config-id",
        help="Only project events for this config_id (optional).",
    )
    args = parser.parse_args()

    props, comments = project_properties(args.esml_file, args.config_id)

    # Print sorted for deterministic output
    for key in sorted(props):
        if key in comments:
            # comments in .properties usually start with '#'
            print(f"# {comments[key]}")
        print(f"{key}={props[key]}")


if __name__ == "__main__":
    main()
