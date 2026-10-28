---
type: llm
focus: { source: file, path: ".codeguard/rule-evals/derive-known-values.yaml" }
weight: 1
---

The rule eval has a TypeScript case with both a before and an after, where the change is inside a larger existing function or block and the definition it copies is outside the changed lines, so the violation shows only with the code around the change.
