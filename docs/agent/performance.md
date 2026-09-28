# Performance

**PERF-004 — Measure first.** Don't optimise without a number. The tools, in order:

1. `ros2 topic hz <topic>` / `ros2 topic bw <topic>` / `ros2 topic delay <topic>` (needs a header stamp)
2. `top -H -p <pid>` to see which thread is busy
3. `perf record -g -- ros2 run <pkg> <exe>` / `perf report`
4. `ros2_tracing` (`tracetools` is installed) to get callback durations and end-to-end latency:
   `ros2 trace start my_session`, run the system, then `ros2 trace stop my_session`,
   and analyse with `tracetools_analysis`.

State the before/after numbers in the change description.

**PERF-001 — Compose nodes that exchange high-rate or large data.** Nodes are
components (CPP-002). In launch, put them in one container and enable intra-process
communication:

```python
from launch_ros.actions import ComposableNodeContainer
from launch_ros.descriptions import ComposableNode

ComposableNodeContainer(
    name='perception_container', namespace='', package='rclcpp_components',
    executable='component_container_mt',            # or component_container (single-threaded)
    composable_node_descriptions=[
        ComposableNode(package='my_driver', plugin='my_driver::CameraNode', name='camera',
                       extra_arguments=[{'use_intra_process_comms': True}]),
        ComposableNode(package='my_perception', plugin='my_perception::Detector', name='detector',
                       extra_arguments=[{'use_intra_process_comms': True}]),
    ],
)
```

Lifecycle components in a container are managed with `nav2_lifecycle_manager`
or `ros2 lifecycle` (launch.md).

**PERF-002 — Publish `unique_ptr`.** `publisher_->publish(std::move(msg_unique_ptr))`
lets intra-process delivery move the message instead of copying it. Subscribers take
`ConstSharedPtr` (read-only, shared) or `UniquePtr` (to take ownership and modify).
Publishing by `const &` forces a copy.

**PERF-003 — Don't copy big messages.** Never take `sensor_msgs::msg::PointCloud2`
or `Image` by value. Don't build output clouds with `push_back` per point: `resize` once
and write through `sensor_msgs::PointCloud2Iterator`. Reuse buffers across callbacks
(members sized in `on_configure`).

**PERF-005 — Choose the executor on purpose.**

| Situation | Executor |
|---|---|
| Default | `SingleThreadedExecutor` (the component main uses it) |
| One node needs concurrent callbacks | `MultiThreadedExecutor` + explicit callback groups (CPP-011), `component_container_mt` |
| Many nodes, high message rate, CPU-bound on executor overhead | `rclcpp::experimental::executors::EventsExecutor` (experimental in Jazzy: measure and test before adopting) |

**PERF-006 — No allocation per message in steady state** where it's avoidable.
Prefer `reserve`, preallocated members, `std::array`, and moving instead of copying.
The per-message `make_unique` that PERF-002 needs is acceptable. Hot paths in
control loops follow realtime.md strictly.

## Other levers

- Build type: `RelWithDebInfo` is the default for `tools/check.sh` and for deployment.
  Don't ship `Debug`. Use `-O3`/`-march=native` only through `PROJECT.md`-approved flags,
  because they break binary portability.
- Logging: DEBUG statements cost little when disabled. Formatted INFO per message
  does not.
- For images, use `image_transport` (with the `compressed` plugin for network links) and
  keep raw images in-process.
- For DDS, big messages across machines need tuned RMW settings (shared memory,
  fragment sizes, or Cyclone `SocketReceiveBufferSize`). These go in the RMW XML named in
  `PROJECT.md`, never in code.
- For Python, see python.md. Move hot paths to C++.
