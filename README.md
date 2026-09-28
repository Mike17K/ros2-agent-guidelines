# ROS 2 agent guidelines workspace

A ROS 2 Jazzy workspace template that makes coding agents (Claude Code, Codex,
Cursor, Copilot, …) produce consistent, tested, production-style ROS 2 code.
Copy it for each new project.

It works in three layers:

1. **Guidance**: short, ID'd rules that agents read on demand.
   `AGENTS.md` (the core, always loaded) indexes `docs/agent/*.md` (topic files, loaded per task).
2. **Examples**: golden packages in `templates/`, which agents copy through a scaffolder
   instead of writing from memory.
3. **Enforcement**: `tools/check.sh` is the Definition of Done. It runs the rules linter, a
   `-Werror` build, clang-tidy, and unit, node, launch and lint tests. A Claude Code hook gives
   feedback after every edit, and CI runs the same gate.

```
AGENTS.md            core rules + index (all agents)     CLAUDE.md   imports AGENTS.md + PROJECT.md
PROJECT.md           per-project facts & overrides       .claude/    hook, permissions, skills, reviewer agent
project.env          machine-readable config (RMW, domain, DEVENV, container, coverage)
Makefile             front door: make help
docs/agent/          topic rules, ladder, contracts, planning, devenv, prompts, benchmarks
docs/plans/ docs/decisions/   approved plans and design decisions (project-owned)
templates/           ros_template_cpp | ros_template_py | ros_template_interfaces | devenv/
tools/               check.sh  new_package.py  lint_rules.py  contracts.py  verify_templates.sh  sync_guidelines.sh
scripts/             env.sh  container.sh  setup_host.sh  setup_external.sh  launch/panes.sh
external/            pinned non-ROS deps (external.list)
src/                 your packages, grouped by domain folder
```

The workflow agents follow: **plan** (`docs/plans/`, approved by you) → **contract** →
**tests** → **code**, climbing the verification ladder L0–L6 one level at a time.

## Start a new project

```bash
cp -r guidelines ~/ws/my_robot_ws && cd ~/ws/my_robot_ws
git init
$EDITOR PROJECT.md project.env           # identity, package map / RMW, domain, DEVENV
scripts/setup_host.sh                    # what this machine is missing
scripts/container.sh init isaac_ros      # optional: or docker; then make image && make shell
make new-cpp n=my_imu_driver d=src/drivers
make check                               # must print CHECK: PASS
```

Then work with your agent as usual. In Claude Code, `/ros2-new-package` and the
`ros2-reviewer` agent are available.

## Keep projects up to date

Treat this folder as the **upstream** repo (put it in git). In a project:

```bash
tools/sync_guidelines.sh ~/src/guidelines --dry-run
tools/sync_guidelines.sh ~/src/guidelines
```

This only touches the paths in `.guidelines-managed`. `PROJECT.md`, `src/`,
`docs/agent/local/` and `tools/local/` belong to the project and are never touched.

## Improve the guidelines

When an agent repeats a mistake, turn it into a rule (see `docs/agent/maintenance.md`,
or `/guidelines-add-rule` in Claude Code). Then measure the change with
`docs/agent/benchmarks/`. After changing templates or tools:

```bash
python3 tools/lint_rules.py --self-test
tools/verify_templates.sh               # scaffolds every template and runs the full check
```

## Requirements

Ubuntu 24.04, ROS 2 Jazzy (`ros-jazzy-ros-base`), plus
`ros-jazzy-generate-parameter-library`, `ros-jazzy-launch-testing-ros`, `ros-jazzy-std-srvs`,
and optionally `clang-tidy`, `pre-commit` and `ros-jazzy-realtime-tools`.
