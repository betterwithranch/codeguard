# Testing the writing-rules skill

The writing-rules skill, in `skills/writing-rules/`, is the guidance codeguard's plugin
gives an agent that writes or changes a codeguard rule. Its evals are in
`evals/writing-rules/` and run with `claude plugin eval`.
[Test plugins with evals](https://code.claude.com/docs/en/plugin-evals.md) explains the
command, how to write a case and its graders, and how cases are scored. This page says
only what codeguard adds. [How to test your changes](testing.md) covers testing
codeguard, testing rules and reviewing code.

## What the evals check

Each case asks an agent with the skill to write or fix a rule, then grades the rule files
it wrote against what the skill says: its `.codeguard/skills/<id>/SKILL.md`,
`.codeguard/bindings/<id>.yaml` or `.codeguard/rule-evals/<id>.yaml`. The evals never
check whether the rule works, whether its rule tests or rule evals pass. That is tested
wherever the rule lives, and is out of scope here. So:

- A case never runs codeguard. The agent gets `Write` and `Edit`, never `Bash`.
- A grader reads one of the rule's files, never the agent's replies or session.

## Running them

CI runs them when `skills/writing-rules/` or `evals/writing-rules/` changes. Each case
runs 3 times, and passes when at least 80% of its graders pass, averaged over the runs.

```sh
claude plugin eval . --scaffold --allow-tools Write Edit --runs 3 --threshold 0.8 \
  --trust-plugin --no-publish
```

Run it from a checkout with no `.venv`: the eval copies the plugin and refuses the hard
links uv makes there.
