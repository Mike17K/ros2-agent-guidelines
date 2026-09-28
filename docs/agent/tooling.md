# Tooling: what runs, and what to do when it fails

**TOOL-001 — `tools/check.sh` is the Definition of Done.** CI runs the same script
(`--strict`), so green locally means green in CI.

| Step | What | On failure |
|---|---|---|
| guideline rules | `tools/lint_rules.py` over the selected packages | Each finding cites a rule ID and a doc. Fix it, or add a `guideline-ignore: ID reason` if the rule genuinely doesn't apply. |
| build | `colcon build --symlink-install` with `-Werror`, `RelWithDebInfo`, compile_commands | Read the **first** error. Warnings are errors, so fix them; never silence them with pragmas. |
| contracts | `tools/contracts.py validate --require-for-nodes` + `graph` (after the build, so interface types are checked against the ament index) | Read the ERROR line. See contracts.md. The contract changes first (CONTRACT-002). |
| clang-tidy | `.clang-tidy` on every C++ source of the selected packages | Fix it. Suppress with `// NOLINT(check-name): reason` only for false positives. |
| test | `colcon test` + `colcon test-result` (unit, node, launch, and every ament linter) | See below. |

Useful flags: `--coverage` (instrumented build in `build-cov/`, threshold from project.env),
`--nightly` (also L4 replay / L5 scenario tests), `--packages a b` (scope, including building their dependencies),
`--no-tidy`/`--no-test` (only while iterating, never for the final report),
`--sanitize asan|tsan`, and `--debug`.

### Linter failures inside `colcon test`

| Test | Fix |
|---|---|
| `uncrustify` | `ament_uncrustify --reformat <files>` |
| `cpplint` | Read the message. Common ones: include guard name `PKG__FILE_HPP_`, include order, line > 100 |
| `flake8` | Import order is alphabetical (google style). Max line 99. Use relative imports for your own package |
| `pep257` | Multi-line docstring summary on the **second** line (`"""\n    Summary.`) |
| `copyright` | Every source file starts with the license header (templates show it) |
| `lint_cmake` | Formatting of CMake commands |
| `xmllint` | `package.xml` must validate against format 3 |
| `cppcheck` | Skipped on Jazzy with cppcheck 2.x (a known upstream slowdown). Clang-tidy covers it. |

**TOOL-002 — clang-tidy.** Install it with `sudo apt install clang-tidy`. The config
covers bugs, performance and modern C++ only. Style belongs to uncrustify and
cpplint. Without clang-tidy installed, `check.sh` reports it as SKIP, and in `--strict`
mode as FAIL.

**TOOL-003 — Templates are tested.** `tools/verify_templates.sh` scaffolds every
template under a new name into a temporary workspace and runs the full check.
Run it after any change to `templates/`, `tools/` or the lint rules, in the upstream
guidelines repo.

**TOOL-004 — Editor and agent hooks.** In Claude Code, `.claude/settings.json` runs
`tools/hooks/post_edit.sh` after every edit under `src/`. It formats C++ with
uncrustify, then runs the guideline rules and flake8, and feeds findings back to the
agent. With other agents, run `python3 tools/lint_rules.py <file>` after editing.
Humans can use `pre-commit install` (see `.pre-commit-config.yaml`).

### Sanitizers

- `--sanitize asan` builds with AddressSanitizer + UBSan into `build-asan/` and runs the
  C++ gtests. Use it for anything that touches memory, buffers, parsing or
  lifetimes.
- `--sanitize tsan` uses ThreadSanitizer (`build-tsan/`). Use it for anything with
  threads, callback groups or a MultiThreadedExecutor. DDS internals can produce
  reports. Put justified suppressions in a file and pass `TSAN_SUPP=<file>`.
- Python tests are skipped in sanitizer mode, because instrumented extensions need
  LD_PRELOAD. The normal run covers them.

### Build problems that aren't your code

| Symptom | Cause / fix |
|---|---|
| `existing path cannot be removed: Is a directory` | The package was built once without `--symlink-install`. `check.sh` cleans this automatically. By hand: `rm -rf build/<pkg> install/<pkg>` |
| `Could not find a package configuration file provided by "X"` | Missing dependency: add it to `package.xml`, then `rosdep install --from-paths src --ignore-src -y` |
| Stale behaviour after editing a Python launch or config file | New files need a rebuild to be installed (symlink mode only links existing ones) |
| `ros2 run` can't find the executable | `source install/setup.bash` in this shell |
