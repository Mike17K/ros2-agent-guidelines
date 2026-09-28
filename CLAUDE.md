# CLAUDE.md

@AGENTS.md
@PROJECT.md

## Claude Code specifics

- **Skills**: `/ros2-plan` to brainstorm and write a plan before building anything PLAN-001 covers,
  `/ros2-new-package` to create a package or node, and `/guidelines-add-rule`
  when you (or the user) spot a recurring mistake worth a rule.
- **Reviewer subagent**: after a non-trivial change, delegate a review to the
  `ros2-reviewer` agent (read-only, cites rule IDs) before running the final check.
- **Hook**: every Edit/Write under `src/` is auto-formatted with `ament_uncrustify`
  and checked with `tools/lint_rules.py` (plus `ament_flake8` for Python). If the hook
  reports findings, fix them before continuing. Don't work around the hook.
- Load topic docs from `docs/agent/` on demand (AGENTS.md §4). Don't read them all up front.
- Long commands: `tools/check.sh` can take minutes. Scope it with `--packages` while iterating
  and run the full check once at the end.
