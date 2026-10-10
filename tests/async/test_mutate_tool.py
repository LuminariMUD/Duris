#!/usr/bin/env python3
"""scripts/mutate.py scores only what its tests notice, in a scratch repository.

- A comparison clang-format leaves at the end of a line (`a !=` then the operand on the
  next line) was never mutated: the pattern wanted a space after it. The legacy
  `return (0);` was not taken for a constant return, and the continued lines of a
  multi-line macro were mutated as code.
- Without ccache every compile through scripts/mutate/g++ failed, so every mutant counted
  as caught. The wrapper now runs the real g++ uncached.
- A test that fails unmutated counted as catching every mutant. Each file's tests now run
  once unmutated first, and a failing one is left out and listed.
- The tests were listed from the checkout and run in a worktree of HEAD, so an uncommitted
  test that names the file failed to open there and "caught" every survivor. They are
  listed from the worktree now, and a checkout with changes under src/ or tests/ is refused.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import mutate  # noqa: E402

wrapped = "\tif (left(1) !=\n\t    right(2))\n"
assert [(old, new) for _, _, old, new in mutate.mutants(wrapped)] == [("!=", "==")]
# The legacy `return (0);` is a constant return too; a continued macro is preprocessor text.
legacy = "\treturn (0);\n#define BOTH(a, b) \\\n\t((a) && \\\n\t (b))\n\treturn 1;\n"
assert [(old, new) for _, _, old, new in mutate.mutants(legacy)] == [("0", "1"), ("1", "0")]

# A function, its harness test, and a test that fails whatever the code says.
VALUE = "int value(int x)\n{\n\treturn x < 3;\n}\n"
TEST = r'''import subprocess, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory() as build:
    main = Path(build) / "main.c"
    main.write_text("int value(int);\nint main() { return !(value(2) == 1 && value(3) == 0); }\n")
    subprocess.run(["g++", "-x", "c++", str(ROOT / "src/value.c"), "-x", "c++", str(main),
                    "-o", str(Path(build) / "test")], check=True)
    subprocess.run([str(Path(build) / "test")], check=True)
'''

with tempfile.TemporaryDirectory(prefix="mutate-tool-") as temporary:
    root = Path(temporary)
    # Without ccache on PATH the wrapper still compiles and links.
    tools = root / "tools"
    tools.mkdir()
    for tool in ("g++", "python3", "as", "ld"):
        # The tool itself, not a ccache link to it (this machine has /usr/lib/ccache first).
        found = next(Path(directory) / tool for directory in os.environ["PATH"].split(os.pathsep)
                     if (Path(directory) / tool).is_file() and
                     Path(os.path.realpath(Path(directory) / tool)).name != "ccache")
        os.symlink(found, tools / tool)
    (root / "a.c").write_text("int b();\nint main() { return b(); }\n")
    (root / "b.c").write_text("int b() { return 0; }\n")
    path = f"{ROOT / 'scripts/mutate'}{os.pathsep}{tools}"
    for command in (["g++", "-c", "a.c", "-o", "a.o"], ["g++", "a.c", "b.c", "-o", "ab"]):
        built = subprocess.run(command, cwd=root, env=dict(os.environ, PATH=path),
                               capture_output=True, text=True)
        assert built.returncode == 0, (command, built.stderr)

    repo = root / "repo"
    for name in ("scripts/mutate.py", "scripts/mutate/g++", "tests/run_regression_tests.py"):
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, repo / name)
    (repo / "src").mkdir()
    (repo / "tests/async").mkdir()
    (repo / "src/value.c").write_text(VALUE)
    (repo / "tests/async/test_value.py").write_text(TEST)
    (repo / "tests/async/test_broken.py").write_text("# names value.c\nraise SystemExit(1)\n")
    (repo / ".gitignore").write_text("/bin/\n")

    def git(*arguments: str) -> None:
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                        *arguments], cwd=repo, check=True, capture_output=True)

    def score() -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "scripts/mutate.py", "--jobs", "2",
                               "src/value.c"], cwd=repo, capture_output=True, text=True)

    git("init", "-q")
    git("add", "-A")
    git("commit", "-qm", "value")
    scored = score()
    assert scored.returncode == 0, scored.stdout + scored.stderr
    report = (repo / "bin/analysis/mutate-report.txt").read_text()
    # x < 3 -> x <= 3 is caught by value(3); return 0/1 is not a constant return here.
    assert "src/value.c: 100.0% (1 caught, 0 survived, 0 timed out; 1 tests)" in report, report
    assert "left out, fail unmutated: test_broken.py" in report, report

    (repo / "tests/async/test_new.py").write_text("# names value.c\n")
    refused = score()
    assert refused.returncode == 2 and "commit or stash" in refused.stderr, refused
print("mutate.py scores only what its tests notice")
