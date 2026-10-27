---
name: writing-rules
description: Use when adding or changing a codeguard rule, its tests, or its snapshots — any file under .codeguard/ or in a codeguard rule package. Use even if you already know ast-grep; codeguard adds its own layout, scoping, and test conventions.
---

# Writing codeguard rules

codeguard checks the changed lines of each changed file against the project's rules:
pattern rules (ast-grep) and judge rules (a skill a model judges the change against). An
`error` diagnostic blocks the agent's Stop and fails CI.

## Workflow

1. **Pick the tool.** The cheapest exact tool decides the convention: a linter or type
   checker setting, the import linter, a pattern rule, a language-server lookup, and only
   then a judge rule. Read `references/choosing-a-tool.md` before writing any rule.
2. **State the claim and why it exists.** One claim per rule, as one yes/no test in the
   words a reviewer would use, scoped to the change, and the harm it prevents. Read
   `references/rule-design.md` before writing or rewording a rule, and when two rules
   disagree about the same code.
3. **Gate it.** A pattern rule matches only where the code breaks the convention. A judge
   rule's binding has `triggers` on where its violations appear.
4. **Write the cases.** One case per branch of a pattern rule; for a judge rule, `invalid`,
   `valid` and `skipped` cases at the boundary of its test. A judge rule's cases never
   reuse code from its skill's examples, even renamed.
5. **Verify** with the rule's own cases (below). Nothing else proves a rule.

For a judge rule, also read `references/judge-rules.md` before writing or changing it,
and whenever its eval fails, flips between runs or reports a warning. For examples in the
project's language, read `references/python.md`, `references/typescript.md` or
`references/ruby.md`.

## Layout

- Pattern rule: `.codeguard/rules/pattern/<id>.yml`; its tests:
  `.codeguard/rule-tests/<id>-test.yml`, never under the rules directory (every YAML file
  there loads as a rule).
- Judge rule: the skill `.codeguard/skills/<id>/SKILL.md`, the binding
  `.codeguard/bindings/<id>.yaml` (`skill`, `paths`, `triggers`), and the rule eval
  `.codeguard/rule-evals/<id>.yaml`.
- Gate: `.codeguard/gates/<id>.yml`, an ast-grep rule tested by
  `.codeguard/rule-tests/<id>-test.yml`.
- In a rule package (a repo with `codeguard-package.yaml`), the same layout sits under
  each ruleset's directory instead of `.codeguard/`.
- Before writing a rule, check the rulesets the project opts into in
  `.codeguard/config.yaml`. To change a packaged rule for this project, override or
  exclude it there; don't copy it into `.codeguard/`.

codeguard's README has the binding and rule eval formats.

## Pattern rules

- Match the construct only where it breaks the convention: a `len()` compared with a
  literal, not a `len()` inside a slice. `stopBy: end` on `has` or `inside` searches every
  descendant or ancestor; in a positive match, use it only when the construct breaks the
  convention in every position.
- Give each matched construct a `valid` case where the convention allows it, if it has
  such a position, so a rule that matches too widely fails a case.
- Write one `valid` or `invalid` case per branch, so deleting a branch fails a case. A
  comment above each case names its branch.
- Put the reason and the fix in the rule's `note`. codeguard prints it under the
  diagnostic, so it is what the blocked agent reads (no comments in rule files).
- Scope a rule with a binding, `bindings/<id>.yaml` with `rule`, `paths` and
  `exclude_paths`, never with ast-grep's `files` or `ignores`, so a project can change
  the scope. The exception is a file name that is the convention itself (`__all__` only
  in `__init__.py`).
- When syntax decides only some forms of a convention, write a pattern rule for those
  forms and a judge rule gated on every form. No judge rule runs on a file with an
  `error` diagnostic, so the two report the same code only if the pattern rule is a
  `warning`.

## Every rule

- Use made-up names in cases (`ExampleModel`), so a case shows the pattern rather than
  one class in the codebase. Match a code pattern, never a named class, function or file.
- Set `severity: error` on a rule that must block; `warning` only reports.
- Write a judge rule's skill as the violation: code in the file under review that breaks
  the convention, and no fix. The judge reports violations only. Its examples illustrate
  the question on both sides; they never define it.
- Give every judge rule an eval with an `invalid` case. `codeguard eval` fails a rule
  without one, and a violation outside the triggers.
- Leave the codebase clean for a new rule: fix each existing violation, or put an
  `ast-grep-ignore: <id>` comment on the line above it.

## Verify

```sh
codeguard test                 # rule tests and eval triggers; --update-all regenerates snapshots
codeguard eval --rule <id> --repeat 20  # a judge rule: every case passes 20 runs of 20; calls the model
codeguard review --all --dry-run  # existing violations of pattern rules; calls no model
```

Never run `codeguard review --all` without `--dry-run`: it judges every file against
every judge rule.
