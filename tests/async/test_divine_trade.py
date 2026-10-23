#!/usr/bin/env python3
"""Native lot/cap preparation and codec proof; no settlement/runtime claim."""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS

output_root = ROOT / "bin/tests"
output_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="divine-trade-", dir=output_root) as directory:
    binary = str(Path(directory) / "trade")
    subprocess.run(
        ["g++", "-std=c++20", "-g", "-Og", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
         "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
         "-ffunction-sections", "-fdata-sections", "-Isrc",
         "tests/async/divine_trade_harness.cpp", "src/economy/divine_trade.c",
         "src/persistence/critical_command.c", str(HARNESS_STUBS),
         "-Wl,--gc-sections", "-lcrypto", "-o", binary], cwd=ROOT, check=True,
    )
    subprocess.run([binary], cwd=ROOT, check=True)
