# Python nodes (rclpy, Jazzy)

Start from `templates/ros_template_py/` (via `tools/new_package.py py <name>`).

**PY-005 — Python is allowed only off the hot path.** Use it for mission and task
logic, orchestration, monitoring, tooling and launch (see the table in
architecture.md). Never use it for drivers, control loops, or per-message
processing of high-rate or large data. If profiling shows a Python node on the
critical path, move the hot part to a C++ component.

## Structure

- **ARCH-002 applies.** Logic goes in a plain module (`rate_monitor.py`) with no `rclpy`
  import, taking time as an argument. The node module (`rate_monitor_node.py`) adapts.
- One node class per module, plus a `main()` registered in `setup.py`
  `console_scripts`.
- Import your own package's modules relatively inside the package
  (`from .rate_monitor import RateMonitor`). ament_flake8 sorts imports
  alphabetically, and relative imports stay valid when the package is renamed.

**PY-007 — `main()` pattern** (exact):

```python
def main(args=None) -> None:
    rclpy.init(args=args)
    node = MyNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
```

## Rules

**PY-001 — No `time.sleep()` in node code.** Use `self.create_timer(period, cb)`.
To "wait then do X", use a one-shot timer that cancels itself, or a state
machine advanced by a periodic timer.

**PY-002 — No `print()`.** Use `self.get_logger().info/warn/error/debug(...)`, with
`throttle_duration_sec=` or `once=True` for anything in a callback above 1 Hz.

**PY-003 — Never spin inside node code.** Calling
`rclpy.spin_until_future_complete(self, ...)` or `spin_once` from a callback
deadlocks or re-enters the executor. Use one of these instead:

```python
# (a) callback style
future = self._client.call_async(req)
future.add_done_callback(self._on_response)

# (b) async callback: the executor resumes it when the result arrives.
#     The service call must use a *different* callback group than the caller,
#     and the node must run under a MultiThreadedExecutor.
async def _on_timer(self):
    result = await self._client.call_async(req)
```

Always check `self._client.service_is_ready()` first, and handle a missing or slow
server: time it out with a timer that checks `future.done()` and calls
`future.cancel()`.

**PY-004 — Parameters with descriptors.** Every `declare_parameter` passes a
`ParameterDescriptor` with a `description`, a range (`FloatingPointRange` or
`IntegerRange`), and `read_only=True` if it's applied only at startup. Apply
runtime changes in an `add_on_set_parameters_callback`. rclpy already enforces the
descriptor ranges, so the callback only applies values (the template shows this).
Parameter names carry units.

**PY-006 — Typing and style.** Type hints on public functions and methods.
`ament_flake8` (max line 99, google import order) and `ament_pep257` (summary on
the second line of multi-line docstrings) are part of the tests. Use `f`-strings for
log messages.

## QoS in Python

Define named profiles once per package (the template's `STATE_QOS`) and import
them. Don't pass a bare integer depth (QOS-001). Standard profiles:
`rclpy.qos.qos_profile_sensor_data`, plus
`QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL)`
for latched data.

## Executors and concurrency

- By default, `rclpy.spin(node)` runs a `SingleThreadedExecutor`, and callbacks never
  overlap. That's the preferred mode for Python.
- `MultiThreadedExecutor` + `MutuallyExclusiveCallbackGroup` exist, but because of the GIL
  they buy concurrency (for waiting on I/O or services), not CPU speed.
- Never start `threading.Thread`s that call ROS APIs without a clear ownership and
  shutdown story. Join them in `destroy_node()`.

## Performance

- Keep callbacks O(message). No growing lists, and no per-callback imports.
- Use `numpy.frombuffer` on array fields instead of Python loops over message
  elements.
- Don't copy large messages. Don't convert images or clouds in Python on a path that
  must keep up with the sensor rate.
