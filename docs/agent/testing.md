# Testing: the verification ladder

Every piece of code comes with tests at the right level, and **work moves up a
level only after it passes the current one**. When something fails at level N,
the cause is in what level N added, not somewhere in the whole system.

## The ladder

| Level | What | Tools | Exit criterion | Runs |
|---|---|---|---|---|
| **L0 static** | build, lint, analysis, contracts | `-Werror`, uncrustify/cpplint/flake8/pep257, clang-tidy, `lint_rules.py`, `contracts.py validate/graph`, ASan/UBSan/TSan builds | zero warnings, zero findings | every change (`tools/check.sh`) |
| **L1 core units** | ROS-free core (ARCH-002) | gtest/gmock, pytest (Hypothesis/RapidCheck for math-heavy code) | all pass, core line coverage ≥ `COVERAGE_MIN_LINES` (TEST-017) | every change |
| **L2 single node** | one node in-process | gtest + executor / pytest + rclpy; fake device backend (TEST-010) | lifecycle incl. failure paths, every parameter validated, known input → known output, input loss → safe/reported state | every change |
| **L3 progressive integration** | real nodes as processes, one neighbour at a time | `launch_testing`, live contract check (CONTRACT-003), `contracts.py graph` | topics connect, QoS compatible, rate/latency budgets met, lifecycle ordering, clean shutdown (exit 0) | every change / MR |
| **L4 data replay** | recorded bags through the pipeline | `rosbag2_py`, golden outputs | outputs within tolerance of golden results | nightly (`--nightly`) |
| **L5 simulation scenarios** | full stack in Gazebo (gz sim) or Isaac Sim, scripted | launch_testing + sim, sim time | scenario pass criteria ("reaches goal < 60 s, no collision") | nightly |
| **L6 system acceptance** | real hardware | `ros2_tracing`, `performance_test`, soak, fault injection | budgets met, faults detected, safe state or recovery as designed | per release |

CI mapping:

| Stage | Levels | Trigger | Budget |
|---|---|---|---|
| local / pre-commit | L0–L2 (+ L3 of the touched package) | every change | < 2 min per package |
| merge request | L0–L3, ASan | every MR | < 15 min |
| nightly | L4, L5, TSan, coverage | schedule | hours |
| release | L6 | release candidate | days |

## What every package ships

**TEST-001 — Required tests per package.**

| Package type | Required |
|---|---|
| any | `ament_lint_auto` + `ament_lint_common` (C++/CMake) or the flake8/pep257/copyright/xmllint tests (Python) — L0 |
| core library | unit tests of every public function with edge cases: empty, NaN/Inf, bounds, time going backwards or wrapping — L1 |
| C++ node | node test: full lifecycle round trip **including failure paths** (invalid params make `on_configure` fail), each parameter's validation, data flow when active, silence when inactive, input loss / invalid input — L2 |
| Python node | node test: parameters, data flow, services, input loss — L2 |
| every node | `contract.yaml` + a launch test with the live contract check (CONTRACT-003) — L3 |
| launch file | launch test: starts, reaches active, publishes, exits 0 (LAUNCH-006) — L3 |
| system bringup | `system.contract.yaml` + progressive integration launch tests (TEST-011) — L3 |
| interfaces | lint only — L0 |

The templates contain one of each. Copy their structure.

## Rules

**TEST-002 — Core first.** Most assertions belong in L1 tests of the ROS-free core.
Node tests check the wiring, not the maths again.

**TEST-003 — Node tests run in-process.** Construct the node with `NodeOptions`
(namespace + `parameter_overrides`), put it and a helper node on one executor,
and drive transitions directly. A failure-path example:

```cpp
TEST(ImuDriverLifecycle, RejectsOutOfRangeRate) {
  rclcpp::NodeOptions opts;
  opts.parameter_overrides({{"device_backend", "fake"}, {"rate_hz", 1000}});
  auto node = std::make_shared<imu_driver::ImuDriver>(opts);
  EXPECT_EQ(node->configure().id(), lifecycle_msgs::msg::State::PRIMARY_STATE_UNCONFIGURED);
}
```

(With generate_parameter_library, an out-of-range override is already rejected at
construction. Test that with `EXPECT_THROW`, and test cross-parameter rules in
`on_configure`.)

**TEST-004 — No sleep-and-hope.** Wait on a condition with a timeout
(`spin_until(pred, timeout)` in the templates), and wait for discovery before
publishing. Timeouts are generous, because CI is slow. Tests must pass 20 times in a row:
`colcon test --packages-select <pkg> --retest-until-fail 20`.

**TEST-005 — Launch tests** include the *installed* launch file and assert behaviour,
not log text. A post-shutdown test checks exit codes.

**TEST-006 — Isolation.** Tests never see real robots or each other.
C++ uses `ament_add_ros_isolated_gtest`. `tools/check.sh` exports
`ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` and a private `ROS_DOMAIN_ID`. Each fixture
uses a unique namespace.

**TEST-007 — Every bug fix adds a regression test** that fails before the fix.

**TEST-008 — Determinism.** Inject time into the core, use sim time in node and
integration tests where time matters, seed randomness, and never depend on ordering
between different publishers.

**TEST-009 — Every handled failure mode has a test proving it's handled.** If the
code handles a timeout, a NaN, a device disconnect, a stale TF or a missing service,
a test triggers that condition and asserts the handling: the safe state, the
diagnostic, the log counter, or the lifecycle transition.

**TEST-010 — Hardware nodes have a fake backend.** A parameter
(`device_backend: real|fake`, or ros2_control `use_fake_hardware`) selects a
simulated device inside the node, so L2 and L3 run without hardware. Its behaviour
is scriptable from the test, for example to inject a disconnect after N reads.

**TEST-011 — Progressive integration.** For each system (or each plan milestone),
launch tests add one node at a time, like driver, then driver + filter, then driver +
filter + consumer. Each step runs the live contract check for the new node and
asserts the step's budgets (rate from a stimulus, latency from header stamps).
When a step fails, the newly added node or its connection is the suspect.

**TEST-012 — L4 replay tests** feed curated bags from `test/data/` (small `.mcap`,
normal operation plus known hard cases like dropouts, fast motion and bad
lighting) through the core, or through the node, and compare against stored golden
outputs with explicit tolerances. Register them with ctest `LABELS replay` or pytest
`@pytest.mark.replay`. `tools/check.sh --nightly` runs them.

**TEST-013 — L5 scenario tests** start the stack in simulation with scripted
scenarios and pass/fail criteria, for example "stop within 0.5 s of e-stop". Label them
`scenario`. They use sim time throughout.

**TEST-014 — L6 acceptance checklist** (per release, on hardware):
- performance: end-to-end latency from header stamps, callback jitter
  (`ros2_tracing` + `tracetools_analysis`), and CPU and memory per node against the
  plan's budgets
- soak: hours to days, watching for memory growth, rising latency and degrading rates
- fault injection: kill nodes, unplug sensors, `tc netem` delay/loss, clock jumps,
  topic floods. Each fault is detected, reported in `/diagnostics`, and ends in a safe
  state or recovery as designed.

**TEST-015 — Failures explain themselves.** Assertion messages state expected vs
observed (`"rate 142 Hz, expected 190–210 Hz"`), so an agent can diagnose without
re-running.

**TEST-016 — Fix the code, not the test.** Change a failing test only if the test is
demonstrably wrong, and say why in the change description. Never loosen tolerances,
raise timeouts, or skip tests to get green (TOOL-001).

**TEST-017 — Coverage.** `make coverage` (`tools/check.sh --coverage`) builds
instrumented binaries in `build-cov/` and fails when a package's line coverage is
below `COVERAGE_MIN_LINES` (project.env). C++ is measured on `src/` and `include/`,
Python on the package module. Core libraries should be well above the threshold.

## Running

```bash
make check p=my_pkg                  # L0–L3 for one package (the gate)
make nightly                         # + L4/L5
make coverage p=my_pkg               # + coverage threshold
colcon test --packages-select my_pkg --event-handlers console_direct+   # verbose
colcon test-result --verbose
```
