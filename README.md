# EventStoreML

**EventStoreML** — a lightweight markup language for event-sourced models and documents.

EventStoreML (pronounced *eventstormel*) is a minimal, self-hosting markup language where **every top-level element is an event — even schema definitions themselves**.  

Every `.esml` file is an **append-only event store that defines its own meanings over time through events**.  

Its core consists of exactly one must-understand event type, `TypeDeclared`, expressed in JSON Schema. All other types, schemas, and instances are declared, validated, and evolved through events.

Underlying idea: Event sourcing has proven powerful — so why not explore using event store files in places where we usually rely on static state snapshots (like config files or model markup files)?

Fancy a complication of the complication? Try chatting with [The EventStoreMLer](https://chatgpt.com/g/g-69123cbb21448191940f86454b5632cc-the-eventstoremler) - just don't trust it too much.

---

## Status: Very Experimental

> EventStoreML is an active exploration. Feedback, discussion, and experiments are welcome. The concepts and syntax may change as we evaluate practical viability.

> EventStoreML is not optimized for performance but for ultimate flexibility and versatility.

---

## Why EventStoreML

EventStoreML is based on the event sourcing idea that a system’s state is often better derived from a complete, ordered log of all events that have occurred, rather than storing only the latest state. Instead of storing objects and their mutable state, we capture both **facts** and their **schemas** as events in a **single file**.

This has several advantages:

* **Self-describing data** - every event store explains itself including its potential schema evolution, without any external schema files  
* **Historical integrity** - schemas evolve through type declaration events, preserving lineage  
* **Bootstrap simplicity** - the entire system can be described, starting from one built-in type  
* **Composable and reusable** - event types, structures, and meta information can be shared and referenced across projects  
* **Schema-first thinking** - everything is defined through explicit schemas, not implicit code models

---

## Core Principles

* **Bootstrap simplicity** - the language defines itself through a single event type and thus type: `TypeDeclared`
* **Schema-first, no state** - all information is expressed as events, never as object state
* **JSON Schema subset** - uses a safe, minimal subset (type, properties, required, items, $defs, internal $ref)
* **Namespaces**
  * All types without namespaces (no `.` in type name) are core, reserved, and must-understand types for parsers  
  * `meta.*` - is suggested for optional meta or governance event types  
  * others - user or domain namespaces; standard namespaces might emerge
* **Versions** - types can optionally be given a version tag by appending an @version identifier to the name, e.g @2 or @new
* **Declare-before-use** - a type can only be used after its type declaration event in the file itself
* **Type redeclaration allowed** - All types except TypeDeclared may be re-declared. Better is to version them of course.

---

## Core Event Type: `TypeDeclared`

`TypeDeclared` is the single built-in event type that bootstraps everything else. Instances of this event type declare new types and their schemas. Such new types can then be used in schema definitions or as event type of new event instances. An event type can also be a new type-declaring event type...

### Payload schema (subset of JSON Schema)

```json
{
  "name": "string",
  "log": "string",
  "schema": {
    "type": "object",
    "properties": { "...": "..." },
    "required": ["..."],
    "additionalProperties": true,
    "items": { "...": "..." },
    "$defs": { "...": "..." },
    "$ref": "#/$defs/..."
  }
}
```

### File Format and Syntax

An EventStoreML (`.esml`) file is a **time-ordered sequence of JSON objects**, each object representing one event in the store. The order of events is significant.

Unlike a standard JSON document, these objects are written in sequence, without separating commas or enclosing brackets — allowing the file to be **append-only**. Whitespace between these objects is ignored for the parsing of each event (NDJSON and JSONL are fine, just stricter) but may be significant for any operations processing the file (e.g. secure hash calculations or indexes pointing to events in the file). Again, each file is append-only and any change within leads to unspecified behaviour. 

Example:

```json
{"type": "TypeDeclared", "data": {...TypeDeclared...}}
{"type": "TypeDeclared", "data": {...some.namespace.EventName...}}
{"type": "some.namespace.EventName", "data": {...}}
```

The typical file structure might look as follows:

- **Self-definition of `TypeDeclared`**  
  Invariably, the file begins by bootstrapping its own basic type system through a `TypeDeclared` self-declaration. This must be idempotent with what any parser knows as hard-coded declaration and it thus originates how all later types and events are described within the file itself.

- **Optional definition of special type-declaring event types**  
  Using `TypeDeclared` new type definitions may define special new ways for how to declare other new types, such as `custom.EventTypeDeclared` for declaring event-specific types.

- **Definition of application-specific event types**  
  Using the one of the above above (for example `custom.EventTypeDeclared`), a number of application-specific event types are declared — these represent the possible event types that can appear later in the file.

- **Optional hashing/signing/locking of the specification**  
  Up to this point, the file defines everything a tool needs in order to understand the structure of the file: what types exist, what event types exist, and how event instances should be read or written. To fix a specific version or ensure integrity up to this point in time, the specification might be hashed, signed, or otherwise “locked.” This action itself might be represented as an event — a meta-event — indicating that the schema is sealed or verified.

- **Recording of actual application-level events**  
  After the schema definitions (and optional locking), the file proceeds with application-level event entries. Each event is appended in order and conforms to one of the declared event types, representing occurrences in the system over time.

- **Optional schema evolution and extended tooling**  
  If the tooling evolves and new event types or type versions become available, additional type declarations can appear later in the file. Tools should therefore handle schema-type events dynamically, supporting extensions and type changes within the event stream itself to some degree.

Another example is [eventsourced-eventmodel-library.esml](./eventsourced-eventmodel-library.esml). In this we define first the - **admittedly not so sensible** - types of events that can happen during any event modeling session, then apply these event types in event instances that mimic what happens then during an event modeling session for modeling use cases occuring in a library. Unlike the versioning of complete modified event model files representing the state after each modeling session such an approach would allow to track what has actually changed in the model and possibly the intentions behind changes apart from timings, etc. The sample [project-eventmodel.py](./project-eventmodel.py) then projects the latest event model summary to stdout (not an eventmodel in a DSL yet).

Another example is [eventsourced-openapi-todolist.esml](./eventsourced-openapi-todolist.esml). In this we define first the - **admittedly ad-hoc chosen** - types of events that can happen during any OpenAPI designing and re-designing session, then apply these event types in event instances that mimic what happens then during an OpenAPI specification session for modeling a todo list use case. Unlike the versioning of complete modified OpenAPI yaml or json files representing the state after each (re-)specification session such an approach would allow to track what has actually changed in the API and possibly the intentions behind changes apart from timings, etc. The sample [project-openapi.py](./project-openapi.py) then projects the latest yaml-formatted OpenAPI spec to stdout.

Another example is [eventsourced-properties-config.esml](./eventsourced-properties-config.esml). In this we define first the - **admittedly ad-hoc chosen** - types of events that can happen during any properties configuration and re-configuration session, then apply these event types in event instances that mimic what happens then during a configuration session for some application config. Unlike the versioning of complete modified properties files representing the state after each (re-)configuration session such an approach would allow to track what has actually changed in the configuration and possibly the intentions behind changes apart from timings, etc. The sample [project-properties.py](./project-properties.py) then projects the latest properties config file to stdout.

Another example is [eventsourced-bpmn-sample.esml](./eventsourced-bpmn-sample.esml). In this we define first the - **admittedly ad-hoc chosen** - types of events that can happen during any BPMN modeling session, then apply these event types in event instances that mimic what happens then during a BPMN modeling session for modeling a sample use case of invoice processing. Unlike the versioning of complete modified BPMN XML files representing the state after each modeling session such an approach would allow to track what has actually changed in the model and possibly the intentions behind changes apart from timings, etc. The sample [project-bpmn.py](./project-bpmn.py) then projects the latest BPMN model as BPMN2.0 XML to stdout (as this projector doesn't do automagic diagram layouting it looks a bit crappy in e.g. the free bpmn.io tool).

Another example is [eventsourced-c4model-ebanking.esml](./eventsourced-c4model-ebanking.esml). In this we define first the - **admittedly ad-hoc chosen** - types of events that can happen during any C4 modeling session, then apply these event types in event instances that mimic what happens then during a C4 modeling session for modeling a sample case of an e-banking system. Unlike the versioning of complete modified C4 DSL files representing the state after each modeling session such an approach would allow to track what has actually changed in the model and possibly the intentions behind changes apart from timings, etc. The sample [project-c4model.py](./project-c4model.py) then projects the latest C4 model in the Structurizr DSL to stdout (you can paste the result into the https://structurizr.com/dsl tool). In this example the projector allows you to list releases and project releases. E.g. v1.4 has a mobile app access that is deprecated later on. Releases are here simply based on some C4-independent event type "meta.ReleaseMarked".

Another example is [eventsourced-plm-sample.esml](./eventsourced-plm-sample.esml). In this we define first the - **admittedly ad-hoc chosen** - types of events that can happen during any PLM modeling session, then apply these event types in event instances that mimic what happens then during a PLM modeling session for modeling a sample case of an aircraft. This is not based on any existing PLM modeling language/notation/standard. Such an approach would allow to track what has actually changed in the model and possibly the intentions behind changes apart from timings, etc. This can go down to details such as after-delivery configuration changes of an aircraft close to a digital twin representation. Acknowledging that computers can only hold descriptions of virtual or real-world objects the modeling approach is based on prototypes of *configurations* not classes and instances (compare Smalltalk vs Self). The sample [project-plm-graphml.py](./project-plm-graphml.py) then projects the latest PLM model into a .graphml file that can be opened with the wonderful yEd diagramming desktop tool from yworks.com. The sample output is given here as [eventsourced-plm-sample.graphml](./eventsourced-plm-sample.graphml), showing the configuration specialisations as well as the part-of relationships.

---

## Example `.esml` File

```json
{"type": "TypeDeclared",
 "data": {
  "name": "TypeDeclared",
  "log": "TypeDeclared declared itself.",
  "schema": {
    "type": "object",
    "properties": {
      "name":    { "type": "string" },
      "log":     { "type": "string"},
      "schema":  { "type": "object" }
    },
    "required": ["name", "schema"],
    "additionalProperties": false
  }
}}

{"type": "TypeDeclared",
 "data": {
  "name": "common.struct.Address",
  "log": "The common.struct.Address structure type was declared.",
  "schema": {
    "type": "object",
    "properties": {
      "street": { "type": "string" },
      "city":   { "type": "string" },
      "zip":    { "type": "string" }
    },
    "required": ["street", "city", "zip"],
    "additionalProperties": false
  }
}}

{"type": "TypeDeclared",
 "data": {
  "name": "event.CustomerRegistered",
  "log": "The event.CustomerRegistered event type was declared.",
  "schema": {
    "type": "object",
    "properties": {
      "customer_id": { "type": "string" },
      "name":        { "type": "string" },
      "address":     { "$ref": "#/$defs/common.struct.Address" }
    },
    "required": ["customer_id", "name", "address"],
    "additionalProperties": false
  }
}}

{"type": "event.CustomerRegistered",
 "data": {
  "customer_id": "0123456789",
  "name": "Pxxle",
  "address": {
    "street": "Bahnhofstrasse 1",
    "city": "Zürich",
    "zip": "8001"
  }
}}
```

---

## Other Type-Declaring Types

EventStoreML has one built-in event type for declaring a type: `TypeDeclared`. An event of `TypeDeclared` must have at least:
  - `name`: the name of the type to introduce
  - `schema`: JSON Schema (subset) for that type

When such an event appears, the parser adds that type to its registry.

If `TypeDeclared` is deemed insufficient for your desired approach it can be used to declare another type-declaring event type.

If you declare a new type whose schema itself requires both `name` and `schema`, the parser treats that type as a declarer too when an event of that type later appears.
- That way, a declarer can declare another declarer, and so on - while a general parser can still validate the entire file.
- Types that don’t require both `name` and `schema` are just normal data types. Types with both but not used as event types are just normal data types, too.

```json
{"type": "TypeDeclared",
 "data": {
  "name": "custom.EventTypeDeclared",
  "log": "Type custom.EventTypeDeclared was declared. It is for declaring event types and requires a timestamp for each type declaration.",
  "schema": {
    "type": "object",
    "properties": {
      "name":      { "type": "string" },
      "log":       { "type": "string"},
      "schema":    { "type": "object" },
      "timestamp": { "type": "string"}
    },
    "required": ["name", "schema", "timestamp"],
    "additionalProperties": false
  }
}}
```

Future event type declarations can then use `custom.EventTypeDeclared` as well. Of course, the file processing tool needs to understand this.

---

## Use Cases

It is a bit early to say if and where this goes but currently the expectations are as follows.

### When to Use
- You want a **self-contained, human-readable event store** that includes both schema and data.
- You’re building **tools, prototypes, or CLIs** that don’t need a full event-store database yet benefit from event-sourcing.
- You care about **schema evolution and replayability**, seeing *how* a model or config changed over time.

### When Not to Use
- You need **concurrency, streaming, or high-volume writes** (use a real event store).
- You prefer **established tooling or interoperability** (use JSON Schema, Avro, Protobuf, etc.).
- You only care about **current state**, not event history.
- You need **binary efficiency or performance-critical storage**.

---

## Validating .esml files

An EventStoreML file can be parsed and validated with the provided eventstoreml.py tool as follows:

```bash
python eventstoreml.py mymodel.esml
```

Alternatively it can provide a summary with the types defined and the count of events of certain event types:

```bash
python eventstoreml.py --summary mymodel.esml
```

EventStoreML files need not stick to "one json object per line" but for tools like `jq` this is needed. Here's how to feed `jq` what it needs:

```bash
python eventstoreml.py --jsonl mymodel.esml | jq .
```

---

## Roadmap

1. Maybe better add "$schema": "http://json-schema.org/draft-07/schema#" to schema specs
4. A specification document derived from this README  
5. Examples and tests for validation and evolution
6. Meta types for timestamping/signing/sealing (minimalistic)
7. Meta types for documentation and governance
8. Generally Unix-y tooling that supports reading, projecting, appending, transforming, piping etc. (should work with `jq` for example)

---

## Contributing

Feedback and contributions are welcome! Nonsense? Useful? Suggestions?

---

## License

MIT License  
Copyright (c) 2025 EventStoreML contributors

---

## Final Thoughts

While EventStoreML uses a sequence of JSON objects as its native form, the same idea can live in other serializations too. So while not really desirable, an ESXML (XML with XSD schema for type declarations) or ESYML (YAML) format is in principle possible.

The initial types an `.esml` file declares at its start usually act as the frame that defines the purpose of the file. And so it can be expected that specific purposes should have their own file extensions. Should you prefer to convey both aspects, simply append your extension to the `.esml` as in `.esml.foo` or, if this were to cause confusion, add your extension in front as in `.bpmn.esml` for instance.

Note that an .esml file can freely mix event types of different domains. For instance, the C4 modeling example has C4 related events but additionally a meta-event for managing releases, an event that has no match in the C4 DSL realm. In a similar fashion additional event types may be useful depending on the application concerned, e.g. a combination of modeling events of different modeling languages (e.g. C4 + BPMN) that might reference each other. Experimental, as said before...

