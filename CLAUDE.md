# codeguard

[README.md](README.md) explains the CLI, rule packages and how to work on codeguard.

## Testing

Before testing any change, follow [docs/testing.md](docs/testing.md).

- Run only the checks the change's row names. Never write a script, a copy of the
  repository or a workaround to test a change some other way.
- If a change fits no row, or a listed check can't run, say so and change the guide.
- Don't list the checks CI runs in a pull request description: their results already
  show on the pull request.

## Rules

Before adding or changing a rule, and whenever a rule eval, an LLM test or a judged
review fails, flips between runs or reports a warning, follow
[skills/writing-rules/SKILL.md](skills/writing-rules/SKILL.md). This covers the LLM
tests' fixtures in `evals/judge`, every rule package, and judged reviews of codeguard's
own code.
