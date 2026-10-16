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
```

The action reviews the files changed since the merge base with the PR's base branch,
then runs the rule tests.

`v0` moves to each 0.x release, so the plugin and the action update together with no
project edits. A release that breaks the rule format starts `v1`.

### Rules

Rules live in the project, under `.codeguard/`. The plugin's `writing-rules` skill
guides an agent through writing a rule and its tests.

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
error blocks the stop, and the agent sees the diagnostics. It runs the `codeguard` the
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

## CLI

From the project:

```sh
codeguard review              # uncommitted changes
codeguard review --base main  # changes since the merge base with main
codeguard review --all        # every file
codeguard test                # rule tests
codeguard test --update-all   # rule tests, regenerating snapshots
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
