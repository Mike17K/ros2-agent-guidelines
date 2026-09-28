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

"""Bring up the rate monitor."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    args = [
        DeclareLaunchArgument('namespace', default_value='', description='Node namespace.'),
        DeclareLaunchArgument(
            'params_file',
            default_value=PathJoinSubstitution(
                [FindPackageShare('ros_template_py'), 'config', 'rate_monitor.yaml']),
            description='Parameter YAML file.'),
        DeclareLaunchArgument(
            'input_topic', default_value='imu/data', description='Topic to monitor.'),
        DeclareLaunchArgument('use_sim_time', default_value='false', description='Use /clock.'),
    ]
    node = Node(
        package='ros_template_py',
        executable='rate_monitor',
        name='rate_monitor',
        namespace=LaunchConfiguration('namespace'),
        parameters=[
            LaunchConfiguration('params_file'),
            {'use_sim_time': LaunchConfiguration('use_sim_time')},
        ],
        remappings=[('input', LaunchConfiguration('input_topic'))],
        output='screen',
    )
    return LaunchDescription([*args, node])
