---
type: llm
focus: {source: file, path: pyproject.toml}
weight: 1
---

This pyproject.toml sets a type checker to report values typed Any as errors, such as basedpyright's reportAny = "error" (or mypy's disallow_any_expr).
