#!/usr/bin/env python3
"""Classify raw item evidence without constructing or modifying game objects."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT

output = ROOT / "bin/tests"
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="artifact-population-", dir=output) as directory:
    binary = Path(directory) / "population"
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-D__NO_MYSQL__",
        "-Isrc", "-Isrc/no_mysql", "-ffunction-sections", "-fdata-sections", "-fsanitize=address,undefined",
        "-fno-sanitize-recover=all", "-fno-omit-frame-pointer",
        "tests/async/artifact_population_harness.cpp", "src/guild/artifact_population.c", "src/item/item_transfer_command.c",
        "-Wl,--gc-sections",
        "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True, timeout=30)
