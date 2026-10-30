#!/bin/sh
# Build codeguard's environment in the plugin's data directory, here, outside Claude
# Code's sandbox: inside it, uv can't write its cache or download codeguard's
# dependencies. Then point the Bash tool's codeguard, which gets no CLAUDE_PLUGIN_DATA,
# at it.
environment="$CLAUDE_PLUGIN_DATA/venv"
"$CLAUDE_PLUGIN_ROOT/bin/codeguard" --help >/dev/null 2>&1
if [ -n "${CLAUDE_ENV_FILE:-}" ] && [ -x "$environment/bin/codeguard" ]; then
    echo "export CODEGUARD_ENVIRONMENT=\"$environment\"" >>"$CLAUDE_ENV_FILE"
fi
exit 0
