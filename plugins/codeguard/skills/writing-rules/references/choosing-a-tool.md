# Choosing a tool

codeguard adds the checks a project's linters can't do. Use the first row that can
express the convention.

| The convention | Use |
|---|---|
| A linter the project runs already has the rule | Enable or configure it (Ruff, ESLint, RuboCop) |
| A linter can express it through configuration | Configure it: ESLint `no-restricted-syntax` (AST selectors) or `no-restricted-imports`, Ruff `banned-api`, a configurable RuboCop cop |
| Which modules may import which | The project's import linter (import-linter, `import/no-restricted-paths`) |
| A code shape in one file | A codeguard pattern rule |
| Logic across nodes (counting, state, types), or an autocorrect | The linter's custom rule: a Pylint checker, an ESLint plugin rule, a RuboCop custom cop |
| Judgment | Skill prose |

A codeguard pattern rule replaces a custom rule that only matches a shape: a YAML file
and test cases instead of a class and a spec. A custom rule with an autocorrect stays
in the linter.

Ruff has no custom rules and no syntax-selector config, so most Python shape
conventions land in codeguard. ESLint's `no-restricted-syntax` covers most
TypeScript shapes, so fewer land there.
