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

#ifndef ROS_TEMPLATE_CPP__LOW_PASS_FILTER_HPP_
#define ROS_TEMPLATE_CPP__LOW_PASS_FILTER_HPP_

namespace ros_template_cpp
{

/// First-order low-pass filter for irregularly sampled signals.
///
/// Pure C++ (no ROS types) so it can be unit tested, benchmarked and reused
/// outside a node [ARCH-002]. Real-time safe: no allocation, no locks,
/// no exceptions after construction [RT-001].
class LowPassFilter
{
public:
  /// @param cutoff_hz  -3 dB cutoff frequency, must be > 0.
  /// @param max_dt_s   gaps longer than this reset the filter state, must be > 0.
  /// @throws std::invalid_argument on invalid arguments (construction only).
  LowPassFilter(double cutoff_hz, double max_dt_s);

  /// Feed one sample taken @p dt_s seconds after the previous one.
  /// The first sample, a non-positive dt, or a gap > max_dt resets the state
  /// to @p sample and returns it unchanged.
  [[nodiscard]] double update(double sample, double dt_s) noexcept;

  /// Forget the state; the next update() re-initialises from its sample.
  void reset() noexcept;

  [[nodiscard]] double cutoff_hz() const noexcept {return cutoff_hz_;}
  [[nodiscard]] bool initialized() const noexcept {return initialized_;}

private:
  double cutoff_hz_;
  double time_constant_s_;
  double max_dt_s_;
  double state_{0.0};
  bool initialized_{false};
};

}  // namespace ros_template_cpp

#endif  // ROS_TEMPLATE_CPP__LOW_PASS_FILTER_HPP_
