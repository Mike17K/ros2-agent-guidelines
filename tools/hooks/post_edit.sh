#!/usr/bin/env bash
# Claude Code PostToolUse hook: after an Edit/Write, auto-format the file with the
# ROS 2 formatter and run the guideline rules on it. Findings are fed back to the
# agent (exit 2 -> stderr is shown to Claude) so it fixes them immediately.
# Never blocks on missing tools; never touches files outside src/ or templates/.
input="$(cat)"
file="$(python3 -c 'import json,sys; d=json.load(sys.stdin); print((d.get("tool_input") or {}).get("file_path",""))' <<<"$input" 2>/dev/null)"
[[ -n "$file" && -f "$file" ]] || exit 0
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
case "$file" in
  "$ROOT"/src/*|"$ROOT"/templates/*) ;;
  *) exit 0 ;;
esac

if [[ -z "${ROS_DISTRO:-}" && -f /opt/ros/jazzy/setup.bash ]]; then
  # shellcheck disable=SC1091
  source /opt/ros/jazzy/setup.bash >/dev/null 2>&1
fi

case "$file" in
  *.cpp|*.hpp|*.h|*.cc)
    command -v ament_uncrustify >/dev/null && ament_uncrustify --reformat "$file" >/dev/null 2>&1 ;;
esac

out="$(python3 "$ROOT/tools/lint_rules.py" "$file" 2>&1)"
if [[ $? -ne 0 ]]; then
  echo "$out" | grep -v '^lint_rules:' >&2
  echo "Fix the guideline findings above in $file (see the cited docs/agent/ file)." >&2
  exit 2
fi
case "$file" in
  *.py)
    if command -v ament_flake8 >/dev/null; then
      f8="$(ament_flake8 "$file" 2>&1 | grep -E "^$file:|^\./" )"
      if [[ -n "$f8" ]]; then echo "$f8" >&2; echo "flake8 (ROS 2 style) findings above." >&2; exit 2; fi
    fi ;;
esac
exit 0
