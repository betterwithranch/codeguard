# codeguard

[README.md](README.md) explains the CLI, rule packages and how to work on codeguard.

## Rules

Before adding or changing a rule, and whenever a rule eval or a judged review fails,
flips between runs or reports a warning, follow
[skills/writing-rules/SKILL.md](skills/writing-rules/SKILL.md) and its
[judge rule guide](skills/writing-rules/references/judge-rules.md). This covers the judge
evals in `evals/judge`, every rule package, and judged reviews of codeguard's own code.
A finding you think is wrong is fixed in the rule's package, never by changing
codeguard's code to get past it.
