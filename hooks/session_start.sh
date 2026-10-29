#!/bin/sh
# Build the environment the Bash tool's codeguard runs in, here, outside Claude Code's
# sandbox: inside it, uv can't write its cache or download codeguard's dependencies. Then
# point the Bash tool's codeguard at it, and put that codeguard on PATH, which
# `claude plugin eval` doesn't do for a plugin's bin directory.
environment="${XDG_CACHE_HOME:-$HOME/.cache}/codeguard/venv"
env -u CLAUDE_PLUGIN_DATA "$CLAUDE_PLUGIN_ROOT/bin/codeguard" --help >/dev/null 2>&1
if [ -n "${CLAUDE_ENV_FILE:-}" ] && [ -x "$environment/bin/codeguard" ]; then
    {
        echo "export CODEGUARD_ENVIRONMENT=\"$environment\""
        echo "export PATH=\"$CLAUDE_PLUGIN_ROOT/bin:\$PATH\""
    } >>"$CLAUDE_ENV_FILE"
fi
exit 0
