---
type: llm
focus: { source: file, path: ".codeguard/rule-evals/derive-known-values.yaml" }
weight: 1
---

No TypeScript case reuses typescript.md's example code: no type named Size over a SIZES array, no union "s" | "m" | "l", and no enum named Size. Renamed copies of those snippets with the same structure and values count as reuse.
