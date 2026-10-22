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

The review uses the package tags in `.codeguard/lock.yaml`, the same as a local review,
so run `codeguard update` and commit the lock. For now, a package range the lock
doesn't have uses the newest tag in the range; a later release will require the lock.

A judge call that couldn't complete fails the review. To merge the PR anyway, add the
`codeguard-allow-judge-errors` label to it. The action then passes
`--judge-errors-as-warnings` to the review, so those calls print as warnings, and rule
violations still fail. The label doesn't cover the `eval` input's `codeguard eval`,
which still fails on them.

Re-running the job doesn't pick up the label: a re-run reuses the event that started
the workflow, with the PR's labels at that time. For adding the label to start a new
review, and removing it to start a strict one, trigger on `labeled` and `unlabeled` for
that label only. Without the `if`, every label added to a PR re-runs the whole review and
its judge calls.

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened, labeled, unlabeled]

jobs:
  codeguard:
    if: >-
      (github.event.action != 'labeled' && github.event.action != 'unlabeled')
      || github.event.label.name == 'codeguard-allow-judge-errors'
```

`v0` moves to each 0.x release, so the plugin and the action update together with no
project edits. A release that breaks the rule format starts `v1`.

### Run formatters first

Format code before codeguard reviews it. A formatter that runs after the review changes
code that was never reviewed, and it changes the file, so the next review can't reuse
the cached verdict: it calls the model again and can reach a different verdict.

- In Claude Code, format each file when it's edited, in a `PostToolUse` hook on `Edit`
  and `Write`, not in a `Stop` hook: hooks on the same event run in parallel, so a
  formatter there can run after codeguard's review.
- In CI, run the format check before the codeguard step.
- Format an unformatted codebase in a commit of its own. Reformatted lines are changed
  lines, so formatting inside a feature change sends every one of them to the judge.

codeguard ignores added and removed blank lines, which change nothing in any language.
Other whitespace can change meaning, such as indentation in Python, so codeguard
leaves it to the formatter.

### Rules

A project's own rules live under `.codeguard/`. The plugin's `writing-rules` skill
guides an agent through writing a rule and its tests.

A rule is one of two kinds:

- A **pattern rule** is an ast-grep rule. It matches code by its syntax tree.
- A **judge rule** is a skill that Claude judges each change to a file against.

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
- `rules.<id>` overrides a rule's `paths`, `exclude_paths` or `severity`.
  `exclude_paths: []` brings back the files its binding leaves out. A judge rule's
  model can't be overridden: its evals pass on the model its binding names.
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
  `.codeguard/lock.yaml`; commit it. Local and CI reviews use the locked tag until the
  next update, so a commit gets the same rules everywhere. A range the lock doesn't have
  uses the newest tag in the range, until a later release requires the lock.
  `codeguard review --latest`
  uses the newest tag in the range and ignores the lock, for trying a new version
  locally.
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
  bindings/<id>.yaml         # a rule's paths; a judge rule's triggers and model
  rule-evals/<id>.yaml       # rule evals: test cases for judge rules
```

Pattern rule tests in `rule-tests/pattern/`, the old layout, still run. codeguard
rejects anything else in a ruleset directory, and in `.codeguard/` anything
else but `config.yaml` and `lock.yaml`, so a rule moves between a project and a package unchanged.

### Bindings

A binding applies a rule to the files that match `paths` and none of `exclude_paths`.
A pattern rule's binding names its `rule`. A pattern rule without one runs on every file
in its language:

```yaml
rule: no-comments-in-tests
paths: ["**/test_*.py", "**/*_test.py", "**/tests/**/*.py", "**/conftest.py"]
```

Put a glob in the binding, never in ast-grep's `files` or `ignores`, so a project can
change it. The exception is a file name that is the convention itself, like
`all-only-in-init` skipping `__init__.py`. Rule and gate ids are unique within a
ruleset.

### Judge rules

A judge rule is three files, all named by its id:

```
python/
  skills/<id>/SKILL.md       # the convention the judge checks
  bindings/<id>.yaml         # where it runs, when it runs, and the model that judges it
  rule-evals/<id>.yaml       # the rule eval: edits and the review each should get
```

The rule eval is what makes a rule trustworthy. It shows the rule flags the edits it
should and passes the ones it should, on the model that will judge it in reviews. That
model is the binding's, and nothing overrides it: a project can't switch a rule to a
model its rule eval never passed on. To move a rule to another model, change its
binding and pass its rule eval again.

#### The binding

A judge rule's binding names its `skill`, from the package root, and where and when it
runs:

```yaml
skill: python/skills/mock-only-at-boundary
paths: ["**/test_*.py", "**/*_test.py", "**/tests/**/*.py", "**/conftest.py"]
triggers: [mock-use]
```

`provider` and `model` are optional. A binding that leaves them out is judged with
`claude-sonnet-5-5` through the `claude` CLI. Set them only to judge the rule with
something else:

```yaml
provider: gemini                  # default: claude-cli
model: gemini-3.1-pro-preview     # default: claude-sonnet-5-5; gemini needs one
```

A judge rule's id is its skill's directory name.

`triggers` names the code the rule's violations need. The judge skips a changed file
whose changed lines fall inside none of it, so a narrow trigger saves judge calls. Gate
on where a violation appears, not on the rule's topic. A binding without `triggers`
gets `[any]`, so packages written before triggers still load.

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
touches every trigger it matches. A blank line is never a changed line, in any language:
adding or removing blank lines fires no trigger, isn't judged and leaves no diagnostic,
so the blank line before a new method doesn't make its class part of the change. A rule
that needs every change says `triggers: [any]`; `codeguard test` warns on `any`, `code`,
`function-body` and `function-signature`. The built-in kinds are `comment`, `docstring`,
`import`, `function-signature`, `function-body`, `test-function`, `fixture`, `helper-function`,
`class-header`, `class-attribute`, `module-statement`, `annotation`, `call`,
`control-flow`, `return-yield`, `collection-literal`, `string-literal`,
`number-literal`, `attribute-access`, `subscript`, `conditional-expression`,
`membership-test`, `assert` and `raise`, plus three from the diff:
`definition-added-or-removed` (a def or class name added or removed), `code` (any line
that is not only a comment or docstring) and `any`. The syntax table in
`src/codeguard/syntax/languages/` defines each kind as an ast-grep rule.

#### The rule eval

`rule-evals/<id>.yaml` (or `<id>.yml`, but not both) lists cases. Each case is an edit and
the review it should get:

- `name`: what the edit does, unique in the file.
- `inputs`: the edit. `before` is the file before it (leave it out for a new file),
  `after` is the file after it, and `file` is its path (default `module.py`), which
  must match the binding's paths. `unchanged` maps the path of each other file the
  edit needs, such as a package's `__init__.py`, to its text; the judge can read them,
  but they aren't part of the change, and can't include `file`. Every path is relative
  to the repository root, with no `..` or `./`, and outside `.git`.
- `expected_output`: the review's `outcome`, one of:
  - `invalid`: the triggers fire and the judge reports a violation;
  - `valid`: the triggers fire and the judge reports none;
  - `uncertain`: the judge reports a violation below the confidence threshold;
  - `skipped`: the triggers don't fire, so the judge never sees the edit.

```yaml
cases:
  - name: adds a second class
    inputs:
      before: |
        class Order:
            pass
      after: |
        class Order:
            pass


        class Invoice:
            pass
    expected_output:
      outcome: invalid
  - name: defines one class
    inputs:
      after: |
        class Order:
            pass
    expected_output:
      outcome: valid
  - name: changes an attribute
    inputs:
      before: |
        class Order:
            total = 1
      after: |
        class Order:
            total = 2
    expected_output:
      outcome: skipped
```

`expected_output` can also list the exact `violations`, each with a `line`,
`confidence`, `message` and `kinds`. A case that leaves them out checks only the
outcome. The file holds nothing else: codeguard decides how a case is judged and
checked, so every rule is held to the same bar.

Every judge rule needs at least one `invalid` case. Give it `valid` cases for the
nearby code it must not flag, and `skipped` cases for the changes its triggers should
ignore.

#### Test a judge rule

1. `codeguard test` checks the triggers on every case, with no model call. It commits
   each `before` and `unchanged` file to a scratch repository, writes each `after`, and
   classifies the diff the way a review does. Fix the triggers until it passes.
2. `codeguard eval` reviews every case with the binding's model, the way
   `codeguard review` would. Fix the skill, or the case, until it passes.
3. `codeguard eval --repeat 3` reviews each case three times, so an unstable verdict
   shows up as a failing run, named like `adds a second class [2/3]`. A rule is ready
   when every case passes all three runs.

Both take a package directory, so `codeguard eval path/to/package` evaluates a package
outside the current repository. An eval tests the rule, not the code, so it never uses
the verdict cache: every run calls the model. With a Logfire token each rule's run is
also in Logfire.

#### What makes a case fail

`codeguard test` fails a case when:

- its `file` is outside the binding's paths;
- its edit changes no code;
- it expects `invalid`, `uncertain` or `valid` but the triggers miss the change, since a
  review would never judge it. The message lists the kinds the change touches;
- it expects `skipped` but the triggers fire. Narrow the gate until it passes, and keep
  every other case passing.

`codeguard eval` fails a case when:

- the review's outcome, or its violations when the case lists them, differ from
  `expected_output`. The message shows what the judge reported;
- it expects `invalid` and the judge flags only lines outside the triggers. Reviews
  would miss that violation, so the message lists the kinds on those lines to add to
  `triggers`;
- the judge call fails, such as a quota error that outlasts the provider's retries. The
  other cases still run, so a passing eval means every case was judged.

`codeguard eval` also fails a judge rule with no `invalid` case, and a rule eval whose
id matches no judge rule. `codeguard eval` prints a table per rule, then one line per
failure.

#### Where an eval's inputs come from

| Input | From |
|---|---|
| The edits, the files around them and their expected reviews | the rule eval, `rule-evals/<id>.yaml` |
| The convention | the skill |
| Paths, triggers, provider and model | the binding |
| The confidence threshold, and the Google Cloud project, location and calls at once | the caller's `.codeguard/config.yaml` |
| The judge prompt and how each case is checked | codeguard |

### Which test to write

A project tests the rules in its `.codeguard/` the same way a package does.

| You add or change | Write | It checks | Run | Calls the model |
|---|---|---|---|---|
| A pattern rule or gate | `rule-tests/<id>-test.yml` | the rule matches its `invalid` cases and none of its `valid` ones | `codeguard test` | no |
| A judge rule's skill, binding or `triggers` | `rule-evals/<id>.yaml` | the triggers fire on each edit but the `skipped` ones | `codeguard test` | no |
| | | each edit gets its expected review, 3 runs of 3 | `codeguard eval --repeat 3` | yes |

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
  CI still fails on them unless the PR has the `codeguard-allow-judge-errors` label.
- If the review crashes or `codeguard` isn't on your PATH, you see why, and the stop
  goes through.

The judge gets the code the change touched: each changed function, method or class, and
each changed line outside them, with the file's line numbers. A new file is sent whole
but for its blank lines outside a function or class; every file with `--all` is sent
whole. The judge reads the rest of the file, or any other file in
the repository, with its read-only tools. A verdict is cached until the changed code, the
rest of the file, the rule, the model, or a file the judge loaded changes. A loaded file
is one the judge read, or one its searches returned: a file a grep matched or a glob
listed. A file a search would only start returning later doesn't count.

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

Each judge rule is judged with its binding's provider and model, the same ones its rule
eval passed on; see [Judge rules](#judge-rules). A binding that sets neither is judged
with `claude-sonnet-5-5` through the `claude` CLI.

### Judge with Gemini on Google Cloud

By default the judge runs `claude -p`. A judge rule whose binding sets
`provider: gemini` is judged with Gemini on Google Cloud (Vertex AI) instead, in reviews
and in its rule eval, so its rule eval has to pass on Gemini:

```yaml
skill: .claude/skills/responsibility-placement
paths: ["app/**/*.py"]
provider: gemini
model: gemini-3.1-pro-preview
```

`judge` in `.codeguard/config.yaml` sets where Gemini runs and how many calls run at once:

```yaml
judge:
  project: my-project             # default: GOOGLE_CLOUD_PROJECT
  location: global                # default: GOOGLE_CLOUD_LOCATION
  calls_at_once: 2                # default: 2 for gemini, one per CPU for claude-cli
```

Gemini reads the working directory through read-only `read_file`, `grep` and `glob`
tools, limited to the repository, and reports through a `submit_verdict` tool that
takes the same verdict schema as Claude. Verdicts are cached per provider and model,
so switching providers doesn't reuse Claude's verdicts.

Gemini's pay-as-you-go capacity is shared and limited by tokens per minute, so the
gemini provider makes 2 calls at once. Each provider has its own limit, so Claude and
Gemini rules in one review don't wait on each other. A call that Gemini turns away with
a 429 is retried for about 15 seconds, and then the rule is reported as not judged.

Use `gemini-3.1-pro-preview`, the Gemini model codeguard was tested with. Flash was
unreliable in testing.

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
- `judge {rule} on {file}`: one span per rule and file, with `cache_hit`, `violations`,
  `loaded_files` (the files the verdict depends on) and `changed_files` (the loaded files
  that changed since the cached verdict, which is why it was judged again). The Claude or
  Gemini span inside it has that judgement's time and tokens.
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

`evals/judge` is a rule package whose rule evals check the judge itself, on the model
each of its bindings names. They run the real `claude` CLI and cost tokens. CI runs
them; run them after changing the judge's instructions, request or tools:

```sh
codeguard test evals/judge     # its triggers; no model call
codeguard eval evals/judge
codeguard eval evals/judge --repeat 5
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
