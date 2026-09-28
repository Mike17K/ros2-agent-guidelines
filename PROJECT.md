# PROJECT.md — project profile (owned by this workspace, never synced)

Fill this in when you copy the guidelines into a new workspace. Agents read it
right after AGENTS.md; anything here overrides the defaults in docs/agent/.
Keep it factual and short. Delete the placeholder lines in angle brackets.

## Identity

| Item | Value |
|---|---|
| Project | <name, one-line purpose> |
| Robot(s) | <platform, number of robots, sim or real> |
| Maintainers | <name <email>> |
| Copyright holder | <organisation> (scaffold with `ROS_COPYRIGHT_HOLDER="..."`) |
| License | Apache-2.0 <or override> |

Machine-readable settings (RMW, domain, DEVENV, container, maintainer, coverage
threshold) live in `project.env`. Don't repeat them here.
Plans: `docs/plans/`. Structural decisions: `docs/decisions/`.

## Stack overrides (only if different from AGENTS.md §1)

| Item | Value |
|---|---|
| RMW | rmw_fastrtps_cpp <or rmw_cyclonedds_cpp + config file path> |
| ROS_DOMAIN_ID | <n> (tests run on an isolated domain regardless) |
| Simulator | <Gazebo Harmonic / Isaac / none> |
| Extra upstream stacks | <ros2_control, Nav2, MoveIt 2, ...> |

## Package map

Domain folders under `src/` (ARCH-010) and the entities in the system (ARCH-011).
The instance list itself lives in the system bringup's `layout.py` (ARCH-012).

| Package | Domain folder | Role | Responsibility | Owner |
|---|---|---|---|---|
| <project>_interfaces | src/ | interfaces | project msgs/srvs/actions | |
| <project>_utils | src/ | shared utils | clients, helpers, CLI checks | |
| <entity>_description / _bringup | src/robots/<entity>/ | entity | one instance of <entity> | |
| <system>_bringup | src/<system>/ | system bringup | layout.py + system launch | |
| <system>_orchestrator | src/<system>/ | orchestrator | task cycle state machine | |

## Conventions specific to this project

- Namespaces: <e.g. /robot_<id>/...>
- Frames: <map, odom, base_link, sensor frames...> (REP 105 unless stated)
- Hardware: <devices, ports via parameters, udev rules location>
- Network: <single machine / multi-machine, discovery server?>

## Project rules (LOCAL-xxx)

Rules that apply only to this project. Same format as docs/agent/.

| ID | Rule | Why |
|---|---|---|
| LOCAL-001 | <rule> | <reason> |

## Known exceptions

Deliberate deviations from the guidelines, with the reason and the date decided.

| Rule | Where | Reason | Date |
|---|---|---|---|
