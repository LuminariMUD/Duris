#!/usr/bin/env python3
"""Real persistence writer exercises the Divine Boon boot/publication boundary."""

import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS


output_root = ROOT / "bin" / "tests"
output_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="divine-boon-runtime-", dir=output_root) as directory:
    binary = f"{directory}/divine_boon_runtime_test"
    subprocess.run(
        [
            "g++", "-std=c++20", "-g", "-Og", "-Wall", "-Wextra", "-Wpedantic",
            "-Werror", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
            "-fno-pie", "-no-pie", "-D__NO_MYSQL__",
            "-DDURIS_FLATFILE_AUTHORITY_FAULT_TEST", "-Isrc", "-Isrc/no_mysql",
            "tests/async/divine_boon_runtime_harness.cpp",
            "src/economy/divine_boon.c", "src/economy/divine_boon_repository.c",
            "src/economy/divine_boon_runtime.c", "src/player/player_save_worker.c",
            "src/persistence/persistence_observability.c",
            "src/persistence/maintenance_scheduler.c",
            str(HARNESS_STUBS),
            "src/flatfile/flatfile_authority_transaction.c", "src/flatfile/flatfile_store.c",
            "-lcrypto", "-pthread", "-o", binary,
        ],
        cwd=ROOT, check=True,
    )
    subprocess.run([binary, f"{directory}/state"], cwd=ROOT, check=True, timeout=20)

comm = (ROOT / "src/net/comm.c").read_text()
boot = comm[comm.index("int run_the_game("):comm.index("static void run_recurring_persistence_phase(")]
assert boot.index("player_save_pipeline_init()") < boot.index("divine_boon_runtime_boot(")
assert "divine_boon_runtime_pulse();" in comm
