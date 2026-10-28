---
tags: [skill-creator]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Our codeguard judge rule derive-known-values only runs on Python. The web app in web/ is TypeScript and has the same problem, so make the rule run on our TypeScript files too. I've already written its TypeScript examples in .codeguard/skills/derive-known-values/typescript.md; add the rule's TypeScript eval cases. I can't run codeguard eval here, so run codeguard test.

Input files: pyproject.toml, src/shop/__init__.py, src/shop/orders.py, web/package.json, web/src/orders.ts, .codeguard/config.yaml, .codeguard/skills/derive-known-values/SKILL.md, .codeguard/skills/derive-known-values/python.md, .codeguard/skills/derive-known-values/typescript.md, .codeguard/bindings/derive-known-values.yaml, .codeguard/rule-evals/derive-known-values.yaml
