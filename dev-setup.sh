#!/bin/sh
# Run codeguard from this clone in every Claude Code session on this machine: the CLI with
# its locked dependencies on PATH, and the plugin from this folder at user scope.
# Run it yourself in a session that works on codeguard; nothing runs it for you.
# Usage: ./dev-setup.sh
set -eu

clone="$(cd "$(dirname "$0")" && pwd)"
bin="${XDG_BIN_HOME:-$HOME/.local/bin}"

uv sync --frozen --project "$clone"
mkdir -p "$bin"
ln -sf "$clone/.venv/bin/codeguard" "$bin/codeguard"
claude plugin marketplace add "$clone"
claude plugin install codeguard@codeguard --scope user
