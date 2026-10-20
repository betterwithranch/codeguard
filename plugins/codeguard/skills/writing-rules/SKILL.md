---
name: writing-rules
description: Use when adding or changing a codeguard rule, its tests, or its snapshots — any file under .codeguard/. Use even if you already know ast-grep; codeguard adds its own layout, scoping, and test conventions.
---

# Writing codeguard rules

codeguard runs the project's ast-grep rules on each changed file. An `error` diagnostic
blocks the agent's Stop and fails CI.

- Write one `valid` or `invalid` test case per branch of the rule, so deleting a branch
  fails a case. A comment above each case names its branch.
- Use made-up names in test cases (`ExampleModel`), so the case shows the pattern rather
  than one class in the codebase.
- Put the reason and the fix in the rule's `note`. codeguard prints it under the
  diagnostic, so it is what the blocked agent reads (no comments in rule files).
- Match a code pattern, never a named class, function, or file.
- Set `severity: error` on a rule that must block; `warning` only reports.
- Write a pattern rule whenever ast-grep can check the convention, and a judge rule
  (a skill) only when it needs judgment. A pattern rule is fast, free, and gives the
  same answer every time; a judge rule costs a Claude call per changed file.
- A pattern rule runs on every file in its language. Scope it with a binding,
  `bindings/<id>.yaml` with `rule`, `paths` and `exclude_paths`, never with ast-grep's
  `files` or `ignores`, so a project can change the scope. The exception is a file name
  that is part of the convention itself (`__all__` only in `__init__.py`).
- Give a judge rule's binding `triggers`: the code its violations need, as a gate
  (`gates/<id>.yml`, an ast-grep rule with tests in `rule-tests/gates/`) or a built-in
  change kind. Gate on where a violation appears, not on the topic: a rule about passing
  enum members needs a gate on literals, because the enum is defined elsewhere. The judge
  skips a file whose changes miss every trigger.
- Give every judge rule an eval with an `invalid` case. `codeguard eval` fails a rule
  without one, and a violation outside the triggers.
- Write a codeguard rule only for a code shape in one file that no linter the project
  runs has or can be configured to check (`references/choosing-a-tool.md`), because a
  linter rule already runs in the editor and can autocorrect.
- Save the rule as `.codeguard/rules/pattern/<id>.yml` and its tests as
  `.codeguard/rule-tests/pattern/<id>-test.yml`, never under the rules directory
  (every YAML file there loads as a rule).
- In a rule package (a repo with `codeguard-package.yaml`), save under the ruleset's
  directory instead of `.codeguard/`: `<ruleset>/rules/pattern/<id>.yml` and
  `<ruleset>/rule-tests/pattern/<id>-test.yml`.
- Evaluate a judge rule with `rule-evals/<id>-eval.yml`, listing `valid` and `invalid`
  case files in `rule-evals/<id>/`. Add an `invalid` case for each kind of code the rule
  forbids and a `valid` case for each near miss it allows. Name case files for their
  code, not their expected result, because the judge reads that directory. Run them with
  `codeguard eval`.
- Before writing a rule, check the rulesets the project opts into in
  `.codeguard/config.yaml`. To change a packaged rule for this project, override or
  exclude it there; don't copy it into `.codeguard/`.
- Leave the codebase clean for a new rule: fix each existing violation, or put an
  `ast-grep-ignore: <id>` comment on the line above it.

Verify:

```sh
codeguard test               # --update-all regenerates snapshots
codeguard review --all
```

`references/example.md` has a complete rule and test file in Python, TypeScript, and
Ruby.
