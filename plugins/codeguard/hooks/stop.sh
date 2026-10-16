#!/bin/sh
hook_input=$(cat)
if command -v codeguard > /dev/null; then
  codeguard review >&2
  case $? in
    0) exit 0 ;;
    1) exit 2 ;;
  esac
else
  echo "codeguard is not on PATH." >&2
fi
echo "codeguard review failed, so these changes were not reviewed. Tell the user." >&2
case $hook_input in
  *'"stop_hook_active": true'* | *'"stop_hook_active":true'*) exit 1 ;;
esac
exit 2
