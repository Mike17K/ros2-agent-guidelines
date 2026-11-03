#!/usr/bin/env bash
# Host prerequisites for the dev environment chosen in project.env (DEVENV).
# Default: CHECK ONLY and print what is missing with the command to fix it.
#   scripts/setup_host.sh            # check
#   scripts/setup_host.sh --install  # install what can be installed automatically (sudo)
set -uo pipefail
WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEVENV="$(grep -E '^DEVENV=' "$WS/project.env" 2>/dev/null | cut -d= -f2-)"; DEVENV="${DEVENV:-native}"
DISTRO="$(grep -E '^ROS_DISTRO=' "$WS/project.env" 2>/dev/null | cut -d= -f2-)"; DISTRO="${DISTRO:-jazzy}"
INSTALL=0; [[ "${1:-}" == "--install" ]] && INSTALL=1
missing=0

need() {  # need <description> <check-cmd> <fix-cmd>
  if eval "$2" >/dev/null 2>&1; then
    printf '  ok       %s\n' "$1"
  elif [[ $INSTALL -eq 1 && -n "$3" ]]; then
    printf '  install  %s\n' "$1"; eval "$3" || { printf '  FAILED   %s\n' "$1"; missing=1; }
  else
    printf '  MISSING  %s\n           fix: %s\n' "$1" "${3:-see docs/agent/devenv.md}"; missing=1
  fi
}

echo "DEVENV=$DEVENV"
case "$DEVENV" in
  native)
    need "ROS 2 $DISTRO" "test -f /opt/ros/$DISTRO/setup.bash" \
      "see https://docs.ros.org/en/$DISTRO/Installation.html"
    need "rosdep" "command -v rosdep" "sudo apt-get install -y python3-rosdep"
    need "colcon" "command -v colcon" "sudo apt-get install -y python3-colcon-common-extensions"
    need "clang-tidy" "command -v clang-tidy" "sudo apt-get install -y clang-tidy"
    need "generate_parameter_library" "test -d /opt/ros/$DISTRO/share/generate_parameter_library" \
      "sudo apt-get install -y ros-$DISTRO-generate-parameter-library"
    ;;
  docker|isaac_ros)
    need "docker" "command -v docker" "see https://docs.docker.com/engine/install/ubuntu/"
    need "docker without sudo" "docker info" "sudo usermod -aG docker \$USER  (then log out and in)"
    if command -v nvidia-smi >/dev/null 2>&1 || [[ "$DEVENV" == isaac_ros ]]; then
      need "nvidia-container-toolkit" "command -v nvidia-ctk" \
        "curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg && curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list && sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit"
      need "docker nvidia runtime" "docker info --format '{{json .Runtimes}}' | grep -q nvidia" \
        "sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker"
    fi
    if [[ "$DEVENV" == isaac_ros ]]; then
      need "isaac-ros CLI" "command -v isaac-ros" \
        "see https://nvidia-isaac-ros.github.io/getting_started/index.html (isaac-ros-cli apt package)"
      need "NGC login (nvcr.io)" "grep -q nvcr.io ~/.docker/config.json" \
        "docker login nvcr.io  (user: \$oauthtoken, password: NGC API key)"
    fi
    ;;
  *) echo "unknown DEVENV=$DEVENV"; exit 2 ;;
esac
need "tmux (scripts/launch/panes.sh)" "command -v tmux" "sudo apt-get install -y tmux"
need "auto-source scripts/env.sh in ~/.bashrc (DEVENV-002)" \
  "grep -qF 'guidelines DEVENV-002' ~/.bashrc 2>/dev/null" \
  "printf '\n# ROS 2 workspace auto-env (guidelines DEVENV-002)\nif [[ -f \"\$PWD/scripts/env.sh\" ]]; then source \"\$PWD/scripts/env.sh\"; fi\n' >> ~/.bashrc"
[[ $missing -eq 0 ]] && echo "host ready" || { echo "host NOT ready"; exit 1; }
