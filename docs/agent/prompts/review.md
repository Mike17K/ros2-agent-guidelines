# Prompt: review a change (paste into any agent)

---

Review the current change (`git diff`, plus untracked files under `src/`) against this
workspace's guidelines. Don't edit files.

1. Read `AGENTS.md`, `docs/agent/anti_patterns.md`, the topic docs for the changed
   file types, `PROJECT.md`, and the related plan in `docs/plans/` if there is one.
2. Run `python3 tools/lint_rules.py <changed paths>` and `python3 tools/contracts.py graph`.
3. Check what tools can't: deadlocks and blocking in callbacks, lifecycle
   create/release symmetry, threading and shared state, QoS per endpoint and
   compatibility, command timeouts and safe states, input validation, RT-path
   allocation and locks, logic in a ROS-free core, contracts matching the code, the
   required tests per ladder level, and APIs that don't exist in Jazzy (verify with
   `grep -rn <symbol> /opt/ros/jazzy/include`).
4. Output one finding per line, most severe first:
   `[BLOCKER|MAJOR|MINOR] RULE-ID path:line — problem → concrete fix`.
   Report only issues you verified. End with the counts.
