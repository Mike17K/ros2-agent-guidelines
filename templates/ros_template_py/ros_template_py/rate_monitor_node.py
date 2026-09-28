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

"""Publish whether an input stream is arriving at its expected rate."""

from typing import Optional

from rcl_interfaces.msg import FloatingPointRange, ParameterDescriptor, SetParametersResult
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Imu
from std_msgs.msg import Bool
from std_srvs.srv import Trigger

from .rate_monitor import RateMonitor

# Named QoS profiles [QOS-001]; see docs/agent/qos.md.
STATE_QOS = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)


class RateMonitorNode(Node):
    """
    Watch ``input`` and publish ``~/healthy`` (std_msgs/Bool) periodically.

    Topics (relative, remap in launch [ARCH-005]):
      sub  input       sensor_msgs/msg/Imu  sensor data QoS
      pub  ~/healthy   std_msgs/msg/Bool    reliable, depth 10
    Services:
      ~/reset          std_srvs/srv/Trigger clears the rate window
    """

    def __init__(self) -> None:
        super().__init__('rate_monitor')

        # [PY-004] Every parameter has a descriptor with description and range.
        self._expected_rate_hz = self.declare_parameter(
            'expected_rate_hz', 100.0, ParameterDescriptor(
                description='Nominal input rate.',
                floating_point_range=[FloatingPointRange(from_value=0.1, to_value=10000.0)],
            )).value
        self._min_rate_ratio = self.declare_parameter(
            'min_rate_ratio', 0.8, ParameterDescriptor(
                description='Healthy when measured rate >= ratio * expected_rate_hz.',
                floating_point_range=[FloatingPointRange(from_value=0.0, to_value=1.0)],
            )).value
        window_s = self.declare_parameter(
            'window_s', 1.0, ParameterDescriptor(
                description='Sliding window length for the rate estimate.',
                read_only=True,
                floating_point_range=[FloatingPointRange(from_value=0.05, to_value=60.0)],
            )).value
        publish_period_s = self.declare_parameter(
            'publish_period_s', 0.5, ParameterDescriptor(
                description='Period of the ~/healthy publication.',
                read_only=True,
                floating_point_range=[FloatingPointRange(from_value=0.01, to_value=10.0)],
            )).value
        self.add_on_set_parameters_callback(self._on_parameters)

        self._monitor = RateMonitor(window_s)
        self._healthy: Optional[bool] = None

        self._pub = self.create_publisher(Bool, '~/healthy', STATE_QOS)
        self._sub = self.create_subscription(
            Imu, 'input', self._on_input, qos_profile_sensor_data)
        self._srv = self.create_service(Trigger, '~/reset', self._on_reset)
        self._timer = self.create_timer(publish_period_s, self._on_timer)

    def _now_s(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def _on_parameters(self, params):
        # Ranges are enforced by rclpy from the descriptors; only apply here.
        for param in params:
            if param.name == 'expected_rate_hz':
                self._expected_rate_hz = param.value
            elif param.name == 'min_rate_ratio':
                self._min_rate_ratio = param.value
        return SetParametersResult(successful=True)

    def _on_input(self, _msg: Imu) -> None:
        # Keep callbacks short and non-blocking [PY-002].
        self._monitor.tick(self._now_s())

    def _on_timer(self) -> None:
        rate = self._monitor.rate_hz(self._now_s())
        healthy = rate >= self._min_rate_ratio * self._expected_rate_hz
        if healthy != self._healthy:
            log = self.get_logger().info if healthy else self.get_logger().warn
            log(f'input rate {rate:.1f} Hz (expected {self._expected_rate_hz:.1f} Hz): '
                f'{"healthy" if healthy else "UNHEALTHY"}')
            self._healthy = healthy
        self._pub.publish(Bool(data=healthy))

    def _on_reset(self, _request: Trigger.Request, response: Trigger.Response):
        self._monitor.reset()
        self._healthy = None
        response.success = True
        response.message = 'rate window cleared'
        return response


def main(args=None) -> None:
    rclpy.init(args=args)
    node = RateMonitorNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
