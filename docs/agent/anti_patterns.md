# Anti-patterns: bad → good

Mistakes agents actually make, each tied to its rule ID. Use this as the review
checklist. Add a new pair every time a mistake recurs (maintenance.md).

---

### 1. Blocking service call in a callback — CPP-004 / PY-003
```cpp
// BAD: deadlocks. This callback holds the executor that must deliver the response.
auto future = client_->async_send_request(req);
rclcpp::spin_until_future_complete(shared_from_this(), future);
```
```cpp
// GOOD: continue in the response callback; prune timed-out requests from a timer.
client_->async_send_request(req, [this](Client::SharedFuture f) {on_enabled(*f.get());});
```

### 2. Sleeping to wait — CPP-003 / PY-001
```python
# BAD
self.pub.publish(start); time.sleep(2.0); self.pub.publish(go)
```
```python
# GOOD: a one-shot timer
self.pub.publish(start)
self._go_timer = self.create_timer(2.0, self._send_go)   # _send_go cancels the timer
```

### 3. Bare QoS depth / wrong reliability — QOS-001 / QOS-003
```cpp
// BAD: reliable depth 10 for a 1 kHz IMU; a SensorDataQoS publisher elsewhere never connects.
sub_ = create_subscription<Imu>("imu", 10, cb);
```
```cpp
// GOOD
sub_ = create_subscription<Imu>("imu/data", qos::sensor_subscription(), cb);
```

### 4. Plain node that owns hardware — CPP-001
```cpp
// BAD: opens the port in the constructor; no way to reconfigure or recover.
Driver() : Node("driver") { fd_ = open("/dev/ttyUSB0", O_RDWR); timer_ = create_wall_timer(...); }
```
```cpp
// GOOD: LifecycleNode. Port from a parameter, opened in on_configure,
// I/O started in on_activate, closed in on_cleanup/on_error.
```

### 5. Allocation in the control loop — RT-002
```cpp
// BAD
void update() { std::vector<double> cmd(joints_.size()); auto msg = std::make_shared<State>(); ... }
```
```cpp
// GOOD: preallocated in on_configure; the loop only writes into it.
void update() noexcept { for (size_t i = 0; i < n_; ++i) {cmd_[i] = ...;} rt_pub_->try_publish(state_); }
```

### 6. Throwing out of a callback — CPP-006
```cpp
// BAD: one bad packet kills the process and every component in the container.
void on_packet(const Packet & p) { auto v = parse(p); /* throws */ }
```
```cpp
// GOOD
void on_packet(const Packet & p) {
  auto v = try_parse(p);            // returns std::optional
  if (!v) {++parse_errors_; RCLCPP_WARN_THROTTLE(get_logger(), *get_clock(), 5000, "bad packet"); return;}
}
```

### 7. Absolute topic names and hard-coded config — ARCH-005 / ARCH-007
```cpp
// BAD
pub_ = create_publisher<Twist>("/robot1/cmd_vel", 10);
declare_parameter("port", "/dev/ttyUSB0");  // and a path like "/home/user/cfg.yaml"
```
```cpp
// GOOD: relative name, remapped in launch; values come from the params YAML.
pub_ = create_publisher<Twist>("cmd_vel", qos::command());
```

### 8. Ad-hoc parameters — CPP-010 / PY-004
```cpp
// BAD: no description, no range, silently accepts -5 Hz.
rate_ = declare_parameter("rate", 50.0);
```
```yaml
# GOOD: src/<node>_parameters.yaml
rate_hz: {type: double, default_value: 50.0, description: "Loop rate.", validation: {bounds<>: [1.0, 1000.0]}}
```

### 9. ROS 1 / deprecated API from training data — ARCH-006 / CMAKE-002
```cmake
# BAD
ament_target_dependencies(node rclcpp std_msgs)
include_directories(include)
```
```cmake
# GOOD
target_link_libraries(node PUBLIC rclcpp::rclcpp ${std_msgs_TARGETS})
target_include_directories(node PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>)
```

### 10. No command timeout — RT-006
```cpp
// BAD: the last cmd_vel is applied forever if the publisher dies.
void on_cmd(const Twist & c) { target_ = c; }
```
```cpp
// GOOD
void on_cmd(const Twist & c) { target_ = c; last_cmd_ = now(); }
void update() { if (now() - last_cmd_ > timeout_) {target_ = Twist{}; /* WARN once */} ... }
```

### 11. Sleep-and-hope tests — TEST-004
```cpp
// BAD
pub->publish(msg); std::this_thread::sleep_for(500ms); EXPECT_TRUE(received);
```
```cpp
// GOOD
ASSERT_TRUE(spin_until([&] {return pub->get_subscription_count() > 0;}, 5s));
pub->publish(msg);
ASSERT_TRUE(spin_until([&] {return received;}, 5s));
```

### 12. Logic inside the node — ARCH-002
```cpp
// BAD: 200 lines of filtering maths inside the subscription callback, testable only via ROS.
```
```cpp
// GOOD: callback = convert msg -> call core -> convert result -> publish (≈ 10 lines).
```

### 13. Stamping at publish time — ARCH-008
```cpp
// BAD: latency is hidden; sensor fusion gets wrong timing.
msg.header.stamp = now();   // after 30 ms of processing
```
```cpp
// GOOD: the stamp of the input (or the hardware acquisition time) is carried through.
out->header = in->header;
```

### 14. Weakening checks to get green — TOOL-001
```
BAD: deleting a failing test, adding `# noqa`/NOLINT without a reason, removing
     ament_lint_common from package.xml, raising a timeout from 2 s to 60 s "to be safe".
GOOD: fix the cause. If the rule really doesn't apply, a guideline-ignore with the reason.
```

### 15. Unowned threads and data races — CPP-011 / CPP-013
```cpp
// BAD
std::thread([this] {while (true) {latest_ = read();}}).detach();   // races with the timer reading latest_
```
```cpp
// GOOD: owned thread, stop flag, joined in on_deactivate; latest_ is guarded by a
// std::mutex (non-RT) or a realtime_tools::RealtimeThreadSafeBox (RT).
```
