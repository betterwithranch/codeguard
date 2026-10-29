---
type: llm
focus: {source: file, path: .codeguard/rule-evals/no-swallowed-exceptions.yaml}
weight: 1
---

In this rule eval, the case about logging an error and re-raising it is either removed or clearly keeps a rule against swallowing exceptions: its except clause re-raises, and nothing else in it gives a reviewer a reason to call it a violation.
