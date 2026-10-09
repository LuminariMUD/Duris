#!/usr/bin/env python3
"""The migrations/tools binaries build against the current src/ headers.

They are not part of the default build, so a src/ header change can break them unseen:
since 2026-09-13 a C++20 defaulted operator== in output_preference_state.h stopped the
C++14 tool build. They now build as C++20 like the server, and this test builds all three
into a scratch directory.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
assert "-std=c++20" in (ROOT / "migrations/tools/Makefile").read_text()
# An unchecked "len += snprintf(buf + len, size - len, ...)" writes past the buffer once it
# fills; migrate_players.c batches its rows through append_row() instead.
for source in sorted((ROOT / "migrations/tools").glob("*.c")):
    assert "+= snprintf(" not in source.read_text(), f"unchecked snprintf append in {source.name}"
(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="migration-tools-", dir=ROOT / "bin/tests") as scratch:
    for target in ("all", "affects", "pfile_converter"):
        built = subprocess.run(["make", "-C", "migrations/tools", f"BIN_ROOT={scratch}", target],
                               cwd=ROOT, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
        if built.returncode:
            raise SystemExit(built.stdout[-4000:])
    for binary in ("migrate_pfiles", "migrate_locker_affects", "pfile_converter"):
        assert (Path(scratch) / "migrations" / binary).is_file(), binary
print("[PASS] migrate_pfiles, migrate_locker_affects and pfile_converter build")
