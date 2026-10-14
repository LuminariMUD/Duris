#!/usr/bin/env python3
"""Execute production petition/ptell bodies, native conversion, and real sockets."""

import os
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, SRC, SRC_ROOT, HARNESS_STUBS, extract_function

functions = [extract_function(path, signature) for path, signature in [
    ("actcomm.c", "void do_petition("),
    ("actwiz.c", "void do_ptell("),
    ("actcomm.c", "void send_to_gods("),
    ("interp.c", "void half_chop("),
    ("handler.c", "bool isname(const char *str, const char *namelist)"),
    ("comm.c", "void escape_act_dollars("),
]]

# Only these two accepted command paths may invoke the exporter. This prevents
# a future global GMCP/send/log hook from exporting other channels or echoes.
callers = []
for path in SRC_ROOT.rglob("*.c"):
    if path.name != "discord_petition.c" and "discord_petition_export(" in path.read_text():
        callers.append(path.relative_to(SRC_ROOT).as_posix())
        assert path.read_text().count("discord_petition_export(") == 1
assert sorted(callers) == ["cmd/actcomm.c", "cmd/actwiz.c"], callers
assert functions[0].count("discord_petition_export(") == 1
assert functions[1].count("discord_petition_export(") == 1

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
flags = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie"] if os.environ.get("SANITIZE") == "1" else []
with tempfile.TemporaryDirectory(prefix="discord-petition-", dir=build) as directory:
    temp = Path(directory)
    (temp / "petition_commands.inc").write_text("\n\n".join(functions))
    binary = temp / "harness"
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Og", "-g", *flags,
        f"-I{SRC}", f"-I{temp}",
        str(ROOT / "tests/async/discord_petition_export_harness.cpp"),
        str(SRC / "net/discord_bridge.c"), str(SRC / "net/discord_petition.c"),
        str(SRC / "net/ansi.c"), str(SRC / "net/unicode.c"),
        str(SRC / "core/safe_format.c"), str(HARNESS_STUBS), "-lcjson", "-lcrypto",
        "-o", str(binary),
    ], check=True, cwd=ROOT, timeout=120)
    subprocess.run([str(binary)], check=True, cwd=ROOT, timeout=60)

print("Accepted-command petition/ptell export and scope checks passed")
