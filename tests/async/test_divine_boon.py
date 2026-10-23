#!/usr/bin/env python3
"""Executable Divine Boon rotation and snapshot contracts; no running server needed."""

import subprocess
import tempfile

from _paths import ROOT


output_root = ROOT / "bin" / "tests"
output_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="divine-boon-", dir=output_root) as directory:
    binary = f"{directory}/divine_boon_test"
    subprocess.run(
        [
            "g++", "-std=c++20", "-g", "-Og", "-Wall", "-Wextra", "-Wpedantic",
            "-Werror", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
            "-fno-pie", "-no-pie", "-Isrc",
            "tests/async/divine_boon_harness.cpp", "src/economy/divine_boon.c",
            "-lcrypto", "-o", binary,
        ],
        cwd=ROOT, check=True,
    )
    subprocess.run([binary], cwd=ROOT, check=True)
