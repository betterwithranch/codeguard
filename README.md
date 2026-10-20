# codeguard

Makes coding agents follow your project's coding conventions. Each convention is
written once, in the project, and applies wherever code is written or reviewed: while
Claude Code or Codex works, and in CI.

codeguard adds the checks a project's linters can't do. It doesn't replace or wrap
them.

## Add codeguard to a project

### Claude Code

In the project's `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "codeguard": {
      "source": {
        "source": "github",
        "repo": "betterwithranch/codeguard",
        "ref": "v0"
      }
    }
  },
  "enabledPlugins": {
    "codeguard@codeguard": true
  }
}
```

### Codex

List the plugin in the project's `.agents/plugins/marketplace.json`:

```json
{
  "name": "<project>",
  "plugins": [
    {
      "name": "codeguard",
      "source": {
        "source": "git-subdir",
        "url": "https://github.com/betterwithranch/codeguard.git",
        "path": "plugins/codeguard",
        "ref": "v0"
      }
    }
  ]
}
```

### CI

```yaml
on: pull_request

jobs:
  codeguard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
      - uses: betterwithranch/codeguard@v0
        with:
          claude-code-oauth-token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
```

The action reviews the files changed since the merge base with the PR's base branch,
then runs the rule tests. The judge needs the token; create it with `claude setup-token`
and store it as a repository secret.

`v0` moves to each 0.x release, so the plugin and the action update together with no
project edits. A release that breaks the rule format starts `v1`.

### Rules

A project's own rules live under `.codeguard/`. The plugin's `writing-rules` skill
guides an agent through writing a rule and its tests.

A rule is one of two kinds:

- A **pattern rule** is an ast-grep rule. It matches code by its syntax tree.
- A **judge rule** is a skill that Claude reads each changed file against.

Write a pattern rule whenever ast-grep can check the convention: it runs in
milliseconds, costs nothing, and gives the same answer every time. A judge rule costs a
Claude call for every changed file it matches. Use one only when the convention needs
judgment, such as whether a name matches what the code does.

A project can also opt into rulesets from rule packages:

```yaml
# .codeguard/config.yaml
packages:
  - kind: versioned
    git: https://github.com/betterwithranch/codeguard-rules.git
    version: ">=0.2,<1"
    rulesets:
      python:
        exclude: [no-del-param]
        rules:
          names-match-behavior:
            paths: ["src/**/*.py"]
            severity: warning
```

- Only the listed rulesets run.
- `include` lists the only rules that run, pattern and judged; rules the package adds
  later stay off. `exclude` turns rules off. Set one or the other.
- `rules.<id>` overrides a rule's `paths`, `exclude_paths` or `severity`, and a judge
  rule's `model`. `exclude_paths: []` brings back the files its binding leaves out.
- `severity` on the ruleset sets every rule in it, including rules the package adds
  later; a rule's own `severity` override wins. Only `error` blocks Stop and fails CI,
  so `severity: warning` trials a package: its findings print without blocking. A
  failed judge call takes its rule's severity too.
- An unknown ruleset or rule id is an error.
- `kind: path` with `path: ../my-rules` in place of `git` uses a local package, for
  working on one. To use it without editing the committed config, put that config in a
  gitignored file such as `codeguard.local.yaml` and set
  `CODEGUARD_CONFIG=codeguard.local.yaml`. The path is relative to the repository root.

Diagnostics name a packaged rule by package, ruleset and id:
`betterwithranch/python/no-del-param`.

A git package takes a `version` range (`kind: versioned`) or a `ref` (`kind: git`):

- `version` follows the newest tag in the range. `codeguard update` writes that tag to
  `.codeguard/lock.yaml`; commit it. Local reviews use the locked tag until the next
  update. CI reviews (`codeguard review --latest`, which the action runs) use the newest
  tag in the range and ignore the lock.
- `ref` pins a tag or commit everywhere. `codeguard update` leaves it alone.

codeguard fetches each tag once into `~/.cache/codeguard/packages` and reuses it, so a
`ref` must not be a branch.

A project runs one ast-grep version for all its rules: codeguard's own, or the version
`.codeguard/config.yaml` sets, which runs through `uv tool run`:

```yaml
ast-grep: 0.45.3
```

codeguard fails when that version is outside a package's `ast-grep` range.

For a private package in CI, pass a token that can read it:

```yaml
      - uses: betterwithranch/codeguard@v0
        with:
          claude-code-oauth-token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          packages-token: ${{ secrets.CODEGUARD_PACKAGES_TOKEN }}
```

## Write a rule package

A package is a git repo with a `codeguard-package.yaml` at its root:

```yaml
name: betterwithranch
rulesets: [python]
ast-grep: ">=0.45,<0.46"   # the ast-grep versions its pattern rules work with
codeguard: ">=0.2"         # the codeguard versions that can load it
```

Each ruleset is a directory with the same layout as a project's `.codeguard/`:

```
python/
  rules/pattern/<id>.yml     # ast-grep rules
  gates/<id>.yml             # ast-grep rules that gate judge rules
  rule-tests/<id>-test.yml   # tests for both, with __snapshots__/
  skills/<id>/SKILL.md       # judge rules
  bindings/<id>.yaml         # skill and default paths
  rule-evals/<id>-eval.yml   # judge rule evals
```

Pattern rule tests in `rule-tests/pattern/`, the old layout, still run. codeguard
rejects anything else in a ruleset directory, and in `.codeguard/` anything
else but `config.yaml` and `lock.yaml`, so a rule moves between a project and a package unchanged.

A binding's `skill` path starts at the package root (`skill: python/skills/<id>`). A
judge rule's id is its skill's directory name. Rule and gate ids are unique within a
ruleset.

A binding applies a rule to the files that match `paths` and none of `exclude_paths`. A
judge rule's binding names its `skill`:

```yaml
skill: python/skills/names-match-behavior
paths: ["**/*.py"]
exclude_paths: ["**/test_*.py", "**/*_test.py", "**/tests/**/*.py", "**/conftest.py"]
```

A pattern rule's binding names its `rule`. A pattern rule without one runs on every file
in its language:

```yaml
rule: no-comments-in-tests
paths: ["**/test_*.py", "**/*_test.py", "**/tests/**/*.py", "**/conftest.py"]
```

Put a glob in the binding, never in ast-grep's `files` or `ignores`, so a project can
change it. The exception is a file name that is the convention itself, like
`all-only-in-init` skipping `__init__.py`.

A judge rule's binding lists `triggers`: the code its violations need. A binding without
`triggers` gets `[any]`, so packages written before triggers still load. The judge
skips a changed file whose changed lines fall inside none of it. Gate on where a
violation appears, not on the rule's topic:

```yaml
skill: python/skills/mock-only-at-boundary
paths: ["**/test_*.py", "**/*_test.py", "**/tests/**/*.py", "**/conftest.py"]
triggers: [mock-use]
```

A trigger is a gate or a built-in change kind. A gate is an ast-grep rule in
`<ruleset>/gates/<id>.yml`, tested like a pattern rule by `rule-tests/<id>-test.yml`
(`invalid` cases are code the gate matches):

```yaml
id: mock-use
language: python
rule:
  kind: call
  has: {field: function, regex: "(^|\\.)(Mock|MagicMock|patch)$"}
```

A file touches a trigger when a changed line falls inside a node it matches. A new file
touches every trigger it matches. A rule that needs every change says `triggers: [any]`;
`codeguard test` warns on `any`, `code`, `function-body` and `function-signature`. The
built-in kinds are `comment`, `docstring`, `import`,
`function-signature`, `function-body`, `test-function`, `fixture`, `helper-function`,
`class-header`, `class-attribute`, `module-statement`, `annotation`, `call`,
`control-flow`, `return-yield`, `collection-literal`, `string-literal`,
`number-literal`, `attribute-access`, `subscript`, `conditional-expression`,
`membership-test`, `assert` and `raise`, plus three from the diff:
`definition-added-or-removed` (a def or class name added or removed), `code` (any line
that is not only a comment or docstring) and `any`. The syntax table in
`src/codeguard/syntax/languages/` defines each kind as an ast-grep rule.

A judge rule's eval, `rule-evals/<id>-eval.yml`, lists edits. Each is a `before` (left
out for a new file), an `after` and a `file` (default `module.py`), which must match the
binding's paths:

```yaml
id: one-concept-per-module
invalid:                         # the triggers fire and the judge reports a violation
  - before: |
      class Order:
          pass
    after: |
      class Order:
          pass


      class Invoice:
          pass
valid:                           # the judge reports no violation
  - after: |
      class Order:
          pass
skipped:                         # the triggers don't fire, so the judge never sees it
  - before: |
      class Order:
          total = 1
    after: |
      class Order:
          total = 2
```

`codeguard test` checks the triggers on every case, with no model call. It commits each
`before` to a scratch repository, writes each `after`, and classifies the diff the way a
review does. An `invalid` case fails when the triggers miss the change, and a `skipped`
case fails when they fire. The message lists the kinds the change touches. Narrow a gate
until a `skipped` case passes, and keep every `invalid` case passing.

`codeguard eval` judges the file after each `invalid` and `valid` edit with the
binding's model. An `invalid` case needs a violation at the confidence threshold, on a
line with one of the rule's `triggers`; the message lists the kinds on that line. A
`valid` case needs no violation. Verdicts are cached like reviews, so only changed cases
and skills call Claude again.

`codeguard eval` also fails a judge rule with no eval that has an `invalid` case.

The eval also judges each case with its names renamed, without comments, and with its
imports reordered, and each must keep its expected result. A rule whose verdict depends
on one of these lists it in its binding:

```yaml
skill: python/skills/naming
paths: ["**/*.py"]
disable_skips: [renames]   # also: comments, imports
```

Variants exist for Python files. Other languages get the original case only.

`codeguard eval --repeat 3` judges each case three times. Runs after the first skip the
cache, so an unstable verdict shows up as a failing run.

### Which test to write

A project tests the rules in its `.codeguard/` the same way a package does.

| You add or change | Write | It checks | Run | Calls Claude |
|---|---|---|---|---|
| A pattern rule or gate | `rule-tests/<id>-test.yml` | the rule matches its `invalid` cases and none of its `valid` ones | `codeguard test` | no |
| A judge rule's skill or `triggers` | `rule-evals/<id>-eval.yml` | the triggers fire on each `invalid` edit and on no `skipped` edit | `codeguard test` | no |
| | | the judge finds a violation after each `invalid` edit and none after a `valid` one | `codeguard eval` | yes |

Run `codeguard test` and `codeguard eval` at the package root; they cover every ruleset. Tag
releases `v<major>.<minor>.<patch>` so `codeguard update` finds them.
[betterwithranch/codeguard-rules](https://github.com/betterwithranch/codeguard-rules) is
an example.

## Setup

Once the project has codeguard, everyone working in it runs the installer, then starts
a new agent session. Rerun it to upgrade.

```sh
curl -LsSf https://raw.githubusercontent.com/betterwithranch/codeguard/v0/install.sh | sh
```

In Claude Code, install the plugin. Project settings enable it but don't install it.

```sh
claude plugin install codeguard@codeguard --scope project
```

In Codex, trust codeguard's hooks in `/hooks`.

## What the hooks check

When an agent or subagent stops, the hook runs `codeguard review` in its working
directory: the uncommitted and untracked files, whoever changed them and however. It runs
the `codeguard` the installer put on your PATH, the same one you run from the command
line, through `uv`. Claude Code and Codex get the same behaviour.

- An error blocks the stop, and only errors reach the agent. It blocks every time the
  agent stops until the errors are fixed. When the agent can't fix one, interrupt it
  and fix the rule.
- Everything else goes to you, not the agent: warnings, findings below the confidence
  threshold, and rules the judge couldn't check (a failed `claude` call or the time
  limit). The hook passes `--judge-errors-as-warnings`, since the agent can't fix those;
  CI still fails on them.
- If the review crashes or `codeguard` isn't on your PATH, you see why, and the stop
  goes through.

The judge rates its confidence in each violation from 0 to 1. An error below the
threshold is reported as a warning, with its confidence, and doesn't block. The
threshold defaults to 0.9; set it in `.codeguard/config.yaml`:

```yaml
confidence_threshold: 0.8
```

A judged diagnostic prints its confidence, so a warning shows how far it fell short:

```
app/orders.py:12: warning no-pre-derived-arguments: The call passes both lines and the context they come from. (confidence 0.70) [3f1c9a2b7d40]
```

A review stops judging after 5 minutes. Each rule and file it didn't judge gets a
`judge_error` diagnostic at the rule's severity, so an unchecked `error` rule fails the
review. A failed judge call does the same.
The GitHub Action stops the review 2 minutes after the limit, in case it hangs. Change the
limit in `.codeguard/config.yaml`:

```yaml
review_time_limit_minutes: 10
```

Each binding judges with `claude-sonnet-5-5` unless it sets `model`:

```yaml
skill: .claude/skills/responsibility-placement
paths: ["app/**/*.py"]
model: claude-haiku-5-5
```

### Judge with Gemini on Google Cloud

By default the judge runs `claude -p`. To judge with Gemini on Google Cloud (Vertex AI)
instead, set `judge` in `.codeguard/config.yaml`:

```yaml
judge:
  provider: gemini         # default: claude-cli
  model: gemini-3.8-flash  # replaces every rule's model
  project: my-project      # default: GOOGLE_CLOUD_PROJECT
  location: global         # default: GOOGLE_CLOUD_LOCATION
```

Gemini reads the working directory through read-only `read_file`, `grep` and `glob`
tools, limited to the repository, and reports through a `submit_verdict` tool that
takes the same verdict schema as Claude. Verdicts are cached per provider and model,
so switching providers doesn't reuse Claude's verdicts.

codeguard signs in with Application Default Credentials. Set it up once per project:

1. Enable the Vertex AI API:
   `gcloud services enable aiplatform.googleapis.com --project my-project`.
2. Create a service account with the Vertex AI User role:
   ```sh
   gcloud iam service-accounts create codeguard --project my-project
   gcloud projects add-iam-policy-binding my-project \
     --member serviceAccount:codeguard@my-project.iam.gserviceaccount.com \
     --role roles/aiplatform.user
   ```
3. Give codeguard the credentials. On your machine, `gcloud auth application-default login`
   is enough. Elsewhere, create a key with
   `gcloud iam service-accounts keys create key.json --iam-account codeguard@my-project.iam.gserviceaccount.com`
   and set `GOOGLE_APPLICATION_CREDENTIALS` to its path. In GitHub Actions, use
   `google-github-actions/auth` before the codeguard action.

Where a proxy adds credentials to requests, as Claude Code cloud environments' network
secrets do, use an API key bound to the service account instead: create it under
**APIs & Services → Credentials** with only Agent Platform API allowed, have the proxy send
it as the `x-goog-api-key` header to `aiplatform.googleapis.com`, and set
`GOOGLE_API_KEY=proxy-injected` with `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`,
`project` and `location` unset. The key identifies the project.

## Telemetry

Set `LOGFIRE_TOKEN` to a Logfire write token and codeguard sends a trace of each run.
Without it, codeguard sends nothing. Set it where the agent runs: your shell profile, or
`env` in `~/.claude/settings.json`.

- `claude judges {rule} on {file}`: one span per Claude call, with `model`, `num_turns`,
  `duration_ms`, `cost_usd`, `input_tokens`, `output_tokens`, `cache_read_input_tokens`,
  `cache_creation_input_tokens` and `thinking_tokens`.
- `gemini judges {rule} on {file}`: one span per Gemini judgement, with `model`,
  `num_turns`, `input_tokens`, `output_tokens`, `cache_read_input_tokens` and
  `thinking_tokens`, summed over its turns.
- `judge {rule} on {file}`: one span per rule and file, with `cache_hit` and `violations`.
- `review {repository}`: `files`, `diagnostics`, `errors`, and `host` (the caller passed
  with `--host`, such as `claude-code` or `codex`).

In CI, pass the token as the action's `logfire-token` input.

## CLI

From the project:

```sh
codeguard review              # uncommitted changes
codeguard review --base main  # changes since the merge base with main
codeguard review --all        # every file
codeguard review --latest     # newest tag in each package range, not the lock
codeguard review --dry-run    # pattern rules, then count the judge calls; calls no model
codeguard review --format json  # one JSON object with every diagnostic
codeguard review --judge-errors-as-warnings  # judge calls that couldn't complete don't fail
codeguard test                # pattern rule and gate tests, and judge rule eval triggers
codeguard test --update-all   # the same, regenerating snapshots
codeguard eval                # judge rule evals; calls the configured judge
codeguard update              # lock each package range to its newest tag
```

## Working on codeguard

Tests:

```sh
uv run pytest
```

Judge evals run the real `claude` CLI against fixture skills and cost tokens. Run them
after changing the judge's instructions, request, model or tools:

```sh
uv run evals/judge_eval.py              # each case once
uv run evals/judge_eval.py --repeat 5   # pass rate over 5 runs per case
uv run evals/judge_eval.py --gemini gemini-3.8-flash  # a Gemini model instead of Claude
```

Run the CLI from this clone. `--editable` links the tool to the source, so edits
apply on the next run; reinstall only after changing dependencies:

```sh
uv tool install --editable .
```

Point a project's hooks at this clone.

- Claude Code: in the project's `.claude/settings.local.json`, declare the marketplace
  as a directory. It replaces the GitHub entry by name, for you only.
  ```json
  {
    "extraKnownMarketplaces": {
      "codeguard": {
        "source": { "source": "directory", "path": "/path/to/codeguard" }
      }
    }
  }
  ```
  Python edits apply on the next hook run. Edits to `hooks.json` or `plugin.json`
  need `/reload-plugins`.
- Codex:
  ```sh
  codex plugin marketplace add /path/to/codeguard
  codex plugin add codeguard@codeguard
  ```
  Run `codex plugin add` again after each edit.

## Release

1. Bump `version` in `plugins/codeguard/.claude-plugin/plugin.json` and
   `plugins/codeguard/.codex-plugin/plugin.json`.
2. Validate:
   ```sh
   claude plugin validate .
   claude plugin validate plugins/codeguard
   ```
3. Commit, then tag the release and push the tag:
   ```sh
   git tag v<version>
   git push origin v<version>
   ```
   The release workflow checks the tag matches both manifests' `version`, then moves
   the major tag (`v0`) to the release.
