---
name: ros2-new-package
description: Create a new ROS 2 package or node in this workspace (C++ lifecycle component, Python node, or msg/srv/action interfaces) from the golden templates, following the project guidelines through to a passing tools/check.sh. Use whenever the user asks for a new package, node, driver, interface definition or bringup.
---

# New ROS 2 package / node

Follow these steps in order. Don't skip the check at the end.

## 0. Plan

If this is part of a larger feature (PLAN-001), there must be an approved plan in
`docs/plans/`. If there isn't one, run `/ros2-plan` first. Follow the plan's package, contract and milestone decisions.

## 1. Decide

- **Language**: use the "C++ or Python?" table in `docs/agent/architecture.md`. If unsure, choose C++.
- **Role**: interfaces, driver/node, core library or bringup (same doc, "Package taxonomy").
- **Name**: `lower_snake_case`, domain first, no `ros_` prefix. Interface packages end in `_interfaces`.
- **Existing package?** If the node belongs in an existing package, skip step 2. Copy the
  template's node files (node .hpp/.cpp, parameters YAML, config, launch, tests) into that
  package by hand, and register the component in its CMakeLists.txt.
- Read `PROJECT.md` for namespaces, frames, the RMW and any `LOCAL-` rules.

## 2. Scaffold

```bash
tools/new_package.py cpp|py|interfaces <name> [--dest src/<group>]
```

If it fails for lack of maintainer info, ask the user or use the values from `PROJECT.md`.

## 3. Adapt the template

**Write `contract.yaml` first** (CONTRACT-001/002, `docs/agent/contracts.md`), then the tests, then the code.
Rename the example (`FilterNode`/`LowPassFilter` or `RateMonitorNode`/`RateMonitor`) to the
domain: files, classes, the plugin name in CMake, the executable, launch and config. Keep the structure:

- The ROS-free core goes in `include/<pkg>/<core>.hpp` + `src/<core>.cpp` (or `<pkg>/<core>.py`),
  with unit tests.
- The node is a thin adapter. Lifecycle transitions follow the table in `docs/agent/cpp.md`.
- Parameters go in `src/<node>_parameters.yaml` (C++) with descriptions, units and validation.
- QoS: choose each endpoint's profile from `docs/agent/qos.md`, and extend `qos.hpp` if needed.
- Timing-critical work: read `docs/agent/realtime.md` first. Actuator control → ros2_control.
- Update the tests to your behaviour, level by level (`docs/agent/testing.md`): L1 core, L2 node (lifecycle
  incl. failure paths, parameter rejection, data flow when active, silence when inactive, input loss),
  L3 launch test with the live contract check. Hardware nodes get a fake backend (TEST-010).
- Delete template leftovers you don't use. `grep -rni "filter\|imu\|rate_monitor" src/<name>` should
  only match things that are really yours.
- Update `README.md` (interface table) and the `package.xml` description and dependencies.

Before using any API you haven't seen in the template, verify it exists in Jazzy:
`grep -rn "<symbol>" /opt/ros/jazzy/include/<pkg>/`.

## 4. Verify

```bash
tools/check.sh --packages <name>
```

Iterate until it prints `CHECK: PASS`. For threads, buffers or parsing, also run
`--sanitize asan` (and `tsan` for threads). Then consider delegating a review to the
`ros2-reviewer` agent, and fix what it finds.

## 5. Report

Report: files created, the interface (topics/services/params with QoS), design decisions, the exact
check commands run and their results, and anything skipped or left open.
