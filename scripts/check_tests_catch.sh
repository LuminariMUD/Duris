#!/usr/bin/env bash
# check_tests_catch.sh BASE [HEAD]: does each regression test a range adds or changes fail
# on the code before the range? A test that passes on the broken code proves nothing, and
# in the gate it looks the same as one that works.
#
# For each tests/async/test_*.py the range adds or changes, when the range also changes
# src/, the test runs in two fresh worktrees under bin/analysis/: HEAD's, the control, where
# it must pass, and BASE's sources with HEAD's whole tests/ tree (so a test file the range
# deleted is gone there too). Both get the generated world first (make world), which many
# tests read. "catches" means it passed on HEAD and failed on BASE; "does not catch" means
# it passed on both, which a refactor's reshaped test may do and still be right; "cannot
# judge" means it failed on HEAD's tree too, for something a fresh worktree lacks. It
# reports and does not block: the reviewer reads it, and the landing commit records it. A
# journey builds a server in each worktree first, about three minutes.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

usage() { echo "usage: $0 BASE [HEAD]" >&2; exit 2; }
[[ $# -ge 1 && $# -le 2 ]] || usage
base=$(git rev-parse --verify --quiet "$1^{commit}") || usage
head=$(git rev-parse --verify --quiet "${2:-HEAD}^{commit}") || usage

if git diff --quiet "$base" "$head" -- src; then
    echo "The range changes nothing under src/; there is no fix for a test to catch."
    exit 0
fi
mapfile -t tests < <(git diff --name-only --diff-filter=AMR "$base" "$head" -- 'tests/async/test_*.py')
if (( ${#tests[@]} == 0 )); then
    echo "The range adds or changes no tests/async/test_*.py."
    exit 0
fi
tree="$PWD/bin/analysis/catch-${head:0:12}"
control="$tree-head"
cleanup() {
    git worktree remove --force "$tree" 2>/dev/null || true
    git worktree remove --force "$control" 2>/dev/null || true
}
cleanup
trap cleanup EXIT
git worktree add --quiet --detach "$control" "$head"
git worktree add --quiet --detach "$tree" "$base"
rm -rf "$tree/tests"
git -C "$tree" checkout --quiet "$head" -- tests
make -s -C "$control" world >/dev/null
make -s -C "$tree" world >/dev/null

last_line() { tail -n 1 "$1" | cut -c1-120; }
caught=0
for test in "${tests[@]}"; do
    log=$(basename "$test" .py).log
    if ! (cd "$control" && timeout 1800 python3 "$test" >"$log" 2>&1); then
        echo "cannot judge    $test (fails on ${head:0:12} too: $(last_line "$control/$log"))"
    elif (cd "$tree" && timeout 1800 python3 "$test" >"$log" 2>&1); then
        echo "does not catch  $test (passes on ${base:0:12})"
    else
        echo "catches         $test (fails on ${base:0:12}: $(last_line "$tree/$log"))"
        caught=$((caught + 1))
    fi
done
echo "${caught} of ${#tests[@]} tests pass on ${head:0:12} and fail on ${base:0:12}."
