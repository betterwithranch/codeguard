# Every violation a judge rule describes is inside code its triggers match

The file under review describes one judge rule. codeguard judges a changed file with the
rule only when a changed line is inside code one of the rule's triggers matches. A trigger
matches every line of each node its rule matches: a gate on a function matches every line
of that function. A violation in code no trigger matches is never judged.

The file has four sections:

- `Skill`: the convention the rule judges.
- `Triggers`: each of the rule's triggers and what it matches.
- `Other gates`: gates in the rule's package that are not triggers of this rule.
- `Other change kinds`: built-in change kinds that are not triggers of this rule.

Report each bullet or sentence of the skill that describes a violation no trigger matches:

- `line`: the line of that bullet or sentence.
- `message`: one line of code that breaks it and that no trigger matches, in backticks, and
  the part of the skill it breaks.
- `note`: the clause of the closest trigger that leaves the code out, then a gate from
  `Other gates` or a change kind from `Other change kinds` that would match it, or "no gate
  or change kind matches it".

Also report a bullet that an ast-grep rule could check alone, without judgment. Its
`message` names the bullet and the node kind and condition of that ast-grep rule.

Judge each trigger by its definition in the file, not by its name. Report a bullet only
when you can write the line of code. A violation's line can be outside the node the skill
talks about: a rule that wants enum members passed instead of bare literals is broken at
the literal, because the enum is defined in another file.
