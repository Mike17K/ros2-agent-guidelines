# Dev image for DEVENV=docker (project-owned after `scripts/container.sh init docker`).
# System dependencies only; the workspace is bind-mounted at CONTAINER_WS.
ARG BASE_IMAGE=ros:jazzy-ros-base
FROM ${BASE_IMAGE}

ARG ROS_DISTRO=jazzy
ARG USER_UID=1000
ARG USER_GID=1000
ARG CONTAINER_WS=/workspaces/ros2_ws
ENV DEBIAN_FRONTEND=noninteractive \
    WS_IN_CONTAINER=1

# Tooling the guidelines rely on (tools/check.sh, templates).
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential git clang-tidy python3-pip python3-pytest-cov lcov tmux sudo \
      ros-${ROS_DISTRO}-generate-parameter-library ros-${ROS_DISTRO}-launch-testing-ros \
      ros-${ROS_DISTRO}-rclcpp-components ros-${ROS_DISTRO}-std-srvs \
      ros-${ROS_DISTRO}-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

# Project dependencies from every package.xml (only those are in the build context).
COPY src /tmp/deps/src
RUN apt-get update \
    && (rosdep init 2>/dev/null || true) && rosdep update --rosdistro ${ROS_DISTRO} \
    && rosdep install --from-paths /tmp/deps/src --ignore-src -r -y --rosdistro ${ROS_DISTRO} \
    && rm -rf /tmp/deps /var/lib/apt/lists/*

# Non-root user with the host UID/GID so bind-mounted files keep their owner.
RUN if getent passwd ${USER_UID} >/dev/null; then userdel -r "$(getent passwd ${USER_UID} | cut -d: -f1)"; fi \
    && (getent group ${USER_GID} >/dev/null || groupadd -g ${USER_GID} dev) \
    && useradd -m -u ${USER_UID} -g ${USER_GID} -s /bin/bash dev \
    && echo "dev ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/dev
USER dev
WORKDIR ${CONTAINER_WS}
