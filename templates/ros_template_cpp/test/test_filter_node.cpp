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
#include <gtest/gtest.h>

#include <atomic>
#include <chrono>
#include <cmath>
#include <functional>
#include <limits>
#include <memory>
#include <string>
#include <vector>

#include "lifecycle_msgs/msg/state.hpp"
#include "rclcpp/rclcpp.hpp"

#include "ros_template_cpp/filter_node.hpp"
#include "ros_template_cpp/qos.hpp"

using namespace std::chrono_literals;
using lifecycle_msgs::msg::State;
using ros_template_cpp::FilterNode;
using Imu = sensor_msgs::msg::Imu;

namespace
{
std::string unique_namespace()
{
  static std::atomic<int> counter{0};
  return "/filter_node_test_" + std::to_string(counter++);
}
}  // namespace

class FilterNodeTest : public ::testing::Test
{
protected:
  static void SetUpTestSuite() {rclcpp::init(0, nullptr);}
  static void TearDownTestSuite() {rclcpp::shutdown();}

  void SetUp() override
  {
    const auto ns = unique_namespace();
    rclcpp::NodeOptions options;
    options.arguments({"--ros-args", "-r", "__ns:=" + ns});
    options.parameter_overrides({{"cutoff_frequency_hz", 1.0}});
    node_ = std::make_shared<FilterNode>(options);

    helper_ = std::make_shared<rclcpp::Node>("helper", ns);
    raw_pub_ = helper_->create_publisher<Imu>(
      "imu/data_raw", ros_template_cpp::qos::sensor_publisher());
    filtered_sub_ = helper_->create_subscription<Imu>(
      "imu/data", ros_template_cpp::qos::sensor_subscription(),
      [this](const Imu::ConstSharedPtr & msg) {received_.push_back(*msg);});

    executor_.add_node(node_->get_node_base_interface());
    executor_.add_node(helper_);
  }

  void TearDown() override
  {
    executor_.remove_node(helper_);
    executor_.remove_node(node_->get_node_base_interface());
  }

  /// Spin until @p done returns true or @p timeout elapses. Never sleep-and-hope.
  bool spin_until(const std::function<bool()> & done, std::chrono::milliseconds timeout)
  {
    const auto deadline = std::chrono::steady_clock::now() + timeout;
    while (std::chrono::steady_clock::now() < deadline) {
      executor_.spin_some(10ms);
      if (done()) {
        return true;
      }
    }
    return done();
  }

  void wait_for_connection()
  {
    ASSERT_TRUE(
      spin_until(
        [this] {
          return raw_pub_->get_subscription_count() > 0 &&
                 filtered_sub_->get_publisher_count() > 0;
        }, 5s));
  }

  Imu make_imu(double value, int32_t sec, uint32_t nanosec) const
  {
    Imu msg;
    msg.header.frame_id = "imu_link";
    msg.header.stamp.sec = sec;
    msg.header.stamp.nanosec = nanosec;
    msg.angular_velocity.x = value;
    msg.linear_acceleration.z = value;
    return msg;
  }

  rclcpp::executors::SingleThreadedExecutor executor_;
  std::shared_ptr<FilterNode> node_;
  rclcpp::Node::SharedPtr helper_;
  rclcpp::Publisher<Imu>::SharedPtr raw_pub_;
  rclcpp::Subscription<Imu>::SharedPtr filtered_sub_;
  std::vector<Imu> received_;
};

TEST_F(FilterNodeTest, FullLifecycleRoundTrip)
{
  EXPECT_EQ(node_->get_current_state().id(), State::PRIMARY_STATE_UNCONFIGURED);
  EXPECT_EQ(node_->configure().id(), State::PRIMARY_STATE_INACTIVE);
  EXPECT_EQ(node_->activate().id(), State::PRIMARY_STATE_ACTIVE);
  EXPECT_EQ(node_->deactivate().id(), State::PRIMARY_STATE_INACTIVE);
  EXPECT_EQ(node_->cleanup().id(), State::PRIMARY_STATE_UNCONFIGURED);
  // Must be re-configurable after cleanup.
  EXPECT_EQ(node_->configure().id(), State::PRIMARY_STATE_INACTIVE);
  EXPECT_EQ(node_->shutdown().id(), State::PRIMARY_STATE_FINALIZED);
}

TEST_F(FilterNodeTest, RejectsOutOfRangeParameter)
{
  EXPECT_FALSE(node_->set_parameter(rclcpp::Parameter("cutoff_frequency_hz", -1.0)).successful);
  EXPECT_TRUE(node_->set_parameter(rclcpp::Parameter("cutoff_frequency_hz", 5.0)).successful);
}

TEST_F(FilterNodeTest, ReadOnlyParameterCannotChange)
{
  EXPECT_FALSE(node_->set_parameter(rclcpp::Parameter("max_sample_gap_s", 2.0)).successful);
}

TEST_F(FilterNodeTest, FiltersStepInputWhenActive)
{
  ASSERT_EQ(node_->configure().id(), State::PRIMARY_STATE_INACTIVE);
  ASSERT_EQ(node_->activate().id(), State::PRIMARY_STATE_ACTIVE);
  wait_for_connection();

  raw_pub_->publish(make_imu(0.0, 1, 0));
  ASSERT_TRUE(spin_until([this] {return !received_.empty();}, 2s));
  raw_pub_->publish(make_imu(1.0, 1, 10'000'000));  // +10 ms, step to 1.0
  ASSERT_TRUE(spin_until([this] {return received_.size() >= 2;}, 2s));

  const auto & out = received_.back();
  EXPECT_GT(out.angular_velocity.x, 0.0);
  EXPECT_LT(out.angular_velocity.x, 0.2);  // 1 Hz cutoff attenuates a 10 ms step
  EXPECT_DOUBLE_EQ(out.angular_velocity.x, out.linear_acceleration.z);
  EXPECT_EQ(out.header.frame_id, "imu_link");
}

TEST_F(FilterNodeTest, SilentWhenInactive)
{
  ASSERT_EQ(node_->configure().id(), State::PRIMARY_STATE_INACTIVE);
  raw_pub_->publish(make_imu(1.0, 1, 0));
  EXPECT_FALSE(spin_until([this] {return !received_.empty();}, 300ms));
}

TEST_F(FilterNodeTest, DropsNonFiniteSamples)
{
  ASSERT_EQ(node_->configure().id(), State::PRIMARY_STATE_INACTIVE);
  ASSERT_EQ(node_->activate().id(), State::PRIMARY_STATE_ACTIVE);
  wait_for_connection();

  raw_pub_->publish(make_imu(std::numeric_limits<double>::quiet_NaN(), 1, 0));
  EXPECT_FALSE(spin_until([this] {return !received_.empty();}, 300ms));
  raw_pub_->publish(make_imu(2.0, 1, 1000));
  ASSERT_TRUE(spin_until([this] {return !received_.empty();}, 2s));
  EXPECT_DOUBLE_EQ(received_.front().angular_velocity.x, 2.0);
}
