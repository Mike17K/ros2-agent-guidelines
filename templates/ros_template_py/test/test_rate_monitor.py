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

import pytest

from ros_template_py.rate_monitor import RateMonitor  # noqa: I100


def test_rejects_non_positive_window():
    with pytest.raises(ValueError):
        RateMonitor(0.0)


def test_steady_rate():
    m = RateMonitor(window_s=1.0)
    for i in range(100):
        m.tick(i * 0.01)
    assert m.rate_hz(0.995) == pytest.approx(100.0, rel=0.02)


def test_rate_decays_after_stream_stops():
    m = RateMonitor(window_s=1.0)
    for i in range(50):
        m.tick(i * 0.02)
    assert m.rate_hz(5.0) == 0.0


def test_time_going_backwards_restarts_window():
    m = RateMonitor(window_s=1.0)
    for i in range(10):
        m.tick(10.0 + i * 0.1)
    m.tick(0.0)
    assert m.rate_hz(0.0) == pytest.approx(1.0)


def test_reset():
    m = RateMonitor(window_s=1.0)
    m.tick(0.1)
    m.reset()
    assert m.rate_hz(0.2) == 0.0
