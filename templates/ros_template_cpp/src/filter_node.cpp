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
#include "ros_template_cpp/filter_node.hpp"

#include <cmath>
#include <exception>
#include <memory>
#include <utility>

#include "rclcpp_components/register_node_macro.hpp"

#include "ros_template_cpp/qos.hpp"

namespace ros_template_cpp
{

namespace
{
constexpr std::size_t kNumChannels = 6;
constexpr int kWarnThrottleMs = 5000;

bool all_finite(const FilterNode::Imu & msg)
{
  const auto & w = msg.angular_velocity;
  const auto & a = msg.linear_acceleration;
  return std::isfinite(w.x) && std::isfinite(w.y) && std::isfinite(w.z) &&
         std::isfinite(a.x) && std::isfinite(a.y) && std::isfinite(a.z);
}
}  // namespace

FilterNode::FilterNode(const rclcpp::NodeOptions & options)
: rclcpp_lifecycle::LifecycleNode("filter_node", options),
  param_listener_(std::make_shared<ros_template_cpp::ParamListener>(
    get_node_parameters_interface()))
{
}

FilterNode::CallbackReturn FilterNode::on_configure(const rclcpp_lifecycle::State &)
{
  try {
    params_ = param_listener_->get_params();
    rebuild_filters();
  } catch (const std::exception & e) {
    // [CPP-006] Exceptions never escape a callback; fail the transition instead.
    RCLCPP_ERROR(get_logger(), "Configuration failed: %s", e.what());
    release();
    return CallbackReturn::FAILURE;
  }

  publisher_ = create_publisher<Imu>("imu/data", qos::sensor_publisher());

  RCLCPP_INFO(
    get_logger(), "Configured: cutoff=%.3f Hz, max_gap=%.3f s",
    params_.cutoff_frequency_hz, params_.max_sample_gap_s);
  return CallbackReturn::SUCCESS;
}

FilterNode::CallbackReturn FilterNode::on_activate(const rclcpp_lifecycle::State &)
{
  publisher_->on_activate();
  last_stamp_.reset();
  subscription_ = create_subscription<Imu>(
    "imu/data_raw", qos::sensor_subscription(),
    [this](const Imu::ConstSharedPtr & msg) {on_imu(msg);});
  RCLCPP_INFO(get_logger(), "Activated");
  return CallbackReturn::SUCCESS;
}

FilterNode::CallbackReturn FilterNode::on_deactivate(const rclcpp_lifecycle::State &)
{
  subscription_.reset();
  publisher_->on_deactivate();
  for (auto & f : filters_) {
    f.reset();
  }
  RCLCPP_INFO(get_logger(), "Deactivated");
  return CallbackReturn::SUCCESS;
}

FilterNode::CallbackReturn FilterNode::on_cleanup(const rclcpp_lifecycle::State &)
{
  release();
  RCLCPP_INFO(get_logger(), "Cleaned up");
  return CallbackReturn::SUCCESS;
}

FilterNode::CallbackReturn FilterNode::on_shutdown(const rclcpp_lifecycle::State &)
{
  release();
  return CallbackReturn::SUCCESS;
}

FilterNode::CallbackReturn FilterNode::on_error(const rclcpp_lifecycle::State &)
{
  RCLCPP_ERROR(get_logger(), "Error state reached; releasing resources");
  release();
  // SUCCESS -> unconfigured (recoverable); FAILURE -> finalized.
  return CallbackReturn::SUCCESS;
}

void FilterNode::rebuild_filters()
{
  // Allocates: only called from configure or on a parameter change, never
  // per message [RT-002].
  std::vector<LowPassFilter> filters;
  filters.reserve(kNumChannels);
  for (std::size_t i = 0; i < kNumChannels; ++i) {
    filters.emplace_back(params_.cutoff_frequency_hz, params_.max_sample_gap_s);
  }
  filters_ = std::move(filters);
}

void FilterNode::release()
{
  subscription_.reset();
  publisher_.reset();
  filters_.clear();
  last_stamp_.reset();
}

void FilterNode::on_imu(const Imu::ConstSharedPtr & msg)
{
  // Pick up dynamic parameter changes. Cheap when nothing changed.
  if (param_listener_->is_old(params_)) {
    params_ = param_listener_->get_params();
    rebuild_filters();
    RCLCPP_INFO(get_logger(), "cutoff_frequency_hz -> %.3f", params_.cutoff_frequency_hz);
  }

  // [CPP-007] Validate inputs at the boundary; never propagate NaN downstream.
  if (!all_finite(*msg)) {
    RCLCPP_WARN_THROTTLE(
      get_logger(), *get_clock(), kWarnThrottleMs, "Dropping IMU sample with non-finite values");
    return;
  }

  const rclcpp::Time stamp(msg->header.stamp, get_clock()->get_clock_type());
  const double dt_s = last_stamp_ ? (stamp - *last_stamp_).seconds() : 0.0;
  last_stamp_ = stamp;

  // [PERF-002] unique_ptr publish enables zero-copy intra-process delivery.
  auto out = std::make_unique<Imu>(*msg);
  auto & w = out->angular_velocity;
  auto & a = out->linear_acceleration;
  w.x = filters_[0].update(w.x, dt_s);
  w.y = filters_[1].update(w.y, dt_s);
  w.z = filters_[2].update(w.z, dt_s);
  a.x = filters_[3].update(a.x, dt_s);
  a.y = filters_[4].update(a.y, dt_s);
  a.z = filters_[5].update(a.z, dt_s);
  publisher_->publish(std::move(out));
}

}  // namespace ros_template_cpp

RCLCPP_COMPONENTS_REGISTER_NODE(ros_template_cpp::FilterNode)
