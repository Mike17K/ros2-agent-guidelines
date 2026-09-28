# Planning before implementation

Robotics mistakes are expensive to undo once they're spread over packages,
interfaces and launch files. For anything beyond a local change, the agent first
brainstorms and writes a plan, a human approves it, and only then does
implementation start.

**PLAN-001 — When a plan is required.** A written, approved plan in `docs/plans/`
is required before implementation when the task does any of these:
- creates a package or more than one node,
- adds or changes an interface (msg/srv/action) or a node contract between packages,
- changes system structure: domain folders, entities, the layout module, bring-up order,
- touches motion, safety, RT paths or hardware I/O,
- adds a dependency, a container change or a new external library,
- would take more than about one session of work.

A plan isn't needed for bug fixes inside one package, tests, docs, or refactors
that keep interfaces and contracts unchanged. When unsure, write a short plan.
It costs minutes.

**PLAN-002 — Process: understand, explore, options, recommend, plan, approval.**

1. **Understand.** Restate the goal, the users and the success criteria in your own
   words. Identify what's unknown.
2. **Explore before proposing.** Read `PROJECT.md`, `docs/decisions/`, and the existing
   packages and contracts (`tools/contracts.py graph`), plus the upstream packages you'd
   reuse (`ros2 pkg list`, `ros2 interface list`). Never propose building what already
   exists in the workspace, in ROS 2 Jazzy, or in a standard stack (ros2_control,
   MoveIt 2, Nav2, Isaac ROS).
3. **Ask only blocking questions**, batched in one message, each with your proposed
   default. Don't ask anything the code, PROJECT.md or a sensible default answers.
4. **Brainstorm 2–3 genuinely different options.** Examples: different decomposition,
   an existing stack vs custom, C++ vs Python, one node vs a pipeline of components.
   Compare them in a table on the same criteria: fit to requirements, latency and
   throughput, robustness and failure modes, testability, effort, and how it scales to
   N instances.
5. **Recommend one** and say why the others lose. Don't hedge.
6. **Write the plan** from `docs/agent/plan_template.md` to
   `docs/plans/YYYY-MM-DD-<slug>.md`, with `Status: proposed`.
7. **Stop and ask for approval.** Don't create packages or write code until the user
   approves or edits the plan. Then set `Status: approved`.

**PLAN-003 — A plan is concrete enough to check code against.** It names every
package (with domain folder and taxonomy role, ARCH-010/011), every node with a draft
`contract.yaml` (CONTRACT-001), and every new interface with its fields. It gives QoS
per endpoint, lifecycle and bring-up order, parameters with units and ranges, rate,
latency and safety budgets, and a verification plan per ladder level (testing.md).
"A perception node that processes the camera" is not a plan.

**PLAN-004 — Milestones are integration steps.** Each milestone adds one
capability or node, reaches L2 on its own, and then integrates with its already
working neighbours at L3 before the next one starts (progressive integration,
testing.md). Every milestone has exit criteria that are commands with expected
results, like `tools/check.sh --packages x y` passing or a launch test proving X
reaches Y at ≥ N Hz.

**PLAN-005 — The plan stays true.** While implementing, tick off milestones in the
plan file. When reality forces a deviation (a missing API, a failed assumption),
stop, update the plan with the reason, and tell the user before continuing if it
changes interfaces, contracts or scope. Decisions that outlive the plan go into
`docs/decisions/` (ARCH-016).

## Prompts

Copy-paste prompts for any agent are in `docs/agent/prompts/`:

| Prompt | Use |
|---|---|
| `plan.md` | brainstorm and write a plan for a new feature or system |
| `implement.md` | implement the next milestone of an approved plan |
| `review.md` | review a change against the guidelines |

In Claude Code, `/ros2-plan <goal>` runs the planning prompt.
