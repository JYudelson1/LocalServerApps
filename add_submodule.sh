#!/usr/bin/env bash
# Register a GitHub repo as a submodule under the parent repo.
# If the target path already exists as a local clone, it must be clean (no
# uncommitted changes and no unpushed commits) before it is removed and re-added.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PATH_TO_APP=""
GITHUB_REPO=""
BRANCH="main"

usage() {
  cat <<'EOF'
Usage: ./add_submodule.sh --path-to-app PATH --github-repo URL

Options:
  --path-to-app PATH   Submodule path relative to repo root (e.g. sites/MyApp)
  --github-repo URL    GitHub clone URL (https:// or git@)
  --branch NAME        Branch to track (default: main)

If PATH already exists as a local git repo, it must be clean before this script
will remove it and re-add from GitHub. Push or stash any local work first.

Examples:
  ./add_submodule.sh \
    --path-to-app sites/MyApp \
    --github-repo https://github.com/JYudelson1/MyApp.git
EOF
}

die() {
  echo "Error: $*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --path-to-app)
      [[ $# -ge 2 ]] || die "missing value for --path-to-app"
      PATH_TO_APP="$2"
      shift 2
      ;;
    --github-repo)
      [[ $# -ge 2 ]] || die "missing value for --github-repo"
      GITHUB_REPO="$2"
      shift 2
      ;;
    --branch)
      [[ $# -ge 2 ]] || die "missing value for --branch"
      BRANCH="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1 (try --help)"
      ;;
  esac
done

[[ -n "$PATH_TO_APP" ]] || die "--path-to-app is required (try --help)"
[[ -n "$GITHUB_REPO" ]] || die "--github-repo is required (try --help)"

git rev-parse --git-dir >/dev/null 2>&1 || die "run this from the LocalServerApps git repo root"

# Reject absolute paths and path traversal.
if [[ "$PATH_TO_APP" == /* ]] || [[ "$PATH_TO_APP" == *".."* ]]; then
  die "--path-to-app must be a relative path inside this repo (no '..' or leading /)"
fi

is_registered_submodule() {
  git config -f .gitmodules --get-regexp '^submodule\..*\.path$' 2>/dev/null \
    | awk '{ print $2 }' | grep -Fxq "$PATH_TO_APP"
}

is_git_repo() {
  local dir="$1"
  git -C "$dir" rev-parse --git-dir >/dev/null 2>&1
}

repo_has_uncommitted_changes() {
  local dir="$1"
  [[ -n "$(git -C "$dir" status --porcelain)" ]]
}

repo_has_unpushed_commits() {
  local dir="$1"
  local branch upstream unpushed

  branch="$(git -C "$dir" symbolic-ref -q HEAD 2>/dev/null || true)"
  [[ -n "$branch" ]] || return 0

  git -C "$dir" fetch origin --quiet 2>/dev/null || true

  upstream="$(git -C "$dir" rev-parse --abbrev-ref '@{u}' 2>/dev/null || true)"
  if [[ -n "$upstream" ]]; then
    unpushed="$(git -C "$dir" log '@{u}..HEAD' --oneline 2>/dev/null || true)"
  else
    local branch_name="${branch#refs/heads/}"
    if git -C "$dir" rev-parse "origin/${branch_name}" >/dev/null 2>&1; then
      unpushed="$(git -C "$dir" log "origin/${branch_name}..HEAD" --oneline 2>/dev/null || true)"
    else
      unpushed=""
    fi
  fi

  [[ -n "$unpushed" ]]
}

check_local_repo_clean() {
  local dir="$1"
  local problems=()

  if repo_has_uncommitted_changes "$dir"; then
    problems+=("uncommitted changes")
  fi
  if repo_has_unpushed_commits "$dir"; then
    problems+=("unpushed commits")
  fi

  if ((${#problems[@]} > 0)); then
    echo "Error: ${dir} is not clean (${problems[*]})." >&2
    echo >&2
    echo "Push or stash your work in that repo before adding it as a submodule." >&2
    echo "  cd ${dir}" >&2
    echo "  git status" >&2
    echo "  git push origin ${BRANCH}   # if you have unpushed commits" >&2
    exit 1
  fi
}

remove_existing_path() {
  local path="$1"

  if is_registered_submodule; then
    echo "Removing existing submodule registration for ${path}..."
    git submodule deinit -f -- "$path" 2>/dev/null || true
    git rm -f -- "$path" 2>/dev/null || true
    rm -rf ".git/modules/${path}"
  fi

  if [[ -e "$path" ]]; then
    echo "Removing existing directory ${path}..."
    rm -rf "$path"
  fi
}

if [[ -e "$PATH_TO_APP" ]]; then
  if is_git_repo "$PATH_TO_APP"; then
    echo "Checking ${PATH_TO_APP} for uncommitted or unpushed work..."
    check_local_repo_clean "$PATH_TO_APP"
    remove_existing_path "$PATH_TO_APP"
  elif is_registered_submodule; then
    remove_existing_path "$PATH_TO_APP"
  else
    die "${PATH_TO_APP} exists but is not a git repo; move or remove it manually, then re-run"
  fi
elif is_registered_submodule; then
  remove_existing_path "$PATH_TO_APP"
fi

echo "Adding submodule ${GITHUB_REPO} -> ${PATH_TO_APP} (branch: ${BRANCH})..."
git submodule add -b "$BRANCH" "$GITHUB_REPO" "$PATH_TO_APP"

git add .gitmodules "$PATH_TO_APP"

echo
echo "Done. Submodule added and staged. Next:"
echo "  git commit -m \"Add ${PATH_TO_APP} submodule\""
echo "  git push"
