# Architecture: workspace, packages, nodes, naming

## Workspace layout

```
<ws>/
  AGENTS.md CLAUDE.md PROJECT.md     # agent entry points
  project.env                        # machine-readable project config (RMW, domain, container, ...)
  Makefile                           # the one command front door (make help)
  docs/agent/                        # these guidelines (synced from upstream)
  docs/plans/  docs/decisions/       # approved plans, design decision records (project-owned)
  templates/                         # golden packages (COLCON_IGNOREd, never built in place)
  tools/                             # check.sh, new_package.py, lint_rules.py, contracts.py
  scripts/                           # env.sh, container + launch entry points (devenv.md)
  external/                          # non-ROS deps as pinned git submodules (ARCH-015)
  src/                               # ALL ROS packages, grouped by domain (ARCH-010):
    <project>_interfaces/            # one project interface package (IF-001)
    <project>_utils/                 # shared helpers + clients (ARCH-013)
    robots/<entity>/<entity>_description|_bringup|_moveit_config|_driver   (ARCH-011)
    perception/...  planning/...  control/...
    <system>/<system>_bringup/       # composes entity bringups from a layout (ARCH-012)
    <system>/<system>_orchestrator/  # high-level behaviour (ARCH-014)
```

colcon only builds `src/` (`tools/check.sh` passes `--base-paths src`).

## Package taxonomy

Every package has exactly one of these roles. The role decides its template and
dependencies.

| Role | Template | Contains | May depend on |
|---|---|---|---|
| interfaces | `interfaces` | `.msg/.srv/.action` only | other interface packages |
| core library | `cpp` (drop the node) | ROS-free algorithms | Eigen, std, other core libs |
| driver / node | `cpp` or `py` | lifecycle node(s) + core | interfaces, core |
| description | (manual) | URDF/xacro, meshes | none |
| entity bringup | `py` (keep only launch/config) | one-instance launch, controllers YAML | its description, drivers |
| shared utils | `py` or `cpp` | helpers, clients, CLI check tools (ARCH-013) | interfaces, core |
| system bringup | `py` | layout module + system launch (ARCH-012) | entity bringups (exec_depend) |
| orchestrator | `py` | high-level behaviour state machines (ARCH-014) | interfaces, utils |

Dependencies point downward: system bringup / orchestrator → entity bringups and
capability nodes → utils → core/interfaces. **Never** make a capability depend on
a bringup or orchestrator package, and never create cycles.
`colcon graph --base-paths src` shows the actual graph.

## Rules

**ARCH-001 — Scaffold, don't hand-roll.** New packages come from
`tools/new_package.py`. It renames every token, fills in the maintainer and
copyright, and refuses invalid or duplicate names. After scaffolding, rename the
example classes and files to the domain and delete what you don't need.
*Why: the templates are verified end to end by `tools/verify_templates.sh`.*

**ARCH-002 — ROS-free core, thin node.** Put algorithms, state machines,
parsers and kinematics in plain C++ classes or Python modules with no
`rclcpp`/`rclpy` includes. They take time as an argument and return values or
error codes. The node only converts messages, handles parameters and lifecycle,
and calls the core.
*Why: the core gets fast deterministic unit tests, can be benchmarked and reused,
and the node stays small enough to review.*

```
templates/ros_template_cpp/include/ros_template_cpp/low_pass_filter.hpp   <- core
templates/ros_template_cpp/src/filter_node.cpp                            <- adapter
```

**ARCH-003 — Naming.**

| Thing | Convention | Example |
|---|---|---|
| Package | `lower_snake_case`, domain-first, no `ros_`/`rcl` prefix | `ur_arm_driver`, `lidar_filters` |
| Interface package | ends in `_interfaces` or `_msgs` | `amr_interfaces` |
| Node name | `lower_snake_case`, what it does | `imu_filter`, `mission_manager` |
| Topic / service / action | `lower_snake_case`, nouns, relative | `imu/data`, `cmd_vel`, `get_map` |
| Private (node-scoped) topic | `~/name` | `~/status` |
| Parameter | `lower_snake_case`, **unit suffix** | `cutoff_frequency_hz`, `timeout_s`, `max_speed_mps` |
| C++ namespace | package name | `namespace ur_arm_driver` |
| C++ class / function / member | `CamelCase` / `snake_case` / `snake_case_` | `FilterNode::on_imu`, `publisher_` |
| C++ constant | `kCamelCase` | `kMaxJoints` |
| Python module / class | `snake_case` / `CamelCase` | `rate_monitor.py` / `RateMonitor` |
| Launch file | `<what>.launch.py` | `robot.launch.py` |

**ARCH-004 — `package.xml` format 3.** Declare every dependency with its rosdep
key, using the right tag: `depend`, `build_depend`, `exec_depend` or
`test_depend`. `rosdep check --from-paths src --ignore-src` must pass.

**ARCH-005 — Relative names, wire in launch.** Code uses `imu/data`, never
`/imu/data` and never `/robot1/imu/data`. Launch files remap and set namespaces.
Use `~/` for topics that belong to one node (status, debug).
*Why: absolute names break namespacing, multi-robot setups and composition.*

**ARCH-006 — ROS 2 only.** Never use `ros/ros.h`, `ros::`, `rospy`, `catkin`,
`roslaunch` XML, or `ROS_INFO` without the `RCLCPP_` prefix.

**ARCH-007 — No absolute or user paths.** Find files with `FindPackageShare`
(launch), `ament_index_cpp::get_package_share_directory` (C++) or
`ament_index_python.packages.get_package_share_directory` (Python). Device paths,
IPs and serial ports are parameters.

**ARCH-008 — Units and frames follow REP 103 / REP 105.** Use SI units: m, s, rad,
m/s, rad/s, N, kg. Axes are right-handed, with x forward, y left, z up (optical
frames `*_optical_frame` are z forward). The standard frames are `map` → `odom` →
`base_link` → sensor frames. Every stamped message carries the correct `frame_id`
and a stamp taken at **acquisition time**, not publish time. Broadcast
transforms only with `tf2_ros` broadcasters; static transforms come from the URDF
(`robot_state_publisher`) or `static_transform_publisher`.

**ARCH-009 — Hardware nodes report diagnostics.** Drivers publish
`/diagnostics` via `diagnostic_updater` (connection state, rates, error counters)
and use `on_error` to release hardware so the node can be reconfigured.
*Why: a silent driver is the hardest failure to debug in the field.*

## C++ or Python?

| Node does | Language | Why |
|---|---|---|
| Hardware driver, sensor I/O | **C++** | latency, lifecycle, composition |
| Control loop ≥ 50 Hz or with deadlines | **C++** (prefer ros2_control, see realtime.md) | determinism |
| Image / point-cloud processing | **C++** | zero-copy, throughput |
| High-rate message transforms (> 100 Hz or > 1 MB/s) | **C++** | GIL, allocation |
| Mission / task logic, state machines, orchestration | Python allowed | clarity, low rate |
| Monitoring, tooling, test helpers, launch | Python | |
| ML inference | Python allowed if the model runtime is in Python; move pre/post-processing hot paths to C++ when profiling says so | |

If you're unsure, use C++. Python nodes must not sit in a control or sensor data path.

## Node granularity

- One node, one responsibility you can describe in a sentence without "and".
- Split along data rate and failure domains, not along source files.
- Don't split for performance at the process level. Nodes are components, and
  launch composes them into one process when latency matters (performance.md).

## System structure: domains, entities, layout

These rules come from a working multi-robot workcell workspace (arm + conveyor
fleet + box factories, simulated in Gazebo). They are what lets a system grow from
one robot to a fleet without rewriting its launch files.

**ARCH-010 — Group packages by domain folder.** `src/robots/`, `src/perception/`,
`src/planning/`, `src/control/`, `src/<system>/`. Folders are organisational only:
package names stay globally unique and descriptive (`conveyor_bringup`, not
`bringup`). A new package goes into the existing domain folder that owns its
responsibility. Create a new domain folder only when none fits, and record it in
`PROJECT.md`.

**ARCH-011 — Every physical thing is an entity with its own package set.** That
includes arms, mobile bases, conveyors, dispensers, sensors mounted in the cell,
and anything with its own frames or controllers. Each entity gets:

| Package | Contains | Required |
|---|---|---|
| `<entity>_description` | URDF/xacro (parametric: dimensions and mount pose as xacro args), meshes, `ros2_control` tags | always |
| `<entity>_bringup` | one `bringup.launch.py` that brings up **one instance**: robot_state_publisher, controller_manager + spawners, sim spawn/bridge, its own nodes | always |
| `<entity>_moveit_config` | MoveIt config (Setup Assistant output) | manipulators |
| `<entity>_driver` | hardware interface or driver node (templates `cpp`) | real hardware |

*Why: an entity bringup that brings up exactly one instance can be included N
times under N namespaces. Fleet size becomes data, not code.*

**ARCH-012 — The system bringup composes instances from one layout.** A
`<system>_bringup` package holds a ROS-free layout module (`<system>_bringup/layout.py`),
which is the **single source of truth** for which instances exist, their
namespaces, poses, dimensions and per-instance overrides, plus the derived geometry
(helper functions, unit tested). The system launch file loops over it and includes
each entity's `bringup.launch.py` inside a `GroupAction` with the standard
arguments (LAUNCH-007). Any other code that needs the cell geometry, like collision
scenes, RViz and demos, imports the same layout module instead of duplicating numbers.

```python
for robot in layout.ROBOTS:
    stacks.append(GroupAction([IncludeLaunchDescription(
        PythonLaunchDescriptionSource(group_a_bringup_launch),
        launch_arguments={'namespace': robot['name'], 'xyz': robot['xyz'], 'rpy': robot['rpy'],
                          'parent_link': 'world', 'sim_gazebo': sim, 'use_fake_hardware': fake}.items())]))
```

Each instance's pipeline is self-contained per namespace (its own
controller_manager and spawners), so instances start in parallel. Never stagger
them with delays that grow with fleet size.

**ARCH-013 — One shared utilities package for cross-cutting helpers.**
`<project>_utils` (Python, and/or C++) holds reusable pieces: planner and action
client wrappers, trajectory execution, geometry and TF helpers, joint-state
helpers, filters, bag I/O, and one-shot CLI tools for checking a capability
(`ros2 run <project>_utils <cap>_cli ...`). It contains **no node that runs as part
of the system** and no system-specific constants. Every module is either ROS-free
and unit tested, or a thin client wrapper with a test. Before writing a helper,
check that it isn't already here. If a second package needs something you wrote,
move it here.

**ARCH-014 — Orchestration is separate from capabilities.** Capability packages
(drivers, perception, planning) expose ROS interfaces: actions, services and
topics. They never decide *what the system does next*. The high-level behaviour
(task cycles, mission logic, demos) lives in a dedicated `<system>_orchestrator`
or `<system>_demo` package. It uses only those interfaces, via the
`<project>_utils` clients, and puts its logic in a ROS-free, tested state machine.
Interactive tools (teleop UIs, navigator CLIs) are separate packages too.

**ARCH-015 — Non-ROS third-party code lives in `external/` as pinned git
submodules.** An idempotent `scripts/setup_external.sh` initialises the submodules,
checks out a pinned tag or commit, and downloads model weights into
`external/weights/`, which is gitignored and never committed. Code finds them
through one helper in `<project>_utils` that adds `external/` to the path. Never
copy third-party sources into `src/`. Forks of ROS packages that you must patch
are submodules under `src/` with the upstream URL and the reason recorded in
`PROJECT.md`. Trim large upstream monorepos with a sparse checkout.

**ARCH-016 — Record structural decisions.** Any decision that constrains future
work gets a short entry in `docs/decisions/` (template:
`docs/agent/decision_template.md`). Examples: why a planner runs in a given mode,
why the workspace lives in the container, why two collision representations are
not mixed. Record it at the moment it's made, and include the alternatives you
rejected. Agents read `docs/decisions/` before proposing changes to the affected
area.
