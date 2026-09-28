# Copyright 2026 COPYRIGHT_HOLDER
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Node-level test: parameters, data flow and service, all in-process."""

import time

import pytest
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu
from std_msgs.msg import Bool
from std_srvs.srv import Trigger

from ros_template_py.rate_monitor_node import RateMonitorNode, STATE_QOS  # noqa: I100


@pytest.fixture
def ros():
    rclpy.init()
    yield
    rclpy.try_shutdown()


def spin_until(executor, predicate, timeout_s):
    """Spin until ``predicate()`` is true; never sleep-and-hope [TEST-004]."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        executor.spin_once(timeout_sec=0.01)
        if predicate():
            return True
    return predicate()


def test_rejects_out_of_range_parameter(ros):
    node = RateMonitorNode()
    result = node.set_parameters([Parameter('min_rate_ratio', value=2.0)])
    assert not result[0].successful
    result = node.set_parameters([Parameter('window_s', value=5.0)])
    assert not result[0].successful  # read-only
    node.destroy_node()


def test_reports_healthy_then_reset(ros):
    node = RateMonitorNode()
    node.set_parameters([Parameter('expected_rate_hz', value=20.0)])
    helper = rclpy.create_node('helper')
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(helper)

    states = []
    helper.create_subscription(Bool, 'rate_monitor/healthy', lambda m: states.append(m.data),
                               STATE_QOS)
    pub = helper.create_publisher(Imu, 'input', qos_profile_sensor_data)
    helper.create_timer(0.01, lambda: pub.publish(Imu()))  # ~100 Hz >> 0.8 * 20 Hz

    assert spin_until(executor, lambda: states and states[-1], 5.0)

    client = helper.create_client(Trigger, 'rate_monitor/reset')
    assert client.wait_for_service(timeout_sec=5.0)
    future = client.call_async(Trigger.Request())
    assert spin_until(executor, future.done, 5.0)
    assert future.result().success

    executor.shutdown()
    helper.destroy_node()
    node.destroy_node()
