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
          no-dead-code:
            paths: ["src/**/*.py"]
            severity: warning
```

- Only the listed rulesets run.
- `exclude` turns rules off.
- `rules.<id>` overrides a rule's `paths` or `severity`, and a judge rule's `model`.
- `severity` on the ruleset sets every rule in it, including rules the package adds
  later; a rule's own `severity` override wins. Only `error` blocks Stop and fails CI,
  so `severity: warning` trials a package: its findings print without blocking. A
  failed judge call takes its rule's severity too.
- An unknown ruleset or rule id is an error.
- `kind: path` with `path: ../my-rules` in place of `git` uses a local package, for
  working on one.

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
```

Each ruleset is a directory with the same layout as a project's `.codeguard/`:

```
python/
  rules/pattern/<id>.yml               # ast-grep rules
  rule-tests/pattern/<id>-test.yml     # their tests and __snapshots__/
  skills/<id>/SKILL.md                 # judge rules
  bindings/<id>.yaml                   # skill and default paths
  rule-evals/<id>-eval.yml             # judge rule evals
  rule-evals/<id>/                     # their case files
```

codeguard rejects anything else in a ruleset directory, and in `.codeguard/` anything
else but `config.yaml` and `lock.yaml`, so a rule moves between a project and a package unchanged.

A binding's `skill` path starts at the package root (`skill: python/skills/<id>`). A
judge rule's id is its skill's directory name. Rule ids are unique within a ruleset.

A judge rule eval lists case files in `rule-evals/<id>/`:

```yaml
id: enum-usage
valid: [literal_severity.py]     # the judge must report no violation
invalid: [shipment_status.py]    # the judge must report one at the confidence threshold
```

The judge reads each case from that directory with the binding's model, so name case
files for their code, not their expected result. Verdicts are cached like reviews, so
only changed cases and skills call Claude again.

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

Run `codeguard test` at the package root for every ruleset's pattern tests, and
`codeguard eval` for its judge evals. Tag
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
directory: the uncommitted and untracked files, whoever changed them and however. An
error blocks the stop, and the agent sees the diagnostics. If the agent stops again with
the same errors, the stop goes through, so the agent can ask you about them. It runs the `codeguard` the
installer put on your PATH, the same one you run from the command line.

The judge rates its confidence in each violation from 0 to 1. An error below the
threshold is reported as a warning and doesn't block. The threshold defaults to 0.9; set
it in `.codeguard/config.yaml`:

```yaml
confidence_threshold: 0.8
```

Each binding judges with `claude-sonnet-5-5` unless it sets `model`:

```yaml
skill: .claude/skills/responsibility-placement
paths: ["app/**/*.py"]
model: claude-haiku-5-5
```

## Telemetry

Set `LOGFIRE_TOKEN` to a Logfire write token and codeguard sends a trace of each run.
Without it, codeguard sends nothing. Set it where the agent runs: your shell profile, or
`env` in `~/.claude/settings.json`.

- `claude judges {rule} on {file}`: one span per Claude call, with `model`, `num_turns`,
  `duration_ms`, `cost_usd`, `input_tokens`, `output_tokens`, `cache_read_input_tokens`,
  `cache_creation_input_tokens` and `thinking_tokens`.
- `judge {rule} on {file}`: one span per rule and file, with `cache_hit` and `violations`.
- `review {repository}`: `files`, `diagnostics` and `errors`.

In CI, pass the token as the action's `logfire-token` input.

## CLI

From the project:

```sh
codeguard review              # uncommitted changes
codeguard review --base main  # changes since the merge base with main
codeguard review --all        # every file
codeguard review --latest     # newest tag in each package range, not the lock
codeguard test                # pattern rule tests
codeguard test --update-all   # the same, regenerating snapshots
codeguard eval                # judge rule evals; calls Claude
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
