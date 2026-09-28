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

"""Sliding-window message-rate estimator. Pure Python, no ROS imports [ARCH-002]."""

from collections import deque


class RateMonitor:
    """
    Estimate the arrival rate of events over a sliding time window.

    Time is passed in explicitly (seconds, monotonic within one monitor) so the
    class is deterministic under test and works with sim time.
    """

    def __init__(self, window_s: float) -> None:
        if not window_s > 0.0:
            raise ValueError('window_s must be > 0')
        self._window_s = window_s
        self._stamps: deque[float] = deque()

    @property
    def window_s(self) -> float:
        return self._window_s

    def tick(self, now_s: float) -> None:
        """Record one event at time ``now_s``."""
        if self._stamps and now_s < self._stamps[-1]:
            # Time jumped backwards (e.g. sim/bag restart): start over.
            self._stamps.clear()
        self._stamps.append(now_s)
        self._prune(now_s)

    def rate_hz(self, now_s: float) -> float:
        """Return events per second observed in the window ending at ``now_s``."""
        self._prune(now_s)
        return len(self._stamps) / self._window_s

    def reset(self) -> None:
        self._stamps.clear()

    def _prune(self, now_s: float) -> None:
        horizon = now_s - self._window_s
        while self._stamps and self._stamps[0] <= horizon:
            self._stamps.popleft()
