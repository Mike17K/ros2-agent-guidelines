# Benchmark tasks

Paste the **Prompt** verbatim. The acceptance criteria are for the scorer only.

---

## B01 — Serial IMU lifecycle driver
**Prompt:** "Create a ROS 2 driver package for a serial IMU that sends ASCII lines
`$IMU,<ax>,<ay>,<az>,<gx>,<gy>,<gz>*<checksum>` at 200 Hz on a configurable serial
port and baud rate. Publish sensor_msgs/Imu."

**Acceptance:**
- C++ lifecycle component. The port is opened in `on_configure` and closed in `on_cleanup`/`on_error`.
- The parser is a ROS-free class with unit tests: valid line, bad checksum, truncated line, NaN.
- Port, baud, frame_id and timeout come from parameters (generate_parameter_library, units in names).
- The reader doesn't block the executor: a dedicated owned thread or a non-blocking read on a timer.
- `sensor_publisher()` QoS. The stamp is taken at line reception. Throttled warnings on parse errors.
- Diagnostics (rate, parse errors) via diagnostic_updater.

## B02 — QoS-correct point cloud subscriber
**Prompt:** "Add a node that subscribes to a LiDAR point cloud on `points`, removes
points closer than a configurable distance, and republishes on `points_filtered`."

**Acceptance:**
- C++. `sensor_subscription()` in, `sensor_publisher()` out.
- No per-point `push_back` without `reserve`. Uses `PointCloud2Iterator` or a precomputed layout.
- The core filter is ROS-free and unit tested. Publishes a `unique_ptr`. Is a component.
- Handles an empty cloud and a cloud without `x/y/z` fields (logs, doesn't crash).

## B03 — Velocity command mux with timeout
**Prompt:** "Create a node that takes velocity commands from `cmd_vel_teleop` and
`cmd_vel_nav`, prefers teleop when it is active, and outputs `cmd_vel`."

**Acceptance:**
- A per-input command timeout (a parameter). When all inputs are stale it publishes zero once
  and then stops (RT-006).
- `command()` QoS on all endpoints. The priority logic is a ROS-free core with unit tests,
  including timeout transitions using injected time.

## B04 — Async service client
**Prompt:** "Write a node that, when activated, calls the `enable_motors`
std_srvs/SetBool service and only starts publishing `status` after the call
succeeds. If the service is missing, retry every second."

**Acceptance:**
- No `spin_until_future_complete` or `future.get()` outside the response callback (CPP-004/PY-003).
- Requests time out and get pruned. Retry uses a timer, not sleep.
- A test with a mock service server covers success, failure and the service being absent.

## B05 — Interfaces package
**Prompt:** "Define interfaces for a gripper: a command to open/close with a
target force, feedback with the current width and force, and a status message."

**Acceptance:**
- `*_interfaces` package created via the scaffold.
- The open/close with feedback is an **action**. Status is a msg with `LEVEL_*` style constants.
- Units in brackets and in field names. A Header on status. Reuses std types where possible.

## B06 — Mission state machine (Python)
**Prompt:** "Create a Python node that runs a simple mission: wait until
`battery_ok` is true, send a `NavigateToPose` goal to `(x, y)` from parameters,
and report success or failure on `~/mission_state`."

**Acceptance:**
- The state machine is a ROS-free module with pytest tests.
- An action client with feedback/result callbacks. No sleep, no spin in callbacks.
- Parameter descriptors with ranges. `latched()` or `state()` QoS for mission state (justified).

## B07 — Bringup
**Prompt:** "Create a bringup package that launches the IMU driver and the IMU
filter in one process, in namespace `robot1`, with sim time configurable."

**Acceptance:**
- A composable container with intra-process comms. Lifecycle management via
  nav2_lifecycle_manager or autostart (justified).
- `use_sim_time` is set globally via `SetParameter`. Declared launch arguments. Params from YAML
  with `/**` keys.
- A launch test proves both nodes become active and data flows.

## B09 — Contract-first node with progressive integration
**Prompt:** "Add a node that converts `imu/data` (sensor_msgs/Imu) into a tilt angle
(roll, pitch) published as geometry_msgs/Vector3Stamped at the IMU rate, and integrate it
with the existing IMU filter."

**Acceptance:**
- `contract.yaml` written before the code, installed. The launch test runs the live check (CONTRACT-003).
- A `system.contract.yaml` (or an updated one) wires filter → tilt. `contracts.py graph` passes with no warnings.
- An L3 test brings up filter + tilt together and asserts the tilt output rate from a stimulus (TEST-011).
- Input loss is a tested failure mode (TEST-009).

## B10 — Plan before building
**Prompt:** "We want the arm to pick boxes from the conveyor using a wrist camera. Build it."

**Acceptance:**
- The agent does **not** write code. It explores, asks at most one batch of blocking questions
  with defaults, and writes `docs/plans/<date>-<slug>.md` from the template with 2–3 compared
  options, packages by domain folder and role, draft contracts, a verification ladder plan and
  integration milestones. Then it stops for approval (PLAN-002).

## B11 — Scale by layout, not code
**Setup:** a system bringup with one conveyor entity in `layout.py`.
**Prompt:** "Add a second conveyor next to the first one, 2 m long."

**Acceptance:**
- Only `layout.py` (plus its tests and, if needed, `system.contract.yaml`) changes. No launch
  file or entity package edits (ARCH-011/012).
- No delays proportional to the instance count (LAUNCH-008).

## B08 — Fix a planted bug
**Setup:** scaffold `tools/new_package.py cpp bug_filter`, then plant a bug: in
`on_deactivate`, delete both `subscription_.reset();` and `publisher_->on_deactivate();`
(a deactivated LifecyclePublisher refuses to publish, so both are needed for the symptom).
**Prompt:** "The filter keeps publishing after deactivation. Fix it."

**Acceptance:**
- The fix is minimal. A **regression test** (TEST-007) fails before the fix and passes after.
- The agent reports the root cause accurately.
