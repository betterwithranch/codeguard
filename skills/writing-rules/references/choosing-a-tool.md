# Is it a codeguard rule?

codeguard adds the checks a project's linters and type checker can't do. Before writing
a rule, decide whether the convention is codeguard's at all, and if it is, which kind of
rule it needs.

## Conventions that aren't codeguard's

Write no codeguard rule for a convention another tool can decide exactly, even when
asked for one, and whether or not the project runs that tool or has the check turned on.
An exact tool gives the same answer every run, costs nothing and runs in the editor; a
judge rule sees one changed file and guesses at the rest. Tell the user the convention
isn't a codeguard rule and which kind of tool can check it. Setting up that tool isn't
part of writing rules.

| The convention | Decided by |
|---|---|
| A check a linter or type checker has, or can be configured to have | That linter or type checker |
| A value's type and where it flows, such as an argument that may be `None` | A type checker |
| Which modules may import which | An import linter |
| Logic across nodes (counting, state, types), or an autocorrect | A custom linter rule |
| Who implements, calls or references a symbol, such as every class that implements an interface | A language server's find-references |

## Pattern rule or judge rule

| The convention | Rule |
|---|---|
| A code shape in one file | A codeguard pattern rule |
| Judgment | A judge rule |

A judge rule is for judgment, never for something syntax, types or a symbol lookup
decide. A pattern rule replaces a custom linter rule that only matches a shape: a YAML
file and test cases instead of a class and a spec. Ruff has no custom rules and no
syntax-selector config, so most Python shape conventions land in codeguard; ESLint's
`no-restricted-syntax` covers most TypeScript shapes, so fewer land there.
