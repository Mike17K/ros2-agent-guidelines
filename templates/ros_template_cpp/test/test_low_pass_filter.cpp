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
#include <gtest/gtest.h>

#include <cmath>
#include <limits>
#include <stdexcept>

#include "ros_template_cpp/low_pass_filter.hpp"

using ros_template_cpp::LowPassFilter;

TEST(LowPassFilter, RejectsInvalidConstruction)
{
  EXPECT_THROW(LowPassFilter(0.0, 1.0), std::invalid_argument);
  EXPECT_THROW(LowPassFilter(-1.0, 1.0), std::invalid_argument);
  EXPECT_THROW(LowPassFilter(1.0, 0.0), std::invalid_argument);
  EXPECT_THROW(
    LowPassFilter(std::numeric_limits<double>::quiet_NaN(), 1.0), std::invalid_argument);
}

TEST(LowPassFilter, FirstSampleInitializesState)
{
  LowPassFilter f(1.0, 1.0);
  EXPECT_FALSE(f.initialized());
  EXPECT_DOUBLE_EQ(f.update(3.0, 0.01), 3.0);
  EXPECT_TRUE(f.initialized());
}

TEST(LowPassFilter, StepResponseMatchesFirstOrderSystem)
{
  const double cutoff_hz = 2.0;
  const double dt = 0.001;
  LowPassFilter f(cutoff_hz, 1.0);
  (void)f.update(0.0, dt);

  // After one time constant a first-order system reaches ~63.2 % of a step.
  const double tau = 1.0 / (2.0 * M_PI * cutoff_hz);
  const int steps = static_cast<int>(std::round(tau / dt));
  double y = 0.0;
  for (int i = 0; i < steps; ++i) {
    y = f.update(1.0, dt);
  }
  EXPECT_NEAR(y, 1.0 - std::exp(-1.0), 0.01);
}

TEST(LowPassFilter, LargeGapOrNonPositiveDtResets)
{
  LowPassFilter f(1.0, 0.5);
  (void)f.update(0.0, 0.01);
  EXPECT_DOUBLE_EQ(f.update(5.0, 0.6), 5.0);   // gap > max_dt
  EXPECT_DOUBLE_EQ(f.update(-2.0, 0.0), -2.0);  // dt == 0
  EXPECT_DOUBLE_EQ(f.update(7.0, -0.1), 7.0);   // time went backwards
}

TEST(LowPassFilter, ResetForgetsState)
{
  LowPassFilter f(1.0, 1.0);
  (void)f.update(10.0, 0.01);
  f.reset();
  EXPECT_FALSE(f.initialized());
  EXPECT_DOUBLE_EQ(f.update(-4.0, 0.01), -4.0);
}
