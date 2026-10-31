#!/usr/bin/env python3
"""Execute production private-chest fixes under ASan/UBSan with controlled service boundaries."""
import os
import re
import subprocess
import tempfile
from pathlib import Path
from _paths import ROOT, HARNESS_STUBS, extract_function

sql = (ROOT / "src/sql/sql_player.c").read_text()
audit = sql[sql.index("struct sql_chest_log_entry\n"):sql.index("// single query corpse loading", sql.index("struct sql_chest_log_entry\n"))]

interpreter = (ROOT / "src/cmd/interp.c").read_text()
arguments = re.search(r'const char \*fill_words\[\] = \{.*?\};', interpreter, re.S).group(0)
arguments += "\n" + "\n".join(extract_function("cmd/interp.c", signature) for signature in (
    "int search_block(", "int fill_word(", "char *one_argument(",
))

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="private-chests-", dir=build) as tmp:
    binary = Path(tmp) / "test"
    source = Path(tmp) / "test.cpp"
    harness = (ROOT / "tests/async/private_chest_regressions.cpp").read_text()
    harness = harness.replace("// COMMAND_ARGUMENTS", arguments).replace("// AUDIT_PRODUCTION", audit)
    harness = harness.replace("// ACCOUNT_IDENTITY", extract_function("account/account.c", "const char *get_account_name_safe("))
    source.write_text(harness)
    subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-ffunction-sections", "-fdata-sections",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
                    "-Wl,--gc-sections", "-Wl,--wrap=getrandom", "-Isrc", "-I/usr/include/mysql", "-I/usr/include/libxml2",
                    str(source), "src/persistence/critical_command.c",
                    "src/player/player_snapshot_codec.c", "src/world/condition.c", str(HARNESS_STUBS),
                    "-lbsd", "-lmysqlclient", "-lcrypto", "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True, timeout=30,
                   env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1"})
