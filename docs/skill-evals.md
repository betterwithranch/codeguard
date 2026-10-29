# Testing the writing-rules skill

The writing-rules skill, in `skills/writing-rules/`, is the guidance codeguard's plugin
gives an agent that writes or changes a codeguard rule: what a well-written rule, binding
and set of cases look like. Its evals, in `evals/writing-rules/`, give an agent with the
skill a request for a rule and check that the files it writes follow the skill. They run
with `claude plugin eval`; Anthropic's
[Test plugins with evals](https://code.claude.com/docs/en/plugin-evals.md) is the full
reference for the command, the case format and the graders.

This guide is for changing the skill or its evals.
[How to test your changes](testing.md) covers everything else: testing codeguard, testing
rules and reviewing code.

## What an eval measures

An eval measures the skill by the content of the rule files an agent writes with it.
Each check reads a file the agent wrote and asks whether it does what the skill says,
such as stating one convention in the rule's `SKILL.md` or naming each case for why its
code is or isn't a problem. An eval never checks whether the rule works: whether its
rule tests or rule evals pass, or how reliably. That is the job of the rule's own tests,
in whatever repository the rule lives, and is out of scope here.

## Running the evals

CI runs them when `skills/writing-rules/` or `evals/writing-rules/` changes. Each case
runs 3 times. A run's score is the share of the case's graders that pass, weighted by
each grader's `weight`, and a case passes when its scores average 0.8 or more.

```sh
claude plugin eval . --scaffold --allow-tools Write Edit --runs 3 --threshold 0.8 \
  --trust-plugin --no-publish
```

- `--scaffold` runs each case's `place-files.sh`, which copies the case's project into
  the agent's empty workspace.
- `--allow-tools Write Edit` lets the agent write files. It gets no other tool that needs
  a grant.
- `--trust-plugin` skips the first-run trust prompt, which CI can't answer.
- `--no-publish` keeps the report local.

The report and scores go to `evals/results/<timestamp>/`, which git ignores. Run the
command from a checkout with no `.venv`: the eval copies the plugin and refuses the hard
links uv makes there.

## Writing a case

A case is a directory in `evals/writing-rules/`:

| File | Holds |
|---|---|
| `prompt.md` | The request the agent gets. Its frontmatter sets `allowed_tools`, `max_turns` and `timeout_seconds` |
| `case.yaml` | The case's `name` and `context.scaffold_script: place-files.sh` |
| `files/` | The project the agent works in, with its `.codeguard/config.yaml` |
| `place-files.sh` | Copies `files/` into the workspace |
| `graders/<n>-<check>.md` | One check each: frontmatter with `type: llm`, `focus` and `weight`, and a body that states the check |

- `allowed_tools` lists `Read`, `Glob`, `Grep`, `Skill`, `Write` and `Edit`, never
  `Bash`. The prompt says codeguard isn't available, so the agent doesn't try to run it.
  Without `Bash` the run needs no sandbox and never runs codeguard.
- The prompt names the rule's id, so each grader knows the path of the file it reads:
  `.codeguard/skills/<id>/SKILL.md`, `.codeguard/bindings/<id>.yaml` or
  `.codeguard/rule-evals/<id>.yaml`.
- Each grader reads one of those files, set with `focus: {source: file, path: <path>}`,
  and checks one thing the skill asks for. Never use `focus: trace` (the agent's whole
  session) or the default, `last_message` (its final reply): what the agent said or did
  isn't the rule it wrote.
- The case's request must not already be answered in the skill. If an example in
  `skills/writing-rules/SKILL.md` or its `references/` uses the same convention, domain
  or names as a case, an agent can copy the example instead of applying the guidance,
  and the case measures copying. Give each case a convention the skill's examples don't
  show, and when you add an example to the skill, check that it doesn't match a case.
