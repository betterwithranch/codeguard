---
type: llm
focus: { source: file, path: ".codeguard/rule-evals/derive-known-values.yaml" }
weight: 1
---

No TypeScript case copies the Python case in which values match an enum's by coincidence (HTTP verbs that share a word with an enum): that case doesn't depend on the language, so it needs no TypeScript copy.
