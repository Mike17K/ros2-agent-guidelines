#!/usr/bin/env bash
# Non-ROS third-party code and data (ARCH-015), declared in external/external.list:
#   submodule <path under external/> <git url> <tag|commit>
#   file      <path under external/> <url>          # e.g. model weights (gitignored)
# Idempotent: re-running only fills in what is missing or moves a pin.
set -euo pipefail
WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WS"
LIST=external/external.list
[[ -f "$LIST" ]] || { echo "no $LIST: nothing to do"; exit 0; }
git rev-parse --show-toplevel >/dev/null 2>&1 || { echo "workspace is not a git repo (git init first)" >&2; exit 1; }

while read -r kind path url ref; do
  [[ -z "${kind:-}" || "$kind" == \#* ]] && continue
  dest="external/$path"
  case "$kind" in
    submodule)
      [[ -n "${ref:-}" ]] || { echo "$dest: a pinned tag or commit is required" >&2; exit 1; }
      if ! git config -f .gitmodules --get "submodule.$dest.path" >/dev/null 2>&1; then
        git submodule add "$url" "$dest"
      fi
      git submodule update --init "$dest"
      git -C "$dest" fetch --depth 1 origin "$ref" 2>/dev/null || git -C "$dest" fetch origin
      git -C "$dest" checkout -q "$ref" 2>/dev/null || git -C "$dest" checkout -q FETCH_HEAD
      echo "submodule $dest @ $(git -C "$dest" rev-parse --short HEAD)"
      ;;
    file)
      if [[ -s "$dest" ]]; then echo "file      $dest (present)"; continue; fi
      mkdir -p "$(dirname "$dest")"
      curl -fL --retry 3 -o "$dest.part" "$url" && mv "$dest.part" "$dest"
      echo "file      $dest (downloaded)"
      ;;
    *) echo "unknown entry kind '$kind' in $LIST" >&2; exit 1 ;;
  esac
done < "$LIST"
echo "Commit the pins: git add .gitmodules external/"
