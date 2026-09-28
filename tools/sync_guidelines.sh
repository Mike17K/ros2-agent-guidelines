#!/usr/bin/env bash
# Pull the managed guideline files from the upstream guidelines repo into this
# workspace [MAINT-002]. Project-owned files (PROJECT.md, src/, docs/agent/local/)
# are never touched. See docs/agent/maintenance.md.
#
# Usage: tools/sync_guidelines.sh <path-to-upstream-guidelines-checkout> [--dry-run]
set -euo pipefail
UPSTREAM="${1:?usage: $0 <upstream-dir> [--dry-run]}"
DRY="${2:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPSTREAM="$(cd "$UPSTREAM" && pwd)"
[[ -f "$UPSTREAM/.guidelines-managed" ]] || { echo "$UPSTREAM is not a guidelines repo" >&2; exit 2; }
[[ "$UPSTREAM" != "$HERE" ]] || { echo "upstream and workspace are the same directory" >&2; exit 2; }

RSYNC=(rsync -a --delete --exclude local/ --exclude __pycache__/)
[[ "$DRY" == "--dry-run" ]] && RSYNC+=(--dry-run --itemize-changes)

old="$(cat "$HERE/.guidelines-version" 2>/dev/null || echo none)"
while IFS= read -r entry; do
  [[ -z "$entry" || "$entry" == \#* ]] && continue
  src="$UPSTREAM/$entry"
  [[ -e "$src" ]] || { echo "warning: upstream lacks $entry" >&2; continue; }
  if [[ -d "$src" ]]; then
    mkdir -p "$HERE/$entry"
    "${RSYNC[@]}" "$src/" "$HERE/$entry/"
  else
    mkdir -p "$(dirname "$HERE/$entry")"
    "${RSYNC[@]}" "$src" "$HERE/$entry"
  fi
done < "$UPSTREAM/.guidelines-managed"
new="$(cat "$UPSTREAM/.guidelines-version")"
echo "guidelines: $old -> $new${DRY:+ (dry run)}"
echo "Read docs/agent/CHANGELOG.md for what changed, then run tools/check.sh."
