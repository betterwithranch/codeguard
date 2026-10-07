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

In Codex, trust codeguard's hook in `/hooks`.

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
uv run --directory plugins/codeguard pytest
```

Run the CLI from this checkout. `--editable` links the tool to the source, so edits
apply on the next run; reinstall only after changing dependencies:

```sh
uv tool install --editable plugins/codeguard
```

Point a project's hooks at this checkout.

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
3. Commit, then tag the release, move `v0` to it, and push both:
   ```sh
   git tag v<version>
   git tag --force v0
   git push origin v<version>
   git push --force origin v0
   ```
