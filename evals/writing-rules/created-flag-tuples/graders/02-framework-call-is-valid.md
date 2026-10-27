---
type: llm
focus: trace
weight: 1
---

The rule eval has a valid case in which code calls a framework's own get_or_create (or a similar idiomatic API that returns a created flag) and is not flagged.
