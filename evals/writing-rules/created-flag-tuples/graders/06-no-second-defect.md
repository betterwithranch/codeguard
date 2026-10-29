---
type: llm
focus: {source: file, path: .codeguard/rule-evals/created-flag-results.yaml}
weight: 1
---

No case in this rule eval contains a second problem a reviewer would flag whatever the rule says, such as a bug, a crash or a security hole, so each case is judged only on whether a function returns a created flag. Code that is merely simple or made up is not a second problem.
