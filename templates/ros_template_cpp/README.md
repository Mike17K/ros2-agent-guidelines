# ros_template_cpp

Golden reference for C++ nodes. Scaffold a copy with
`tools/new_package.sh cpp <package_name>`; do not edit this template in place for project work.

| Item | Where |
|---|---|
| ROS-free core logic (unit tested) | `include/ros_template_cpp/low_pass_filter.hpp`, `src/low_pass_filter.cpp` |
| Lifecycle component node | `include/ros_template_cpp/filter_node.hpp`, `src/filter_node.cpp` |
| Parameter schema (generate_parameter_library) | `src/filter_node_parameters.yaml` |
| Deployment parameter values | `config/filter_node.yaml` |
| Named QoS profiles | `include/ros_template_cpp/qos.hpp` |
| Launch | `launch/filter_node.launch.py` |
| Tests: unit / node / launch | `test/` |

## Interface

| Kind | Name | Type | QoS |
|---|---|---|---|
| sub | `imu/data_raw` | `sensor_msgs/msg/Imu` | sensor_subscription |
| pub | `imu/data` | `sensor_msgs/msg/Imu` | sensor_publisher |
| param | `cutoff_frequency_hz` | double [0.01, 1000], dynamic | |
| param | `max_sample_gap_s` | double > 0, read-only | |

```bash
ros2 launch ros_template_cpp filter_node.launch.py input_topic:=/imu/raw
```
