# A judge rule runs only where its violations can be

The file under review describes one judge rule: its skill, the triggers in its binding,
and the gates its rule package defines. The judge runs the skill on a changed file only
when a changed line falls inside code that one of the triggers matches. A built-in
change kind matches by syntax (`fixture`, `call`, `import`); a gate is an ast-grep rule.

Report a violation when:

- The skill judges a construct (an enum, a `Literal`, a fixture, a mock, a `Protocol`,
  a loop, an import) and no trigger matches the code where that construct's violations
  appear. Name the construct and the gate that would match it.
- A trigger is `any`, `code`, `function-body` or `function-signature` where a narrower
  gate would hold every violation the skill describes. Name the narrower gate.
- A bullet of the skill can be checked by an ast-grep pattern or a type checker setting
  alone. Name the bullet and the pattern or setting.

Gate on where a violation appears, not on the rule's topic. A rule that wants enum
members passed instead of bare literals needs a gate on literals, because the enum is
defined in another file.
