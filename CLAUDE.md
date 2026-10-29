# codeguard

[README.md](README.md) explains the CLI, rule packages and how to work on codeguard.
[docs/testing.md](docs/testing.md) says how to test a change to codeguard, a rule package or
an app.

## Testing

Before testing any change, read [docs/testing.md](docs/testing.md) and find the row for it
under Changing codeguard. Run exactly the commands that row lists, and no others.

- This repository is codeguard, not a rule package: never run `codeguard test` or
  `codeguard eval` here. The rules in `evals/judge/` are fixtures for codeguard's own
  tests, run by `uv run pytest -m llm`.
- Never write a script, a copy of the repository or a workaround to test a change the
  guide doesn't ask you to test that way.
- If no row fits your change, or a listed check can't run, stop and say so; don't invent
  another check.

## Rules

Before adding or changing a rule, and whenever a rule eval, an LLM test or a judged
review fails, flips between runs or reports a warning, follow
[skills/writing-rules/SKILL.md](skills/writing-rules/SKILL.md). This covers the LLM
tests' fixtures in `evals/judge`, every rule package, and judged reviews of codeguard's
own code.
