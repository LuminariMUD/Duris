#!/usr/bin/env python3
"""Native shared cap rules and bounded snapshot codec; no game/database fixtures."""

import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT


output_root = ROOT / "bin" / "tests"
output_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="frag-cap-", dir=output_root) as temporary:
    binary = str(Path(temporary) / "frag_cap_harness")
    subprocess.run(
        [
            "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-O2",
            "-I", str(ROOT / "src"),
            str(ROOT / "tests/async/frag_cap_harness.cpp"),
            "-x", "c++", str(ROOT / "src/combat/frag_cap.c"),
            "-lcrypto", "-o", binary,
        ],
        check=True,
    )
    subprocess.run([binary], check=True)
