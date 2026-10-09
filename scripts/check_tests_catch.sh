#!/usr/bin/env bash
# check_tests_catch.sh BASE [HEAD]: does each regression test a range adds or changes fail
# on the code before the range? A test that passes on the broken code proves nothing, and
# in the gate it looks the same as one that works.
#
# For each tests/async/test_*.py the range adds or changes, when the range also changes
# src/: a detached worktree of BASE under bin/analysis/catch-<sha>/ takes HEAD's version
# of every file the range changed under tests/, and the test runs there against BASE's
# sources. "catches" means it failed on BASE; "does not catch" means it passed, which a
# refactor's reshaped test may do and still be right. It reports and does not block: the
# reviewer reads it, and the landing commit records it. A journey builds a server in the
# worktree first, about three minutes.
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
mapfile -t test_files < <(git diff --name-only --diff-filter=AMR "$base" "$head" -- tests)

tree="$PWD/bin/analysis/catch-${head:0:12}"
git worktree remove --force "$tree" 2>/dev/null || true
git worktree add --quiet --detach "$tree" "$base"
trap 'git worktree remove --force "$tree"' EXIT
git -C "$tree" checkout --quiet "$head" -- "${test_files[@]}"

caught=0
for test in "${tests[@]}"; do
    log="$tree/$(basename "$test" .py).log"
    if (cd "$tree" && timeout 1800 python3 "$test" >"$log" 2>&1); then
        echo "does not catch  $test (passes on ${base:0:12})"
    else
        echo "catches         $test (fails on ${base:0:12}: $(tail -n 1 "$log" | cut -c1-120))"
        caught=$((caught + 1))
    fi
done
echo "${caught} of ${#tests[@]} tests fail on ${base:0:12} without ${head:0:12}'s src/ changes."
