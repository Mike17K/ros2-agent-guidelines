#!/usr/bin/env bash
# Prove the golden templates are still golden [TOOL-003]: scaffold each one
# under a new name into a throwaway workspace and run the full check on it.
# Run after ANY change to templates/, tools/ or lint rules.
#
# Usage: tools/verify_templates.sh [--keep] [extra tools/check.sh args, e.g. --sanitize asan]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEEP=0
if [[ "${1:-}" == "--keep" ]]; then KEEP=1; shift; fi

python3 "$ROOT/tools/lint_rules.py" --self-test

TMP="$(mktemp -d "${TMPDIR:-/tmp}/verify_templates.XXXXXX")"
if [[ $KEEP -eq 0 ]]; then trap 'rm -rf "$TMP"' EXIT; else echo "workspace kept at $TMP"; fi
mkdir -p "$TMP/src"
# The scaffolded copy must pass with the workspace's own configs.
cp "$ROOT/.clang-tidy" "$TMP/" 2>/dev/null || true

ID=(--workspace "$TMP" --maintainer "Template Check" --email "check@example.com")
python3 "$ROOT/tools/new_package.py" interfaces verify_interfaces "${ID[@]}"
python3 "$ROOT/tools/new_package.py" cpp verify_cpp "${ID[@]}"
python3 "$ROOT/tools/new_package.py" py verify_py "${ID[@]}"

leftover=$(grep -rnE 'ros_template_|MAINTAINER_(NAME|EMAIL)|COPYRIGHT_HOLDER' "$TMP/src" || true)
if [[ -n "$leftover" ]]; then
  echo "scaffold left template tokens behind:"; echo "$leftover"; exit 1
fi

"$ROOT/tools/check.sh" --ws "$TMP" "$@"
