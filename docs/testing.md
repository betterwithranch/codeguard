# Testing codeguard

Three different programs run tests around codeguard. Each checks something different,
and they share words like "case", "eval" and "valid". Pick the test by what you
changed (see [Which test for which change](#which-test-for-which-change)), and read a
word as the runner that owns it means it.

## Three runners

| Runner | Owned by | What it runs | What a case is |
|---|---|---|---|
| `pytest` | codeguard's own suite | Python tests of codeguard's code, in `tests/` | a test function |
| `codeguard test` / `codeguard eval` | codeguard, the product | a rule author's rules: rule tests, and judge rules' rule evals | a snippet a pattern rule must or must not match (`rule-tests/<id>-test.yml`), or an edit and the review it should get (`rule-evals/<id>.yaml`) |
| `claude plugin eval` | Anthropic (Claude Code) | an agent doing a task with the plugin loaded, graded afterwards | a task prompt and its graders (`evals/<case>/case.yaml`, `prompt.md`, `graders/*.md`) |

### Whose words are whose

- **codeguard's:** `valid`, `invalid` and `skipped` are the outcomes a rule eval case
  expects. `invalid`: the triggers fire and the judge reports a violation. `valid`: the
  triggers fire and the judge reports none. `skipped`: the triggers don't fire, so the
  judge never sees the edit. Also *rule test*, *rule eval*, *gate*, *trigger* and
  *binding* (see the README's [Write a rule package](../README.md#write-a-rule-package)).
- **Anthropic's:** *grader* and its types (`llm`, `regex`, `tool_used`, `tool_order`,
  `file_exists`, `baseline`), `focus` and `target` (what a grader reads), *arm* and
  *ablation* (with and without the plugin), *scaffold*. `focus:` is a field of
  Anthropic's `llm` grader, not anything in codeguard. See
  [Test plugins with evals](https://code.claude.com/docs/en/plugin-evals.md).
- **Both:** "eval" is `codeguard eval` (judge rule cases) or `claude plugin eval` (agent
  tasks). "Case" is a rule eval case or a plugin eval case. The writing-rules skill
  evals ask an agent to *write* rule eval cases, so both meanings meet in one test.

## In this repository

codeguard is the product, so its own tests check the CLI, the hooks and the judge, not
anyone's rules. `codeguard test` and `codeguard eval` are features it ships for rule
authors; pytest tests those features with fixture rules.

| Test | Run | It checks | Calls a model | In CI |
|---|---|---|---|---|
| Unit and integration tests, `tests/` | `uv run pytest` | the CLI (`review`, `test`, `eval`), config loading, triggers, the hooks, the `bin/codeguard` launcher | no | every push |
| LLM tests, `tests/` marked `llm` | `uv run pytest -m llm -n 8` | the judge's instructions, request and tools still get the right verdicts from a real model; fixtures are the rule eval cases in `evals/judge/python/` | yes, each case 3 times (`--llm-runs 20` before merging a judge change) | every push |
| Lint, format, imports and types | `uv run ruff check`, `uv run ruff format --check`, `uv run lint-imports`, `uv run basedpyright` | style, import boundaries, types | no | every push |
| writing-rules skill evals, `evals/writing-rules/` | `claude plugin eval` | the writing-rules skill leads an agent to a good rule, or to a better tool than codeguard | yes: the agent, and a judge per `llm` grader | no; run by hand |
| Dogfooding | the Stop hook in this clone, and the `codeguard-rules` CI job | codeguard's own code against the codeguard-rules rules it opts into in `.codeguard/config.yaml` | Stop hook: for judge rules; CI: no (`dry-run: true`) | the CI job, on pull requests |

### Which test for which change

| You change | Run |
|---|---|
| CLI, config, triggers, hooks or launcher code | `uv run pytest`, and the lint and type checks |
| The judge's prompt, request or tools | the above, then `uv run pytest -m llm -n 8 --llm-runs 20` |
| A fixture in `evals/judge/` | `uv run pytest` (it checks each case's triggers), then `uv run pytest -m llm -n 8`. Follow the writing-rules skill when a case flips |
| `skills/writing-rules/` | `claude plugin eval` on `evals/writing-rules/` (below) |
| A case in `evals/writing-rules/` | that case alone: `claude plugin eval . --case <name>`, with the options below |

A rule that misjudges codeguard's own code is fixed in codeguard-rules, not here; see
[In a rule package](#in-a-rule-package-codeguard-rules).

### The writing-rules skill evals

Each case under `evals/writing-rules/` is a task prompt, a scaffold script that seeds a
git repository from the case's `files/`, and graders. `claude plugin eval` runs each
case with the plugin loaded and again without it, 3 times each by default, and scores
the graders.

```sh
claude plugin eval . --scaffold --allow-tools Write Edit Bash --runs 3 --trust-plugin --no-publish --keep-temp
```

- `--scaffold` runs each case's `place-files.sh`; `--trust-plugin` skips the first-run
  trust prompt; `--no-publish` keeps the HTML report local.
- `--ablation none` runs only the with-plugin arm, which halves the cost when you don't
  need the comparison.
- `--keep-temp` keeps each run's workspace and prints its path. Open the files the agent
  wrote there to check a grader's verdict against them.
- Granting `Bash` runs every command in Claude Code's sandbox. On Linux, install
  `bubblewrap` and `socat` first. The sandbox denies writes under `/tmp`, where the eval
  puts each run, so set `TMPDIR` to a directory outside `/tmp`.
- The graders that expect `codeguard test` to pass need `codeguard` to run inside the
  sandbox, which has no network and doesn't put the plugin's `bin` on `PATH`.

What a grader reads decides what it can check. An `llm` grader with `focus: trace` sees
only the first 12 and the last 12 lines of the session, and a run is usually far longer,
so it doesn't see the files the agent wrote. To grade the rule itself, point a grader at
`{ source: file, path: <path> }`: a `regex` grader for structure, an `llm` grader for
judgement on one short file. Anthropic's guide says to keep `llm` graders for short
outputs and grade what the agent produced, not the path it took.

## In a rule package: codeguard-rules

A rule package tests its rules with `codeguard test` and `codeguard eval`. It has no
pytest suite and no agent evals.
[betterwithranch/codeguard-rules](https://github.com/betterwithranch/codeguard-rules)
has the rulesets `general` and `python`.

| Test | Lives in | Run | It checks | Calls a model | In CI |
|---|---|---|---|---|---|
| Rule tests: pattern rules and gates | `<ruleset>/rule-tests/<id>-test.yml`, snapshots in `__snapshots__/` | `codeguard test` | each rule or gate matches its `invalid` snippets and none of its `valid` ones | no | every push |
| Rule eval triggers | `<ruleset>/rule-evals/<id>.yaml` | `codeguard test` | each judge rule's triggers fire on its `valid` and `invalid` cases and not on its `skipped` ones | no | every push |
| Rule evals: judge verdicts | same files | `codeguard eval` | each case gets its expected review from the binding's model | yes | 3 runs each, only the judge rules a change can affect |
| Release bar for a judge rule | same files | `codeguard eval --rule <id> --repeat 20` | each case passes 20 runs of 20 | yes | no; run by hand before tagging |

The package's CI checks out the codeguard tag in its `CODEGUARD_REF`. A project gets the
package's rules by naming a tag in `.codeguard/config.yaml`, and codeguard checks the
package's `codeguard` version range. The README's
[Which test to write](../README.md#which-test-to-write) has the same table for any rule.

## In an app: otter

An app uses codeguard to check its own code. Its rules come mostly from a package, and it
tests only the rules it writes. otter opts into codeguard-rules' `general` ruleset's
`dry` judge rule and a list of `python` pattern rules, and has one pattern rule of its
own, `django-model-inherits-base-model`.

| Check | Run by | It checks | Calls a model | When |
|---|---|---|---|---|
| Review at agent Stop | the codeguard plugin's Stop hook, enabled in `.claude/settings.json` | the session's changes against otter's rules; an error blocks the agent | for judge rules | every time an agent stops |
| Review in CI | the `jig-code/codeguard@v0` action | the pull request's changed files against the same rules | yes | every pull request |
| Rule tests for otter's own rule | the same action step, or `codeguard test` locally | `django-model-inherits-base-model` matches its snippets in `.codeguard/rule-tests/` | no | every pull request |

otter doesn't test the package's rules; codeguard-rules does that before it tags a
release.
