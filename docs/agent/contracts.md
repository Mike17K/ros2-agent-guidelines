# Node contracts (`contract.yaml`)

A contract is the machine-readable interface of one node: what it publishes and
subscribes, its services and actions, QoS, parameters, lifecycle, and rate/latency
budgets. It's written **before** the code (PLAN-003), the code implements it, and tools
verify it at three points:

| Check | Tool | When | Catches |
|---|---|---|---|
| schema | `tools/contracts.py validate` | every `tools/check.sh` (L0) | malformed contracts, unknown QoS profiles, bad names |
| static graph | `tools/contracts.py graph` | every `tools/check.sh` (L0) | type mismatches, **incompatible QoS**, missing providers, conflicting command publishers |
| live | `contracts.check_live()` inside the node's launch test | L2/L3 | code that drifted from its contract: missing endpoints, wrong types or QoS, undeclared parameters, wrong lifecycle state |

**CONTRACT-001 — Every node has a contract.** `contract.yaml` sits next to
`package.xml` (packages with several nodes use `contracts/<node>.yaml`) and is
installed to `share/<pkg>/`. The templates show both the C++ and Python forms.

**CONTRACT-002 — The contract changes first.** An interface change edits the contract,
then the tests, then the code, in that order and in the same change. A contract that
disagrees with the code fails the live check.

**CONTRACT-003 — Each node's launch test runs the live check** against the node it
brings up (see `test/test_*_launch.py` in the templates). `tools/check.sh` exports
`GUIDELINES_TOOLS` so the test can import `contracts`.

**CONTRACT-004 — Systems declare their wiring.** A system bringup ships
`system.contract.yaml` listing its instances (contract id, namespace, remaps) and the
external topics provided by nodes without contracts (simulator, upstream stacks). With a
system file, `graph` treats a required input with no provider as an **error**.
Without one, it's a warning, because wiring happens in launch.

## Schema

```yaml
node: filter_node                       # default node name
package: my_pkg
executable: filter_node                 # what `ros2 run` starts
plugin: my_pkg::FilterNode              # C++ components only
lifecycle: true                         # live check expects state "active" after bring-up
parameters_schema: src/filter_node_parameters.yaml   # C++: the generate_parameter_library file
parameters:                             # Python (or anything without a schema file)
  - {name: expected_rate_hz, type: double, range: [0.1, 10000.0]}
  - {name: window_s, type: double, read_only: true}
publishes:
  - topic: imu/data                     # relative | ~/private | /absolute
    type: sensor_msgs/msg/Imu
    qos: sensor_publisher               # named profile (qos.md) or {reliability, durability, depth}
    rate_hz: {min: 190, max: 210}       # optional budget (L3 with stimulus, L6)
    max_latency_ms: 5                   # optional budget (header stamp -> receive)
    when: active                        # lifecycle nodes: exists only while active (default)
subscribes:
  - topic: imu/data_raw
    type: sensor_msgs/msg/Imu
    qos: sensor_subscription
    required: true                      # graph: must have a provider (default true)
services:        [{name: ~/reset, type: std_srvs/srv/Trigger}]
clients:         [{name: enable_motors, type: std_srvs/srv/SetBool}]
action_servers:  [{name: move_to, type: my_interfaces/action/MoveToPose}]
action_clients:  [{name: navigate_to_pose, type: nav2_msgs/action/NavigateToPose}]
```

Named QoS profiles, which must match `qos.hpp` / the Python constants:

| Profile | reliability | durability | depth |
|---|---|---|---|
| `sensor_publisher` | reliable | volatile | 5 |
| `sensor_subscription` | best_effort | volatile | 5 |
| `command` | reliable | volatile | 1 |
| `state` | reliable | volatile | 10 |
| `latched` | reliable | transient_local | 1 |

## System file

```yaml
# src/<system>/<system>_bringup/system.contract.yaml
system: workcell
instances:
  - {contract: imu_driver/imu_driver, namespace: robot_1}
  - {contract: imu_filter/filter_node, namespace: robot_1, remap: {imu/data_raw: imu/raw}}
external:                                # provided by nodes without contracts
  publishes:
    - {topic: /clock, type: rosgraph_msgs/msg/Clock, qos: {reliability: best_effort, durability: volatile}}
  services: []
```

Contract ids are `<package>/<node>`. Names resolve as ROS does: a relative
`a/b` in namespace `ns` becomes `/ns/a/b`, and `~/x` becomes `/ns/<node>/x`.
Remaps apply before resolution.

## Using the tool

```bash
python3 tools/contracts.py validate                 # all contracts under src/
python3 tools/contracts.py graph [--system FILE]    # static wiring check (auto-finds system files)
python3 tools/contracts.py live install/my_pkg/share/my_pkg/contract.yaml /robot_1/filter_node \
    --remap imu/data_raw:=imu/raw          # against a running system; mirror the launch remaps
```
