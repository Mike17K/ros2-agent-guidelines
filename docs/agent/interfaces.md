# Interfaces: msg, srv, action

Start from `templates/ros_template_interfaces/` (via `tools/new_package.py interfaces <name>`).

**IF-001 — Dedicated interface packages.** Definitions live in `*_interfaces` or
`*_msgs` packages that contain nothing else: no nodes, no libraries, no launch files.
*Why: any package can depend on them without pulling in code, and the
generated code builds once.*

**IF-002 — Reuse before you define.** Check the standard types first:
`std_msgs` (Header only; never use `std_msgs/String` or `Float64` as a semantic type),
`geometry_msgs`, `sensor_msgs`, `nav_msgs`, `diagnostic_msgs`, `trajectory_msgs`,
`control_msgs`, `shape_msgs`, `vision_msgs`, `lifecycle_msgs` and `std_srvs`. List
what's installed with `ros2 interface list | grep <word>`, and inspect a type with
`ros2 interface show <type>`. Define a new type only when no standard one carries
the meaning.

**IF-003 — Enumerations are constants.** Use `uint8 MODE_IDLE=0` style constants
inside the definition that uses them, and never magic numbers explained in comments.
Name them `PREFIX_VALUE` so the generated code groups them.

**IF-004 — Topic, service or action?**

| Interaction | Use |
|---|---|
| Continuous data, many consumers, latest value wins | topic |
| Request/response that finishes in < ~100 ms, no progress needed | service |
| Takes longer, needs progress feedback, or must be cancellable | **action** |
| Configuration that changes rarely | parameter (not a service) |
| "Tell everyone something happened" | topic with `state()`/`latched()` QoS |

Service servers must answer fast. Never start long work inside a service
callback: make it an action.

**IF-005 — Field conventions.**
- Every field has a trailing comment. Physical quantities give the unit in brackets
  (`# [m/s]`) and the frame if relevant. The name carries the unit suffix when the
  type doesn't make it obvious (`distance_remaining_m`).
- Stamped data includes `std_msgs/Header header` as its first field.
- Use SI units (REP 103). Angles are radians; use quaternions for 3D orientation.
- Use fixed-size arrays (`float64[6]`) when the size is part of the meaning, and bounded
  arrays (`float64[<=100]`) when there's a hard upper limit.
- Use `builtin_interfaces/Time` and `Duration` for time. Never use `float64 seconds` for
  absolute time.
- Actions put the error enum in the result (`ERROR_*` + `error_code` + `message`).

**IF-006 — Interfaces are an API.** Once released, don't rename, retype or reorder
fields. Changing a definition changes its type hash, and old bags and nodes stop
matching. Add new fields at the end, or version with a new type name.
