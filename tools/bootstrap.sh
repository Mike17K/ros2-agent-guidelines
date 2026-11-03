#!/usr/bin/env bash
# Bootstrap a brand-new ROS 2 workspace from the agent-guidelines template.
# This is NOT `git clone`: the new project gets its own fresh git history, not
# this repo's. Equivalent to the README's "Start a new project" cp -r, but for
# a different machine/repo that doesn't have a local checkout of this one.
#
# Run via curl:
#   curl -fsSL https://raw.githubusercontent.com/Mike17K/ros2-agent-guidelines/main/tools/bootstrap.sh \
#     | bash -s -- my_new_robot_ws
#
# Or locally: tools/bootstrap.sh <project-name> [parent-dir]
#
# GUIDELINES_REPO_URL / GUIDELINES_REF override the source repo/branch (e.g. to
# bootstrap from a fork, or from a local checkout for testing).
set -euo pipefail

NAME="${1:?usage: bootstrap.sh <project-name> [parent-dir]}"
PARENT="${2:-.}"
REPO_URL="${GUIDELINES_REPO_URL:-https://github.com/Mike17K/ros2-agent-guidelines.git}"
REF="${GUIDELINES_REF:-main}"

[[ "$NAME" =~ ^[A-Za-z][A-Za-z0-9_-]*$ ]] || {
  echo "bootstrap.sh: project name must start with a letter and contain only letters, digits, '-' or '_' (got '$NAME')" >&2
  exit 2
}
command -v git >/dev/null || { echo "bootstrap.sh: git is required" >&2; exit 2; }

PARENT="$(cd "$PARENT" && pwd)"
TARGET="$PARENT/$NAME"
[[ ! -e "$TARGET" ]] || { echo "bootstrap.sh: $TARGET already exists, refusing to overwrite" >&2; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Fetching guidelines ($REPO_URL@$REF)..."
git clone --quiet --depth=1 --branch "$REF" "$REPO_URL" "$TMP/upstream"
[[ -f "$TMP/upstream/.guidelines-managed" ]] || {
  echo "bootstrap.sh: $REPO_URL is not a guidelines repo (no .guidelines-managed)" >&2
  exit 2
}
VERSION="$(cat "$TMP/upstream/.guidelines-version" 2>/dev/null || echo unknown)"
rm -rf "$TMP/upstream/.git"

echo "Creating $TARGET..."
mkdir -p "$TARGET"
cp -r "$TMP/upstream/." "$TARGET/"

# Seed project.env with the new project's name (PROJECT_NAME and CONTAINER_NAME
# both default to the literal "ros2_project" placeholder).
sed -i "s/ros2_project/$NAME/g" "$TARGET/project.env"

cd "$TARGET"
git init --quiet
git add -A
git commit --quiet -m "Add ROS 2 agent guidelines system (v$VERSION)"

cat <<EOF

Workspace '$NAME' ready at $TARGET (guidelines v$VERSION), git-initialized with one commit.

Next:
  cd $TARGET
  \$EDITOR PROJECT.md project.env     # identity, package map, RMW, domain, DEVENV
  scripts/setup_host.sh               # what this machine is missing
  make new-cpp n=my_node d=src/my_domain
  make check                          # must print CHECK: PASS
EOF
