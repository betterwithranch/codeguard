# codeguard

[README.md](README.md) explains the CLI, rule packages and how to work on codeguard.

## Rules

Before adding or changing a rule, and whenever a rule eval, an LLM test or a judged
review fails, flips between runs or reports a warning, follow
[skills/writing-rules/SKILL.md](skills/writing-rules/SKILL.md). This covers the LLM
tests' fixtures in `evals/judge`, every rule package, and judged reviews of codeguard's
own code.
