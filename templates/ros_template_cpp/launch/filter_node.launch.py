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

"""Bring up filter_node as a lifecycle node that configures and activates itself."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import LifecycleNode
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # [LAUNCH-002] Every tunable is a declared argument with a default and description.
    args = [
        DeclareLaunchArgument('namespace', default_value='', description='Node namespace.'),
        DeclareLaunchArgument(
            'params_file',
            default_value=PathJoinSubstitution(
                [FindPackageShare('ros_template_cpp'), 'config', 'filter_node.yaml']),
            description='Parameter YAML file.'),
        DeclareLaunchArgument(
            'input_topic', default_value='imu/data_raw', description='Raw IMU input topic.'),
        DeclareLaunchArgument(
            'output_topic', default_value='imu/data', description='Filtered IMU output topic.'),
        DeclareLaunchArgument(
            'autostart', default_value='true',
            description='Transition to active automatically (false when a lifecycle '
                        'manager owns the node).'),
        DeclareLaunchArgument(
            'use_sim_time', default_value='false', description='Use /clock.'),
        DeclareLaunchArgument(
            'log_level', default_value='info', description='Logger level.'),
    ]

    node = LifecycleNode(
        package='ros_template_cpp',
        executable='filter_node',
        name='filter_node',
        namespace=LaunchConfiguration('namespace'),
        parameters=[
            LaunchConfiguration('params_file'),
            {'use_sim_time': LaunchConfiguration('use_sim_time')},
        ],
        remappings=[
            ('imu/data_raw', LaunchConfiguration('input_topic')),
            ('imu/data', LaunchConfiguration('output_topic')),
        ],
        autostart=LaunchConfiguration('autostart'),
        arguments=['--ros-args', '--log-level', LaunchConfiguration('log_level')],
        output='screen',
    )

    return LaunchDescription([*args, node])
