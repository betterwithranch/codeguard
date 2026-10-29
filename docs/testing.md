# How to test your changes

This guide tells you how to test a change before you merge it, whether you are working
on codeguard itself, on a rule package such as
[betterwithranch/codeguard-rules](https://github.com/betterwithranch/codeguard-rules), or
on an app that uses codeguard. Find the section for the repository you are changing,
then the row for the kind of change you made. Each row says what CI checks and which
commands run the same checks on your machine, so you can find a failure before CI does.
The rows are the whole list: a change needs no check its row doesn't name. Never write a
script, a copy of the repository or a workaround to test a change some other way. If a
change fits no row, or a listed check can't run, say so and change this guide instead.
A pull request description doesn't list the checks CI runs: their results already show
on the pull request.

## Words

Four kinds of test run here, and they share words like "case" and "eval".

| Test | Run with | It checks | Calls a model | A case is | Cases live in |
|---|---|---|---|---|---|
| codeguard's tests | `uv run pytest` | The CLI, config, triggers, hooks and judge, with no model | No | A test function | `tests/` |
| LLM tests | `uv run pytest -m llm` | The judge gives each fixture case its expected review from a real model | Yes, and its verdicts can vary, so each case runs several times | A fixture case | `evals/judge/` |
| Rule tests | `codeguard rules test` | Each pattern rule and gate matches the code it should, and each judge rule's triggers fire on the edits they should | No, and it gives the same result every run | A snippet a rule or gate must or must not match, or a rule eval's edit, checked for its triggers only | `rule-tests/<id>-test.yml`, `rule-evals/<id>.yaml` |
| Rule evals | `codeguard rules eval` | Each judge rule's model gives each edit the review it should | Yes, and its verdicts can vary, so each case runs several times | An edit and the review it should get | `rule-evals/<id>.yaml` |

Rule tests are free and exact, so they run on every rule change. Rule evals cost model
calls, so they run only for a change that can change a verdict. Both check the rules
themselves; `codeguard review` is different: it runs the rules on your code.

`valid`, `invalid` and `skipped` are what a rule eval case expects. `invalid`: the
triggers fire and the judge reports a violation. `valid`: the triggers fire and the
judge reports none. `skipped`: the triggers don't fire.

The LLM tests' fixtures are a small rule package in `evals/judge/` that exists only to
test the judge. A fixture rule is a judge rule there, and a fixture case is one of its
rule eval cases. They are part of codeguard's tests, not rules codeguard reviews with.

## The bar for a judge rule

A review judges each change once, so a case that flips between runs is a review that
wrongly blocks or misses. A judge rule passes its rule eval when every case gets its
expected review on every run.

CI runs a rule's eval only for a change that can change its verdicts:

| You change | Each case of the rule passes |
|---|---|
| The rule: its skill or a language supplement, its binding (paths, triggers), or a gate its triggers name (the judge is sent the whole trigger node around a change). Or the rule's eval cases | 20 runs of 20 |
| The judge: codeguard's judge prompt, request, tools or harness, or the codeguard version a package or app tests with | 3 runs of 3 |

Twenty clean runs show, with 95% confidence, that a case fails less than 1 run in 7.
Three clean runs catch a rule that a judge change has broken. No other change runs a
rule eval: a pattern rule, a gate no judge rule uses, or another rule. CI applies this
wherever judge rules live: a rule package, an app's `.codeguard/`, and codeguard's
fixture rules, where a change to any fixture rule runs every fixture case 20 times.

When a case fails or flips, fix the rule or the case, as the writing-rules skill
describes; never re-run until it passes.

Rule test warnings, such as broad triggers, are advisory: they don't fail a change.

## Changing codeguard

| You change | It checks | CI runs | Locally, run |
|---|---|---|---|
| Anything | Lint, format, import boundaries, types and codeguard's offline tests | `uv run ruff check`, `uv run ruff format --check`, `uv run lint-imports`, `uv run basedpyright`, `uv run pytest` | Same |
| Anything | The changed files against the rules codeguard opts into, judge rules included; an error fails. In CI, the review action reviews the pull request's changes since its base branch. Locally, the Stop hook reviews the session's uncommitted and untracked files each time the agent stops | `codeguard review --base <base branch>` | `codeguard review` |
| The judge: its review, provider, rules or syntax code, or the dependencies | Each fixture case's review, 3 runs | `uv run pytest -m llm -n 8` | Same |
| A fixture rule or its fixture cases | Each fixture case, 20 runs | `uv run pytest -m llm -n 8 --llm-runs 20` | Same |
| The writing-rules skill or its evals | Each skill eval case's graders, 3 runs | `claude plugin eval .` with the flags in [Testing the writing-rules skill](skill-evals.md) | Same |

The judge's code is under `src/codeguard/`. The LLM tests review each fixture case the
way `codeguard review` does, with the real `claude` CLI; plain `uv run pytest` deselects
them. `-n 8` only sets how many run at once: any number gives the same result.

codeguard ships no rules, so never run `codeguard rules test` or `codeguard rules eval`
here. The rules in `evals/judge/` are fixtures for codeguard's own tests, and the rules
codeguard reviews itself with are tested in their package's CI.

## Changing a rule package

| You change | It checks | CI runs | Locally, run |
|---|---|---|---|
| A pattern rule, a gate or their tests | Each rule and gate matches its `invalid` snippets and none of its `valid` ones | `codeguard rules test` | Same |
| A judge rule's skill, supplement, binding or rule eval, or a gate it uses | Each case's triggers, then each such rule's verdicts, 20 runs | `codeguard rules test`, `codeguard rules eval --rule <id> --repeat 20` | Same |
| The codeguard version CI tests with | Each case's triggers, then every judge rule's verdicts, 3 runs | `codeguard rules test`, `codeguard rules eval --repeat 3` | Same |

Run both commands at the package root; they cover every ruleset. A merged change is
ready to tag: CI has already held each changed rule to the bar.

The README's [Write a rule package](../README.md#write-a-rule-package) has the rule,
binding and rule eval formats.

## Changing an app

| You change | It checks | CI runs | Locally, run |
|---|---|---|---|
| The app's code | The changed files against the app's rules; an error fails. In CI, the review action reviews the pull request's changes since its base branch. Locally, the Stop hook reviews the session's uncommitted and untracked files each time the agent stops, and an error blocks the agent | `codeguard review --base <base branch>` | `codeguard review` |
| A rule the app defines | Each rule's tests and each case's triggers, then the verdicts of each judge rule whose rule or eval cases changed, 20 runs | `codeguard rules test`, `codeguard rules eval --rule <id> --repeat 20` | Same |
| The codeguard release the actions are pinned to | Each case's triggers, then every judge rule's verdicts, 3 runs | `codeguard rules test`, `codeguard rules eval --repeat 3` | Same |

- In CI, the review action, `jig-code/codeguard@v<version>`, runs `codeguard review`.
  The test action, `jig-code/codeguard/test@v<version>`, runs `codeguard rules test`,
  and `codeguard rules eval` when `eval: true` is set.
- An app with no rules of its own runs only the review action.
- To change a packaged rule for the app, override or exclude it in
  `.codeguard/config.yaml`; never copy it into `.codeguard/`. The package's CI tests the
  rule.
- A finding you think is wrong is fixed in the rule or its cases, never by changing the
  code to get past it.
