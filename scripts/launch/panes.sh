#!/usr/bin/env bash
# Open every pane of scripts/launch/panes.list in one window, commands pre-filled.
#   scripts/launch/panes.sh [tmux|terminator]     (default: tmux if installed)
# Works from the host (panes exec into the dev container) or inside it.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="$(cd "$HERE/../.." && pwd)"
BACKEND="${1:-$(command -v tmux >/dev/null && echo tmux || echo terminator)}"
SESSION="$(grep -E '^PROJECT_NAME=' "$WS/project.env" 2>/dev/null | cut -d= -f2-)"; SESSION="${SESSION:-ros2}"
mapfile -t ENTRIES < <(grep -vE '^[[:space:]]*(#|$)' "$HERE/panes.list")
[[ ${#ENTRIES[@]} -gt 0 ]] || { echo "no panes in $HERE/panes.list"; exit 1; }
PANE="bash $HERE/pane.sh"

case "$BACKEND" in
  tmux)
    if tmux has-session -t "$SESSION" 2>/dev/null; then
      echo "tmux session '$SESSION' exists: tmux attach -t $SESSION (or tmux kill-session -t $SESSION)"; exit 1
    fi
    tmux new-session -d -s "$SESSION" -x 240 -y 60 "$PANE 0"
    for ((i = 1; i < ${#ENTRIES[@]}; i++)); do
      tmux split-window -t "$SESSION" "$PANE $i"
      tmux select-layout -t "$SESSION" tiled >/dev/null
    done
    tmux set-option -t "$SESSION" pane-border-status top >/dev/null
    for ((i = 0; i < ${#ENTRIES[@]}; i++)); do
      IFS='|' read -r _c title _cmd <<<"${ENTRIES[$i]}"
      tmux select-pane -t "$SESSION:0.$i" -T "$title"
    done
    if [[ -n "${PANES_NO_ATTACH:-}" ]]; then echo "tmux session '$SESSION' started"; exit 0; fi
    if [[ -n "${TMUX:-}" ]]; then tmux switch-client -t "$SESSION"; else tmux attach -t "$SESSION"; fi
    ;;
  terminator)
    command -v terminator >/dev/null || { echo "terminator not installed"; exit 1; }
    left=(); right=()
    for ((i = 0; i < ${#ENTRIES[@]}; i++)); do
      IFS='|' read -r col _t _c <<<"${ENTRIES[$i]}"
      if [[ "$col" == R ]]; then right+=("$i"); else left+=("$i"); fi
    done
    term() {  # term <index> <parent> <order>
      IFS='|' read -r _c title _cmd <<<"${ENTRIES[$1]}"
      printf '    [[[t%s]]]\n      type = Terminal\n      parent = %s\n      order = %s\n      title = %s\n      command = %s %s\n' \
        "$1" "$2" "$3" "$title" "$PANE" "$1"
    }
    column() {  # column <parent> <order> <name> <indices...>: equal-height rows
      local parent=$1 order=$2 name=$3; shift 3
      local idx=("$@") n=$# k up=$parent ord=$order
      for ((k = 0; k < n - 1; k++)); do
        printf '    [[[%s%s]]]\n      type = VPaned\n      parent = %s\n      order = %s\n      ratio = %s\n' \
          "$name" "$k" "$up" "$ord" "$(awk -v r=$((n - k)) 'BEGIN{printf "%.4f", 1.0 / r}')"
        term "${idx[$k]}" "$name$k" 0; up="$name$k"; ord=1
      done
      term "${idx[$((n - 1))]}" "$up" "$ord"
    }
    cfg="$(mktemp /tmp/panes_terminator.XXXXXX)"
    {
      printf '[global_config]\n  suppress_multiple_term_dialog = True\n[layouts]\n  [[panes]]\n'
      printf '    [[[window0]]]\n      type = Window\n      parent = ""\n'
      if [[ ${#left[@]} -gt 0 && ${#right[@]} -gt 0 ]]; then
        printf '    [[[split]]]\n      type = HPaned\n      parent = window0\n      ratio = 0.5\n'
        column split 0 l "${left[@]}"; column split 1 r "${right[@]}"
      else
        column window0 0 c "${left[@]}" "${right[@]}"
      fi
      printf '[plugins]\n'
    } > "$cfg"
    if [[ -n "${PANES_DRY_RUN:-}" ]]; then cat "$cfg"; exit 0; fi
    terminator -u -g "$cfg" -l panes >/dev/null 2>&1 &
    echo "terminator started ($cfg)"
    ;;
  *) echo "backend must be tmux or terminator"; exit 2 ;;
esac
