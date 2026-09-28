from glob import glob

from setuptools import find_packages, setup

package_name = 'ros_template_py'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'contract.yaml']),  # [CONTRACT-001]
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='MAINTAINER_NAME',
    maintainer_email='MAINTAINER_EMAIL',
    description='Golden reference: rclpy node with a ROS-free core module.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'rate_monitor = ros_template_py.rate_monitor_node:main',
        ],
    },
)
