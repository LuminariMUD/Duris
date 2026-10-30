#!/usr/bin/env python3
"""Execute production private-chest fixes under ASan/UBSan with controlled service boundaries."""
import os
import subprocess
import tempfile
from pathlib import Path
from _paths import ROOT, HARNESS_STUBS

sql = (ROOT / "src/sql/sql_player.c").read_text()
audit = sql[sql.index("namespace\n{\nstruct pending_chest_log"):sql.index("// single query corpse loading", sql.index("struct pending_chest_log"))]

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="private-chests-", dir=build) as tmp:
    binary = Path(tmp) / "test"
    source = Path(tmp) / "test.cpp"
    source.write_text((ROOT / "tests/async/private_chest_regressions.cpp").read_text().replace("// AUDIT_PRODUCTION", audit))
    subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-ffunction-sections", "-fdata-sections",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
                    "-Wl,--gc-sections", "-Isrc", "-I/usr/include/mysql", "-I/usr/include/libxml2",
                    str(source), "src/persistence/critical_command.c",
                    "src/player/player_snapshot_codec.c", str(HARNESS_STUBS),
                    "-lbsd", "-lmysqlclient", "-lcrypto", "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True, timeout=30,
                   env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1"})
