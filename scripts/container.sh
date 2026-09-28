#!/usr/bin/env bash
# Dev container front end (DEVENV-001). The backend comes from DEVENV in project.env:
#   native     no container: `shell` opens a shell with scripts/env.sh sourced
#   docker     plain Docker image built from docker/Dockerfile
#   isaac_ros  NVIDIA Isaac ROS CLI (isaac-ros activate), layer Dockerfile.<ISAAC_ROS_IMAGE_KEY>
#
# Usage:
#   scripts/container.sh init docker|isaac_ros   # copy the devenv template in, set DEVENV
#   scripts/container.sh build                   # build the image (no container start)
#   scripts/container.sh shell                   # start/attach and open a shell
#   scripts/container.sh start | stop            # docker backend: run detached / stop
#   scripts/container.sh exec <cmd...>           # run a command in the running container
#   scripts/container.sh status
set -euo pipefail
WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WS"

get() {  # get KEY [default] -- read project.env without sourcing ROS
  local v
  v="$(grep -E "^$1=" project.env 2>/dev/null | tail -1 | cut -d= -f2-)"
  echo "${v:-${2:-}}"
}
DEVENV="${DEVENV:-$(get DEVENV native)}"
NAME="$(get CONTAINER_NAME "$(basename "$WS")_dev")"
CWS="$(get CONTAINER_WS /workspaces/ros2_ws)"
IMAGE="$(get PROJECT_NAME "$(basename "$WS")"):dev"
die() { echo "container.sh: $*" >&2; exit 1; }
in_container() { [[ -f /.dockerenv || -n "${WS_IN_CONTAINER:-}" ]]; }
running() { docker ps --format '{{.Names}}' | grep -qx "$NAME"; }
TTY=(-i); [[ -t 0 && -t 1 ]] && TTY+=(-t)

start_docker() {  # start the plain-docker dev container detached, if not running
  running && return 0
  local gpu=()
  case "$(get CONTAINER_GPU auto)" in
    on) gpu=(--gpus all) ;;
    auto) command -v nvidia-ctk >/dev/null && gpu=(--gpus all) ;;
  esac
  xhost +local: >/dev/null 2>&1 || true
  docker run -d --rm --name "$NAME" --network host --ipc host "${gpu[@]}" \
    -e DISPLAY="${DISPLAY:-}" -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v "$WS:$CWS" -w "$CWS" "$IMAGE" sleep infinity >/dev/null \
    || die "could not start $IMAGE (build it first: scripts/container.sh build)"
}

cmd="${1:-status}"; shift || true

case "$cmd" in
  init)
    kind="${1:?usage: container.sh init docker|isaac_ros}"
    src="$WS/templates/devenv/$kind"
    [[ -d "$src" ]] || die "unknown devenv '$kind' (templates/devenv/)"
    # Copy without overwriting: these files become project-owned once copied.
    (cd "$src" && find . -type f) | while read -r f; do
      dest="$WS/${f#./}"
      if [[ -e "$dest" ]]; then echo "keep     ${f#./} (exists)"; continue; fi
      mkdir -p "$(dirname "$dest")"; cp "$src/$f" "$dest"; echo "created  ${f#./}"
    done
    if grep -q '^DEVENV=' project.env; then
      sed -i "s/^DEVENV=.*/DEVENV=$kind/" project.env
    else
      echo "DEVENV=$kind" >> project.env
    fi
    echo "DEVENV=$kind written to project.env. Next: scripts/container.sh build"
    ;;

  build)
    case "$DEVENV" in
      native) echo "DEVENV=native: nothing to build" ;;
      docker)
        [[ -f docker/Dockerfile ]] || die "docker/Dockerfile missing: scripts/container.sh init docker"
        docker build -f docker/Dockerfile -t "$IMAGE" \
          --build-arg BASE_IMAGE="$(get DOCKER_BASE_IMAGE ros:jazzy-ros-base)" \
          --build-arg ROS_DISTRO="$(get ROS_DISTRO jazzy)" \
          --build-arg USER_UID="$(id -u)" --build-arg USER_GID="$(id -g)" \
          --build-arg CONTAINER_WS="$CWS" .
        ;;
      isaac_ros)
        command -v isaac-ros >/dev/null || die "isaac-ros CLI not installed (scripts/setup_host.sh)"
        command -v nvidia-ctk >/dev/null || die "nvidia-container-toolkit not installed (scripts/setup_host.sh)"
        ISAAC_ROS_WS="$WS" isaac-ros activate --build-local --build-only
        ;;
      *) die "unknown DEVENV=$DEVENV" ;;
    esac
    ;;

  start)
    [[ "$DEVENV" == docker ]] || die "start is for DEVENV=docker (isaac_ros: use shell; native: nothing to start)"
    start_docker; echo "container $NAME running"
    ;;

  stop)
    running && docker stop "$NAME" >/dev/null && echo "container $NAME stopped" || echo "not running"
    ;;

  shell)
    if in_container || [[ "$DEVENV" == native ]]; then
      exec bash --rcfile "$WS/scripts/container_bashrc" -i
    fi
    case "$DEVENV" in
      docker)
        start_docker
        exec docker exec "${TTY[@]}" -w "$CWS" "$NAME" bash --rcfile "$CWS/scripts/container_bashrc" -i
        ;;
      isaac_ros)
        ISAAC_ROS_WS="$WS" exec isaac-ros activate --config "docker.run.container_name=$NAME"
        ;;
      *) die "unknown DEVENV=$DEVENV" ;;
    esac
    ;;

  exec)
    [[ $# -gt 0 ]] || die "usage: container.sh exec <cmd...>"
    if in_container || [[ "$DEVENV" == native ]]; then
      exec bash -c "source '$WS/scripts/env.sh' && $*"
    fi
    running || die "container $NAME is not running (scripts/container.sh shell | start)"
    exec docker exec "${TTY[@]}" -w "$CWS" "$NAME" bash -c "source '$CWS/scripts/env.sh' && $*"
    ;;

  status)
    echo "DEVENV=$DEVENV  container=$NAME  container_ws=$CWS"
    if in_container; then echo "inside a container"; fi
    if [[ "$DEVENV" != native ]] && command -v docker >/dev/null; then
      if running; then echo "container running"; else echo "container not running"; fi
    fi
    ;;

  *) sed -n '2,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
