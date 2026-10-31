#!/usr/bin/env python3
"""Execute the production bartender geography against controlled authored graphs."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT


(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="world-quest-routes-", dir=ROOT / "bin/tests") as temporary:
    work = Path(temporary)
    binary = work / "routes"
    subprocess.run([
        "g++", "-std=c++20", "-g", "-O1", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
        "-ffunction-sections", "-fdata-sections", "-fsanitize=address,undefined",
        "-fno-sanitize-recover=all", "-Isrc", "-Isrc/no_mysql", "-D__NO_MYSQL__",
        "tests/async/world_quest_routes_harness.cpp",
        "-Wl,--gc-sections", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=work, check=True, timeout=30)
