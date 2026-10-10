#!/usr/bin/env python3
"""scripts/check_tests_catch.sh says "catches" only for a test that passes on HEAD and fails
on BASE, run in a scratch repository.

The script counted any failure on BASE as a catch, in a bare worktree with none of what the
checkout generates, so a comment-only range whose test reads areas/world.* reported one. It
now runs each test in a HEAD worktree first, the control, and reports "cannot judge" when
the test fails there too; both worktrees get `make world`. It also mirrors HEAD's whole
tests/ tree into BASE's worktree, so a test file the range deleted is gone there too.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]

# The fixture's tests read the source as text, the generated file `make world` writes, and
# whether a test-side file is present.
TEST = '''from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
assert "return 2;" in (ROOT / "src/value.c").read_text()
assert (ROOT / "world.txt").read_text() == "generated\\n"
assert not (ROOT / "tests/async/_stale.py").exists()
'''


def git(repo: Path, *arguments: str) -> str:
    return subprocess.run(["git", *arguments], cwd=repo, check=True, capture_output=True,
                          text=True).stdout.strip()


def commit(repo: Path, message: str, files: dict[str, str | None]) -> str:
    for name, text in files.items():
        path = repo / name
        if text is None:
            path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", message)
    return git(repo, "rev-parse", "HEAD")


with tempfile.TemporaryDirectory(prefix="check-tests-catch-") as temporary:
    repo = Path(temporary)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "config", "user.name", "test")
    (repo / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts/check_tests_catch.sh", repo / "scripts")
    base = commit(repo, "the bug", {
        "Makefile": "world:\n\t@echo generated > world.txt\n",
        ".gitignore": "/world.txt\n/bin/\n",
        "src/value.c": "int value(void) { return 1; }\n",
        "tests/async/_stale.py": "",
    })
    fixed = commit(repo, "the fix", {
        "src/value.c": "int value(void) { return 2; }\n",
        "tests/async/_stale.py": None,
        "tests/async/test_value.py": TEST,
        "tests/async/test_broken.py": "raise SystemExit('broken on HEAD as well')\n",
    })
    comment = commit(repo, "a comment", {
        "src/value.c": "// no behaviour change\nint value(void) { return 2; }\n",
        "tests/async/test_value.py": "# no behaviour change\n" + TEST,
    })

    def report(first: str, second: str) -> list[str]:
        result = subprocess.run(["bash", "scripts/check_tests_catch.sh", first, second],
                                cwd=repo, check=True, capture_output=True, text=True)
        return result.stdout.splitlines()

    lines = report(base, fixed)
    assert any(line.startswith("catches         tests/async/test_value.py") for line in lines), lines
    assert any(line.startswith("cannot judge    tests/async/test_broken.py") for line in lines), lines
    assert lines[-1].startswith("1 of 2 tests pass on"), lines
    # The test reads world.txt, which no worktree tracks, and the range deleted _stale.py
    # from tests/ before; neither makes BASE fail any more.
    lines = report(fixed, comment)
    assert lines[0].startswith("does not catch  tests/async/test_value.py"), lines
    git(repo, "checkout", "-q", "--detach", base)
    with_stale = commit(repo, "the fix, with _stale.py still there", {
        "src/value.c": "int value(void) { return 2; }\n",
    })
    deleted = commit(repo, "a comment, and _stale.py deleted", {
        "src/value.c": "int value(void) { return 2; }\n// no behaviour change\n",
        "tests/async/_stale.py": None,
        "tests/async/test_value.py": TEST,
    })
    lines = report(with_stale, deleted)
    assert lines[0].startswith("does not catch  tests/async/test_value.py"), lines
print("check_tests_catch.sh reports a catch only for pass on HEAD, fail on BASE")
