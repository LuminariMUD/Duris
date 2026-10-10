#!/usr/bin/env python3
"""The run history keeps every run, knows what a clean run is, and compares like with like.

- Two runs that start in the same second on one commit wrote the same file name, and the
  second overwrote the first. The name now carries the runner's pid, and the file is
  created exclusively.
- A run counted as clean with untracked files, which change what runs: a test fixed while
  still untracked was then reported flaky. Any untracked file now makes the run dirty: the
  tests read migrations/ and docs/ as well as src/, tests/, areas/ and scripts/.
- A test's time inside a full parallel run was set against its median from focused runs,
  made alone and faster, which reported it slower. Each run records its --match and worker
  count, and scripts/test_history.py compares the last run only with runs made like it.
"""
from pathlib import Path
import json
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def git(repo: Path, *arguments: str) -> None:
    subprocess.run(["git", *arguments], cwd=repo, check=True, capture_output=True)


with tempfile.TemporaryDirectory(prefix="test-history-") as temporary:
    repo = Path(temporary)
    git(repo, "init", "-q")
    (repo / "tests/async").mkdir(parents=True)
    (repo / "tests/async/test_a.py").write_text("")
    (repo / ".gitignore").write_text("/bin/\n")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "a")

    def write(started: str) -> None:
        """One run's history, written by its own process as a runner's is."""
        subprocess.run([sys.executable, "-c", f"""
import sys
from pathlib import Path
sys.path.insert(0, {str(ROOT / "tests")!r})
import run_regression_tests as runner
runner.ROOT = Path({str(repo)!r})
runner.write_history([runner.TestResult(runner.ROOT / "tests/async/test_a.py", 0, "", 2.0)],
                     {started!r}, None, 8)
"""], check=True)

    def runs() -> list[dict]:
        return [json.loads(path.read_text())
                for path in sorted((repo / "bin/test-history").glob("*.json"))]

    write("20261010T000000Z")
    write("20261010T000000Z")
    assert len(runs()) == 2, "a run in the same second overwrote another"
    assert [run["dirty"] for run in runs()] == [False, False]
    assert runs()[0]["jobs"] == 8 and runs()[0]["match"] is None

    (repo / "tests/async/test_new.py").write_text("")
    write("20261010T000001Z")
    (repo / "tests/async/test_new.py").unlink()
    (repo / "docs").mkdir()
    (repo / "docs/new.md").write_text("read by the documentation contract\n")
    write("20261010T000002Z")
    assert [run["dirty"] for run in runs()][2:] == [True, True]

with tempfile.TemporaryDirectory(prefix="test-history-report-") as temporary:
    history = Path(temporary)

    def run(index: int, seconds: float, match: str | None, status: str = "PASS",
            dirty: bool = False) -> None:
        record = {"commit": "c" * 40, "dirty": dirty, "started": f"20261010T{index:06d}Z",
                  "match": match, "jobs": 8,
                  "tests": [{"path": "tests/async/test_b.py", "status": status,
                             "seconds": seconds}]}
        (history / f"20261010T{index:06d}Z-cccccccccccc-1.json").write_text(json.dumps(record))

    # Five full runs at 10 s, six focused runs at 4 s, then a full run at 12 s: slower than
    # the focused runs' median, not than the full runs'. One failure, in a dirty tree.
    for index in range(5):
        run(index, 10.0, None)
    for index in range(5, 11):
        run(index, 4.0, "test_b")
    run(11, 1.0, "test_b", "FAIL", dirty=True)
    run(12, 12.0, None)
    report = subprocess.run([sys.executable, str(ROOT / "scripts/test_history.py"),
                             "--history", str(history)], check=True, capture_output=True,
                            text=True).stdout
    assert "Flaky (passed and failed on one clean commit): 0" in report, report
    assert "runs like the last before: 0" in report, report
print("the run history keeps every run and compares runs made alike")
