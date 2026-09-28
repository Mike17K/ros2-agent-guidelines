---
name: ros2-plan
description: Brainstorm solution options and write an approved implementation plan (docs/plans/) for a new ROS 2 feature, subsystem or project BEFORE any code is written. Use when the user describes something to build that needs new packages, nodes, interfaces, contracts or system-structure changes, or asks to brainstorm, design, architect or plan.
---

# Plan before implementing (PLAN-001..005)

Follow `docs/agent/prompts/plan.md` exactly, with the goal taken from the user's request
(the skill arguments, if given). The rules behind it are in `docs/agent/planning.md`.

Claude Code specifics:
- Explore with read-only tools. For a broad sweep of an existing workspace, delegate to an
  Explore agent and keep only its conclusions.
- Ask blocking questions with AskUserQuestion, in one batch, with your recommended default
  as the first option. Skip the questions entirely if none are blocking.
- Put the options comparison and recommendation in the plan file. In chat, give only the
  3–5 line recommendation, the milestones, the open questions, and the file path.
- **Stop after writing the plan.** Don't scaffold packages or write code until the user
  approves. After approval, set `Status: approved` and implement milestone by milestone
  following `docs/agent/prompts/implement.md`. Use `/ros2-new-package` for each new
  package, and the `ros2-reviewer` agent before each milestone's final check.
