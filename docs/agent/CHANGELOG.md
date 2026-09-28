# Guidelines changelog

Versioning (`.guidelines-version`): patch = wording/examples, minor = new rule or
check, major = a rule change that makes previously passing code fail.

## 1.1.0 — 2026-09-28

- **Verification ladder L0–L6** (testing.md rewritten): TEST-009 failure-mode tests,
  TEST-010 fake device backend, TEST-011 progressive integration, TEST-012/013 replay and
  scenario tests (labelled, `--nightly`), TEST-014 acceptance checklist, TEST-015 self-explaining
  assertions, TEST-016 fix the code not the test, TEST-017 coverage threshold (`--coverage`).
- **Node contracts** (contracts.md, CONTRACT-001..004): `contract.yaml` per node,
  `system.contract.yaml` per system, `tools/contracts.py` validate/graph/live; the templates'
  launch tests run the live check; check.sh has a contracts step.
- **Planning first** (planning.md, PLAN-001..005): plan template, decision template, prompts
  for plan/implement/review, `/ros2-plan` skill.
- **System structure** from the zero_shot_robot_ws workcell: ARCH-010 domain folders, ARCH-011
  entity package sets, ARCH-012 layout-driven system bringup, ARCH-013 shared utils, ARCH-014
  orchestrator separation, ARCH-015 external/ submodules, ARCH-016 decision records;
  LAUNCH-007 entity bringup arguments, LAUNCH-008 event-based sequencing.
- **Dev environment** (devenv.md, DEVENV-001..005): `project.env`, `scripts/env.sh`,
  Makefile front door, `scripts/container.sh` (native | docker | isaac_ros), host check,
  external deps, tmux/terminator pane launcher.
- Stronger Definition of Done in AGENTS.md.

## 1.0.0 — 2026-09-28

- Initial system: AGENTS.md core rules + topic docs (architecture, cpp, python,
  qos, realtime, performance, interfaces, launch, testing, tooling, anti_patterns,
  maintenance).
- Golden templates: `ros_template_cpp` (lifecycle component + generate_parameter_library
  + unit/node/launch tests), `ros_template_py`, `ros_template_interfaces`.
- Tooling: `check.sh` (Definition of Done), `new_package.py`, `lint_rules.py`
  (18 rules, self-tested), `verify_templates.sh`, `sync_guidelines.sh`, Claude Code
  post-edit hook, clang-tidy config, pre-commit, GitHub Actions CI.
- Benchmarks B01–B08.
