#!/usr/bin/env python3
"""Keep the parallel flat-file journeys on distinct build outputs."""

from _paths import ROOT
from pathlib import Path
import shutil
import subprocess
import tempfile
import time


SOURCES = (
    ("tests/async/test_flatfile_combat_journey.py", "flatfile-combat"),
    ("tests/async/test_flatfile_chaos_new_character_kit.py", "flatfile-combat"),
    ("tests/async/test_account_recovery_journey.py", "flatfile-recovery"),
)

# The prefix is matched WITHOUT its closing bracket: a journey may pass further
# arguments to TemporaryDirectory and wrap the call, which the combat journey
# now does, and the contract is about the prefix rather than the call's shape.
for relative, prefix in SOURCES:
    source = (ROOT / relative).read_text()
    assert f'TemporaryDirectory(prefix=f"{prefix}-{{os.getpid()}}-"' in source, relative
    assert "build_flatfile_server(pathlib.Path(build_tmp))" in source, relative
    assert 'ROOT / "bin/tests/flatfile-combat"' not in source, relative

# Independent journey processes also share make world's scratch files. Exercise
# the real recipe with a small generator that rejects overlapping invocations.
with tempfile.TemporaryDirectory(prefix="duris-world-generation-") as temporary:
    checkout = Path(temporary)
    shutil.copy2(ROOT / "Makefile", checkout / "Makefile")
    areas = checkout / "areas"
    for directory in ("mob", "obj", "qst", "shp", "trg", "wld", "zon", "src"):
        (areas / directory).mkdir(parents=True)
    generator = areas / "m_slow"
    generator.write_text("""#!/bin/sh
set -eu
mkdir active
trap 'rmdir active' EXIT
touch started
sleep 0.3
for suffix in mob obj qst shp trg wld zon; do
    echo complete > "world.$suffix"
done
echo generated >> generations
""")
    generator.chmod(0o755)
    command = ["make", "--no-print-directory", "-o", "build-area-tools", "world"]
    processes = []
    try:
        processes.append(subprocess.Popen(command, cwd=checkout, stdout=subprocess.PIPE,
                                          stderr=subprocess.STDOUT, text=True))
        deadline = time.monotonic() + 5
        while not (areas / "started").exists():
            assert processes[0].poll() is None, processes[0].communicate()[0]
            assert time.monotonic() < deadline, "world generator did not start"
            time.sleep(0.01)
        processes.append(subprocess.Popen(command, cwd=checkout, stdout=subprocess.PIPE,
                                          stderr=subprocess.STDOUT, text=True))
        for process in processes:
            output, _ = process.communicate(timeout=10)
            assert process.returncode == 0, output
        assert (areas / "generations").read_text().splitlines() == ["generated"]
        for suffix in ("mob", "obj", "qst", "shp", "trg", "wld", "zon"):
            assert (areas / f"world.{suffix}").read_text() == "complete\n"
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.communicate()

print("parallel flat-file journey build isolation, world generation and cleanup passed")
