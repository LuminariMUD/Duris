#!/usr/bin/env python3
"""Native prepared intent and entity-save/ACK crash boundaries."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT

sources = ["tests/async/flatfile_artifact_delivery_harness.cpp",
    "src/flatfile/flatfile_artifact_guild_delivery.c",
    "src/guild/artifact_guild_delivery.c",
    "src/flatfile/flatfile_player_domain_repository.c",
    "src/flatfile/flatfile_artifact_repository.c",
    "src/flatfile/flatfile_association_repository.c",
    "src/flatfile/flatfile_player_snapshot_file.c", "src/player/player_snapshot_codec.c",
    "src/guild/artifact_population.c", "src/item/item_transfer_command.c",
    "src/flatfile/flatfile_authority_transaction.c", "src/flatfile/flatfile_store.c",
    "src/world/epic_command.c", "src/world/zone_touch_command.c", "src/economy/currency_command.c",
    "src/combat/combat_outcome_command.c", "src/guild/artifact_guild_command.c",
    "src/persistence/critical_command.c"]
(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="artifact-delivery-", dir=ROOT / "bin/tests") as temporary:
    binary = Path(temporary) / "delivery"
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=undefined", "-fno-sanitize-recover=all", "-g", "-O1",
        "-D__NO_MYSQL__", "-DDURIS_FLATFILE_AUTHORITY_FAULT_TEST", "-Isrc", "-Isrc/no_mysql",
        *sources, "-lcrypto", "-pthread", "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary), str(Path(temporary) / "state")], cwd=ROOT, check=True, timeout=60)
    for mode in ("runtime-pending", "runtime-orphan", "runtime-reservation", "zone"):
        subprocess.run([str(binary), str(Path(temporary) / mode), mode], cwd=ROOT, check=True, timeout=30)
