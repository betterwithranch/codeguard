---
type: llm
focus: {source: file, path: .codeguard/rule-evals/created-flag-results.yaml}
weight: 1
---

In every case of this rule eval, the code defines or imports every name it uses and keeps no state shared between calls, such as a module-level dict or list it changes.
