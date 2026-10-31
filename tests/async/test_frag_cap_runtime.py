#!/usr/bin/env python3
"""Actual game-thread publication over native storage with a controlled writer seam."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT

output = ROOT / "bin/tests"
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="frag-cap-runtime-", dir=output) as directory:
    binary = Path(directory) / "runtime"
    subprocess.run([
        "g++", "-std=c++20", "-g", "-Og", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        "-D__NO_MYSQL__", "-Isrc", "-Isrc/no_mysql", "tests/async/frag_cap_runtime_harness.cpp",
        "src/combat/frag_cap.c", "src/combat/frag_cap_repository.c", "src/combat/frag_cap_config.c",
        "src/flatfile/flatfile_store.c", "src/flatfile/flatfile_authority_transaction.c",
        "-lcrypto", "-pthread", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary), str(Path(directory) / "state")], check=True)
