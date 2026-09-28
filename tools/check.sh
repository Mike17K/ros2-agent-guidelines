#!/usr/bin/env bash
# Definition of Done gate [TOOL-001]. A task is complete only when this prints
# "CHECK: PASS". Agents run it themselves and fix every failure.
#
# Usage:
#   tools/check.sh                              # everything under src/
#   tools/check.sh --packages my_pkg other_pkg  # just these (+ their deps are built)
#   tools/check.sh --sanitize asan              # ASan+UBSan build in build-asan/, C++ gtests
#   tools/check.sh --sanitize tsan              # TSan build in build-tsan/, C++ gtests
#   tools/check.sh --coverage                   # coverage build in build-cov/, enforce COVERAGE_MIN_LINES
#   tools/check.sh --nightly                    # also run L4 replay / L5 scenario tests
#   tools/check.sh --strict                     # CI mode: missing optional tools = failure
#
# Steps: guideline rules -> colcon build (-Werror) -> contracts -> clang-tidy -> colcon test
#        [-> coverage]. Verification ladder: docs/agent/testing.md.
set -o pipefail

WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGES=()
SANITIZE=""
STRICT=0
DO_BUILD=1
DO_TEST=1
DO_TIDY=1
COVERAGE=0
NIGHTLY=0
JOBS="${CHECK_JOBS:-$(nproc)}"
BUILD_TYPE="RelWithDebInfo"

usage() { sed -n '2,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --packages) shift; while [[ $# -gt 0 && "$1" != --* ]]; do PACKAGES+=("$1"); shift; done ;;
    --ws) WS="$(cd "$2" && pwd)"; shift 2 ;;
    --sanitize) SANITIZE="$2"; shift 2 ;;
    --strict) STRICT=1; shift ;;
    --no-build) DO_BUILD=0; shift ;;
    --no-test) DO_TEST=0; shift ;;
    --no-tidy) DO_TIDY=0; shift ;;
    --debug) BUILD_TYPE="Debug"; shift ;;
    --coverage) COVERAGE=1; shift ;;
    --nightly) NIGHTLY=1; shift ;;
    -j|--jobs) JOBS="$2"; shift 2 ;;
    -h|--help) usage 0 ;;
    *) echo "unknown option: $1" >&2; usage 2 ;;
  esac
done

# --- Environment ---------------------------------------------------------------
# Source setup.bash whenever it exists, regardless of whether $ROS_DISTRO already
# looks set: some base images (e.g. ros:jazzy-ros-base) bake ROS_DISTRO into the
# image as a plain Docker ENV, present even when setup.bash was never sourced (e.g.
# under GitHub Actions' container jobs, which docker-exec into the image with its
# entrypoint overridden, so /ros_entrypoint.sh never runs). Gating on -z "$ROS_DISTRO"
# would skip sourcing there and leave CMAKE_PREFIX_PATH unset. Sourcing is idempotent.
DISTRO="${CHECK_ROS_DISTRO:-${ROS_DISTRO:-jazzy}}"
if [[ -f "/opt/ros/$DISTRO/setup.bash" ]]; then
  # shellcheck disable=SC1090
  source "/opt/ros/$DISTRO/setup.bash"
fi
if [[ -z "${AMENT_PREFIX_PATH:-}" ]]; then
  echo "ROS not found: no /opt/ros/$DISTRO/setup.bash and no ROS environment already sourced" >&2
  exit 2
fi
cd "$WS" || exit 2
[[ -d src ]] || { echo "no src/ in $WS" >&2; exit 2; }

penv() { grep -E "^$1=" "$WS/project.env" 2>/dev/null | tail -1 | cut -d= -f2-; }
# Test with the project's middleware (project.env), unless the caller overrides it.
if [[ -z "${RMW_IMPLEMENTATION:-}" && -n "$(penv RMW_IMPLEMENTATION)" ]]; then
  export RMW_IMPLEMENTATION="$(penv RMW_IMPLEMENTATION)"
fi
if [[ -n "$(penv RMW_CONFIG_FILE)" ]]; then
  cfg="$(penv RMW_CONFIG_FILE)"; [[ "$cfg" = /* ]] || cfg="$WS/$cfg"
  case "${RMW_IMPLEMENTATION:-}" in
    rmw_cyclonedds_cpp) export CYCLONEDDS_URI="file://$cfg" ;;
    rmw_fastrtps_cpp) export FASTRTPS_DEFAULT_PROFILES_FILE="$cfg" ;;
  esac
fi
COVERAGE_MIN="${COVERAGE_MIN_LINES:-$(penv COVERAGE_MIN_LINES)}"; COVERAGE_MIN="${COVERAGE_MIN:-80}"
# Launch tests import tools/contracts.py for the live contract check [CONTRACT-003].
export GUIDELINES_TOOLS="$TOOLS"

SUFFIX=""
CXX_FLAGS="-Werror"
LINK_FLAGS=""
case "$SANITIZE" in
  "") ;;
  asan) SUFFIX="-asan"; CXX_FLAGS+=" -fsanitize=address,undefined -fno-omit-frame-pointer -fno-sanitize-recover=undefined"
        LINK_FLAGS="-fsanitize=address,undefined"; BUILD_TYPE="Debug"
        export ASAN_OPTIONS="${ASAN_OPTIONS:-detect_leaks=0:abort_on_error=1:strict_string_checks=1}"
        export UBSAN_OPTIONS="${UBSAN_OPTIONS:-print_stacktrace=1:halt_on_error=1}" ;;
  tsan) SUFFIX="-tsan"; CXX_FLAGS+=" -fsanitize=thread -fno-omit-frame-pointer"
        LINK_FLAGS="-fsanitize=thread"; BUILD_TYPE="Debug"
        export TSAN_OPTIONS="${TSAN_OPTIONS:-second_deadlock_stack=1:halt_on_error=1${TSAN_SUPP:+:suppressions=$TSAN_SUPP}}" ;;
  *) echo "--sanitize must be asan or tsan" >&2; exit 2 ;;
esac
if [[ $COVERAGE -eq 1 ]]; then
  [[ -z "$SANITIZE" ]] || { echo "--coverage and --sanitize are exclusive" >&2; exit 2; }
  SUFFIX="-cov"; CXX_FLAGS+=" --coverage -fprofile-update=atomic"; LINK_FLAGS="--coverage"
  BUILD_TYPE="Debug"; DO_TIDY=0
fi
BUILD_BASE="build${SUFFIX}"
INSTALL_BASE="install${SUFFIX}"
LOG_BASE="log${SUFFIX}"
COLCON=(colcon --log-base "$LOG_BASE")
COMMON=(--base-paths src --build-base "$BUILD_BASE" --install-base "$INSTALL_BASE")

RESULTS=()
FAILED=0
record() {  # record <step> <PASS|FAIL|SKIP> [detail]
  RESULTS+=("$(printf '%-14s %-5s %s' "$1" "$2" "${3:-}")")
  [[ "$2" == FAIL ]] && FAILED=1
  return 0
}
section() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }

ALL_PKGS=$("${COLCON[@]}" list --base-paths src --names-only 2>/dev/null)
if [[ -z "$ALL_PKGS" ]]; then
  echo "No packages under src/ (scaffold one with tools/new_package.py). Nothing to check."
  echo "CHECK: PASS"
  exit 0
fi
if [[ ${#PACKAGES[@]} -gt 0 ]]; then
  for p in "${PACKAGES[@]}"; do
    grep -qx "$p" <<<"$ALL_PKGS" || { echo "unknown package: $p" >&2; exit 2; }
  done
  SELECT=(--packages-select "${PACKAGES[@]}")
  UPTO=(--packages-up-to "${PACKAGES[@]}")
else
  SELECT=()
  UPTO=()
fi
mapfile -t PKG_PATHS < <("${COLCON[@]}" list --base-paths src --paths-only "${SELECT[@]}")
mapfile -t PY_PKGS < <("${COLCON[@]}" list --base-paths src "${SELECT[@]}" | awk '$3=="(ros.ament_python)"{print $1}')

# Tests must never talk to a real robot on the lab network [TEST-006].
export ROS_AUTOMATIC_DISCOVERY_RANGE="${CHECK_DISCOVERY_RANGE:-LOCALHOST}"
export ROS_DOMAIN_ID="${CHECK_DOMAIN_ID:-$(( ($$ % 100) + 100 ))}"

# This workspace always builds with --symlink-install. A package build dir made
# without it cannot be reused (colcon fails with "existing path cannot be
# removed"), so drop such stale, derived build dirs up front.
for cache in "$BUILD_BASE"/*/CMakeCache.txt; do
  [[ -f "$cache" ]] || continue
  stale="$(dirname "$cache")"
  pkg="$(basename "$stale")"
  py_copy="$stale/ament_cmake_python/$pkg/$pkg"  # a real dir here = copied, not symlinked
  if ! grep -q '^AMENT_CMAKE_SYMLINK_INSTALL:.*=1' "$cache" || [[ -d "$py_copy" && ! -L "$py_copy" ]]; then
    echo "note: $stale was built without --symlink-install; removing it (derived artifacts only)"
    rm -rf "$stale" "$INSTALL_BASE/$(basename "$stale")"
  fi
done

# --- 1. Guideline rules --------------------------------------------------------
section "guideline rules"
if python3 "$TOOLS/lint_rules.py" "${PKG_PATHS[@]}"; then record rules PASS; else record rules FAIL; fi

# --- 2. Build --------------------------------------------------------------------
if [[ $DO_BUILD -eq 1 ]]; then
  section "colcon build ($BUILD_TYPE${SANITIZE:+, $SANITIZE}, -Werror)"
  CMAKE_ARGS=(-DCMAKE_BUILD_TYPE="$BUILD_TYPE" -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
              "-DCMAKE_CXX_FLAGS=$CXX_FLAGS")
  [[ -n "$LINK_FLAGS" ]] && CMAKE_ARGS+=("-DCMAKE_EXE_LINKER_FLAGS=$LINK_FLAGS"
                                        "-DCMAKE_SHARED_LINKER_FLAGS=$LINK_FLAGS")
  if "${COLCON[@]}" build "${COMMON[@]}" --symlink-install "${UPTO[@]}" \
      --parallel-workers "$JOBS" --event-handlers console_cohesion+ summary+ \
      --cmake-args "${CMAKE_ARGS[@]}"; then
    record build PASS
  else
    hint="see $LOG_BASE/latest_build"
    if grep -rqs "existing path cannot be removed" "$LOG_BASE/latest_build"; then
      hint="stale non-symlink build: rm -rf $BUILD_BASE/<pkg> $INSTALL_BASE/<pkg> for the failing package"
    fi
    record build FAIL "$hint"
    DO_TEST=0; DO_TIDY=0
  fi
fi

# --- 3. Contracts ----------------------------------------------------------------
if [[ $DO_BUILD -eq 0 || " ${RESULTS[*]} " == *"build          PASS"* ]]; then
  section "contracts"
  # shellcheck disable=SC1090,SC1091
  [[ -f "$INSTALL_BASE/setup.bash" ]] && source "$INSTALL_BASE/setup.bash"
  if python3 "$TOOLS/contracts.py" validate --require-for-nodes "${PKG_PATHS[@]}" \
      && python3 "$TOOLS/contracts.py" graph src; then
    record contracts PASS
  else
    record contracts FAIL "see docs/agent/contracts.md"
  fi
fi

# --- 4. clang-tidy ---------------------------------------------------------------
if [[ $DO_TIDY -eq 1 && -z "$SANITIZE" ]]; then
  section "clang-tidy"
  TIDY="$(command -v clang-tidy || ls /usr/bin/clang-tidy-* 2>/dev/null | sort -V | tail -1)"
  if [[ -z "$TIDY" ]]; then
    msg="clang-tidy not installed (sudo apt install clang-tidy)"
    echo "$msg"
    if [[ $STRICT -eq 1 ]]; then record clang-tidy FAIL "$msg"; else record clang-tidy SKIP "$msg"; fi
  else
    tidy_fail=0; tidy_files=0
    for pkg_path in "${PKG_PATHS[@]}"; do
      pkg=$(basename "$pkg_path")
      db="$BUILD_BASE/$pkg/compile_commands.json"
      [[ -f "$db" ]] || continue
      mapfile -t files < <(python3 - "$db" "$WS/$pkg_path" <<'PY'
import json, os, sys
db, root = sys.argv[1], os.path.realpath(sys.argv[2])
seen = set()
for e in json.load(open(db)):
    f = os.path.realpath(os.path.join(e['directory'], e['file']))
    if f.startswith(root + os.sep) and f not in seen:
        seen.add(f)
        print(f)
PY
)
      [[ ${#files[@]} -eq 0 ]] && continue
      tidy_files=$((tidy_files + ${#files[@]}))
      printf '%s\n' "${files[@]}" | xargs -P "$JOBS" -n 1 "$TIDY" -p "$BUILD_BASE/$pkg" --quiet \
        || tidy_fail=1
    done
    if [[ $tidy_fail -eq 0 ]]; then record clang-tidy PASS "$tidy_files files"; else record clang-tidy FAIL; fi
  fi
fi

# --- 5. Test ---------------------------------------------------------------------
if [[ $DO_TEST -eq 1 ]]; then
  section "colcon test${SANITIZE:+ (C++ gtests only, $SANITIZE)}"
  TEST_ARGS=()
  CTEST=()
  # L4 replay / L5 scenario tests are labelled (ctest LABELS, pytest markers) and
  # run only with --nightly [TEST-012, TEST-013].
  [[ $NIGHTLY -eq 0 ]] && CTEST+=(-LE "replay|scenario")
  [[ $NIGHTLY -eq 0 ]] && TEST_ARGS+=(--pytest-args -m "not replay and not scenario")
  [[ $COVERAGE -eq 1 ]] && TEST_ARGS+=(--pytest-with-coverage)
  if [[ -n "$SANITIZE" ]]; then
    # Python cannot load sanitizer-instrumented extensions without LD_PRELOAD;
    # sanitizer runs cover C++ unit/node tests, the normal run covers the rest.
    CTEST+=(-L gtest)
    [[ ${#PY_PKGS[@]} -gt 0 ]] && TEST_ARGS=(--packages-skip "${PY_PKGS[@]}" "${TEST_ARGS[@]}")
  fi
  [[ ${#CTEST[@]} -gt 0 ]] && TEST_ARGS+=(--ctest-args "${CTEST[@]}")
  "${COLCON[@]}" test "${COMMON[@]}" "${SELECT[@]}" --parallel-workers "$JOBS" \
    --event-handlers console_cohesion- summary+ "${TEST_ARGS[@]}" >/dev/null 2>&1
  bases=()
  if [[ ${#PACKAGES[@]} -gt 0 ]]; then
    for p in "${PACKAGES[@]}"; do [[ -d "$BUILD_BASE/$p" ]] && bases+=("$BUILD_BASE/$p"); done
  else
    bases=("$BUILD_BASE")
  fi
  test_fail=0
  for b in "${bases[@]}"; do
    "${COLCON[@]}" test-result --test-result-base "$b" --verbose | grep -v '^$' | tail -60 \
      || true
    "${COLCON[@]}" test-result --test-result-base "$b" >/dev/null 2>&1 || test_fail=1
  done
  summary=$("${COLCON[@]}" test-result --test-result-base "$BUILD_BASE" 2>/dev/null | tail -1)
  if [[ $test_fail -eq 0 ]]; then record test PASS "$summary"; else record test FAIL "$summary"; fi
fi

# --- 6. Coverage -------------------------------------------------------------------
if [[ $COVERAGE -eq 1 && $DO_TEST -eq 1 ]]; then
  section "coverage (lines, threshold ${COVERAGE_MIN}%)"
  cov_fail=0; cov_lines=()
  for pkg_path in "${PKG_PATHS[@]}"; do
    pkg=$(basename "$pkg_path"); b="$BUILD_BASE/$pkg"
    if grep -qx "$pkg" < <(printf '%s\n' "${PY_PKGS[@]}"); then
      data="$(find "$b" -maxdepth 3 -name .coverage 2>/dev/null | head -1)"
      [[ -n "$data" ]] || { cov_lines+=("$pkg: no Python coverage data"); continue; }
      pct="$(python3 -m coverage report --data-file="$data" --include="$WS/$pkg_path/*" \
              --omit='*/test/*,*/setup.py,*/launch/*' 2>/dev/null | awk '/^TOTAL/{gsub("%","",$NF); print $NF}')"
    else
      if [[ -z "$(find "$b" -name '*.gcda' -print -quit 2>/dev/null)" ]]; then
        cov_lines+=("$pkg: no C++ coverage data (interfaces-only package?)"); continue
      fi
      info="$b/coverage.info"
      lcov --quiet --capture --directory "$b" --output-file "$info.raw" \
           --ignore-errors mismatch,negative,unused,empty,inconsistent >/dev/null 2>&1
      lcov --quiet --extract "$info.raw" "$WS/$pkg_path/src/*" "$WS/$pkg_path/include/*" \
           --output-file "$info" --ignore-errors unused,empty,inconsistent >/dev/null 2>&1
      pct="$(lcov --summary "$info" --ignore-errors empty,inconsistent 2>/dev/null | awk '/lines/{gsub("%","",$2); print $2}')"
    fi
    [[ -n "$pct" ]] || { cov_lines+=("$pkg: coverage could not be computed"); continue; }
    if awk -v p="$pct" -v m="$COVERAGE_MIN" 'BEGIN{exit !(p+0 < m+0)}'; then
      cov_lines+=("$pkg: ${pct}% < ${COVERAGE_MIN}%  FAIL"); cov_fail=1
    else
      cov_lines+=("$pkg: ${pct}%")
    fi
  done
  printf '  %s\n' "${cov_lines[@]}"
  if [[ $cov_fail -eq 0 ]]; then record coverage PASS; else record coverage FAIL "below ${COVERAGE_MIN}% (TEST-017)"; fi
fi

# --- Summary ---------------------------------------------------------------------
section "summary"
printf '%s\n' "${RESULTS[@]}"
if [[ $FAILED -eq 0 ]]; then
  echo "CHECK: PASS"
  exit 0
fi
echo "CHECK: FAIL"
exit 1
