#!/usr/bin/env python3
"""scripts/tidy.sh fails on a clang-tidy finding on a staged line, and only there.

A fixture repository has the real .clang-tidy and tidy.sh and a src/Makefile with the
flags the script reads. A staged array whose last two strings lack a comma between them
fails --staged; the same file with the comma passes; a finding on a line no one changed
does not count, and `--all` on a clean file passes. What is staged decides, not the working tree: an unstaged fix does not
pass a staged finding, and an unstaged finding does not fail a staged fix. The user's git
config does not change the result: color.diff=always let every finding through, and
diff.noprefix=true failed every commit. Skipped where clang-tidy or clang-tidy-diff is not
installed.
"""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

from _paths import ROOT

if not (shutil.which("clang-tidy") and shutil.which("clang-tidy-diff")):
    print("SKIP: clang-tidy and clang-tidy-diff are not installed")
    raise SystemExit(0)

GLUED = 'const char *messages[] = { "one", "two", "three", "four", "five"\n\t"" };\n'
FIXED = 'const char *messages[] = { "one", "two", "three", "four", "five" };\n'

with tempfile.TemporaryDirectory() as temporary:
    repo = Path(temporary)
    (repo / "scripts").mkdir()
    (repo / "src").mkdir()
    shutil.copy2(ROOT / ".clang-tidy", repo / ".clang-tidy")
    shutil.copy2(ROOT / "scripts/tidy.sh", repo / "scripts/tidy.sh")
    (repo / "src/Makefile").write_text("CFLAGS = -std=c++20\nINCLUDES = -I.\n")
    source = repo / "src/probe.c"

    def git(*args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                        *args], cwd=repo, check=True, capture_output=True)

    def tidy(**config):
        environment = dict(os.environ, GIT_CONFIG_COUNT=str(len(config)))
        for index, (key, value) in enumerate(config.items()):
            environment[f"GIT_CONFIG_KEY_{index}"] = key.replace("_", ".")
            environment[f"GIT_CONFIG_VALUE_{index}"] = value
        return subprocess.run(["scripts/tidy.sh", "--staged"], cwd=repo, text=True,
                              capture_output=True, env=environment)

    git("init", "-q")
    source.write_text("int value()\n{\n\treturn 0;\n}\n")
    git("add", ".")
    git("commit", "-qm", "base")

    source.write_text(source.read_text() + GLUED)
    git("add", "src/probe.c")
    glued = tidy()
    assert glued.returncode == 1, glued.stdout + glued.stderr
    assert "bugprone-suspicious-missing-comma" in glued.stdout, glued.stdout
    for config in ({"color_diff": "always"}, {"diff_noprefix": "true"}):
        configured = tidy(**config)
        assert configured.returncode == 1 and \
            "bugprone-suspicious-missing-comma" in configured.stdout, \
            (config, configured.stdout + configured.stderr)
    # The finding stays staged while the working tree has the fix.
    source.write_text("int value()\n{\n\treturn 0;\n}\n" + FIXED)
    unstaged_fix = tidy()
    assert unstaged_fix.returncode == 1, unstaged_fix.stdout + unstaged_fix.stderr

    git("add", "src/probe.c")
    fixed = tidy()
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr
    # --all with no finding at all: the summary's grep matches nothing.
    clean = subprocess.run(["scripts/tidy.sh", "--all", "src/probe.c"], cwd=repo, text=True,
                           capture_output=True)
    assert clean.returncode == 0 and "0 findings" in clean.stdout, clean.stdout + clean.stderr
    # The fix is staged and the working tree has the finding again.
    source.write_text("int value()\n{\n\treturn 0;\n}\n" + GLUED)
    unstaged_finding = tidy()
    assert unstaged_finding.returncode == 0, unstaged_finding.stdout + unstaged_finding.stderr

    # The glued array committed, then an unrelated line changed: not this change's finding.
    source.write_text("int value()\n{\n\treturn 0;\n}\n" + GLUED)
    git("add", "src/probe.c")
    git("commit", "-qm", "legacy")
    source.write_text("int value()\n{\n\treturn 1;\n}\n" + GLUED)
    git("add", "src/probe.c")
    unrelated = tidy()
    assert unrelated.returncode == 0, unrelated.stdout + unrelated.stderr
print("tidy.sh fails on a finding on a staged line, and only there")
