# Real-time and control loops

Scope: any loop with a deadline. That includes motor and joint control, driver
read/write loops, safety monitors, and anything above 50 Hz that actuates.

**RT-008 — Use ros2_control for actuator control.** Joint- or motor-level
control is written as a `hardware_interface::SystemInterface` (or
`ActuatorInterface`/`SensorInterface`) plus existing controllers
(`joint_trajectory_controller`, `diff_drive_controller`, …), or a custom
`controller_interface::ControllerInterface`. Don't write a standalone node with its
own control loop. ros2_control already provides the RT thread, the lifecycle, lock-free
command/state exchange, and the tooling. Follow its API docs for Jazzy
(`/opt/ros/jazzy/include/hardware_interface/`, `controller_interface/`).

The rules below apply inside ros2_control `read()`/`write()`/`update()` and to any
dedicated RT thread you own.

**RT-001 — The RT path calls only RT-safe code.** It uses bounded time, and has no
allocation, no blocking, no syscalls with unbounded latency, and no exceptions. Core
classes on the RT path document this and mark functions `noexcept` (see
`LowPassFilter`).

**RT-002 — Nothing unbounded in the loop.** Specifically:

| Forbidden in the loop | Do instead |
|---|---|
| `new`, `make_shared`, `push_back` beyond capacity, `std::string` building, `std::function` construction | preallocate in `on_configure` (`reserve`, fixed-size `std::array`) |
| `std::mutex::lock()` shared with non-RT threads | `realtime_tools::RealtimeBuffer` / `RealtimeThreadSafeBox`, `std::atomic` for PODs, `try_lock` and skip |
| `RCLCPP_INFO` etc. | `RCLCPP_*_THROTTLE`, or count errors and report from a non-RT thread |
| `publisher->publish()` of a non-RT publisher | `realtime_tools::RealtimePublisher::try_publish(msg)` (the older `trylock()`/`unlockAndPublish()` pair is deprecated) |
| File, socket or serial I/O with no timeout | non-blocking I/O with a bounded timeout, or I/O in a separate thread feeding a lock-free buffer |
| `param_listener_->get_params()` | `param_listener_->try_get_params(params_)` |
| Exceptions | error codes / `std::optional` |

**RT-003 — Handoff between threads is lock-free or try-lock.** The RT thread
never waits on a lock held by a non-RT thread (priority inversion).

**RT-004 — Measure the loop.** Record period jitter and execution time
(min/mean/max) with `std::chrono::steady_clock`, and publish them from a non-RT
context through `diagnostic_updater`. An overrun is a WARN diagnostic, not a
log line per cycle.

**RT-005 — Dedicated RT threads are set up once, in `on_activate`.**

```cpp
#include "realtime_tools/realtime_helpers.hpp"

// on_configure: lock memory and preallocate before the loop ever runs.
if (auto [ok, msg] = realtime_tools::lock_memory(); !ok) {
  RCLCPP_WARN(get_logger(), "lock_memory failed: %s", msg.c_str());
}
// on_activate:
running_ = true;
rt_thread_ = std::thread([this] {
  if (!realtime_tools::configure_sched_fifo(params_.rt_priority)) {
    RCLCPP_WARN(get_logger(), "SCHED_FIFO unavailable; running best-effort");  // once, before loop
  }
  auto next = std::chrono::steady_clock::now();
  while (running_.load(std::memory_order_relaxed)) {
    next += period_;
    step();                                             // RT-safe only
    std::this_thread::sleep_until(next);                // guideline-ignore: CPP-003 dedicated RT thread, absolute-time sleep
  }
});
// on_deactivate: running_ = false; rt_thread_.join();
```

Check `realtime_tools::has_realtime_kernel()` at configure and report it in diagnostics.
Use `sleep_until` on an absolute schedule, never `sleep_for`, because relative sleeps
drift. Make the priority a parameter. Real-time behaviour needs a PREEMPT_RT
kernel and rtprio limits, and PROJECT.md states whether the target has them.

**RT-006 — Command timeout and safe state.** Every command consumer stores the
receive time of the latest command, taken from a steady clock or the node clock.
When a command is older than `command_timeout_s` (a parameter, typically 0.1–0.5 s),
it switches to a defined safe state: zero velocity, hold position, or brake. It logs
the switch once and recovers when commands resume. QoS deadline is not a substitute.

**RT-007 — Clocks.** Measure durations and schedules with
`std::chrono::steady_clock`, which is monotonic. Message stamps and anything that
must follow simulation use the node clock (`now()`, ROS time). Never use
`system_clock` for timing, because it jumps.

**Safety note.** Emergency stop and safety-rated functions must not depend
on ROS 2 message delivery alone. Hardware e-stop chains and drive-level safety are
outside this software stack. Software can only add a secondary layer of
monitoring on top.
