# Layer on top of the Isaac ROS base image (DEVENV=isaac_ros).
# System dependencies only: the workspace is mounted by the Isaac ROS CLI, so the
# sources are never copied in (the build context is limited by .dockerignore).
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=jazzy \
    WS_IN_CONTAINER=1

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
      clang-tidy lcov tmux terminator python3-pytest-cov \
      ros-jazzy-generate-parameter-library ros-jazzy-launch-testing-ros \
      ros-jazzy-rmw-cyclonedds-cpp

# Project dependencies from every package.xml.
COPY src /tmp/deps/src
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && rosdep update --rosdistro jazzy \
    && rosdep install --from-paths /tmp/deps/src --ignore-src -r -y --rosdistro jazzy \
    && rm -rf /tmp/deps

# Every interactive shell gets the workspace environment (scripts/env.sh), once.
RUN printf '\n# workspace environment (scripts/env.sh)\n[ -f "${ISAAC_ROS_WS:-/workspaces/isaac_ros-dev}/scripts/env.sh" ] && source "${ISAAC_ROS_WS:-/workspaces/isaac_ros-dev}/scripts/env.sh"\n' >> /etc/bash.bashrc
