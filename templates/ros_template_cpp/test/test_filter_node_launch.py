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

"""Integration test: the installed launch file brings filter_node up; contract and data flow."""

import os
import sys
import time
import unittest

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare
import launch_testing
import launch_testing.actions
import pytest
import rclpy
from rclpy.qos import qos_profile_sensor_data, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Imu

NAMESPACE = 'launch_test'
# Mirrors qos::sensor_publisher() in include/ros_template_cpp/qos.hpp [QOS-001].
SENSOR_PUBLISHER_QOS = QoSProfile(depth=5, reliability=ReliabilityPolicy.RELIABLE)


@pytest.mark.launch_test
def generate_test_description():
    bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution(
            [FindPackageShare('ros_template_cpp'), 'launch', 'filter_node.launch.py'])),
        launch_arguments={'namespace': NAMESPACE, 'autostart': 'true'}.items(),
    )
    return LaunchDescription([bringup, launch_testing.actions.ReadyToTest()])


class TestFilterNodeRuns(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        rclpy.init()

    @classmethod
    def tearDownClass(cls):
        rclpy.shutdown()

    def setUp(self):
        self.node = rclpy.create_node('filter_node_launch_test', namespace=NAMESPACE)

    def tearDown(self):
        self.node.destroy_node()

    @unittest.skipUnless(os.environ.get('GUIDELINES_TOOLS'),
                         'GUIDELINES_TOOLS not set: run through tools/check.sh')
    def test_matches_contract(self):
        # [CONTRACT-003] endpoints, types, QoS, parameters and lifecycle state vs contract.yaml.
        sys.path.insert(0, os.environ['GUIDELINES_TOOLS'])
        from contracts import check_live
        contract = os.path.join(get_package_share_directory('ros_template_cpp'), 'contract.yaml')
        failures = check_live(contract, f'/{NAMESPACE}/filter_node', node=self.node)
        self.assertEqual(failures, [], 'contract mismatch:\n' + '\n'.join(failures))

    def test_republishes_filtered_imu(self):
        received = []
        self.node.create_subscription(
            Imu, 'imu/data', received.append, qos_profile_sensor_data)
        pub = self.node.create_publisher(Imu, 'imu/data_raw', SENSOR_PUBLISHER_QOS)

        deadline = time.monotonic() + 20.0
        stamp_ns = 0
        while time.monotonic() < deadline and not received:
            msg = Imu()
            msg.header.frame_id = 'imu_link'
            stamp_ns += 10_000_000
            msg.header.stamp.sec = stamp_ns // 1_000_000_000
            msg.header.stamp.nanosec = stamp_ns % 1_000_000_000
            pub.publish(msg)
            rclpy.spin_once(self.node, timeout_sec=0.1)

        self.assertTrue(received, 'filter_node never published on imu/data')
        self.assertEqual(received[0].header.frame_id, 'imu_link')


@launch_testing.post_shutdown_test()
class TestShutdown(unittest.TestCase):

    def test_exit_codes(self, proc_info):
        launch_testing.asserts.assertExitCodes(proc_info)
