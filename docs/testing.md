# Testing

How to test a change to codeguard, to a rule package such as
[betterwithranch/codeguard-rules](https://github.com/betterwithranch/codeguard-rules), or
to an app that uses codeguard. CI enforces each check below; run the same commands
locally to find a failure before CI does.

## Words

Three programs run tests here, and they share words like "case" and "eval".

| Runner | What it tests | A case is |
|---|---|---|
| `pytest` | codeguard's own code, in `tests/` | a test function |
| `codeguard test`, `codeguard eval` | a rule author's rules | a snippet a pattern rule must or must not match (`rule-tests/<id>-test.yml`), or an edit and the review it should get (`rule-evals/<id>.yaml`) |
| `claude plugin eval` | an agent doing a task with the codeguard plugin loaded | a prompt and its graders (`evals/writing-rules/<case>/`) |

- `valid`, `invalid` and `skipped` are what a rule eval case expects. `invalid`: the
  triggers fire and the judge reports a violation. `valid`: the triggers fire and the
  judge reports none. `skipped`: the triggers don't fire.
- *Grader*, `focus`, `target`, *arm* and *scaffold* are `claude plugin eval`'s words;
  see [Test plugins with evals](https://code.claude.com/docs/en/plugin-evals.md).

## The bar for a judge rule

A review judges each change once, so a case that flips between runs is a review that
wrongly blocks or misses. A judge rule passes its rule eval when every case gets its
expected review on every run:

| The change | Each affected case passes |
|---|---|
| Defines the rule: its skill or a language supplement, its binding (paths, triggers), or its rule eval | 20 runs of 20 |
| Reaches the rule only through the framework: codeguard's judge prompt, request, tools or harness, a shared gate, a new codeguard release | 3 runs of 3 |

Twenty clean runs show, with 95% confidence, that a case fails less than 1 run in 7.
Three clean runs catch a rule that a change has broken. CI applies this bar wherever
judge rules live: a rule package, an app's `.codeguard/`, and codeguard's own fixtures
in `evals/judge/`.

When a case fails or flips, follow the `writing-rules` skill: fix the rule or the case,
never re-run until it passes.

`codeguard test` warnings, such as broad triggers, are advisory: they don't fail a
change.

## Changing codeguard

| You change | CI runs | Locally |
|---|---|---|
| Anything | lint, format, import boundaries, types and the offline tests, on every push | `uv run ruff check`, `uv run ruff format --check`, `uv run lint-imports`, `uv run basedpyright`, `uv run pytest` |
| Anything | codeguard reviews the PR's changed files against the rules it opts into in `.codeguard/config.yaml`, judge rules included; an `error` fails the PR | the Stop hook reviews each session's changes |
| The judge: `src/codeguard/` review, provider, rules or syntax code, the rule eval harness, `pyproject.toml` or `uv.lock` | the LLM tests, every fixture 3 times | `uv run pytest -m llm -n 8` |
| A fixture rule in `evals/judge/` | the LLM tests, that rule's cases 20 times | `uv run pytest -m llm -n 8 --llm-runs 20 -k <rule>` |
| `skills/writing-rules/` or `evals/writing-rules/` | the writing-rules skill evals | [below](#the-writing-rules-skill-evals) |

`uv run pytest` calls no model. The LLM tests review each fixture case the way
`codeguard review` does, with the real `claude` CLI; plain `pytest` deselects them.

codeguard ships no rules, so its CI doesn't run `codeguard test`. The rules it reviews
itself with are tested in their package's CI.

A PR description doesn't list the checks CI runs.

### The writing-rules skill evals

Each case in `evals/writing-rules/` asks an agent to write or fix a rule with the
plugin loaded, then grades what it wrote. The skill is guidance and the rules it leads
to have their own evals, so the bar is lower than a judge rule's: CI runs each case 3
times and passes a case scoring 0.8 or more.

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
- `--case <name>` runs one case; `--ablation none` skips the run without the plugin.

### Writing a skill eval case

A grader checks what the agent produced, not what it said or the steps it took.

- The prompt names the rule's id, so the grader knows each file's path.
- A grader reads one file: `focus` or `target` is
  `{ source: file, path: .codeguard/skills/<id>/SKILL.md }`, or the binding or rule eval.
- Structure, such as a `## Why` heading or triggers other than `any`, is a `regex`
  grader. Judgement, such as whether the convention is one declarative sentence, is an
  `llm` grader on that one short file, with PASS and FAIL stated concretely.
- Never grade the trace with an `llm` grader: its judge sees only the first and last 12
  lines of the session, never the files.
- That `codeguard test` ran is a `tool_used` grader on `Bash` whose `input_match` is
  `codeguard test`.
- Nothing in the skill gives a case's answer: no example in `SKILL.md` or `references/`
  shares a case's convention, domain or names. A case the skill answers measures
  copying.

## Changing a rule package

| You change | CI runs | Locally |
|---|---|---|
| A pattern rule, a gate or their tests | `codeguard test`: each rule and gate matches its `invalid` snippets and none of its `valid` ones | `codeguard test` |
| A judge rule's skill, binding or rule eval | `codeguard test` (each case's triggers), then `codeguard eval` on that rule, 20 runs | `codeguard test`, then `codeguard eval --rule <id> --repeat 20` |
| Anything else a judge rule depends on, such as a shared gate | `codeguard eval` on each affected judge rule, 3 runs | `codeguard eval --rule <id> --repeat 3` |

Run both commands at the package root; they cover every ruleset. CI tests with the
latest codeguard release. A merged change is ready to tag: CI has already held each
changed rule to the bar.

The README's [Write a rule package](../README.md#write-a-rule-package) has the rule,
binding and rule eval formats.

## Changing an app

| You change | Checked by | When |
|---|---|---|
| The app's code | the codeguard plugin's Stop hook, `codeguard review`, against the rules in `.codeguard/config.yaml`; an `error` blocks the agent | every time an agent stops |
| The app's code | the review action, `jig-code/codeguard@v0`, on the PR's changed files; an `error` fails the PR | every pull request |
| A rule in the app's own `.codeguard/` | the test action, `jig-code/codeguard/test@v0`: `codeguard test`, and with `eval: true` the judge rules' evals at the bar above | every pull request |

- An app with no rules of its own runs only the review action.
- To change a packaged rule for the app, override or exclude it in
  `.codeguard/config.yaml`; never copy it into `.codeguard/`. The package's CI tests the
  rule.
- Opt into the latest tag of each rule package, and move to a new tag when it ships.
- A finding you think is wrong is fixed in the rule or its cases, never by changing the
  code to get past it.
