---
name: writing-rules
description: Use when adding or changing a codeguard rule, its tests, or its snapshots — any file under .codeguard/. Use even if you already know ast-grep; codeguard adds its own layout, scoping, and test conventions.
---

# Writing codeguard rules

codeguard runs the project's ast-grep rules on each changed file. An `error` finding
blocks the agent's Stop and fails CI.

- Write one `valid` or `invalid` test case per branch of the rule, so deleting a branch
  fails a case. A comment above each case names its branch.
- Use made-up names in test cases (`ExampleModel`), so the case shows the pattern rather
  than one class in the codebase.
- Put the reason and the fix in the rule's `note`. codeguard prints it under the
  finding, so it is what the blocked agent reads (no comments in rule files).
- Match a code pattern, never a named class, function, or file.
- Set `severity: error` on a rule that must block; `warning` only reports.
- Scope a rule to some files through its binding's `paths`, never ast-grep's `files`, so
  each glob lives in one place. Bindings aren't built yet: until they are, a rule runs
  on every file in its language, so ask before writing one that needs scoping.
- Write a codeguard rule only for a code shape in one file that no linter the project
  runs has or can be configured to check (`references/choosing-a-tool.md`), because a
  linter rule already runs in the editor and can autocorrect.
- Save the rule as `.codeguard/rules/pattern/<id>.yml` and its tests as
  `.codeguard/rule-tests/pattern/<id>-test.yml`, never under the rules directory
  (every YAML file there loads as a rule).
- Leave the codebase clean for a new rule: fix each existing violation, or put an
  `ast-grep-ignore: <id>` comment on the line above it.

Verify:

```sh
codeguard test               # --update-all regenerates snapshots
codeguard review --all
```

`references/example.md` has a complete rule and test file in Python, TypeScript, and
Ruby.
