cmake_minimum_required(VERSION 3.22)
project(ros_template_cpp LANGUAGES CXX)

# [CMAKE-001] Language standard and warnings are set per project, never globally.
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  add_compile_options(-Wall -Wextra -Wpedantic -Wshadow -Wconversion -Wnon-virtual-dtor)
endif()

find_package(ament_cmake_ros REQUIRED)
find_package(generate_parameter_library REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_components REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)
find_package(sensor_msgs REQUIRED)

# --- Core library: pure C++, no ROS dependency [ARCH-002] ---------------------
add_library(${PROJECT_NAME}_core
  src/low_pass_filter.cpp
)
target_include_directories(${PROJECT_NAME}_core PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include/${PROJECT_NAME}>
)
target_compile_features(${PROJECT_NAME}_core PUBLIC cxx_std_17)

# --- Parameters: declared in YAML, validated and typed at compile time [CPP-010]
generate_parameter_library(${PROJECT_NAME}_filter_node_parameters
  src/filter_node_parameters.yaml
)

# --- ROS node, built as a component [CPP-002] ---------------------------------
add_library(${PROJECT_NAME}_filter_node SHARED
  src/filter_node.cpp
)
target_include_directories(${PROJECT_NAME}_filter_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include/${PROJECT_NAME}>
)
# [CMAKE-002] Link exported targets; never ament_target_dependencies().
target_link_libraries(${PROJECT_NAME}_filter_node
  PUBLIC
    ${PROJECT_NAME}_core
    ${PROJECT_NAME}_filter_node_parameters
    rclcpp::rclcpp
    rclcpp_lifecycle::rclcpp_lifecycle
    ${sensor_msgs_TARGETS}
  PRIVATE
    rclcpp_components::component
)
rclcpp_components_register_node(${PROJECT_NAME}_filter_node
  PLUGIN "ros_template_cpp::FilterNode"
  EXECUTABLE filter_node
)

# --- Install ------------------------------------------------------------------
install(
  DIRECTORY include/
  DESTINATION include/${PROJECT_NAME}
)
install(
  TARGETS
    ${PROJECT_NAME}_core
    ${PROJECT_NAME}_filter_node_parameters
    ${PROJECT_NAME}_filter_node
  EXPORT export_${PROJECT_NAME}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)
install(
  DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME}
)
# [CONTRACT-001] contract + its parameter schema, for tools/contracts.py live checks.
install(FILES contract.yaml src/filter_node_parameters.yaml DESTINATION share/${PROJECT_NAME})

# --- Tests [TEST-001] ---------------------------------------------------------
if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()

  # [TEST-006] ros_isolated tests get a private DDS domain: parallel tests never
  # cross-talk and never reach a robot on the network.
  find_package(ament_cmake_gtest REQUIRED)
  find_package(launch_testing_ament_cmake REQUIRED)
  find_package(lifecycle_msgs REQUIRED)

  # Unit: core logic, no ROS.
  ament_add_ros_isolated_gtest(test_low_pass_filter test/test_low_pass_filter.cpp)
  target_link_libraries(test_low_pass_filter ${PROJECT_NAME}_core)

  # Node: lifecycle transitions, parameters, data flow (in-process).
  ament_add_ros_isolated_gtest(test_filter_node test/test_filter_node.cpp TIMEOUT 60)
  target_link_libraries(test_filter_node
    ${PROJECT_NAME}_filter_node
    ${lifecycle_msgs_TARGETS}
  )

  # Integration: the installed launch file brings the node up and it publishes.
  add_launch_test(test/test_filter_node_launch.py TIMEOUT 60)
endif()

ament_export_targets(export_${PROJECT_NAME} HAS_LIBRARY_TARGET)
ament_export_dependencies(generate_parameter_library rclcpp rclcpp_lifecycle sensor_msgs)
ament_package()
