---
type: llm
focus: last_message
weight: 1
---

The agent's final reply says it wrote no codeguard rule for this convention, and why: whether a value read with json.loads, yaml.safe_load or .json() is validated before use is decided exactly by a type checker that reports values typed Any, not by a codeguard rule. Whether or how the agent sets up the type checker doesn't matter.
