---
name: writing-rules
description: Use when adding or changing a codeguard rule, its tests, or its snapshots — any file under .codeguard/. Use even if you already know ast-grep; codeguard adds its own layout, scoping, and test conventions.
---

# Writing codeguard rules

codeguard checks the changed lines of each changed file against the project's rules:
pattern rules (ast-grep) and judge rules (a skill Claude judges the change against). An
`error` diagnostic blocks the agent's Stop and fails CI.

- Write one `valid` or `invalid` test case per branch of the rule, so deleting a branch
  fails a case. A comment above each case names its branch.
- Match a pattern rule's construct only where it breaks the convention: a `len()`
  compared with a literal, not a `len()` inside a slice. `stopBy: end` on `has` or
  `inside` searches every descendant or ancestor; in a positive match, use it only when
  the construct breaks the convention in every position.
- Give each construct a pattern rule matches a `valid` case where the convention allows
  it, if it has such a position, so a rule that matches too widely fails a case.
- Use made-up names in test cases (`ExampleModel`), so the case shows the pattern rather
  than one class in the codebase.
- Put the reason and the fix in a pattern rule's `note`. codeguard prints it under the
  diagnostic, so it is what the blocked agent reads (no comments in rule files).
- Write a judge rule's skill as the violation: code in the file under review that breaks
  the convention, one claim per rule, and no fix. The judge reports violations only.
- Match a code pattern, never a named class, function, or file.
- Set `severity: error` on a rule that must block; `warning` only reports.
- Write a pattern rule whenever ast-grep can check the convention, and a judge rule
  (a skill) only when it needs judgment. A pattern rule is fast, free, and gives the
  same answer every time; a judge rule costs a Claude call per changed file.
- When syntax decides only some forms of a convention, write a pattern rule for those
  forms and a judge rule gated on every form. No judge rule runs on a file with an
  `error` diagnostic, so the two report the same code only if the pattern rule is a
  `warning`.
- A pattern rule runs on every file in its language. Scope it with a binding,
  `bindings/<id>.yaml` with `rule`, `paths` and `exclude_paths`, never with ast-grep's
  `files` or `ignores`, so a project can change the scope. The exception is a file name
  that is part of the convention itself (`__all__` only in `__init__.py`).
- Give a judge rule's binding `triggers`: the code its violations need, as a gate
  (`gates/<id>.yml`, an ast-grep rule tested by `rule-tests/<id>-test.yml`) or a
  built-in change kind. Gate on where a violation appears, not on the topic: a rule
  about passing enum members needs a gate on literals, because the enum is defined
  elsewhere. The judge skips a file whose changes miss every trigger.
- Give every judge rule an eval with an `invalid` case. `codeguard eval` fails a rule
  without one, and a violation outside the triggers.
- Before writing or changing a judge rule, and whenever its eval or a judged review
  fails, flips between runs or reports a warning, follow `references/judge-rules.md`:
  how to read the code it will judge, state the criterion, gate every form of the
  violation, write eval cases at the boundary, and verify.
- Write a codeguard rule only for a code shape in one file that no linter the project
  runs has or can be configured to check (`references/choosing-a-tool.md`), because a
  linter rule already runs in the editor and can autocorrect.
- Save a pattern rule as `.codeguard/rules/pattern/<id>.yml` and its tests as
  `.codeguard/rule-tests/<id>-test.yml`, never under the rules directory (every YAML
  file there loads as a rule).
- Save a judge rule as `.codeguard/skills/<id>/SKILL.md`, its binding as
  `.codeguard/bindings/<id>.yaml` (`skill`, `paths`, `triggers`), and its rule eval as
  `.codeguard/rule-evals/<id>.yaml`.
- In a rule package (a repo with `codeguard-package.yaml`), save under the ruleset's
  directory instead of `.codeguard/`, with the same layout.
- A rule eval lists `cases`, each with a `name` saying what the edit does, the edit as
  `inputs` (`file`, `before`, `after`) and `expected_output` with its `outcome`:
  `invalid`, `valid` or `skipped`. Add an `invalid` case for each kind of code the rule
  forbids, a `valid` case for each near miss it allows, and a `skipped` case for each
  change its triggers should ignore. codeguard's README has the format.
- Before writing a rule, check the rulesets the project opts into in
  `.codeguard/config.yaml`. To change a packaged rule for this project, override or
  exclude it there; don't copy it into `.codeguard/`.
- Leave the codebase clean for a new rule: fix each existing violation, or put an
  `ast-grep-ignore: <id>` comment on the line above it.

Verify:

```sh
codeguard test                 # rule tests and eval triggers; --update-all regenerates snapshots
codeguard eval --repeat 20     # judge rules: every case passes 20 runs of 20; calls the model
codeguard review --all --dry-run  # existing violations of pattern rules; calls no model
```

Never run `codeguard review --all` without `--dry-run`: it judges every file against
every judge rule.

`references/example.md` has a complete rule and test file in Python, TypeScript, and
Ruby.
