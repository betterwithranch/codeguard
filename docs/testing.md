# How to test your changes

This guide tells you how to test a change before you merge it, whether you are working
on codeguard itself, on a rule package such as
[betterwithranch/codeguard-rules](https://github.com/betterwithranch/codeguard-rules), or
on an app that uses codeguard. Find the section for the repository you are changing,
then the row for the kind of change you made. Each row says what CI checks and which
commands run the same checks on your machine, so you can find a failure before CI does.

## Words

Four kinds of test run here, and they share words like "case" and "eval".

| Test | Run with | It checks | Calls a model | A case is | Cases live in |
|---|---|---|---|---|---|
| codeguard's tests | `uv run pytest` | The CLI, config, triggers, hooks and judge | Only the LLM tests | A test function | `tests/` |
| Rule tests | `codeguard rules test` | Each pattern rule and gate matches the code it should, and each judge rule's triggers fire on the edits they should | No, and it gives the same result every run | A snippet a rule or gate must or must not match, or a rule eval's edit, checked for its triggers only | `rule-tests/<id>-test.yml`, `rule-evals/<id>.yaml` |
| Rule evals | `codeguard rules eval` | Each judge rule's model gives each edit the review it should | Yes, and its verdicts can vary, so each case runs several times | An edit and the review it should get | `rule-evals/<id>.yaml` |
| Skill evals | `claude plugin eval` | The writing-rules skill leads an agent to a good rule | Yes | A prompt and its graders | `evals/writing-rules/<case>/` |

Rule tests are free and exact, so they run on every rule change. Rule evals cost model
calls, so they run only for a change that can change a verdict. Both check the rules
themselves; `codeguard review` is different: it runs the rules on your code.

- `valid`, `invalid` and `skipped` are what a rule eval case expects. `invalid`: the
  triggers fire and the judge reports a violation. `valid`: the triggers fire and the
  judge reports none. `skipped`: the triggers don't fire.
- `claude plugin eval` has its own words: a grader checks a run, its `focus` or
  `target` says what it reads, an arm is a set of runs with or without the plugin, and a
  scaffold seeds each run's workspace. See
  [Test plugins with evals](https://code.claude.com/docs/en/plugin-evals.md).

## The bar for a judge rule

A review judges each change once, so a case that flips between runs is a review that
wrongly blocks or misses. A judge rule passes its rule eval when every case gets its
expected review on every run.

CI runs a rule's eval only for a change that can change its verdicts:

| The change | Each case of the rule passes |
|---|---|
| The rule's definition: its skill or a language supplement, its binding (paths, triggers), its rule eval, or a gate its triggers name (the judge is sent the whole trigger node around a change) | 20 runs of 20 |
| The judge: codeguard's judge prompt, request, tools or harness, or the codeguard version a package or app tests with | 3 runs of 3 |

Twenty clean runs show, with 95% confidence, that a case fails less than 1 run in 7.
Three clean runs catch a rule that a judge change has broken. No other change runs a
rule eval: a pattern rule, a gate no judge rule uses, or another rule. CI applies this
wherever judge rules live: a rule package, an app's `.codeguard/`, and codeguard's own
fixtures in `evals/judge/`.

When a case fails or flips, follow the writing-rules skill: fix the rule or the case,
never re-run until it passes.

Rule test warnings, such as broad triggers, are advisory: they don't fail a change.

## Changing codeguard

| You change | CI runs | Locally |
|---|---|---|
| Anything | Lint, format, import boundaries, types and codeguard's offline tests | `uv run ruff check`, `uv run ruff format --check`, `uv run lint-imports`, `uv run basedpyright`, `uv run pytest` |
| Anything | A review of the pull request's changed files against the rules in `.codeguard/config.yaml`, judge rules included; an `error` fails the pull request | The Stop hook reviews each session's changes |
| The judge: `src/codeguard/` review, provider, rules or syntax code, the rule eval harness, `pyproject.toml` or `uv.lock` | The LLM tests, each fixture case 3 runs | `uv run pytest -m llm -n 8` |
| A fixture rule in `evals/judge/` | The LLM tests, that rule's cases 20 runs | `uv run pytest -m llm -n 8 --llm-runs 20 -k <rule>` |
| `skills/writing-rules/` or `evals/writing-rules/` | The skill evals | [The writing-rules skill evals](#the-writing-rules-skill-evals) |

`uv run pytest` calls no model. The LLM tests review each fixture case the way
`codeguard review` does, with the real `claude` CLI; plain `uv run pytest` deselects
them.

codeguard ships no rules, so its CI runs no rule tests. The rules it reviews itself
with are tested in their package's CI.

A pull request description doesn't list the checks CI runs.

### The writing-rules skill evals

Each case in `evals/writing-rules/` asks an agent to write or fix a rule with the
plugin loaded, then grades what it wrote. The skill is guidance and the rules it leads
to have their own evals, so the bar is lower than a judge rule's: CI gives each case 3
runs and passes a case scoring 0.8 or more.

```sh
claude plugin eval . --scaffold --allow-tools Write Edit Bash --runs 3 --threshold 0.8 \
  --trust-plugin --no-publish --keep-temp
```

- Run it from a checkout with no `.venv`.
- Granting Bash runs the agent's commands in Claude Code's sandbox. On Linux, install
  `bubblewrap` and `socat`, and set `TMPDIR` to a directory outside `/tmp`, where the
  sandbox denies writes.
- `--keep-temp` keeps each run's workspace. When a grader fails, open the files the
  agent wrote there and check them against the verdict before changing the skill.
- `--case <name>` runs one case.
- `--ablation none` skips the runs without the plugin.

### Writing a skill eval case

A grader checks what the agent produced, not what it said or the steps it took.

- The prompt names the rule's id, so the grader knows each file's path.
- A grader reads one file: its `focus` or `target` is
  `{ source: file, path: .codeguard/skills/<id>/SKILL.md }`, or the binding or rule eval.
- Structure, such as a `## Why` heading or triggers other than `any`, is a `regex`
  grader. Judgement, such as whether the convention is one declarative sentence, is an
  `llm` grader on that one short file, with PASS and FAIL stated concretely.
- Never grade the trace with an `llm` grader: its judge sees only the first and last 12
  lines of the session, never the files.
- That the agent ran the rule tests is a `tool_used` grader on `Bash` whose
  `input_match` is `codeguard rules test`.
- Nothing in the skill gives a case's answer: no example in `SKILL.md` or `references/`
  shares a case's convention, domain or names. A case the skill answers measures
  copying.

## Changing a rule package

| You change | CI runs | Locally |
|---|---|---|
| A pattern rule, a gate or their tests | The rule tests: each rule and gate matches its `invalid` snippets and none of its `valid` ones | `codeguard rules test` |
| A judge rule's skill, supplement, binding or rule eval, or a gate it uses | The rule tests, then each such rule's evals, 20 runs | `codeguard rules test`, then `codeguard rules eval --rule <id> --repeat 20` |
| The codeguard version CI tests with | The rule tests, then every judge rule's evals, 3 runs | `codeguard rules test`, then `codeguard rules eval --repeat 3` |

Run both commands at the package root; they cover every ruleset. A merged change is
ready to tag: CI has already held each changed rule to the bar.

The README's [Write a rule package](../README.md#write-a-rule-package) has the rule,
binding and rule eval formats.

## Changing an app

| You change | Checked by | When |
|---|---|---|
| The app's code | The codeguard plugin's Stop hook reviews the session's changes against the rules in `.codeguard/config.yaml`; an `error` blocks the agent | Every time an agent stops |
| The app's code | The review action, `jig-code/codeguard@v<version>`, reviews the pull request's changed files; an `error` fails the pull request | Every pull request |
| A rule in the app's own `.codeguard/` | The test action, `jig-code/codeguard/test@v<version>`, runs the rule tests, and with `eval: true` the judge rules' evals at the bar above | Every pull request |
| The codeguard release the actions are pinned to | The test action runs each of the app's own judge rules' evals, 3 runs | The upgrade's pull request |

- An app with no rules of its own runs only the review action.
- To change a packaged rule for the app, override or exclude it in
  `.codeguard/config.yaml`; never copy it into `.codeguard/`. The package's CI tests the
  rule.
- A finding you think is wrong is fixed in the rule or its cases, never by changing the
  code to get past it.
