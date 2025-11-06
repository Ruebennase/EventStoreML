# EventStoreML

**EventStoreML** (pronounced *eventstormel*) is a minimal, self-hosting markup language where **every top-level element is an event** — even schema definitions themselves.  

Every `.esml` file is an **append-only event store that defines its own meanings over time through events**.  

Its core consists of exactly one must-understand event type, `TypeDeclared`, expressed in pure JSON Schema. All other types, schemas, and instances are declared, validated, and evolved through events.

Underlying idea: Event sourcing has proven powerful — so why not explore using event store files in places where we usually rely on static state snapshots (like config files or model markup files)?

---

## Status: Very Experimental

> EventStoreML is an active exploration. Feedback, discussion, and experiments are welcome. The concepts and syntax may change as we evaluate practical viability.

> EventStoreML is not optimized for performance but for ultimate flexibility and versatility.

---

## Why EventStoreML

EventStoreML is based on the event sourcing idea that a system’s state is often better derived from a complete, ordered log of all events that have occurred, rather than storing only the latest state. Instead of storing objects and their mutable state, we capture both **facts** and their **schemas** as events.

This has several advantages:

* **Self-describing data** - every event store explains itself including its potential evolution, without external schema files  
* **Historical integrity** - schemas evolve through versioned declaration events, preserving lineage  
* **Bootstrap simplicity** - the entire system can be described, starting from one built-in type  
* **Composable and reusable** - event types, structures, and meta information can be shared and referenced across projects  
* **Schema-first thinking** - everything is defined through explicit schemas, not implicit code models

---

## Core Principles

* **Bootstrap simplicity** - the language defines itself through a single event type and thus type: `TypeDeclared`
* **Schema-first, no state** - all information is expressed as events, never as object state
* **JSON Schema subset** - uses a safe, minimal subset (type, properties, required, items, $defs, internal $ref)
* **Namespaces**
  * All types without namespaces (no `.`) are core, reserved, and must-understand types for parsers  
  * `meta.*` - optional meta or governance layer  
  * others - user or domain namespaces
* **Versions** - types can optionally be given a version tag by appending an @version, e.g @2 or @new
* **Declare-before-use** - a type can only appear and be used after it has been declared

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

Unlike a standard JSON document, these objects are written in sequence, without commas or enclosing brackets — allowing the file to be **append-only**. Whitespace between these objects is ignored for the parsing of each event but may be significant for any operations processing the file (e.g. secure hash calculations or indexes pointing to events in the file). Again, each file is append-only and any manipulation within leads to unspecified behaviour.

Example 1:

```json
{"type": "some.namespace.EventName", "data": {...}}
{"type": "some.namespace.EventName@2", "data": {...}}
{"type": "some.namespace.EventName@2", "data": {...}}
```

### Parser duties (WORK IN PROGRESS)

1. Parse the sequence of `{type, data}` items.  
2. When encountering `TypeDeclared`:
   * Validate the payload against its schema  
   * Register `(name, version) -> schema`  
   * Enforce *declare-before-use* and *tree rule*
3. For all other events:
   * Look up their schema in the registry  
   * Validate the data accordingly  
   * Treat everything with a namespace `*.*` as semantically opaque

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
      "version": { "type": "integer" },
      "doc":     { "type": "string"},
      "schema":  { "type": "object" }
    },
    "required": ["name", "version", "schema"],
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

## Type Evolution

If TypeDeclared is deemed insufficient for the desired approach it can be used to declare another type-declaring event type.

```json
{"type": "TypeDeclared",
 "data": {
  "name": "custom.TypeDeclared",
  "doc": "custom.TypeDeclared was declared. It requires a timestamp for each subsequent type declared by it.",
  "schema": {
    "type": "object",
    "properties": {
      "name":      { "type": "string" },
      "version":   { "type": "integer" },
      "doc":       { "type": "string"},
      "schema":    { "type": "object" },
      "timestamp": { "type": "string"}
    },
    "required": ["name", "version", "schema", "timestamp"],
    "additionalProperties": false
  }
}}
```

Future declarations can then use `custom.TypeDeclared` as well. Of course, the tool needs to understand this.

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

Once a reference parser is available, an EventStoreML file can be parsed and validated as follows:

```bash
python -m eventstoreml validate mymodel.esml
```

The parser will (WORK IN PROGRESS):

1. Load and parse the `.esml` file.  
2. Build a type registry from all `TypeDeclared` events and...
3. Validate each subsequent event against its declared schema.  
4. Report validation results and lineage.

---

## Roadmap

1. A reference parser in Python (to validate schemas)  
2. A specification document derived from this README  
3. Examples and tests for validation and evolution
4. Meta types for timestamping/signing/sealing (minimalistic)
5. Meta types for documentation and governance  

---

## Contributing

Feedback and contributions are welcome!
If you want to propose changes to the core spec or parser, please open an issue describing:

* the motivation for your change  
* any potential compatibility or tooling impact  
* example `.esml` files demonstrating the idea, if sensible

---

## License

MIT License  
Copyright (c) 2025 EventStoreML contributors

---

## Summary

EventStoreML is a minimal, self-hosting markup language where **every top-level element is an event**, including the schema definitions themselves.  
Each `.esml` file is an event store that defines its own structure and meaning.  
Its core consists of exactly one must-understand event type, `TypeDeclared`, expressed in pure JSON Schema.  
All other types, schemas, and instances are declared, validated, and evolved through events.
