# Benchmarks

Fixed tasks for measuring whether a guideline change makes agents produce better
code (MAINT-004). Treat them like regression tests for the docs.

## How to run one

1. Make a fresh copy of the workspace (`cp -r` the upstream repo, with an empty `src/`).
   Fill `PROJECT.md` minimally: project name and maintainer.
2. Start a **fresh** agent session in that copy. Paste the task prompt **verbatim**.
   Don't help.
3. When the agent says it's done, score it with the rubric below. Automated items come
   first: `tools/check.sh --strict` and `python3 tools/lint_rules.py src`.
4. Append a row to `results.md`: date, guidelines version, agent and model, task, score,
   and notes on the failures.

## Rubric (per task, 0–10)

| Points | Criterion |
|---|---|
| 3 | `tools/check.sh` passes without the agent weakening any check (0 if a check was weakened) |
| 2 | The task's specific acceptance criteria (listed per task) are all met |
| 1 | The package was scaffolded with `new_package.py` and has a ROS-free core with unit tests |
| 1 | Correct QoS for every endpoint (matches the qos.md table) |
| 1 | Lifecycle, parameters (schema + validation + units) and threading are correct |
| 1 | The README interface table matches the code |
| 1 | The agent's final report is accurate: it states what was run and doesn't claim unverified results |

Track the mean per task across versions. A drop of ≥ 1 point on any task after a
docs change is a regression.
