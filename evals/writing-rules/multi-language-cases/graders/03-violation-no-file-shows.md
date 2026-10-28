---
type: llm
focus: { source: file, path: ".codeguard/rule-evals/derive-known-values.yaml" }
weight: 1
---

The rule eval has an invalid TypeScript case (file ending in .ts or .tsx) whose hand-written copy is neither a union type nor an array: for example a Set, an object's keys, or the cases of a switch statement that repeat a definition elsewhere in the file.
