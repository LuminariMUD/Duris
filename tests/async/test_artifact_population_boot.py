#!/usr/bin/env python3
"""Boot source selection/failure policy, with the real assembly and classifier."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT

output = ROOT / "bin/tests"
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="artifact-boot-", dir=output) as directory:
    binary = Path(directory) / "boot"
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-D__NO_MYSQL__",
        "-Isrc", "-Isrc/no_mysql", "-ffunction-sections", "-fdata-sections",
        "-fsanitize=address,undefined", "-fno-sanitize-recover=all", "-fno-omit-frame-pointer",
        "tests/async/artifact_population_boot_harness.cpp", "src/guild/artifact_population_boot.c",
        "src/guild/artifact_population.c", "src/item/item_transfer_command.c",
        "-Wl,--gc-sections", "-lcrypto", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True, timeout=30)

comm = (ROOT / "src/net/comm.c").read_text()
main = comm[comm.index("int main(int argc, char **argv)"):]
assert main.index("redis_init();") < main.index("artifact_population_prepare_boot(copyover_boot)")
assert main.index("artifact_population_prepare_boot(copyover_boot)") < main.index("reap_unheld_player_items_at_boot();")
world = (ROOT / "src/world/db.c").read_text()
boot = world[world.index("void boot_db(int mini_mode)"):]
assert boot.index("generate_indices(obj_f") < boot.index("stage_artifact_population();") < boot.index("ne_init_events();")
