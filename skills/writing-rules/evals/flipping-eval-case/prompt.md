---
tags: [skill-creator]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

The case 'logs the error and re-raises' in .codeguard/rule-evals/no-swallowed-exceptions.yaml flips between valid and invalid across codeguard eval --repeat 20 runs (it failed 7 of 20 as invalid). Fix it. I can't run codeguard eval here, so run codeguard test.

Input files: .codeguard/config.yaml, .codeguard/skills/no-swallowed-exceptions/SKILL.md, .codeguard/bindings/no-swallowed-exceptions.yaml, .codeguard/rule-evals/no-swallowed-exceptions.yaml, src/shop/__init__.py, src/shop/orders.py
