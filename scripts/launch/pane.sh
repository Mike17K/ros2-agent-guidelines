#!/usr/bin/env bash
# One pane of scripts/launch/panes.sh:  pane.sh <index>
# On the host with DEVENV=docker|isaac_ros it re-runs itself inside the dev
# container; inside (or native) it sources scripts/env.sh, pre-fills the pane's
# command on the prompt (edit it, Enter runs it, Ctrl+C skips it) and always leaves
# an interactive, prepared shell behind.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="$(cd "$HERE/../.." && pwd)"
INDEX="${1:?usage: pane.sh <index>}"
get() { grep -E "^$1=" "$WS/project.env" 2>/dev/null | tail -1 | cut -d= -f2-; }
DEVENV="$(get DEVENV)"; DEVENV="${DEVENV:-native}"

if [[ "$DEVENV" != native && ! -f /.dockerenv && -z "${WS_IN_CONTAINER:-}" ]]; then
  NAME="$(get CONTAINER_NAME)"; CWS="$(get CONTAINER_WS)"
  if ! docker ps --format '{{.Names}}' | grep -qx "$NAME"; then
    echo "Dev container '$NAME' is not running. Start it: scripts/container.sh shell"
    exec bash -i
  fi
  exec docker exec -it -w "$CWS" "$NAME" bash "$CWS/scripts/launch/pane.sh" "$INDEX"
fi

source "$WS/scripts/env.sh"
cd "$WS" || exit 1
mapfile -t ENTRIES < <(grep -vE '^[[:space:]]*(#|$)' "$HERE/panes.list")
ENTRY="${ENTRIES[$INDEX]:-}"
IFS='|' read -r _col TITLE CMD <<<"$ENTRY"
printf '\033]0;%s\007' "$TITLE"
echo "== $TITLE =="
rc="$(mktemp)"
printf 'source ~/.bashrc 2>/dev/null\nsource %q\ncd %q\n' "$WS/scripts/env.sh" "$WS" > "$rc"
trap 'echo; exec bash --rcfile "$rc" -i' INT
if [[ -n "${CMD:-}" ]]; then
  echo "Enter runs it (edit first if needed), Ctrl+C skips it."
  read -r -e -p "$(whoami)@$(hostname):${PWD/#$HOME/\~}\$ " -i "$CMD" LINE
  if [[ -n "$LINE" ]]; then history -s "$LINE"; echo "$LINE" >> ~/.bash_history; eval "$LINE"; fi
fi
exec bash --rcfile "$rc" -i
