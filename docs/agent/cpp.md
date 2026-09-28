# C++ nodes (rclcpp, Jazzy) and CMake

Start from `templates/ros_template_cpp/` (via `tools/new_package.py cpp <name>`).
Everything below is already done correctly there, so copy its patterns.

## Node structure

**CPP-001 — Lifecycle for anything that owns resources or is depended on.**
Subclass `rclcpp_lifecycle::LifecycleNode`. Each resource is created in one
transition and released in its mirror:

| Transition | Do | Never |
|---|---|---|
| constructor | declare parameters (`ParamListener`) | open devices, create pub/sub/timers, throw on bad config |
| `on_configure` | read and validate params, allocate buffers, open devices, create publishers/services | start timers or subscriptions that act |
| `on_activate` | `publisher_->on_activate()`, create subscriptions/timers, start threads | long blocking work (> 100 ms) |
| `on_deactivate` | stop timers/subs/threads; mirror of activate | release configure-time resources |
| `on_cleanup` | release everything from configure; mirror of configure | |
| `on_shutdown` / `on_error` | release everything; `on_error` returns SUCCESS to allow reconfigure | |

Return `CallbackReturn::FAILURE` (with an `RCLCPP_ERROR` giving the reason)
instead of throwing when configuration is invalid. Plain `rclcpp::Node` is fine
for stateless helpers that own nothing and that nothing waits on.

**CPP-002 — Components.** Build nodes as a `SHARED` library and register them:

```cmake
rclcpp_components_register_node(${PROJECT_NAME}_filter_node
  PLUGIN "my_pkg::FilterNode"
  EXECUTABLE filter_node)
```

The constructor signature is `explicit FilterNode(const rclcpp::NodeOptions & options)`.
Don't write a `main()`. The generated executable and component containers both work.

## Callbacks and the executor

**CPP-003 — No sleeping in node code.** No `std::this_thread::sleep_for`,
`rclcpp::sleep_for`, `usleep` or `sleep`. Use a timer, or a state machine
advanced by a timer.

**CPP-004 — Never block on the executor from inside it.** No
`spin_until_future_complete`, `spin_some`, `future.get()` or `future.wait_for()`
inside callbacks or lifecycle transitions. Use the callback form of
`async_send_request` and prune stale requests from a timer:

```cpp
// configure
client_ = create_client<std_srvs::srv::SetBool>("enable_motor");
prune_timer_ = create_wall_timer(1s, [this] {
  // Drop requests that never got an answer; log so the failure is visible.
  std::vector<int64_t> pruned;
  // Note: takes a std::chrono::system_clock time point, not rclcpp::Time.
  if (client_->prune_requests_older_than(std::chrono::system_clock::now() - 2s, &pruned) > 0) {
    RCLCPP_WARN(get_logger(), "enable_motor: %zu request(s) timed out", pruned.size());
  }
});

// anywhere (callback, timer, transition)
if (!client_->service_is_ready()) {
  RCLCPP_WARN_THROTTLE(get_logger(), *get_clock(), 5000, "enable_motor not available");
  return;
}
auto req = std::make_shared<std_srvs::srv::SetBool::Request>();
req->data = true;
client_->async_send_request(
  req, [this](rclcpp::Client<std_srvs::srv::SetBool>::SharedFuture future) {
    const auto & res = future.get();  // ready: safe inside the response callback
    if (!res->success) {RCLCPP_ERROR(get_logger(), "enable failed: %s", res->message.c_str());}
  });
```

**CPP-011 — Threading is explicit.** The default is a `SingleThreadedExecutor`
and the default callback group, so no two callbacks of a node run at the same
time and you need no locks. If a callback must run concurrently (for example, a
long computation that shouldn't block a high-rate subscription):

- create a `MutuallyExclusive` callback group per independent activity,
- pass it via `rclcpp::SubscriptionOptions::callback_group` or the timer/client argument,
- run under a `MultiThreadedExecutor` (set in launch/container), and
- protect every piece of shared state (`std::mutex` for non-RT, atomics or
  `realtime_tools` for RT). Document which group touches which member.

`Reentrant` groups are allowed only for stateless callbacks.

**CPP-012 — Timers, not loops.** No `while (rclcpp::ok())` or `rclcpp::Rate` in
node code. Use `create_wall_timer` for wall-clock periods and `create_timer`
for periods that must follow ROS/sim time. A tight hardware loop that truly
needs its own thread follows realtime.md.

**CPP-013 — Own your threads.** Never `detach()`. Store the `std::thread`, signal it
with an `std::atomic<bool>` or `std::stop_token`-style flag, and `join()` it in
`on_deactivate` or `on_cleanup` and the destructor.

## Errors, validation, logging

**CPP-005 — Logging.** Use `RCLCPP_{DEBUG,INFO,WARN,ERROR,FATAL}` with
`get_logger()`. Inside callbacks that run above 1 Hz use `_THROTTLE`, `_ONCE` or
`_SKIPFIRST`. No `std::cout`, `printf` or `std::cerr`. Log levels:

| Level | Use for |
|---|---|
| INFO | lifecycle transitions, configuration summary |
| WARN | recoverable anomalies |
| ERROR | failed operations |
| DEBUG | per-message detail |

**CPP-006 — Exceptions don't escape callbacks.** An exception thrown out of a
callback propagates out of `spin()` and kills the whole process, including every
other component in the container. Handle expected failures (I/O, parsing,
hardware) inside the callback: log, count, and transition to error if the
failure is persistent. Don't wrap bodies in `catch (...) {}`. Programming bugs
should crash in tests, not be swallowed.

**CPP-007 — Validate at the boundary.** Check incoming messages for NaN/Inf,
empty arrays, mismatched sizes, a wrong `frame_id` and stale stamps before
using them. Drop and log throttled; never propagate invalid data downstream.
Validate parameters by schema (CPP-010), not by ad-hoc `if`s scattered through
the code.

## Memory and ownership

**CPP-008 — No raw `new`/`delete`.** Use `std::make_unique`, `std::make_shared`,
containers and RAII wrappers for OS handles (file descriptors, sockets). Node
entities (`SharedPtr`s from `create_*`) are members, so they live exactly as long as
the node.

- Capturing `this` in callbacks of entities the node owns is fine. For callbacks
  handed to objects the node doesn't own, capture a `weak_ptr`.
- Never call `shared_from_this()` in a constructor.
- Pass messages to functions as `const Msg &`. Subscriptions take
  `const Msg::ConstSharedPtr &` (or `Msg::UniquePtr` when you'll modify and republish).

**CPP-009 — Headers.** Use include guards `PKG__FILE_HPP_` (cpplint enforces
them). Never put `using namespace` in a header. Include what you use, in this
order: own header, C system, C++ standard, other libraries, ROS, this package
(the template shows it).

## Parameters

**CPP-010 — `generate_parameter_library`.** Declare parameters in
`src/<node>_parameters.yaml` with `type`, `default_value`, a `description` and
`validation` for each, plus `read_only: true` for parameters that are only
applied at configure time. Then:

```cpp
// constructor
param_listener_ = std::make_shared<my_pkg::ParamListener>(get_node_parameters_interface());
// on_configure
params_ = param_listener_->get_params();
// hot path, only for dynamic params (non-RT: is_old/get_params; RT: try_get_params)
if (param_listener_->is_old(params_)) {params_ = param_listener_->get_params(); apply();}
```

- Parameter names carry units (`timeout_s`, `rate_hz`) (ARCH-003).
- Deployment values live in `config/*.yaml` of the package or bringup, never in code.
- Don't call `declare_parameter` by hand in C++. It skips validation and documentation.

## Style

Formatting belongs to `ament_uncrustify` (ROS 2 style, 2-space indent, 100
columns). Run `ament_uncrustify --reformat <files>` (the Claude hook does it
automatically). Use `const` everywhere possible, `[[nodiscard]]` on functions whose
result must be checked, `noexcept` on core functions that can't fail,
`explicit` single-argument constructors, `override` on every override,
`enum class` over `enum`, `std::optional` over sentinel values, and
`std::chrono` durations over raw doubles at API boundaries.

## CMake

**CMAKE-001 — Per-project settings.** Set `CMAKE_CXX_STANDARD 17`, `_REQUIRED ON`
and `_EXTENSIONS OFF`, with warnings
`-Wall -Wextra -Wpedantic -Wshadow -Wconversion -Wnon-virtual-dtor` guarded by
compiler id. `tools/check.sh` injects `-Werror`.

**CMAKE-002 — Targets, not `ament_target_dependencies`.** It's deprecated since
Kilted, and Jazzy already exports modern targets:

```cmake
target_link_libraries(my_node PUBLIC rclcpp::rclcpp rclcpp_lifecycle::rclcpp_lifecycle
                                    ${sensor_msgs_TARGETS} ${PROJECT_NAME}_core)
```

(Message packages provide `${<pkg>_TARGETS}`; libraries provide `<pkg>::<target>`.)

**CMAKE-003 — No directory-scoped commands.** No `include_directories`,
`link_directories`, `link_libraries` or `add_definitions`. Use the `target_*` forms with
`PUBLIC`/`PRIVATE`/`INTERFACE`. Use `$<BUILD_INTERFACE:…>`/`$<INSTALL_INTERFACE:include/${PROJECT_NAME}>`.

**CMAKE-004 — No `file(GLOB)`.** List sources explicitly.

**CMAKE-005 — Don't touch `CMAKE_CXX_FLAGS`.** Use `add_compile_options` or
`target_compile_options`. Optimisation level comes from `CMAKE_BUILD_TYPE`.

Other rules:
- Install headers to `include/${PROJECT_NAME}`, and install libraries with
  `EXPORT export_${PROJECT_NAME}`. Call `ament_export_targets(export_${PROJECT_NAME} HAS_LIBRARY_TARGET)`
  and `ament_export_dependencies(<public deps>)`.
- Install `launch/` and `config/` to `share/${PROJECT_NAME}`.
- Put tests under `if(BUILD_TESTING)`. Use `ament_lint_auto_find_test_dependencies()`
  and `ament_add_ros_isolated_gtest` (testing.md).
