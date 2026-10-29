---
type: llm
focus: {source: file, path: .codeguard/skills/no-swallowed-exceptions/SKILL.md}
weight: 1
---

This SKILL.md adds no exception written for one kind of code, such as "unless the clause logs and re-raises" or "logging is allowed". Saying that a clause which logs and then re-raises keeps the convention, because the error still reaches the caller, is the convention deciding that code, not an exception.
