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
#ifndef ROS_TEMPLATE_CPP__FILTER_NODE_HPP_
#define ROS_TEMPLATE_CPP__FILTER_NODE_HPP_

#include <memory>
#include <optional>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "rclcpp_lifecycle/lifecycle_node.hpp"
#include "sensor_msgs/msg/imu.hpp"

#include "ros_template_cpp/low_pass_filter.hpp"
#include "ros_template_cpp/ros_template_cpp_filter_node_parameters.hpp"

namespace ros_template_cpp
{

/// Low-pass filters the angular velocity and linear acceleration of an IMU
/// stream.
///
/// Topics (relative names, remap in launch [ARCH-005]):
///   sub  imu/data_raw  sensor_msgs/msg/Imu  qos::sensor_subscription()
///   pub  imu/data      sensor_msgs/msg/Imu  qos::sensor_publisher()
///
/// Lifecycle [CPP-001]:
///   configure  -> read parameters, build filters, create publisher
///   activate   -> activate publisher, create subscription
///   deactivate -> drop subscription (no processing while inactive)
///   cleanup    -> release everything created in configure
class FilterNode : public rclcpp_lifecycle::LifecycleNode
{
public:
  using CallbackReturn =
    rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn;
  using Imu = sensor_msgs::msg::Imu;

  /// Constructor only declares parameters; it never allocates resources,
  /// opens hardware, or creates pub/sub [CPP-001].
  explicit FilterNode(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());

  CallbackReturn on_configure(const rclcpp_lifecycle::State & previous_state) override;
  CallbackReturn on_activate(const rclcpp_lifecycle::State & previous_state) override;
  CallbackReturn on_deactivate(const rclcpp_lifecycle::State & previous_state) override;
  CallbackReturn on_cleanup(const rclcpp_lifecycle::State & previous_state) override;
  CallbackReturn on_shutdown(const rclcpp_lifecycle::State & previous_state) override;
  CallbackReturn on_error(const rclcpp_lifecycle::State & previous_state) override;

private:
  void on_imu(const Imu::ConstSharedPtr & msg);
  void rebuild_filters();
  void release();

  // Parameters: listener is created in the constructor so parameters are
  // declared (and visible to `ros2 param`) before configure.
  std::shared_ptr<ros_template_cpp::ParamListener> param_listener_;
  ros_template_cpp::Params params_;

  // Order: [gx, gy, gz, ax, ay, az].
  std::vector<LowPassFilter> filters_;
  std::optional<rclcpp::Time> last_stamp_;

  rclcpp_lifecycle::LifecyclePublisher<Imu>::SharedPtr publisher_;
  rclcpp::Subscription<Imu>::SharedPtr subscription_;
};

}  // namespace ros_template_cpp

#endif  // ROS_TEMPLATE_CPP__FILTER_NODE_HPP_
