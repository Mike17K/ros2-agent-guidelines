// Copyright 2026 COPYRIGHT_HOLDER
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
#ifndef ROS_TEMPLATE_CPP__QOS_HPP_
#define ROS_TEMPLATE_CPP__QOS_HPP_

#include <cstddef>

#include "rclcpp/qos.hpp"

/// Named QoS profiles [QOS-001]. Never pass a bare depth like `10` to
/// create_publisher/create_subscription; pick the profile matching the data
/// (see docs/agent/qos.md). Profiles follow REP 2003.
namespace ros_template_cpp::qos
{

/// Publisher side of a high-rate sensor stream. Reliable so that both
/// reliable and best-effort subscribers can connect (REP 2003).
inline rclcpp::QoS sensor_publisher(std::size_t depth = 5)
{
  return rclcpp::QoS(rclcpp::KeepLast(depth)).reliable().durability_volatile();
}

/// Subscriber side of a high-rate sensor stream: latest data wins, never
/// stall on retransmission.
inline rclcpp::QoS sensor_subscription(std::size_t depth = 5)
{
  return rclcpp::SensorDataQoS(rclcpp::KeepLast(depth));
}

/// Commands (e.g. velocity setpoints): only the newest matters. The consumer
/// must still enforce its own command timeout [RT-006].
inline rclcpp::QoS command()
{
  return rclcpp::QoS(rclcpp::KeepLast(1)).reliable().durability_volatile();
}

/// Low-rate state/status that consumers must not miss.
inline rclcpp::QoS state(std::size_t depth = 10)
{
  return rclcpp::QoS(rclcpp::KeepLast(depth)).reliable().durability_volatile();
}

/// Latched data (maps, robot_description, static config): late joiners get
/// the last value. Both publisher and subscriber must use this profile.
inline rclcpp::QoS latched()
{
  return rclcpp::QoS(rclcpp::KeepLast(1)).reliable().transient_local();
}

}  // namespace ros_template_cpp::qos

#endif  // ROS_TEMPLATE_CPP__QOS_HPP_
