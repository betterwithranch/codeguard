# Writing a judge rule that judges reliably

A judge rule is ready when every eval case comes out the same way on every run. A
result is unreliable when it flips between runs, is judged with low confidence, or comes
back as a warning. That is a defect in the rule or in the case, never in the code under
review:

- Don't re-run until it passes.
- Don't loosen a gate to get past it.
- Don't change the reviewed code to get past a finding you think is wrong. Fix the rule.
- Don't change the rule's wording to get a weak case to pass. Fix the case, or drop it.
- Don't add a failing case's code to the skill as an example. The case would then pass
  by memory; restate the question instead.

## State the criterion

`references/rule-design.md` has what the claim must be: one yes/no test, scoped to the
change, in plain words. In the skill:

- Open with one sentence saying what the rule enforces, in words that don't depend on the
  language.
- Give the judge the test as a question it can answer for each piece of code it reads:
  "does a caller have to unpack the result to know what happened?", not "is this clean?".
- Name the language's and its common libraries' forms on both sides of the test, as
  illustrations of it. A judge wavers on code in a form the skill doesn't place, such as
  a framework's validated data or an ORM's rows.
- End with a `## Why` section: the harm the rule prevents, which helps the judge apply the
  test to unnamed code but never widens it (`references/rule-design.md`).
- When a judge can't decide a case, restate the test so the case is decided by it.
  Don't add a carve-out for the code that was just flagged. A rule that needs a new
  example each time it meets new code has a bad criterion.

## Gate every form of the violation

- The judge sees a changed file only when a changed line falls inside one of the
  binding's `triggers`. A violation the gate doesn't match is never reported.
- List the syntactic forms the violation takes, including forms the skill doesn't name,
  and give each one an `invalid` gate test, so a gate that stops matching a form fails
  `codeguard test`.
- Gate on where a violation appears, not on the rule's topic: a rule about passing enum
  members needs a gate on literals, because the enum is defined elsewhere.
- A wider gate costs judge calls. `codeguard review --dry-run` counts them.
- A wider gate costs tokens too: the judge is sent the whole node a trigger matched
  around the change. Gate on the narrowest node that holds the violation, such as the
  `except` clause rather than the whole `try`.

## Write eval cases at the boundary

- Each case is clear. An `invalid` case breaks the rule beyond argument, a `valid` case
  obviously keeps it, and a `skipped` case is outside the gate. If a reasonable reviewer
  could argue a case either way, make it clear or remove it.
- A case shows what's at stake. A reader of the case alone sees why the code is a
  problem or why it's fine, and its name says that, not only what the code does:
  "caller can't tell a new customer from an existing one", not "returns a tuple".
- A case tests one thing. It doesn't mix in a second defect, such as a CSV split on
  `","`, which is a bug whatever the rule says, so the judge can't flag the case for the
  wrong reason.
- Pair the cases: for each form the criterion allows, a `valid` case, and beside it an
  `invalid` case of the same shape that breaks the rule.
- Add `invalid` cases in forms the skill doesn't name, so the eval shows the judge
  applies the test rather than matching its examples.
- Use made-up code. A public rule package never holds code copied from a private
  repository.
- A case never reuses code from the skill's examples: not the same snippet, and not the
  same code with renamed identifiers or changed literals. Use different code, a
  different domain and different names that ask the same question. A case that copies
  an example tests whether the judge recognizes the example, not whether it applies the
  intent, and proves nothing.

## Verify

1. `codeguard test`: rule tests, gate tests, and every case's triggers.
2. `codeguard eval --rule <id> --repeat 20`: every case passes 20 runs of 20.
   `--case <text>` judges only the cases whose name contains the text, while you work on
   one. In CI, run the evals of the rules a change touches.
