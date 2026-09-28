# Maintaining the guideline system

The guidelines are a living system. They improve only when real agent mistakes
are turned into rules, examples and checks, and when you measure that the
change helped.

## Ownership model

```
upstream guidelines repo (this folder's origin)       each project workspace (a copy)
  AGENTS.md, CLAUDE.md, docs/agent/, templates/,  ──►  same files, synced read-only
  tools/, .claude/, configs  (.guidelines-managed)     + PROJECT.md, docs/agent/local/,
                                                         tools/local/, src/   (project-owned)
```

**MAINT-002 — Sync, don't fork.** A workspace updates its managed files with
`tools/sync_guidelines.sh <upstream-checkout>` (use `--dry-run` first). The paths are
listed in `.guidelines-managed`. Project-specific content lives only in project-owned
paths, so a sync never destroys it. A rule that would help every project goes
upstream. A rule that applies to one project goes in `PROJECT.md` as `LOCAL-xxx`.

## MAINT-001 — Adding or changing a rule

Trigger: an agent made the same mistake twice, a review found a class of bug, or
a production incident happened.

1. **Pick the ID**: the next free number in the topic's prefix. Never reuse or
   renumber IDs, because reviews and suppressions reference them.
2. **Write the rule** in the topic doc: bold ID, a one-sentence rule, a one-line
   *why*, and a code example if it's non-obvious. It should be specific and testable,
   like "X must Y", not "be careful with X".
3. **Add a bad → good pair** to `anti_patterns.md` if it's a mistake agents make.
4. **Enforce it mechanically** if you can:
   - with a regex over code: add a `Rule(...)` to `tools/lint_rules.py` with `bad`/`good`
     samples, then run `python3 tools/lint_rules.py --self-test` (it fails if the doc
     doesn't mention the ID).
   - if a clang-tidy check covers it: enable it in `.clang-tidy`.
   - if it's behavioural: add the test pattern to the template, with a test.
5. **Promote it to AGENTS.md §2** only if violating it causes deadlocks, crashes, unsafe
   motion or silent data loss. Keep AGENTS.md under ~200 lines.
6. **Update the templates** if the rule changes what golden code looks like, then
   run `tools/verify_templates.sh`.
7. **Record it**: bump `.guidelines-version` (patch: wording or examples; minor: new rule or
   check; major: a rule change that makes existing code fail) and add an entry to
   `CHANGELOG.md`.
8. **Measure it**: run the affected benchmark tasks (`benchmarks/`) before and
   after.

## MAINT-003 — Keep it small

- Delete rules that tooling fully enforces from AGENTS.md. The linter message
  is enough.
- Prefer one example over three paragraphs.
- When a topic file passes ~300 lines, split it and add a row to the AGENTS.md §4 index.
- Every six months, review the rules: are there any agents no longer violate, or any the
  team suppresses often? Frequent suppressions mean the rule is wrong.

## MAINT-004 — Benchmarks

`docs/agent/benchmarks/` holds fixed tasks with acceptance criteria. After
changing the guidelines, run the tasks in a fresh copy of the workspace, in a
fresh agent session with the prompt verbatim, then score them with the rubric and log
the result. A guideline change that doesn't move a benchmark (or adds a regression)
gets reverted or reworked.
