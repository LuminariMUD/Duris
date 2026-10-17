#!/usr/bin/env python3
"""Inspect pinned recovery graphs with the actual codec and framing validator."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, rel, HARNESS_STUBS

output = ROOT / "bin/tests"
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="artifact-recovery-population-", dir=output) as directory:
    binary = Path(directory) / "population"
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-pthread",
        "-D__NO_MYSQL__", "-Isrc", "-Isrc/no_mysql",
        "-fsanitize=address,undefined", "-fno-sanitize-recover=all", "-fno-omit-frame-pointer",
        "-ffunction-sections", "-fdata-sections",
        "tests/async/artifact_recovery_population_harness.cpp",
        "src/guild/artifact_population_recovery.c",
        *[rel(source) for source in ("world_recovery_pipeline.c", "world_recovery_codec.c",
                                    "generated_npc_state.c", "pet_restore_state.c")],
        str(HARNESS_STUBS), "-Wl,--gc-sections", "-lz", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True, timeout=30)
