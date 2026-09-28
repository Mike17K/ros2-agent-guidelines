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

"""Integration test: the installed launch file starts rate_monitor, it matches its contract."""

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
from std_msgs.msg import Bool

from ros_template_py.rate_monitor_node import STATE_QOS  # noqa: I100

NAMESPACE = 'launch_test'


@pytest.mark.launch_test
def generate_test_description():
    bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution(
            [FindPackageShare('ros_template_py'), 'launch', 'rate_monitor.launch.py'])),
        launch_arguments={'namespace': NAMESPACE}.items(),
    )
    return LaunchDescription([bringup, launch_testing.actions.ReadyToTest()])


class TestRateMonitorRuns(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        rclpy.init()

    @classmethod
    def tearDownClass(cls):
        rclpy.shutdown()

    def setUp(self):
        self.node = rclpy.create_node('rate_monitor_launch_test', namespace=NAMESPACE)

    def tearDown(self):
        self.node.destroy_node()

    @unittest.skipUnless(os.environ.get('GUIDELINES_TOOLS'),
                         'GUIDELINES_TOOLS not set: run through tools/check.sh')
    def test_matches_contract(self):
        # [CONTRACT-003] endpoints, types, QoS and parameters vs contract.yaml.
        sys.path.insert(0, os.environ['GUIDELINES_TOOLS'])
        from contracts import check_live
        contract = os.path.join(get_package_share_directory('ros_template_py'), 'contract.yaml')
        # Mirror the launch file's default remapping (input -> input_topic default).
        failures = check_live(contract, f'/{NAMESPACE}/rate_monitor', node=self.node,
                              remap={'input': 'imu/data'})
        self.assertEqual(failures, [], 'contract mismatch:\n' + '\n'.join(failures))

    def test_reports_unhealthy_without_input(self):
        # [TEST-009] input loss is a handled failure mode: it must be reported.
        states = []
        self.node.create_subscription(
            Bool, 'rate_monitor/healthy', lambda m: states.append(m.data), STATE_QOS)
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline and not states:
            rclpy.spin_once(self.node, timeout_sec=0.1)
        self.assertTrue(states, 'rate_monitor never published ~/healthy within 15 s')
        self.assertFalse(states[-1], f'expected healthy=False with no input, got {states}')


@launch_testing.post_shutdown_test()
class TestShutdown(unittest.TestCase):

    def test_exit_codes(self, proc_info):
        launch_testing.asserts.assertExitCodes(proc_info)
