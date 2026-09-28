cmake_minimum_required(VERSION 3.22)
project(ros_template_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)

# [IF-001] Interface packages contain only definitions: no nodes, no libraries.
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/ComponentStatus.msg"
  "srv/SetMode.srv"
  "action/MoveToPose.action"
  DEPENDENCIES builtin_interfaces geometry_msgs std_msgs
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_export_dependencies(rosidl_default_runtime)
ament_package()
