# QoS: choosing profiles

**QOS-001 — Named profiles only.** Every `create_publisher`/`create_subscription`
takes a profile from the package's `qos.hpp` (C++) or module constants (Python).
There are no bare depths (`10`) and no inline `rclcpp::QoS(10)`. The template's
`include/<pkg>/qos.hpp` shows the full set. Copy it, or depend on the project's
common package if `PROJECT.md` names one.

**QOS-002 — Pick the profile from this table.** It follows REP 2003.

| Data | Publisher | Subscriber | Notes |
|---|---|---|---|
| Sensor stream (IMU, LiDAR, camera, joint_states > 10 Hz) | `sensor_publisher()`: reliable, keep_last 5, volatile | `sensor_subscription()`: best-effort (`SensorDataQoS`), keep_last 5 | A reliable publisher lets both reliable and best-effort subscribers connect. |
| Commands (`cmd_vel`, setpoints) | `command()`: reliable, keep_last 1 | `command()` | Only the newest matters. The consumer **must** time out (RT-006). |
| State/status/events that must not be missed | `state()`: reliable, keep_last 10 | `state()` | Size the depth to the burst length. |
| Latched: map, `robot_description`, static config, one-shot "ready" | `latched()`: reliable, transient_local, keep_last 1 | `latched()` | **Both sides** must be transient_local (QOS-004). |
| `/tf` | `tf2_ros::TransformBroadcaster` | `tf2_ros::TransformListener` | Never create tf pub/sub by hand. |
| `/tf_static` | `tf2_ros::StaticTransformBroadcaster` | listener | |
| Parameters, services, actions | defaults | defaults | Don't override without a measured reason. |
| Large data over Wi-Fi / between machines | best-effort both sides, depth 1–2 | best-effort | Also consider `image_transport` compression, or composition to avoid the network. |

**QOS-003 — Compatibility is checked at connect time, and fails silently.**

| Publisher \ Subscriber | best-effort sub | reliable sub |
|---|---|---|
| best-effort pub | ✅ | ❌ no connection |
| reliable pub | ✅ | ✅ |

| Publisher \ Subscriber | volatile sub | transient_local sub |
|---|---|---|
| volatile pub | ✅ | ❌ no connection |
| transient_local pub | ✅ | ✅ |

The rule of thumb: a publisher should be at least as strong as any subscriber.
Check a live system with `ros2 topic info -v <topic>` (it shows each endpoint's QoS).
Nodes that must detect this at runtime set
`PublisherOptions::event_callbacks.incompatible_qos_callback` (or the subscription
equivalent) and log an ERROR.

**QOS-004 — Latched topics need transient_local on both ends.** A volatile
subscriber to a transient_local publisher connects, but it misses the latched sample.

## Deadline, lifespan, liveliness

- Use a `deadline` only when a consumer reacts to it (via `deadline_callback`) and the
  RMW supports it (Fast DDS and Cyclone do). It never replaces an application-level
  timeout for safety (RT-006).
- Use `lifespan` to drop stale samples in queues, for example commands older than 100 ms.
- Leave `liveliness` at its default unless you implement a watchdog on it.

## Python equivalents

```python
from rclpy.qos import (QoSProfile, ReliabilityPolicy, DurabilityPolicy,
                       qos_profile_sensor_data)
SENSOR_PUB = QoSProfile(depth=5, reliability=ReliabilityPolicy.RELIABLE)
SENSOR_SUB = qos_profile_sensor_data
COMMAND = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE)
STATE = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)
LATCHED = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                     durability=DurabilityPolicy.TRANSIENT_LOCAL)
```
