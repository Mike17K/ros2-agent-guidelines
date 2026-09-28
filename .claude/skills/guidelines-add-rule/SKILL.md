---
name: guidelines-add-rule
description: Turn a recurring agent mistake, review finding or incident into a guideline rule (ID, doc text, anti-pattern pair, lint rule, template/test update, version bump). Use when the user says "add a rule", "agents keep doing X", "remember not to do X in the guidelines", or after a bug whose class should be prevented.
---

# Add or change a guideline rule

This follows MAINT-001 in `docs/agent/maintenance.md`. Read that file first.

**Where does it go?**
- Every project would benefit, and you're in the **upstream guidelines repo** → `docs/agent/<topic>.md`.
- Every project would benefit, but you're in a **project workspace** → don't edit
  `docs/agent/` (it's overwritten on sync). Write the rule as `LOCAL-xxx` in `PROJECT.md` now,
  and tell the user it should be upstreamed.
- It's specific to this project → `PROJECT.md` "Project rules" as `LOCAL-xxx`.

**Steps** (upstream):
1. Find the next free ID: `grep -rhoE "\b<PREFIX>-[0-9]{3}\b" docs/agent AGENTS.md | sort -u | tail -3`.
2. Add the rule to the topic doc: bold ID, a one-sentence testable rule, a one-line *why*, and an example if needed.
3. Add a bad → good pair to `docs/agent/anti_patterns.md`.
4. If a regex can detect it, add a `Rule(...)` to `tools/lint_rules.py` with `bad`/`good` samples, and
   make sure it doesn't fire on the templates:
   `python3 tools/lint_rules.py --self-test && python3 tools/lint_rules.py templates`.
5. Promote it to AGENTS.md §2 only if violations cause deadlocks, crashes, unsafe motion or data loss.
6. If golden code changes, update `templates/` and run `tools/verify_templates.sh`.
7. Bump `.guidelines-version` and add a `docs/agent/CHANGELOG.md` entry.
8. Suggest which benchmark in `docs/agent/benchmarks/tasks.md` measures it, or add one.

Report the rule ID, the files changed, and whether it's mechanically enforced.
