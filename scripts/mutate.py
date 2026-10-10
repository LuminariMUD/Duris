#!/usr/bin/env python3
"""Mutation testing, by hand: do the tests that name a source notice when it is wrong?

    python3 scripts/mutate.py [--jobs N] [--timeout SECONDS] [--journeys] SRC_FILE...

For each file it finds the mutation sites outside comments, strings and preprocessor
lines: a relational operator flipped (< and <=, > and >=), == and != swapped, && and ||
swapped, a ! dropped, and a returned constant replaced (true and false, 0 and 1). Each
mutant is written into a worktree of HEAD under bin/analysis/mutate/, where the tests that
name the file run, the quickest first (by bin/test-history), N at a time, until one fails:
the mutant is caught. It works from HEAD, so it refuses a checkout with uncommitted changes
under src/ or tests/: commit a new test before scoring with it. Each file's tests first run
once unmutated, and one that fails there is left out of its score and listed.
scripts/mutate/g++, first on the tests' PATH, sends each compile through ccache when it is
installed, so a mutant rebuilds only its own file. The journeys (the runner's resource-intensive tests) run only with
--journeys: each takes minutes, and they name these files only to build a helper. A mutant no test fails survived, and is a missing test or dead code;
one whose tests ran out of time counts apart. The report, a score per file and every
survivor with its line, is printed and kept in bin/analysis/mutate-report.txt.

It never runs in a gate. The score counts only the tests that name the file: journeys
reach most files without naming them, so it shows where the focused tests are weak.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import signal
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TREE = ROOT / "bin/analysis/mutate"

# Comments (a // comment with its backslash continuations), string and character literals
# (raw strings to their own delimiter; an apostrophe after a digit or a letter is a digit
# separator), and preprocessor lines with their backslash continuations, blanked so no
# mutation lands in them; every offset and newline survives.
MASK = re.compile(r'(?<![A-Za-z0-9_])(?:u8|[uUL])?R"([^()\\\s]{0,16})\(.*?\)\1"|'
                  r'//(?:[^\n]*\\\n)*[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\\n])*"|'
                  r'(?<![A-Za-z0-9_])(?:u8|[uUL])?\'(?:\\.|[^\'\\\n])*\'|'
                  r'^[ \t]*#(?:[^\n]*\\\n)*[^\n]*', re.S | re.M)
OPERATORS = [
    # An operator clang-format leaves at the end of a line has a newline after it.
    (re.compile(r"(?<= )(<=|>=|<|>)(?=[ \n])"), {"<": "<=", "<=": "<", ">": ">=", ">=": ">"}),
    (re.compile(r"(?<= )(==|!=)(?=[ \n])"), {"==": "!=", "!=": "=="}),
    (re.compile(r"(?<= )(&&|\|\|)(?=[ \n])"), {"&&": "||", "||": "&&"}),
    (re.compile(r"!(?=[A-Za-z_(])"), {"!": ""}),
    # `return 0;` and the legacy `return (0);`.
    (re.compile(r"(?<=return )(true|false|0|1)(?=;)|(?<=return \()(true|false|0|1)(?=\);)"),
     {"true": "false", "false": "true", "0": "1", "1": "0"}),
]


def mutants(text: str) -> list[tuple[int, int, str, str]]:
    masked = MASK.sub(lambda match: re.sub(r"[^\n]", " ", match.group(0)), text)
    found = []
    for pattern, replacement in OPERATORS:
        for match in pattern.finditer(masked):
            found.append((match.start(), match.end(), match.group(0), replacement[match.group(0)]))
    return sorted(found)


def tests_naming(path: Path, journeys: bool) -> list[str]:
    # The whole file name, not the tail of a longer one (files.c in output_profiles.c).
    named = re.compile(rf"(?<![\w.-]){re.escape(path.name)}(?!\w)")
    sys.path.insert(0, str(ROOT / "tests"))
    from run_regression_tests import RESOURCE_INTENSIVE_TEST_NAMES
    tests = [test.name for test in sorted((TREE / "tests/async").glob("test_*.py"))
             if named.search(test.read_text(errors="replace")) and
             (journeys or test.name not in RESOURCE_INTENSIVE_TEST_NAMES)]
    seconds: dict[str, list[float]] = {}
    for record in sorted((ROOT / "bin/test-history").glob("*.json")):
        try:
            for test in json.loads(record.read_text())["tests"]:
                seconds.setdefault(Path(test["path"]).name, []).append(test["seconds"])
        except (OSError, ValueError, KeyError):
            continue
    return sorted(tests, key=lambda test: statistics.median(seconds.get(test, [600.0])))


# scripts/mutate/g++ splits each harness's one-command build into ccache compiles, so a
# mutant recompiles only the file it changed.
ENVIRONMENT = {**os.environ, "PATH": f"{ROOT / 'scripts/mutate'}{os.pathsep}{os.environ['PATH']}",
               "CCACHE_DIR": str(ROOT / "bin/analysis/mutate-ccache")}


def run_test(test: str, timeout: int) -> str:
    process = subprocess.Popen([sys.executable, f"tests/async/{test}"], cwd=TREE,
                               env=ENVIRONMENT, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        return "pass" if process.wait(timeout=timeout) == 0 else "fail"
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        return "timeout"


def judge(tests: list[str], jobs: int, timeout: int) -> tuple[str, str]:
    """caught (and by which test), survived, or timeout."""
    timed_out = False
    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        for start in range(0, len(tests), jobs):
            batch = tests[start:start + jobs]
            for test, outcome in zip(batch, pool.map(lambda t: run_test(t, timeout), batch)):
                if outcome == "fail":
                    return "caught", test
                timed_out |= outcome == "timeout"
    return ("timeout", "") if timed_out else ("survived", "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--journeys", action="store_true", help="run the journeys too")
    args = parser.parse_args()

    if subprocess.check_output(["git", "status", "--porcelain", "--", "src", "tests"], cwd=ROOT,
                               text=True).strip():
        print("mutate.py runs HEAD's tests on HEAD's sources: commit or stash the changes "
              "under src/ and tests/ first.", file=sys.stderr)
        return 2
    if not shutil.which("ccache"):
        print("No ccache: every harness rebuilds in full for every mutant.", flush=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    subprocess.run(["git", "worktree", "remove", "--force", str(TREE)], cwd=ROOT,
                   capture_output=True)
    subprocess.run(["git", "worktree", "add", "--quiet", "--detach", str(TREE), head], cwd=ROOT,
                   check=True)
    (TREE / "bin/tests").mkdir(parents=True, exist_ok=True)
    report = [f"Mutation testing of {head[:12]}"]
    try:
        for file in args.files:
            relative = file.resolve().relative_to(ROOT) if file.is_absolute() else file
            source = TREE / relative
            original = source.read_text()
            tests = tests_naming(source, args.journeys)
            # A test that fails unmutated would count as catching every mutant.
            with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
                baseline = dict(zip(tests, pool.map(lambda t: run_test(t, args.timeout), tests)))
            broken = [test for test in tests if baseline[test] != "pass"]
            tests = [test for test in tests if baseline[test] == "pass"]
            sites = mutants(original)
            print(f"{relative}: {len(sites)} mutants, {len(tests)} tests name it and pass",
                  flush=True)
            outcomes = {"caught": 0, "survived": 0, "timeout": 0}
            survivors = []
            for number, (start, end, old, new) in enumerate(sites, 1):
                line = original.count("\n", 0, start) + 1
                source.write_text(original[:start] + new + original[end:])
                try:
                    outcome, by = judge(tests, args.jobs, args.timeout)
                finally:
                    source.write_text(original)
                outcomes[outcome] += 1
                text = original.splitlines()[line - 1].strip()
                print(f"  {number}/{len(sites)} line {line} {old!r}->{new!r}: {outcome} {by}",
                      flush=True)
                if outcome != "caught":
                    survivors.append(f"    line {line}: {old!r} -> {new!r} ({outcome}): {text}")
            judged = outcomes["caught"] + outcomes["survived"]
            score = f"{100 * outcomes['caught'] / judged:.1f}%" if judged else "no score"
            report.append(f"{relative}: {score} ({outcomes['caught']} caught, "
                          f"{outcomes['survived']} survived, {outcomes['timeout']} timed out; "
                          f"{len(tests)} tests)")
            report += [f"    left out, {baseline[test]} unmutated: {test}" for test in broken]
            report += survivors
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(TREE)], cwd=ROOT,
                       capture_output=True)
    text = "\n".join(report) + "\n"
    (ROOT / "bin/analysis/mutate-report.txt").write_text(text)
    print("\n" + text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
