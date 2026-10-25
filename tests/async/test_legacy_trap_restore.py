#!/usr/bin/env python3
"""Real legacy writers/readers, SQL extra rows and reward snapshots preserve trap state."""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, SRC, HARNESS_STUBS, extract_function
from legacy_trap_manifest import TRAPS, FINITE

assert len(TRAPS) == 61
assert sum(final is None for _, old, final in TRAPS.values()) == 6
assert sum(final is not None and old != final for _, old, final in TRAPS.values()) == 17

functions = "\n".join(extract_function("files.c", signature) for signature in (
    "static bool has_serializable_extra_description(",
    "ulong ObjUniqueFlags(", "int writeObject(", "int write_one_object(",
    "ush_int getShort(", "uint getInt(", "long getLong(",
    "unsigned long long getUnsignedLongLong(", "char *getString(",
    "P_obj restoreObjects(", "P_obj read_one_object(",
))
files = (SRC / "files.c").read_text()
grouping = files[files.index("#define ObjectsMatch"):files.index("/*", files.index("#define ObjectsMatch"))]
sql = "\n".join(extract_function("sql_player.c", signature) for signature in (
    "static void sql_add_item_extra_descr(", "static bool sql_load_item_extra_descr_from_table(",
))
rows = []
for vnum, (_, old, final) in TRAPS.items():
    expected = final or (0, 0, 0, 0)
    rows.append("    {%d, {%s}, {%s}, %s}," % (
        vnum, ",".join(map(str, old)), ",".join(map(str, expected)),
        "true" if vnum in FINITE else "false"))
harness = (ROOT / "tests/async/legacy_trap_restore_harness.cpp").read_text()
harness = harness.replace("// GOLDEN_ROWS", "\n".join(rows))
harness = harness.replace("// FILE_FUNCTIONS", grouping + functions)
harness = harness.replace("// SQL_FUNCTIONS", sql)
build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="legacy-trap-restore-", dir=build) as directory:
    source = Path(directory) / "test.cpp"
    binary = Path(directory) / "test"
    source.write_text(harness)
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-sanitize-recover=all", "-fno-pie", "-no-pie",
        "-ffunction-sections", "-fdata-sections", "-Isrc", "-I/usr/include/mysql",
        str(source), "src/combat/trap_legacy.c", "src/account/account_reward_snapshot.c",
        "src/sql/item_extra_descr_codec.c", str(HARNESS_STUBS),
        "-Wl,--gc-sections", "-lcjson", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=30)
print("legacy trap restore: 61 profiles, spent/custom/idempotent state and real save/load owners passed")
