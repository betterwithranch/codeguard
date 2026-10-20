#!/bin/sh
hook_input=$(cat)
field() {
  printf '%s' "$hook_input" | sed -n "s/.*\"$1\" *: *\"\([A-Za-z0-9_-]*\)\".*/\1/p"
}
reported="$HOME/.cache/codeguard/stop/$(field session_id)-$(field agent_id)"
if command -v codeguard > /dev/null; then
  diagnostics=$(codeguard review 2>&1)
  case $? in
    0)
      rm -f "$reported"
      [ -n "$diagnostics" ] && printf '%s\n' "$diagnostics" >&2
      exit 0 ;;
    1)
      if [ "$(cat "$reported" 2> /dev/null)" = "$diagnostics" ]; then
        echo "codeguard already reported these errors, so the stop goes through." >&2
        printf '%s\n' "$diagnostics" >&2
        exit 1
      fi
      mkdir -p "${reported%/*}"
      printf '%s\n' "$diagnostics" > "$reported"
      printf '%s\n' "$diagnostics" >&2
      echo "These errors are required fixes, not suggestions. Fix the code. If the fix needs a decision, ask the user. Don't change .codeguard/config.yaml to silence them. Leave the warnings: CI logs them for review, so don't fix them or raise them with the user." >&2
      exit 2 ;;
  esac
  printf '%s\n' "$diagnostics" >&2
else
  echo "codeguard is not on PATH." >&2
fi
echo "codeguard review failed, so these changes were not reviewed. Tell the user." >&2
case $hook_input in
  *'"stop_hook_active": true'* | *'"stop_hook_active":true'*) exit 1 ;;
esac
exit 2
