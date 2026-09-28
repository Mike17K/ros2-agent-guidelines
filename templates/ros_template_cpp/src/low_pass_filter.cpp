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

#include "ros_template_cpp/low_pass_filter.hpp"

#include <cmath>
#include <stdexcept>

namespace ros_template_cpp
{

namespace
{
constexpr double kTwoPi = 6.283185307179586;
}  // namespace

LowPassFilter::LowPassFilter(double cutoff_hz, double max_dt_s)
: cutoff_hz_(cutoff_hz),
  time_constant_s_(0.0),
  max_dt_s_(max_dt_s)
{
  if (!(cutoff_hz > 0.0) || !std::isfinite(cutoff_hz)) {
    throw std::invalid_argument("cutoff_hz must be finite and > 0");
  }
  if (!(max_dt_s > 0.0) || !std::isfinite(max_dt_s)) {
    throw std::invalid_argument("max_dt_s must be finite and > 0");
  }
  time_constant_s_ = 1.0 / (kTwoPi * cutoff_hz);
}

double LowPassFilter::update(double sample, double dt_s) noexcept
{
  if (!initialized_ || !(dt_s > 0.0) || dt_s > max_dt_s_) {
    state_ = sample;
    initialized_ = true;
    return state_;
  }
  const double alpha = dt_s / (time_constant_s_ + dt_s);
  state_ += alpha * (sample - state_);
  return state_;
}

void LowPassFilter::reset() noexcept
{
  state_ = 0.0;
  initialized_ = false;
}

}  // namespace ros_template_cpp
