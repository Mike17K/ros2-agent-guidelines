# Prompt: implement the next milestone (paste into any agent)

Replace `<PLAN FILE>` and paste everything below the line.

---

Implement the next unchecked milestone of the approved plan `<PLAN FILE>`.
Only that milestone: don't start the next one.

1. Read `AGENTS.md`, `PROJECT.md`, the plan, and the topic docs its milestone touches.
2. Write or update each affected node's `contract.yaml` first, then the tests that verify
   it, then the code. Create packages only with `tools/new_package.py`.
3. Work up the verification ladder (`docs/agent/testing.md`): L0 static, L1 core units,
   L2 the node alone, then L3 integration with the neighbours already done in
   earlier milestones. A level must pass before you move up.
4. If a test fails, fix the code, not the test, unless the test is demonstrably wrong.
   In that case, explain why in your report.
5. If reality forces a deviation from the plan (a missing API, a wrong assumption, an
   interface change), stop, update the plan with the reason, and ask before continuing
   if it changes interfaces, contracts or scope.
6. Done means the milestone's exit criteria pass and
   `tools/check.sh --packages <touched>` prints `CHECK: PASS`. Tick the milestone in the plan.
7. Report: what was built, the exact commands run with their results, any deviations,
   and what's next.
