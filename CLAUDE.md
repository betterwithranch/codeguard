# codeguard

[README.md](README.md) explains the CLI, rule packages and how to work on codeguard.

## Rule evals and judged reviews must be reliable

This applies to the judge rule evals in `evals/judge` and in every rule package, such as
[betterwithranch/codeguard-rules](https://github.com/betterwithranch/codeguard-rules). It
also applies to judged reviews of codeguard's own code. A rule eval checks that a judge
rule says what it means. It doesn't measure how a judge handles hard cases. Every case,
and every finding a review reports, should come out the same way on every run.

- **An unreliable result is a defect.** Unreliable means a case or finding that flips
  between runs, is judged with low confidence, or comes back as a warning. The defect is
  in the rule or in the case, never in the code under review. Don't re-run until it
  passes. Don't loosen a gate. Don't change codeguard's code to get past a finding you
  think is wrong; fix the rule in its package.
- **Fix the rule's criterion, not its examples.** When a judge can't decide, the rule's
  test for a violation is unclear. Restate the test so the case is decided by it. Don't
  add another carve-out example for the code that was just flagged. A rule that
  needs a new example each time it meets new code has a bad criterion.
- **Eval cases are clear.** An `invalid` case breaks the rule beyond argument. A `valid`
  case obviously keeps it. A `skipped` case is outside the rule's gate. If a reasonable
  reviewer could argue a case either way, it doesn't belong in the eval: make it clear
  or remove it.
- **A finding the rule gets wrong becomes a case.** When a review flags code the rule
  should allow, fix the criterion. Then add a clear `valid` case modelled on that code,
  plus a clear `invalid` case close to it, so the boundary is tested on both sides.
- **Check the fix with repeated runs.** Judge the changed rule's cases many times, for
  example 20 runs with `codeguard eval --repeat`. Then review the code that was flagged
  until neither has a miss or a warning.
