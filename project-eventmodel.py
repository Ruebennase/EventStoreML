#!/usr/bin/env python3
import argparse
import json
import sys


# -------------------------------------------------------
# ESML reader (JSON objects one after another)
# -------------------------------------------------------
def iter_esml_events(text: str):
    decoder = json.JSONDecoder()
    i = 0
    n = len(text)
    while i < n:
        # skip whitespace
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            break
        obj, j = decoder.raw_decode(text, i)
        yield obj
        i = j


# -------------------------------------------------------
# Projector for modeling.* style ESML
# -------------------------------------------------------
def project_event_model(esml_path: str, debug: bool = False):
    with open(esml_path, "r", encoding="utf-8") as f:
        raw = f.read()

    swimlanes = []          # modeling.TimelineSwimlaneCreated
    event_types = []        # modeling.EventTypeDefined, modeling.EventTypeDefinedSpecial
    commands = []           # modeling.CommandDefined
    views = []              # modeling.ViewDefined
    automations = []        # modeling.AutomationDefined
    examples = []           # modeling.ExampleAddedToEvent
    relationships = []      # modeling.RelationshipAdded
    renames = []            # modeling.ModelElementRenamed
    deprecations = []       # modeling.ElementDeprecated
    other = []              # anything else except TypeDeclared

    for evt in iter_esml_events(raw):
        evt_type = evt.get("type")
        data = evt.get("data", {})

        # ignore the type declarations themselves
        if evt_type == "TypeDeclared" or evt_type.endswith(".TypeDeclared"):
            if debug:
                print(f"[debug] ignoring {evt_type}", file=sys.stderr)
            continue

        # swimlanes
        if evt_type == "modeling.TimelineSwimlaneCreated":
            swimlanes.append(data)
            continue

        # event types
        if evt_type == "modeling.EventTypeDefined" or evt_type == "modeling.EventTypeDefinedSpecial":
            event_types.append((evt_type, data))
            continue

        # commands
        if evt_type == "modeling.CommandDefined":
            commands.append(data)
            continue

        # views
        if evt_type == "modeling.ViewDefined":
            views.append(data)
            continue

        # automations
        if evt_type == "modeling.AutomationDefined":
            automations.append(data)
            continue

        # examples
        if evt_type == "modeling.ExampleAddedToEvent":
            examples.append(data)
            continue

        # relationships
        if evt_type == "modeling.RelationshipAdded":
            relationships.append(data)
            continue

        # renames
        if evt_type == "modeling.ModelElementRenamed":
            renames.append(data)
            continue

        # deprecations
        if evt_type == "modeling.ElementDeprecated":
            deprecations.append(data)
            continue

        # catch-all
        other.append((evt_type, data))

    # ---------------------------
    # print human-readable output
    # ---------------------------
    out = sys.stdout

    print("Event Model (projected from ESML)\n", file=out)

    # Swimlanes
    if swimlanes:
        print("Swimlanes / Timelines:", file=out)
        for s in swimlanes:
            line = f"  - {s.get('name', '(unnamed)')}"
            desc = s.get("description")
            if desc:
                line += f" — {desc}"
            print(line, file=out)
        print(file=out)

    # Event types
    if event_types:
        print("Event Types:", file=out)
        for evt_type, d in event_types:
            name = d.get("name", "(unnamed)")
            desc = d.get("description")
            if desc:
                print(f"  - {name} ({evt_type}): {desc}", file=out)
            else:
                print(f"  - {name} ({evt_type})", file=out)
        print(file=out)

    # Commands
    if commands:
        print("Commands:", file=out)
        for c in commands:
            name = c.get("name", "(unnamed)")
            desc = c.get("description")
            if desc:
                print(f"  - {name}: {desc}", file=out)
            else:
                print(f"  - {name}", file=out)
        print(file=out)

    # Views
    if views:
        print("Views / Read Models:", file=out)
        for v in views:
            name = v.get("name", "(unnamed)")
            desc = v.get("description")
            if desc:
                print(f"  - {name}: {desc}", file=out)
            else:
                print(f"  - {name}", file=out)
        print(file=out)

    # Automations
    if automations:
        print("Automations / Reactions:", file=out)
        for a in automations:
            when = a.get("when", "(when?)")
            then = a.get("then", "(then?)")
            print(f"  - when {when} → {then}", file=out)
        print(file=out)

    # Examples
    if examples:
        print("Examples attached to events:", file=out)
        for ex in examples:
            eid = ex.get("eventId", "(event?)")
            # if you store example payloads, you can show them here
            print(f"  - example for event {eid}", file=out)
        print(file=out)

    # Relationships
    if relationships:
        print("Relationships:", file=out)
        for r in relationships:
            frm = r.get("fromId", "(from?)")
            to = r.get("toId", "(to?)")
            kind = r.get("kind", "(kind?)")
            print(f"  - {frm} --[{kind}]--> {to}", file=out)
        print(file=out)

    # Renames
    if renames:
        print("Renames:", file=out)
        for r in renames:
            el = r.get("elementId", "(element?)")
            oldn = r.get("oldName", "(old?)")
            newn = r.get("newName", "(new?)")
            print(f"  - {el}: {oldn} → {newn}", file=out)
        print(file=out)

    # Deprecations
    if deprecations:
        print("Deprecations:", file=out)
        for d in deprecations:
            el = d.get("elementId", "(element?)")
            reason = d.get("reason")
            if reason:
                print(f"  - {el}: {reason}", file=out)
            else:
                print(f"  - {el}", file=out)
        print(file=out)

    # Other
    if other:
        print("Other / Unclassified events:", file=out)
        for etype, d in other:
            # make it one-line-ish
            short = ", ".join(f"{k}={v}" for k, v in d.items() if not isinstance(v, (dict, list)))
            if short:
                print(f"  - {etype}: {short}", file=out)
            else:
                print(f"  - {etype}", file=out)
        print(file=out)


def main():
    parser = argparse.ArgumentParser(
        description="Project a human-readable event model from an EventStoreML (.esml) modeling file."
    )
    parser.add_argument("esml_file", help="Path to the .esml file")
    parser.add_argument("--debug", action="store_true", help="Show debug info")
    args = parser.parse_args()

    project_event_model(args.esml_file, args.debug)


if __name__ == "__main__":
    main()
