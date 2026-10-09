#!/usr/bin/env bash
# coverage.sh [--db] [COMMIT]: line coverage of src/ under the regression suite, on demand.
#
# Nothing else runs this, and its percentage is never a target: it shows which code no test
# reaches. It works in a detached worktree of COMMIT (HEAD by default) under
# bin/analysis/coverage-<sha>/, so the checkout and any running gate are untouched, with
# scripts/coverage/g++ first on PATH: every compile, the server's, the journeys' flat-file
# builds and the harnesses', gets --coverage and keeps its notes and counts under
# bin/coverage/<sha>/data/. It runs `make -k test-all` (and `make test-db` with --db),
# lists the tests that failed, and writes bin/coverage/<sha>/index.html and a per-directory
# summary for the files under src/.
#
# It cannot see a process ended with SIGKILL (the crash probes), a test that compiles a
# patched copy of a source (only src/ is reported), or a test that calls c++ or clang++.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

database=0
if [[ "${1:-}" == --db ]]; then database=1; shift; fi
commit=$(git rev-parse --verify --quiet "${1:-HEAD}^{commit}") || {
    echo "usage: $0 [--db] [COMMIT]" >&2; exit 2; }
short=${commit:0:12}
report="$PWD/bin/coverage/$short"
tree="$PWD/bin/analysis/coverage-$short"

rm -rf "$report"
mkdir -p "$report/data"
git worktree remove --force "$tree" 2>/dev/null || true
git worktree add --quiet --detach "$tree" "$commit"
trap 'git worktree remove --force "$tree"' EXIT

export COVERAGE_DATA="$report/data"
export PATH="$PWD/scripts/coverage:$PATH"
status=0
(cd "$tree" && make -k -j"$(nproc)" test-all) > "$report/test-all.log" 2>&1 || status=1
if (( database )); then
    (cd "$tree" && make test-db) > "$report/test-db.log" 2>&1 || status=1
fi
grep -hE '^\s+(FAIL|TIMEOUT|SIG[A-Z]+) tests/|^FAIL ' "$report"/test-*.log > "$report/failed.txt" || true

gcovr --root "$tree" --filter "$tree/src/" --html-details "$report/index.html" \
    --txt "$report/summary.txt" "$report/data" > "$report/gcovr.log" 2>&1
python3 - "$report/summary.txt" > "$report/directories.txt" <<'PYTHON'
import re, sys
from collections import defaultdict
lines = defaultdict(lambda: [0, 0])
for row in open(sys.argv[1]):
    match = re.match(r"(src/\S+)\s+(\d+)\s+(\d+)\s+\d+%", row)
    if match:
        directory = match.group(1).rsplit("/", 1)[0]
        lines[directory][0] += int(match.group(2))
        lines[directory][1] += int(match.group(3))
for directory, (total, covered) in sorted(lines.items()):
    print(f"{directory:30} {covered:7}/{total:<7} {100 * covered / total if total else 0:5.1f}%")
PYTHON
echo "Coverage of $short: $report/index.html ($(tail -n 2 "$report/summary.txt" | head -n 1 | awk '{print $NF}') of src/ lines)"
echo "Per directory: $report/directories.txt"
if [[ -s "$report/failed.txt" ]]; then
    echo "Tests that failed under coverage (their counts are missing, not the report):"
    sed 's/^/    /' "$report/failed.txt"
fi
exit $status
