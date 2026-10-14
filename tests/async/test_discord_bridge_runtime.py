#!/usr/bin/env python3
"""Build and run the real Discord JSON endpoint, with bounded syscall faults."""

import pathlib
import subprocess
import tempfile
from _paths import ROOT, SRC

build_root = ROOT / "bin" / "tests"
build_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="discord-bridge-", dir=build_root) as directory:
    binary = pathlib.Path(directory) / "runtime"
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", f"-I{SRC}",
        str(ROOT / "tests/async/discord_bridge_runtime_harness.cpp"),
        str(SRC / "net/discord_bridge.c"), "-lcjson", "-lcrypto",
        "-Wl,--wrap=send", "-Wl,--wrap=recv", "-Wl,--wrap=poll",
        "-Wl,--wrap=accept4", "-o", str(binary),
    ], check=True, cwd=ROOT, timeout=120)
    subprocess.run([str(binary)], check=True, cwd=ROOT, timeout=30)

# These lifecycle assertions complement executable socket/exec tests: real game
# initialization applies to cold boot and copyover; failed copyover skips shutdown.
comm = (SRC / "net/comm.c").read_text()
connection = comm[comm.index("static bool run_connection_phase"):
                  comm.index("static void run_session_input_phase")]
output = comm[comm.index("static void run_output_phase"):
              comm.index("static void run_event_phase")]
loop = comm[comm.index("void game_loop(int port, int sslport)"):]
assert "discord_bridge_poll();" in connection
assert "discord_bridge_flush();" in output
assert loop.index("discord_bridge_init()") < loop.index("resume_game_loop:")
assert loop.index("goto resume_game_loop;") < loop.index("discord_bridge_shutdown();")
assert "discord_bridge_shutdown" not in (SRC / "persistence/copyover.c").read_text()
print("Discord bridge runtime and game-loop integration contracts passed")
