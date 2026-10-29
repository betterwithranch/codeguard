#!/usr/bin/env bash
set -eu
cp -R "$(dirname "$0")/files/." .
# codeguard reviews and tests a git repository's working tree.
git init --quiet
git add --all
git -c user.name=eval -c user.email=eval@example.com commit --quiet --message "Start the case"
# The agent's commands run in a sandbox with no network, so build codeguard's environment
# in the run's home now, as the plugin's first run outside the sandbox would.
"$(dirname "$0")/../../../bin/codeguard" --help >/dev/null
