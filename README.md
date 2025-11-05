# EventStoreML

**EventStoreML** (pronounced *eventstormel*) is a minimal, self-hosting markup language where **every top-level element is an event** — even schema definitions themselves.  

Every `.esml` file is an **append-only event store that defines its own meanings over time through events**.  

Its core consists of exactly one must-understand root event type, `core.TypeDeclared@1`, expressed in pure JSON Schema. All other types, schemas, and instances are declared, validated, and evolved through events.

Underlying idea: If event sourcing is so good then why not attempt to use event store files where normally state snapshot files are being used (e.g. config files, model markup files, etc.). So instead of having multiple file versions a single .esml contains all versions within. 

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

* **Bootstrap simplicity** - the language defines itself through a single event type and thus type: `core.TypeDeclared@1`
* **Schema-first, no state** - all information is expressed as events, never as object state
* **JSON Schema subset** - uses a safe, minimal subset (type, properties, required, items, $defs, internal $ref)
* **Namespaces**
  * `core.*` - reserved, must-understand types for parsers  
  * `meta.*` - optional meta or governance layer  
  * others - user or domain namespaces
* **Declare-before-use** - a type can only appear and be used after it has been declared
* **Tree rule (single-parent lineage)** - every new type or new version of a type must be declared using an already existing type
* **Opaque extensibility** - anything outside `core.*` is validated against its schema but otherwise semantically opaque

---

## Core Type: `core.TypeDeclared@1`

`core.TypeDeclared@1` is the single built-in event type that bootstraps everything else. Instances of this event type declare new types and their schemas. Such new types can then be used in schema definitions or as event type of new event instances. An event type can also be a new type-declaring event type...

### Payload schema (subset of JSON Schema)

```yaml
name: string
version: integer
schema:
  type: object
  properties: { ... }
  required?: [ ... ]
  additionalProperties?: boolean
  items?: { ... }
  $defs?: { ... }
  $ref?: "#/$defs/..."
```

### File Format and Syntax

An EventStoreML (`.esml`) file is a **time-ordered sequence of events**, where each entry has the structure:

```yaml
- type: "some.namespace.EventName@version"
  data: { ... }
```

**Official serialization:** YAML.  
YAML is the normative textual representation used in this project and examples.

**Alternate representation:** JSON.  
JSON is structurally equivalent and may be supported by tooling, but it is not the canonical format in this repository.

**No binary format at this time.**  
There is currently no standardized binary encoding for EventStoreML in this project.

Parsers must treat the file as a sequential list of `{type, data}` records.  
The order of events is significant, since later events may depend on earlier type declarations.

### Parser duties

1. Parse the sequence of `{type, data}` items.  
2. When encountering `core.TypeDeclared@*`:
   * Validate the payload against its schema  
   * Register `(name, version) -> schema`  
   * Enforce *declare-before-use* and *tree rule*
3. For all other events:
   * Look up their schema in the registry  
   * Validate the data accordingly  
   * Treat everything outside `core.*` as semantically opaque

---

## Example `.esml` File

```yaml
# 1. The declarer itself (built-in for most parsers)
- type: "core.TypeDeclared@1"
  data:
    name: "core.TypeDeclared"
    version: 1
    schema:
      type: object
      properties:
        name:    { type: string }
        version: { type: integer }
        schema:  { type: object }
      required: ["name","version","schema"]
      additionalProperties: false

# 2. Declare a struct type
- type: "core.TypeDeclared@1"
  data:
    name: "common.struct.Address"
    version: 1
    schema:
      type: object
      properties:
        street: { type: string }
        city:   { type: string }
        zip:    { type: string }
      required: ["street","city","zip"]
      additionalProperties: false

# 3. Declare an event type
- type: "core.TypeDeclared@1"
  data:
    name: "customer.event.CustomerRegistered"
    version: 1
    schema:
      type: object
      properties:
        customer_id: { type: string }
        name:        { type: string }
        address:     { $ref: "#/$defs/common.struct.Address@1" }
      required: ["customer_id","name","address"]
      additionalProperties: false

# 4. Use the declared event type
- type: "customer.event.CustomerRegistered@1"
  data:
    customer_id: "01J..."
    name: "Ada"
    address:
      street: "Main 1"
      city: "Zürich"
      zip: "8001"
```

---

## Type Evolution

Each type version must reference a single parent version, forming a tree of lineage.

```yaml
# Declare v2 of the declarer itself using v1
- type: "core.TypeDeclared@1"
  data:
    name: "core.TypeDeclared"
    version: 2
    schema:
      type: object
      properties:
        name:    { type: string }
        version: { type: integer }
        schema:  { type: object }
      required: ["name","version","schema"]
      additionalProperties: false
```

Future declarations can then use `core.TypeDeclared@2` as well.

---

## Extensibility

* **Meta namespace** - `meta.*` events can describe documentation, policies, timestamps, signatures, version control, etc.
* **Profiles and declarers** - specialized declarers (for policies, projections, or other structures) can be introduced later.  
* **Custom namespaces** - domain types can coexist in the same file and reference each other through `$ref`.

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

The parser will:

1. Load and parse the `.esml` file.  
2. Build a type registry from all `core.TypeDeclared` events.  
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
Its core consists of exactly one must-understand event type, `core.TypeDeclared@1`, expressed in pure JSON Schema.  
All other types, schemas, and instances are declared, validated, and evolved through events.
