# Rule design

Each principle here corrected a rule that misjudged code. Apply them before stating a
rule, and when two rules or a rule and its cases disagree.

## One convention, one statement

A rule is one convention, stated as one declarative sentence at the level of intent, in
words that don't depend on the language. Each piece of code the judge reads either keeps
the statement or breaks it: that is the rule's one yes/no test. The rule's forms (the
shapes the violation takes in the language and its libraries) illustrate the statement
on both sides: the statement alone decides each form, and no form defines its own
violation.

A rule is a statement, not a question. The judge decides whether code breaks the
convention it is given; a question in its place leaves the judge to infer which answer
is the violation.

A rule whose statement only points at its forms ("code breaks this when it takes a form
below") is several rules. Split it, or find the one statement the forms share and drop
the forms it doesn't decide.

A rule states an abstract intent, never a list of code shapes, values or names: a shape
nobody listed is still decided by its statement. Rules that each police one code shape
contradict each other and fail idiomatic code. The opposite failure is one rule stating
several conventions under one intent; split it into one rule per convention.

## Say why it exists

Every rule states the harm it prevents, in one or two sentences, so it can be reviewed
when the code or the design around it changes. A rule nobody can trace to a reason can
only be kept or dropped blind.

- A judge rule: a `## Why` section in its `SKILL.md`. It is part of the judge's prompt,
  so it helps the judge apply the test to code the examples don't name. It explains the
  test and never widens it: the test alone decides each case.
- A pattern rule: `metadata.why` in its rule file. codeguard doesn't print it; `note`
  stays what the blocked agent reads.
- Optionally, where the rule comes from: a `Source:` line in the Why section, or
  `metadata.source`. A link to public documentation, or the bug, PR comment or team
  decision behind it.

A gate is a judge rule's trigger, not a rule, and needs no why. `codeguard test` warns
on a rule without one; `--missing-why fail` fails it.

## Scoped to the change

A rule and its cases ask for only as much as decides pass or fail: the code the change
adds or edits, and the definitions of the names it uses. A judge that has to read the
rest of the repository to decide is slower, costs more, and wavers.

Only a rule that keeps something unique or consistent across the repository (one home for
a job, one word for one operation) searches beyond that, and it names the one search it
needs.

## Plain language

Write a rule the way a reviewer would say it in a code review. No invented terms: if the
rule needs a word nobody uses, the rule isn't clear yet. A judge reads an unfamiliar term
as loosely as a person does.

## Idiomatic code never fails a rule

Code written the way the language and its libraries intend is never a violation. A bad
pattern isn't idiomatic just because a framework uses it, though: calling the framework's
API is fine, while copying its shape into the project's own code may not be. Give the
idiomatic form a `valid` case beside the `invalid` one.

## Each code shape breaks at most one rule

A code shape is on the violation side of at most one rule. When two rules contradict each
other (one flags what the other requires) or overlap (both flag the same code), settle it
before either ships: move the shape to one rule, or merge them.

## Proven by its own cases

A rule is proven accurate only by its own cases, run through codeguard: `codeguard test`
for pattern rules, gates and triggers, `codeguard eval` for judge rules. Running it over
other code finds code to fix, not evidence that the rule is right.
