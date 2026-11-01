#!/usr/bin/env python3
"""Regression test for Underdark and surface smoking precipitation checks (issue #528)."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
flags = (
    ["-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie"]
    if os.environ.get("SANITIZE") == "1"
    else []
)

with tempfile.TemporaryDirectory(prefix="smoke-weather-", dir=build) as directory:
    binary = Path(directory) / "harness"
    subprocess.run(
        [
            "g++",
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-Wpedantic",
            "-Og",
            "-g",
            *flags,
            f"-I{ROOT / 'src'}",
            "-I/usr/include/mysql",
            "-I/usr/include/libxml2",
            str(ROOT / "tests/async/smoke_weather_harness.cpp"),
            str(ROOT / "src/core/smoke.c"),
            "-o",
            str(binary),
        ],
        check=True,
        timeout=120,
    )
    subprocess.run([str(binary)], check=True, timeout=120)

print("test_smoke_weather passed.")
