# EventStoreML
EventStoreML is a minimal, self-hosting markup language where everything is an event — even the schema definitions themselves.
Each .esml file is an event store that defines its own meaning over time.
Its core consists of exactly one must-understand event type, core.TypeDeclared@1, expressed in pure JSON Schema.
Every other type, schema, and instance is declared, validated, and evolved through events.
