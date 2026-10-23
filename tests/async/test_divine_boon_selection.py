#!/usr/bin/env python3
"""Run the real selector against an ordinary world graph and changing access."""

import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT

output_root = ROOT / "bin/tests"
output_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="divine-selection-", dir=output_root) as directory:
    binary = str(Path(directory) / "selection")
    subprocess.run(
        ["g++", "-std=c++20", "-g", "-Og", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
         "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
         "-Isrc", "-I/usr/include/mysql", "tests/async/divine_boon_selection_harness.cpp",
         "src/economy/divine_boon_selection.c", "src/economy/divine_boon.c",
         "-lcrypto", "-o", binary], cwd=ROOT, check=True,
    )
    subprocess.run([binary], cwd=ROOT, check=True)
