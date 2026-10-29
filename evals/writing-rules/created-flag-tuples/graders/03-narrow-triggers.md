---
type: llm
focus: {source: file, path: .codeguard/bindings/created-flag-results.yaml}
weight: 1
---

Each trigger in this binding gates the narrowest node that holds a violation of this rule: what a function returns or yields, or its return annotation (`return-yield`, `function-signature`, or a gate on those nodes). No trigger is wider, such as `any`, `code` or `function-body`, which fire on any edit inside a function.
