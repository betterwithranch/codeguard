# Rule design

Each principle here corrected a rule that misjudged code. Apply them before stating a
rule, and when two rules or a rule and its cases disagree.

## One claim, one yes/no test

A rule makes one claim, stated as one question with a yes or no answer for each piece of
code the judge reads. The rule's forms (the shapes the violation takes in the language
and its libraries) illustrate that test on both sides: the test alone decides each form,
and no form defines its own violation.

A rule whose test only points at its forms ("flag code that does this in a way a form
below names") is several rules. Split it, or find the one test the forms share and drop
the forms it doesn't decide.

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
