---
type: llm
focus: last_message
weight: 1
---

The agent's final reply says it wrote no codeguard rule for this convention, and why: finding a function nobody calls takes a lookup across the whole repository, which a language server's find-references or a dead-code tool does exactly, while a codeguard rule sees only the changed file. Whether or how the agent sets up such a tool doesn't matter.
