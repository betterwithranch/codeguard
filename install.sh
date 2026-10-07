#!/bin/sh
# Install codeguard's prerequisites if they are missing, then install or upgrade
# the codeguard CLI. Usage:
#   curl -LsSf https://raw.githubusercontent.com/betterwithranch/codeguard/v0/install.sh | sh
set -eu

ref="${CODEGUARD_REF:-v0}"

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # The uv installer adds its directory to new shells' PATH, not this one.
  PATH="${XDG_BIN_HOME:-$HOME/.local/bin}:$PATH"
fi

uv tool install --force \
  "git+https://github.com/betterwithranch/codeguard@${ref}#subdirectory=plugins/codeguard"
