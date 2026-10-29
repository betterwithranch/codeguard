---
type: llm
focus: {source: file, path: .codeguard/bindings/created-flag-results.yaml}
weight: 1
---

Each trigger in this binding is a node that can hold a created flag a function hands back: what the function returns or yields (`return-yield`, or a gate on return statements), or its return annotation (`function-signature`). No trigger is `any`, `code` or `function-body`, which fire on any edit inside a function.
