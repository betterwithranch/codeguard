import json

MODEL_USAGE = {
    "inputTokens": 4,
    "outputTokens": 134,
    "cacheReadInputTokens": 8553,
    "cacheCreationInputTokens": 588,
    "thinkingTokens": 20,
    "costUSD": 0.0022,
}
RATE_LIMIT_EVENT = {
    "type": "rate_limit_event",
    "rate_limit_info": {
        "status": "allowed",
        "unifiedWindows": {
            "five_hour": {"utilization": 0.16, "resetsAt": 1792207200},
            "seven_day": {"utilization": 0.11, "resetsAt": 1792591200},
        },
    },
}


def claude_result(violations: list[dict]) -> dict:
    return {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "num_turns": 3,
        "duration_ms": 2036,
        "duration_api_ms": 1901,
        "total_cost_usd": 0.0022,
        "modelUsage": {"claude-sonnet-5-5": MODEL_USAGE},
        "structured_output": {"violations": violations},
    }


def tool_use(name: str, **arguments: object) -> dict:
    return {
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "name": name, "input": arguments}]},
    }


def fake_claude_script(
    violations: list[dict], before: str = "", tool_uses: tuple[dict, ...] = ()
) -> str:
    stream = "\n".join(
        json.dumps(message) for message in (RATE_LIMIT_EVENT, *tool_uses, claude_result(violations))
    )
    return f"#!/bin/sh\n{before}cat > /dev/null\ncat <<'EOF'\n{stream}\nEOF\n"
