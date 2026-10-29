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

| You change | Each case of the rule passes |
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

| You change | It checks | CI runs | Locally, run |
|---|---|---|---|
| Anything | Lint, format, import boundaries, types and codeguard's offline tests | `uv run ruff check`, `uv run ruff format --check`, `uv run lint-imports`, `uv run basedpyright`, `uv run pytest` | `uv run ruff check`, `uv run ruff format --check`, `uv run lint-imports`, `uv run basedpyright`, `uv run pytest` |
| Anything | The changed files against the rules codeguard opts into, judge rules included; an error fails. In CI, the review action reviews the pull request's changes since its base branch. Locally, the Stop hook reviews the session's uncommitted and untracked files each time the agent stops | `codeguard review --base <base branch>` | `codeguard review` |
| The judge: its review, provider, rules or syntax code, the rule eval harness, or the dependencies | Each fixture case's verdict, 3 runs | `uv run pytest -m llm -n 8` | `uv run pytest -m llm -n 8` |
| A fixture rule for the LLM tests | That rule's verdicts, 20 runs | `uv run pytest -m llm -n 8 --llm-runs 20 -k <rule>` | `uv run pytest -m llm -n 8 --llm-runs 20 -k <rule>` |
| The writing-rules skill or its evals | Each skill eval case's graders, 3 runs | `claude plugin eval . --runs 3 --threshold 0.8` | `claude plugin eval . --runs 3 --threshold 0.8` |

The writing-rules skill and its evals are in `skills/writing-rules/` and
`evals/writing-rules/`, the LLM tests' fixture rules are in `evals/judge/`, and the
judge's code is under `src/codeguard/`.

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
- Granting `Bash` runs the agent's commands in Claude Code's sandbox. On Linux, install
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
  `llm` grader on that one short file, with `PASS` and `FAIL` stated concretely.
- Never grade the trace with an `llm` grader: its judge sees only the first and last 12
  lines of the session, never the files.
- That the agent ran the rule tests is a `tool_used` grader on `Bash` whose
  `input_match` is `codeguard rules test`.
- Nothing in the skill gives a case's answer: no example in `SKILL.md` or `references/`
  shares a case's convention, domain or names. A case the skill answers measures
  copying.

## Changing a rule package

| You change | It checks | CI runs | Locally, run |
|---|---|---|---|
| A pattern rule, a gate or their tests | Each rule and gate matches its `invalid` snippets and none of its `valid` ones | `codeguard rules test` | `codeguard rules test` |
| A judge rule's skill, supplement, binding or rule eval, or a gate it uses | Each case's triggers, then each such rule's verdicts, 20 runs | `codeguard rules test`, `codeguard rules eval --rule <id> --repeat 20` | `codeguard rules test`, `codeguard rules eval --rule <id> --repeat 20` |
| The codeguard version CI tests with | Each case's triggers, then every judge rule's verdicts, 3 runs | `codeguard rules test`, `codeguard rules eval --repeat 3` | `codeguard rules test`, `codeguard rules eval --repeat 3` |

Run both commands at the package root; they cover every ruleset. A merged change is
ready to tag: CI has already held each changed rule to the bar.

The README's [Write a rule package](../README.md#write-a-rule-package) has the rule,
binding and rule eval formats.

## Changing an app

| You change | It checks | CI runs | Locally, run |
|---|---|---|---|
| The app's code | The changed files against the app's rules; an error fails. In CI, the review action reviews the pull request's changes since its base branch. Locally, the Stop hook reviews the session's uncommitted and untracked files each time the agent stops, and an error blocks the agent | `codeguard review --base <base branch>` | `codeguard review` |
| A rule the app defines | Each rule's tests and each case's triggers, then the verdicts of each judge rule whose definition changed, 20 runs | `codeguard rules test`, `codeguard rules eval --rule <id> --repeat 20` | `codeguard rules test`, `codeguard rules eval --rule <id> --repeat 20` |
| The codeguard release the actions are pinned to | Each case's triggers, then every judge rule's verdicts, 3 runs | `codeguard rules test`, `codeguard rules eval --repeat 3` | `codeguard rules test`, `codeguard rules eval --repeat 3` |

- In CI, the review action, `jig-code/codeguard@v<version>`, runs `codeguard review`.
  The test action, `jig-code/codeguard/test@v<version>`, runs `codeguard rules test`,
  and `codeguard rules eval` when `eval: true` is set.
- An app with no rules of its own runs only the review action.
- To change a packaged rule for the app, override or exclude it in
  `.codeguard/config.yaml`; never copy it into `.codeguard/`. The package's CI tests the
  rule.
- A finding you think is wrong is fixed in the rule or its cases, never by changing the
  code to get past it.
