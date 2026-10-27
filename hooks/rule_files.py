# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Block an edit to a codeguard rule file until the session has loaded writing-rules.

Usage: uv run --script rule_files.py

A Claude Code PreToolUse hook on Edit and Write. A rule file is a skill, pattern rule,
gate, binding, rule test or rule eval, under `.codeguard/` or under a ruleset directory
of a rule package (a directory with `codeguard-package.yaml`). The session has loaded the
skill when its transcript shows a Skill call naming `writing-rules`, or a Read of the
skill's `SKILL.md`. Anything this hook can't read lets the edit through: it guards a
convention, not a security boundary.
"""

import json
import re
import sys
from pathlib import Path

SKILL = "writing-rules"
RULE_DIRECTORIES = {"skills", "rules", "gates", "bindings", "rule-tests", "rule-evals"}
CONFIG_DIR = ".codeguard"
MANIFEST = "codeguard-package.yaml"
REASON = (
    "Load codeguard's writing-rules skill before editing codeguard rule files: it holds "
    "the conventions for rules, gates, bindings and their cases. Invoke it with the Skill "
    "tool (codeguard:writing-rules), then make this edit again."
)


def main() -> None:
    try:
        hook_input = json.loads(sys.stdin.read())
    except ValueError:
        return
    response = decision(hook_input)
    if response is not None:
        sys.stdout.write(f"{json.dumps(response)}\n")


def decision(hook_input: dict) -> dict | None:
    file_path = (hook_input.get("tool_input") or {}).get("file_path")
    if not isinstance(file_path, str):
        return None
    path = Path(hook_input.get("cwd") or ".") / file_path
    if not is_rule_file(path) or skill_loaded(hook_input.get("transcript_path")):
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON,
        }
    }


def is_rule_file(path: Path) -> bool:
    parts = path.parts
    for index, part in enumerate(parts[:-2]):
        if part == CONFIG_DIR and parts[index + 1] in RULE_DIRECTORIES:
            return True
    for directory in path.parents:
        manifest = directory / MANIFEST
        if manifest.is_file():
            relative = path.relative_to(directory).parts
            return (
                len(relative) > 2
                and relative[0] in rulesets(manifest)
                and relative[1] in RULE_DIRECTORIES
            )
    return False


def rulesets(manifest: Path) -> set[str]:
    """Read `rulesets` from a manifest, as a flow list or a block list, without a YAML parser."""
    try:
        text = manifest.read_text()
    except OSError:
        return set()
    flow = re.search(r"^rulesets:\s*\[([^\]]*)\]", text, re.MULTILINE)
    if flow:
        return {name.strip().strip("'\"") for name in flow.group(1).split(",") if name.strip()}
    block = re.search(r"^rulesets:\s*\n((?:[ \t]*-[^\n]*\n?)+)", text, re.MULTILINE)
    if block:
        return {line.strip()[1:].strip().strip("'\"") for line in block.group(1).splitlines()}
    return set()


def skill_loaded(transcript_path: object) -> bool:
    if not isinstance(transcript_path, str):
        return True
    try:
        lines = Path(transcript_path).read_text().splitlines()
    except OSError:
        return True
    return any(loads_skill(block) for line in lines for block in tool_uses(line))


def tool_uses(line: str) -> list[dict]:
    try:
        entry = json.loads(line)
    except ValueError:
        return []
    message = entry.get("message") if isinstance(entry, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return []
    return [
        block for block in content if isinstance(block, dict) and block.get("type") == "tool_use"
    ]


def loads_skill(tool_use: dict) -> bool:
    tool_input = tool_use.get("input")
    if not isinstance(tool_input, dict):
        return False
    if tool_use.get("name") == "Skill":
        name = tool_input.get("skill")
        return isinstance(name, str) and name.split(":")[-1] == SKILL
    if tool_use.get("name") == "Read":
        file_path = tool_input.get("file_path")
        return isinstance(file_path, str) and Path(file_path).parts[-2:] == (SKILL, "SKILL.md")
    return False


if __name__ == "__main__":
    main()
