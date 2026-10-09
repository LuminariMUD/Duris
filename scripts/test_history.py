#!/usr/bin/env python3
"""Report on the regression runs kept in bin/test-history/.

tests/run_regression_tests.py writes one file per run, <UTC time>-<short sha>.json, with the
commit, whether the tree was dirty, and each test's path, status and seconds. This reads
them and lists:

- tests that both passed and failed on the same clean commit (flaky);
- tests whose last time rose more than half over their median of the ten runs before;
- the twenty slowest tests of the last run.

    python3 scripts/test_history.py [--history DIR]
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(directory: Path) -> list[dict]:
    runs = []
    for path in sorted(directory.glob("*.json")):
        try:
            runs.append(json.loads(path.read_text()))
        except (OSError, ValueError) as error:
            print(f"skipped {path.name}: {error}")
    return runs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--history", type=Path, default=ROOT / "bin/test-history")
    args = parser.parse_args()
    runs = load(args.history)
    if not runs:
        print(f"No runs in {args.history}.")
        return 0
    print(f"{len(runs)} runs, {runs[0]['started']} to {runs[-1]['started']}")

    outcomes: dict[tuple[str, str], set[str]] = defaultdict(set)
    for run in runs:
        if not run["dirty"]:
            for test in run["tests"]:
                outcomes[(run["commit"], test["path"])].add(test["status"])
    flaky = sorted({(path, commit) for (commit, path), seen in outcomes.items()
                    if "PASS" in seen and len(seen) > 1})
    print(f"\nFlaky (passed and failed on one clean commit): {len(flaky)}")
    for path, commit in flaky:
        print(f"    {path} on {commit[:12]}: {', '.join(sorted(outcomes[(commit, path)]))}")

    times: dict[str, list[float]] = defaultdict(list)
    for run in runs:
        for test in run["tests"]:
            if test["status"] == "PASS":
                times[test["path"]].append(test["seconds"])
    slower = []
    for path, seconds in times.items():
        if len(seconds) >= 2:
            median = statistics.median(seconds[-11:-1])
            if median > 0 and seconds[-1] > 1.5 * median:
                slower.append((seconds[-1] / median, path, median, seconds[-1]))
    print(f"\nSlower than half again their median of the ten runs before: {len(slower)}")
    for ratio, path, median, last in sorted(slower, reverse=True):
        print(f"    {path}: {last:.1f}s against {median:.1f}s ({ratio:.1f}x)")

    print("\nSlowest twenty of the last run:")
    for test in sorted(runs[-1]["tests"], key=lambda test: -test["seconds"])[:20]:
        print(f"    {test['seconds']:8.1f}s  {test['status']:7} {test['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
