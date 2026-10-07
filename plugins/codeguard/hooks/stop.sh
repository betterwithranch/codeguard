#!/bin/sh
# Stop hook for Claude Code (Stop, SubagentStop) and Codex (Stop). Both hosts set
# CLAUDE_PLUGIN_ROOT and CLAUDE_PLUGIN_DATA and send the hook input on stdin.
set -eu

if ! command -v uv >/dev/null 2>&1; then
  echo "codeguard needs uv. Install it with: curl -LsSf https://raw.githubusercontent.com/betterwithranch/codeguard/v0/install.sh | sh" >&2
  exit 1
fi

UV_PROJECT_ENVIRONMENT="$CLAUDE_PLUGIN_DATA/venv" \
  exec uv run --quiet --frozen --project "$CLAUDE_PLUGIN_ROOT" codeguard hook stop
