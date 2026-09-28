# Prompt: brainstorm and plan (paste into any agent)

Replace `<GOAL>` and paste everything below the line.

---

You are working in a ROS 2 Jazzy workspace with agent guidelines. **Do not write
code or create packages in this task.** Your deliverable is an approved plan.

Goal: <GOAL>

Do this, in order:

1. Read `AGENTS.md`, `PROJECT.md`, `docs/agent/planning.md`, `docs/agent/architecture.md`
   and every file in `docs/decisions/`. Then read the topic docs relevant to the goal
   (qos, realtime, interfaces, launch, testing, contracts).
2. Explore what already exists. List the packages and their contracts
   (`python3 tools/contracts.py graph`), the relevant upstream packages and
   interfaces (`ros2 pkg list`, `ros2 interface list`), and `<project>_utils` helpers.
   Summarise what you can reuse.
3. Restate the goal, the success criteria (measurable) and the non-goals.
4. If something blocks planning, ask **all** blocking questions in one message, each
   with the default you'd pick. Then stop and wait. Don't ask anything the
   workspace or a sensible default answers.
5. Brainstorm 2–3 genuinely different solution options. Compare them in one table on:
   fit to requirements, latency and throughput, failure modes and robustness,
   testability, scaling to N instances, and effort. Recommend one, and say why the
   others lose.
6. Write the plan to `docs/plans/<YYYY-MM-DD>-<slug>.md` using
   `docs/agent/plan_template.md`. Fill in every section: packages (domain folder +
   role), a draft `contract.yaml` per node, interfaces with units, QoS per endpoint,
   lifecycle and bring-up order, parameters with units and ranges, rate, latency and
   safety budgets, a verification plan per ladder level L0–L6, milestones as
   progressive integration steps with command-level exit criteria, risks, and open
   questions. `Status: proposed`.
7. Reply with: the recommendation in 3–5 lines, the milestone list, the open questions,
   and the plan file path. Then **stop and wait for approval.**
