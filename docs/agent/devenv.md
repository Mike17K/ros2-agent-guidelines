# Development environment: container, entry points, launching

Read this when you set up a workspace, touch `scripts/`, the `Makefile`, Dockerfiles
or RMW config, or need to run the system.

## The pieces

| File | Owner | Purpose |
|---|---|---|
| `project.env` | project | machine-readable config: distro, RMW, domain, DEVENV, container, maintainer |
| `scripts/env.sh` | managed | **the** environment definition (DEVENV-002) |
| `Makefile` | managed | front door: `make help` (DEVENV-003). `Makefile.local` for project targets |
| `scripts/container.sh` | managed | `init`, `build`, `shell`, `exec`, `status` for the chosen backend |
| `scripts/setup_host.sh` | managed | checks host prerequisites (`--install` to fix what it can) |
| `scripts/setup_external.sh` + `external/external.list` | managed + project | pinned non-ROS deps and weights (ARCH-015) |
| `scripts/launch/panes.sh`, `pane.sh` + `panes.list` | managed + project | multi-pane launch with pre-filled commands |
| `docker/Dockerfile` or `Dockerfile.<key>` + `.isaac-ros-cli/config.yaml` | project | dev image, created by `scripts/container.sh init` |
| RMW XML (`config/cyclonedds.xml`, …) | project | named by `RMW_CONFIG_FILE` in project.env |

**DEVENV-001 — One dev environment per project, declared in `project.env`.**
`DEVENV=native` means ROS is installed on the host. `docker` is a plain image from
`docker/Dockerfile`. `isaac_ros` is the NVIDIA Isaac ROS CLI with a layer
`Dockerfile.<ISAAC_ROS_IMAGE_KEY>` on the Isaac base image, needed for GPU packages
like cuMotion, nvblox and NITROS. Set it up once:

```bash
scripts/setup_host.sh                  # what's missing on this machine
scripts/container.sh init isaac_ros    # or: docker. Copies the template, sets DEVENV
scripts/container.sh build             # the image: system + rosdep deps only
scripts/container.sh shell             # start/attach, shell with the env sourced
make rosdeps && make build             # inside
```

The image holds **dependencies only**. The workspace is bind-mounted, and sources are
never `COPY`'d into a dev image (`.dockerignore` lets only `package.xml` files
through, for rosdep). When dependencies change, add them to `package.xml`, then run
`make rosdeps` in the container, and rebuild the image when convenient. Keep the
container name, workspace path (`CONTAINER_WS`) and RMW identical on every
machine. For Isaac ROS, `CONTAINER_WS` is `/workspaces/isaac_ros-dev`.

**DEVENV-002 — The environment is defined once, in `scripts/env.sh`.** It loads
`project.env`, sources ROS and `install/setup.bash`, and sets `RMW_IMPLEMENTATION`,
the RMW config file (`CYCLONEDDS_URI` / `FASTRTPS_DEFAULT_PROFILES_FILE`),
`ROS_DOMAIN_ID`, `external/` on `PYTHONPATH`, and `.venv` if present. Makefile targets,
panes, container shells and CI all source it. Never append `export ...` lines
to `~/.bashrc`, and never repeat these values in pane scripts, launch files or
Dockerfiles. A value that differs per machine goes in `project.env`, or is
overridden in the environment for one command (`ROS_DOMAIN_ID=7 make build`).

**DEVENV-003 — Routine actions are `make` targets.** Use `make build p=pkg`,
`make check p=pkg`, `make new-cpp n=name d=src/robots/arm`, `make rosdeps` and
`make panes`. Targets wrap the real tools (`tools/check.sh`, `tools/new_package.py`).
Don't duplicate logic in the Makefile. If you add a recurring command, add a target
to `Makefile.local` with a `## description`, not a README paragraph.

**DEVENV-004 — Starting the system: one pane plan.** `scripts/launch/panes.list`
lists `column|title|command` lines, numbered in start order. `make panes`
opens them in tmux (or `scripts/launch/panes.sh terminator`). Each pane sources
`env.sh`, runs inside the container when `DEVENV` isn't native, pre-fills its
command (Enter runs it, Ctrl+C skips it), and always leaves a prepared shell. When
you add a launch entry point a human needs, add a pane line. Never automate
keystrokes (xdotool) into terminals.

**DEVENV-005 — Scripts are idempotent, checked and quiet.** Setup scripts start with
`set -euo pipefail`, detect what's already done and skip it, never append the
same line twice, check prerequisites before acting, and print one line per action.
Comments and messages are in English so every agent and teammate can read them.
Host-modifying scripts check by default and change things only with `--install`.

## Middleware configuration

- Choose one RMW per project (`RMW_IMPLEMENTATION` in project.env). Tests and CI use
  the same one.
- Keep RMW XML in `config/`, name it in `RMW_CONFIG_FILE`, and never hard-code an
  absolute path.
- Cyclone on one machine with many participants: raise `MaxAutoParticipantIndex`
  (large Gazebo + MoveIt setups exceed the default), or use
  `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`.
- Keep `ROS_DOMAIN_ID` per project on shared lab networks, and record it in
  `PROJECT.md`. `tools/check.sh` always isolates tests anyway (TEST-006).
