---
type: llm
focus: { source: file, path: ".codeguard/rule-evals/derive-known-values.yaml" }
weight: 1
---

typescript.md shows two examples. Keeps: a type taken from an as const array with (typeof X)[number]; Object.values over an enum. Breaks: a union type written out beside an as const array holding those values; an array of an enum's values written out beside the enum. For each of the two, the rule eval has a TypeScript case (file ending in .ts or .tsx) that keeps the convention and an invalid case of the same shape that breaks it.
