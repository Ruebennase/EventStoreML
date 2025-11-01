# EventStoreML

**EventStoreML** (pronounced *EventStormel*) is a minimal, self-hosting markup language where **everything is an event** - even the schema definitions themselves.  

Every `.esml` file is an **event store that defines its own meaning over time**.  

Its core consists of exactly one must-understand event type, `core.TypeDeclared@1`, expressed in pure JSON Schema.  
All other types, schemas, and instances are declared, validated, and evolved through events.

---

## Why EventStoreML

EventStoreML is based on the Event Sourcing idea that *events define truth better than projected state does*.  
Instead of storing objects and their mutable state, we capture **facts** and their **schemas** as events.

This has several advantages:

* **Self-describing data** - every event log explains itself, without external schema files  
* **Historical integrity** - schemas evolve through versioned declaration events, preserving lineage  
* **Bootstrap simplicity** - the entire system can be described using one built-in type  
* **Composable and reusable** - event types, structures, and meta information can be shared and referenced across projects  
* **Schema-first thinking** - everything is defined through explicit schemas, not implicit code models

---

## Core Principles

* **Bootstrap simplicity** - the language defines itself through a single type: `core.TypeDeclared@1`
* **Schema-first, no state** - all information is expressed as events, never as object state
* **JSON Schema subset** - uses a safe, minimal subset (type, properties, required, items, $defs, internal $ref)
* **Namespaces**
  * `core.*` - reserved, must-understand types for parsers  
  * `meta.*` - optional meta or governance layer  
  * others - user or domain namespaces
* **Declare-before-use** - a type can only appear after it has been defined
* **Tree rule (single-parent lineage)** - every version of a type must derive from exactly one earlier version; branching allowed, merging forbidden
* **Opaque extensibility** - anything outside `core.*` is validated against its schema but otherwise semantically opaque

---

## Core Type: `core.TypeDeclared@1`

`core.TypeDeclared@1` is the single built-in event type that bootstraps everything else.  
It declares new types and their schemas. It is self-declaring at the start of each .esml file.

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

# 4. Use the declared event
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

Future declarations can then use `core.TypeDeclared@2`.

---

## Extensibility

* **Meta namespace** - `meta.*` events can describe documentation, policies, or version control.  
* **Profiles and declarers** - specialized declarers (for policies, projections, or other structures) can be introduced later.  
* **Custom namespaces** - domain types can coexist in the same file and reference each other through `$ref`.

---

## Working With EventStoreML

EventStoreML files can be used at any level of completeness:

* A file may contain only type declaration events (for others to build upon).  
* A file may contain both type declaration events and application events.  
* Multiple files can be composed or imported to form larger systems.

This makes EventStoreML useful for:

* **Defining schemas** for event-sourced and event-driven systems  
* **Storing and exchanging actual event data** in a self-describing event store format  

An interesting example use case is applying EventStoreML to describe and share **event models** themselves — effectively using event-sourcing principles for defining, evolving, and exchanging event modeling blueprints, rather than storing an event model merely as projected state.


---

## Usage

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

1. Reference parser in Python (validate, register, and evolve schemas)  
2. Specification document derived from this README  
3. Examples and tests for validation and evolution  
4. Meta types for documentation and governance  
5. Visualizers for event lineage and schema trees  
6. Integration with existing event sourcing frameworks  
7. Representation of Event Models entirely as `.esml` files

---

## Contributing

Contributions are welcome.  
If you want to propose changes to the core spec or parser, please open an issue describing:

* the motivation for your change  
* any potential compatibility or tooling impact  
* example `.esml` files demonstrating the idea

Pull requests should include updated examples and tests.

---

## License

MIT License  
Copyright (c) 2025 EventStoreML contributors

---

## Summary

EventStoreML is a minimal, self-hosting markup language where **everything is an event**, including the schema definitions themselves.  
Each `.esml` file is an event store that defines its own structure and meaning.  
Its core consists of exactly one must-understand event type, `core.TypeDeclared@1`, expressed in pure JSON Schema.  
All other types, schemas, and instances are declared, validated, and evolved through events.
