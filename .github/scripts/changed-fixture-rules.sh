#!/bin/sh
# Print a pytest -k expression that selects the LLM tests of each fixture rule changed
# since the base, or nothing when none changed. A fixture rule is its skill, binding and
# rule evals in evals/judge/<ruleset>/. Usage:
#   .github/scripts/changed-fixture-rules.sh <base>
set -eu

git diff --name-only "$1"...HEAD -- evals/judge \
  | sed -nE 's#^(evals/judge/[^/]+)/(skills/([^/]+)/.*|bindings/([^/]+)\.yaml|rule-evals/([^/]+)\.yaml)$#\1 \3\4\5#p' \
  | while read -r ruleset rule; do
      # A deleted rule has no tests left to run.
      if [ -f "$ruleset/rule-evals/$rule.yaml" ]; then echo "$rule"; fi
    done \
  | sort -u \
  | paste -sd '|' - \
  | sed 's/|/ or /g'
