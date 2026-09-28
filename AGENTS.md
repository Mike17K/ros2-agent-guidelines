# AGENTS.md — ROS 2 workspace rules for coding agents

This file is the entry point for every coding agent (Claude Code, Codex, Cursor,
Copilot, custom). It is short on purpose: it holds the non-negotiable rules and
tells you which topic file to read for the task at hand. **Read only the topic
files your task needs** (see §4).

Precedence when instructions conflict: the user's explicit request in this
session > `PROJECT.md` (project-specific facts and overrides) > `docs/agent/*` >
this file's defaults. If a rule blocks the task, do not silently break it: either
suppress it with a written reason (§6) or ask.

## 1. Pinned stack (do not drift)

| Item | Version / choice | Notes |
|---|---|---|
| ROS 2 | **Jazzy Jalisco** | Only Jazzy APIs. No ROS 1, no Humble-only or Rolling-only APIs. |
| OS | Ubuntu 24.04 | |
| C++ | **C++17**, GCC 13 | `CMAKE_CXX_STANDARD 17`, extensions off. |
| Python | 3.12 | Type hints on public functions. |
| CMake | ≥ 3.22, modern target-based | `target_link_libraries` with exported targets only. |
| Build | `colcon build --symlink-install` | Always symlink mode in this workspace. |
| Style | ROS 2 style via `ament_lint_common` | uncrustify, cpplint, flake8, pep257, xmllint, copyright. |
| Params (C++) | `generate_parameter_library` | Typed, validated, documented from YAML. |
| RMW | per `PROJECT.md` (default `rmw_fastrtps_cpp`) | Never hard-code an RMW in code. |

Your training data is full of ROS 1 and older ROS 2 code. When unsure an API
exists in Jazzy, **verify against the installed headers** before using it:
`grep -rn "<symbol>" /opt/ros/jazzy/include/<pkg>/` or
`ros2 interface show <type>`. Never invent an API.

## 2. Non-negotiable rules

Each rule has an ID. The docs, the linter (`tools/lint_rules.py`) and review
comments all use the same IDs.

| ID | Rule | Why |
|---|---|---|
| PLAN-001 | New packages, new or changed interfaces or contracts, structural, safety or RT changes: **brainstorm and write a plan in `docs/plans/` first, get approval, then implement** milestone by milestone (`docs/agent/planning.md`). | Wrong decompositions are the most expensive mistakes to undo. |
| ARCH-001 | Create packages only with `tools/new_package.py {cpp,py,interfaces} <name>`, then adapt. Never hand-copy or start from scratch. | Golden templates already pass every check. |
| ARCH-002 | Algorithms live in a ROS-free core (library or module); the node is a thin adapter. | Core becomes unit-testable, reusable and benchmarkable. |
| ARCH-005 | Nodes use relative topic names; wiring is done by remapping in launch. | The same node works in any namespace or multi-robot setup. |
| CPP-001 | Any node that owns hardware, or that other nodes depend on, is a `rclcpp_lifecycle::LifecycleNode`. The constructor only declares params. `on_configure` allocates. `on_activate` starts I/O. | Deterministic bring-up, recoverable errors, no half-initialised nodes. |
| CPP-002 | C++ nodes are components (`rclcpp_components_register_node`). No hand-written `main()`. | Composition gives zero-copy intra-process transport for free. |
| CPP-003 / PY-001 | Never sleep in a callback or node code. | Sleeping stalls every callback on the executor. |
| CPP-004 / PY-003 | Never spin or block on a future inside node code. Service calls are async with a response callback and a timeout. | Blocking there is the #1 cause of ROS 2 deadlocks. |
| QOS-001 | Every pub/sub uses a **named QoS profile** chosen from the table in `docs/agent/qos.md`. No bare `10`. | Wrong QoS silently drops the connection or data. |
| RT-002 | No heap allocation, blocking locks, logging without throttle, or I/O in a control loop. | Unbounded latency means missed deadlines. |
| RT-006 | Every consumer of commands enforces a command timeout and goes to a safe state. | A dead publisher must not leave a robot moving. |
| CONTRACT-001 | Every node has a `contract.yaml` (topics, types, QoS, services, actions, params, budgets), written **before** the code. The launch test verifies the running node against it. | Integration errors (types, QoS, wiring) become mechanical checks. |
| TEST-001 | Tests at every ladder level the code reaches: L1 core units, L2 node (lifecycle incl. failure paths, params, data, input loss), L3 launch test with the contract check. Every bug fix adds a regression test. | Code moves up a level only after passing the current one. |
| TOOL-001 | You are done only when `tools/check.sh` prints `CHECK: PASS` (§3). | Tools verify what prose cannot. |

## 3. Definition of Done

A task is complete only when **all** of these hold:

1. Each touched node's `contract.yaml` exists and matches the code (CONTRACT-001).
2. Levels L0–L2 pass locally, and a Level 3 `launch_testing` test covers the node's
   integration with its direct neighbours (`docs/agent/testing.md`). In practice that's
   `tools/check.sh --packages <touched packages>` printing `CHECK: PASS`: guideline rules,
   a `-Werror` build, contracts, clang-tidy, and all tests including linters and launch tests.
   For threading or memory changes, also run `--sanitize asan` (`tsan` for concurrency).
   Coverage targets must be met (`--coverage`, TEST-017).
3. Every failure mode the code handles has a test proving it's handled (TEST-009), and
   new or changed behaviour has tests that fail without the change.
4. The package `README.md` interface table matches the contract.
5. No new `guideline-ignore`, `# noqa` or `NOLINT` without a written reason on the same line.
6. You report exactly what was run and its result. If a step was skipped, say so and why.

**If a test fails, fix the code, not the test**, unless the test itself is
demonstrably wrong, and then explain why (TEST-016). Never make a check pass by
weakening it: that means deleting or skipping tests, loosening assertions,
tolerances or timeouts, loosening `.clang-tidy`, removing linters from
`package.xml`, or lowering warning levels.

## 4. What to read for your task

| Task | Read |
|---|---|
| Anything (first time in this workspace) | `PROJECT.md`, then `docs/decisions/` for the area you touch |
| Designing a feature or system, brainstorming, anything PLAN-001 covers | `docs/agent/planning.md` (prompts in `docs/agent/prompts/`) |
| New package or node, choosing C++ vs Python, naming, frames, units, domain folders, entities, layout, utils, orchestrator | `docs/agent/architecture.md` |
| Container, Makefile, `scripts/`, environment, RMW config, starting the system (panes) | `docs/agent/devenv.md` |
| Writing or reviewing C++ nodes, CMake | `docs/agent/cpp.md`, then the template `templates/ros_template_cpp/` |
| Writing Python nodes | `docs/agent/python.md`, then `templates/ros_template_py/` |
| Any publisher or subscriber | `docs/agent/qos.md` |
| Control loops, drivers, anything timing-critical | `docs/agent/realtime.md` |
| Throughput, latency, CPU, large messages (images, clouds) | `docs/agent/performance.md` |
| New msg/srv/action | `docs/agent/interfaces.md`, then `templates/ros_template_interfaces/` |
| Launch files, parameter YAML, bring-up, lifecycle management | `docs/agent/launch.md` |
| Tests, the verification ladder L0–L6, coverage, replay/sim/acceptance | `docs/agent/testing.md` |
| Node contracts (`contract.yaml`, `system.contract.yaml`) | `docs/agent/contracts.md` |
| A check failed and you don't know why | `docs/agent/tooling.md` |
| Reviewing code (yours or others') | `docs/agent/anti_patterns.md` |
| Changing these guidelines | `docs/agent/maintenance.md` |
| Project-specific topics | `docs/agent/local/` (if it exists) |

## 5. Commands

```bash
make help                                   # every routine action (DEVENV-003)
source scripts/env.sh                       # the workspace environment (DEVENV-002)
make new-cpp n=<name> d=src/<domain>        # = tools/new_package.py cpp|py|interfaces (ARCH-001)
make build p=<pkg>   make check p=<pkg>     # = tools/check.sh --packages <pkg> (Definition of Done)
make asan p=<pkg>    make tsan p=<pkg>      # sanitizer gates
python3 tools/lint_rules.py <path>          # guideline rules only (fast)
python3 tools/lint_rules.py --list          # all mechanically enforced rules
make shell   make panes                     # dev container shell / launch panes
```

## 6. Rule IDs and suppression

The ID prefix tells you where a rule lives in `docs/agent/`: `ARCH` goes to
architecture, `CPP`/`CMAKE` to cpp, `PY` to python, `QOS` to qos, `RT` to realtime,
`PERF` to performance, `IF` to interfaces, `LAUNCH` to launch, `TEST` to testing,
`CONTRACT` to contracts, `PLAN` to planning, `DEVENV` to devenv, `TOOL` to tooling,
`MAINT` to maintenance, and `LOCAL` to `PROJECT.md`.

A suppression is acceptable only when the rule genuinely does not apply, and it
must carry the reason on the same (or preceding) line:

```cpp
std::this_thread::sleep_for(2ms);  // guideline-ignore: CPP-003 runs in the dedicated driver thread, not an executor callback
```

## 7. Never

- Edit `templates/`, `docs/agent/` or `tools/` in a project workspace. They are
  synced from upstream (`docs/agent/maintenance.md`). Put project additions in
  `PROJECT.md`, `docs/agent/local/` or `tools/local/`.
- Commit `build*/`, `install*/` or `log*/`.
- Hard-code absolute paths, IPs, robot names or serial ports in code. Use parameters.
- Append environment exports to `~/.bashrc`, or repeat RMW/domain settings anywhere
  but `project.env` (DEVENV-002).
- Copy third-party sources into `src/`. Use `external/` submodules (ARCH-015).
- Add a dependency without declaring it in `package.xml` (rosdep key) and CMake/setup.py.
- Leave a `TODO` without a reason and an owner or issue reference.
