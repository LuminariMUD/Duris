#!/usr/bin/env python3
"""Exercise actual copyover producers, bounded inspection, pinning and projections."""
from pathlib import Path
import subprocess
import os
import tempfile
from _paths import ROOT, rel, HARNESS_STUBS

output = ROOT / "bin/tests"
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="copyover-evidence-", dir=output) as directory:
    folder = Path(directory)
    binary = folder / "evidence"
    subprocess.run([
        "g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror", "-pthread",
        "-D__NO_MYSQL__", "-Isrc", "-Isrc/no_mysql", "-I/usr/include/libxml2",
        "-fsanitize=address,undefined", "-fno-sanitize-recover=all", "-fno-omit-frame-pointer",
        "-ffunction-sections", "-fdata-sections",
        "tests/async/copyover_evidence_harness.cpp", "src/guild/artifact_population_recovery.c",
        *[rel(source) for source in ("world_recovery_pipeline.c", "world_recovery_codec.c",
            "generated_npc_state.c", "pet_restore_state.c", "item_transfer_command.c")],
        str(HARNESS_STUBS), "-Wl,--gc-sections", "-lz", "-lbsd", "-lgnutls", "-o", str(binary),
    ], cwd=ROOT, check=True)
    for scenario in ("formats", "pin", "failed", "two", "nonregular", "symlink", "absent"):
        state = folder / scenario
        state.mkdir()
        subprocess.run([str(binary), scenario], cwd=state, check=True, timeout=30,
                       env=dict(os.environ, COPYOVER_STATE_FILE="copyover.dat"))
