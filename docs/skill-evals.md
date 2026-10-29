# Testing the writing-rules skill

This guide is for changing codeguard's writing-rules skill or its evals. The skill tells
an agent what a well-written rule looks like. Its evals check that an agent with the
skill writes one. They run with `claude plugin eval`;
[Test plugins with evals](https://code.claude.com/docs/en/plugin-evals.md) explains the
command, its options and the case and grader formats.

[How to test your changes](testing.md) covers everything else: testing codeguard, testing
rules and reviewing code.

## Running the evals

A skill eval measures the skill by the content of what an agent writes with it: each
grader checks a file the agent wrote against what the skill says. It doesn't measure
whether that rule's tests or evals pass, or how reliably they pass. Testing a rule is
the job of its own rule tests and evals, wherever the rule lives, and is out of scope
here.

CI runs them when `skills/writing-rules/` or `evals/writing-rules/` changes: each case
gets 3 runs and passes at a score of 0.8 or more.

```sh
claude plugin eval . --scaffold --allow-tools Write Edit --runs 3 --threshold 0.8 \
  --trust-plugin --no-publish
```

Run it from a checkout with no `.venv`: the eval copies the plugin and refuses the hard
links uv makes there.

## Writing a case

Each case in `evals/writing-rules/` asks an agent to write or fix a rule, then grades the
rule files it wrote: not what it said, the steps it took or how the rule behaves.

- The agent gets `Write` and `Edit`, never `Bash`, and the prompt says codeguard isn't
  available. A case needs no sandbox and never runs codeguard.
- The prompt names the rule's id, so each grader knows the path of the file it reads.
- Each grader reads one file: the rule's skill, its binding or its cases. Never grade the
  trace.
- Nothing in the skill gives a case's answer: no example in `SKILL.md` or `references/`
  shares a case's convention, domain or names. A case the skill answers measures
  copying.
