#!/usr/bin/env bash
# The ONE definition of the workspace's ROS environment (DEVENV-002).
# Source it; never copy these exports into ~/.bashrc, pane scripts or Dockerfiles.
#
#   source scripts/env.sh          # from the workspace root, host or container
#
# Loads project.env, sources ROS and the workspace overlay (if built), and sets
# the RMW, its config file, the domain, external/ on PYTHONPATH and an optional .venv.
# Idempotent: sourcing twice is harmless.

_ws_env_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# KEY=VALUE loader: no eval, no expansion, comments and blanks ignored.
_ws_env_load() {
  local file="$1" line key value
  [[ -f "$file" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*(#|$) ]] && continue
    key="${line%%=*}"; value="${line#*=}"
    key="${key//[[:space:]]/}"
    [[ "$key" =~ ^[A-Z_][A-Z0-9_]*$ ]] || continue
    # Explicit environment wins over the file (e.g. ROS_DOMAIN_ID=5 source scripts/env.sh).
    [[ -n "${!key+x}" && -n "${!key}" ]] && continue
    export "$key=$value"
  done < "$file"
}
_ws_env_load "$_ws_env_root/project.env"

export WS_ROOT="$_ws_env_root"
export ROS_DISTRO="${ROS_DISTRO:-jazzy}"

if [[ -f "/opt/ros/$ROS_DISTRO/setup.bash" ]]; then
  # shellcheck disable=SC1090
  source "/opt/ros/$ROS_DISTRO/setup.bash"
else
  echo "env.sh: /opt/ros/$ROS_DISTRO not found (inside the dev container? see docs/agent/devenv.md)" >&2
fi
if [[ -f "$WS_ROOT/install/setup.bash" ]]; then
  # shellcheck disable=SC1091
  source "$WS_ROOT/install/setup.bash"
fi

export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
if [[ -n "${RMW_CONFIG_FILE:-}" ]]; then
  _cfg="$RMW_CONFIG_FILE"; [[ "$_cfg" = /* ]] || _cfg="$WS_ROOT/$_cfg"
  case "$RMW_IMPLEMENTATION" in
    rmw_cyclonedds_cpp) export CYCLONEDDS_URI="file://$_cfg" ;;
    rmw_fastrtps_cpp) export FASTRTPS_DEFAULT_PROFILES_FILE="$_cfg" ;;
  esac
  [[ -f "$_cfg" ]] || echo "env.sh: RMW_CONFIG_FILE $_cfg does not exist" >&2
  unset _cfg
fi
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}"

if [[ -d "$WS_ROOT/external" && ":${PYTHONPATH:-}:" != *":$WS_ROOT/external:"* ]]; then
  export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$WS_ROOT/external"
fi
if [[ -f "$WS_ROOT/.venv/bin/activate" && -z "${VIRTUAL_ENV:-}" ]]; then
  # shellcheck disable=SC1091
  source "$WS_ROOT/.venv/bin/activate"
fi
unset -f _ws_env_load
unset _ws_env_root
