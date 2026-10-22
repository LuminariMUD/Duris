#!/usr/bin/env python3
"""Flat-file state commits, retry identity and interrupted authority recovery."""

import subprocess
import tempfile

from _paths import ROOT


output_root = ROOT / "bin" / "tests"
output_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="divine-boon-store-", dir=output_root) as directory:
    binary = f"{directory}/divine_boon_repository_test"
    subprocess.run(
        [
            "g++", "-std=c++20", "-g", "-Og", "-Wall", "-Wextra", "-Wpedantic",
            "-Werror", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
            "-fno-pie", "-no-pie", "-D__NO_MYSQL__",
            "-DDURIS_FLATFILE_AUTHORITY_FAULT_TEST", "-Isrc", "-Isrc/no_mysql",
            "tests/async/divine_boon_repository_harness.cpp",
            "src/economy/divine_boon.c", "src/economy/divine_boon_repository.c",
            "src/flatfile/flatfile_authority_transaction.c", "src/flatfile/flatfile_store.c",
            "-lcrypto", "-pthread", "-o", binary,
        ],
        cwd=ROOT, check=True,
    )
    subprocess.run([binary, f"{directory}/state"], cwd=ROOT, check=True)
