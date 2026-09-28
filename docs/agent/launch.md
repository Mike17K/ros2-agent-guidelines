# Launch files, parameters, bring-up

**LAUNCH-001 — Python launch files named `<what>.launch.py`**, installed to
`share/<pkg>/launch`. Each node package ships a launch file for its own node(s)
(see the templates). The system is assembled in the project's `<robot>_bringup`
package, which includes those files.

**LAUNCH-002 — Everything tunable is a declared argument.** Use
`DeclareLaunchArgument(name, default_value=..., description=...)` for the
namespace, params file, remapped topics, `use_sim_time`, `autostart` and
`log_level`. Don't use `os.environ` or hard-coded values in launch files.

**LAUNCH-003 — Parameters come from YAML.** Launch passes `params_file` plus
explicit overrides as dicts. Node-scoped keys use wildcards so the file works in
any namespace:

```yaml
/**/filter_node:          # this node name in any namespace
  ros__parameters:
    cutoff_frequency_hz: 10.0
/**:                      # every node launched with this file
  ros__parameters:
    use_sim_time: false
```

The package's `config/` holds defaults that match the code. The bringup's
`config/` holds deployment values for a specific robot.

**LAUNCH-004 — Lifecycle nodes are brought up deterministically.**

| Situation | Mechanism |
|---|---|
| Standalone node, nothing depends on its ordering | `LifecycleNode(..., autostart=True)` (Jazzy launch_ros) |
| Several lifecycle nodes that must come up in order, or be restarted together | `nav2_lifecycle_manager` (`lifecycle_manager` node with `node_names`, `autostart`) |
| Lifecycle components in a container | `ComposableNodeContainer` + `nav2_lifecycle_manager` |

Never bring nodes up with `TimerAction` delays and `ros2 lifecycle set` calls.
Timing-based bring-up is flaky (LAUNCH-008).

**LAUNCH-005 — Simulation time is set in one place.** The bringup's top-level launch
declares `use_sim_time` and applies it globally with
`launch_ros.actions.SetParameter(name='use_sim_time', value=LaunchConfiguration('use_sim_time'))`
before including anything.

**LAUNCH-006 — Each launch file has a launch test** that starts it and asserts
the nodes reach their expected state or publish (TEST-005). Every template has one.

**LAUNCH-007 — Entity bringups share one argument interface.** Every
`<entity>_bringup/launch/bringup.launch.py` (ARCH-011) brings up one instance and
accepts:

| Argument | Meaning | Default |
|---|---|---|
| `namespace` | instance name, which prefixes all its topics, nodes and controller_manager | entity name |
| `prefix` | tf/joint name prefix when instances share one tf tree (usually `<namespace>_`) | `''` |
| `parent_link`, `xyz`, `rpy` | mount pose, passed to the xacro | `world`, `0 0 0`, `0 0 0` |
| `sim_gazebo` | spawn into a running Gazebo and bridge it | `false` |
| `use_fake_hardware` | mock ros2_control hardware (RViz only) | `true` |
| `use_sim_time` | follow `/clock` | same as `sim_gazebo` |
| entity-specific dimensions | e.g. `length`, `width` for parametric conveyors | package defaults |

The system bringup (ARCH-012) passes these from its layout module. It never
reaches inside an entity's launch file.

**LAUNCH-008 — Sequence with events, not timers.** Start controller spawners
after the entity is spawned or the controller_manager is up. Chain dependent
steps with `RegisterEventHandler(OnProcessExit(target_action=spawner_a, on_exit=[spawner_b]))`.
Readiness has to be a real signal, so wait on a service with the spawner's
`--controller-manager-timeout`, or on a lifecycle state via the lifecycle manager.
A single fixed `TimerAction` is acceptable **only** to wait for an external
simulator that exposes no readiness signal. Keep it constant (never proportional
to the number of instances), and comment why.

Other rules:
- Use `output='screen'` for development launch files. Don't use `emulate_tty` hacks
  in code.
- Use `FindPackageShare` + `PathJoinSubstitution` for every path (ARCH-007).
- Use `GroupAction` + `PushRosNamespace` to namespace whole subsystems, for example
  multi-robot.
- Use XML/YAML launch only if `PROJECT.md` says so. Don't mix formats within a project.
