#!/usr/bin/env python3
"""Stage physical artifact population evidence from real flat-file stores."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, rel, HARNESS_STUBS

sources = [
    "artifact_population.c", "flatfile_player_snapshot_file.c", "flatfile_locker_repository.c",
    "flatfile_world_item_repository.c", "flatfile_shopkeeper_repository.c",
    "flatfile_item_repository.c", "flatfile_auction_repository.c",
    "flatfile_collector_repository.c", "collector_command.c", "collector_codec.c", "collector_policy.c",
    "auction_command.c", "flatfile_player_domain_repository.c", "currency_command.c",
    "epic_command.c", "zone_touch_command.c", "combat_outcome_command.c", "boon_reward_command.c", "shop_trade_command.c",
    "flatfile_shop_trade_materialization.c", "legacy_object_identity.c", "flatfile_authority_transaction.c", "flatfile_store.c",
    "player_snapshot_codec.c", "item_transfer_command.c", "critical_command.c",
    "item_claim.c", "dupe_log.c", "persistence_observability.c",
]
output = ROOT / "bin/tests"
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="flat-population-", dir=output) as directory:
    binary = Path(directory) / "population"
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-pthread",
        "-fsanitize=undefined", "-fno-sanitize-recover=all", "-D__NO_MYSQL__",
        "-ffunction-sections", "-fdata-sections", "-Isrc", "-Isrc/no_mysql",
        "tests/async/flatfile_artifact_population_harness.cpp",
        *[rel(source) for source in sources], str(HARNESS_STUBS), "-Wl,--gc-sections", "-lcrypto", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary), str(Path(directory) / "state")], cwd=ROOT, check=True, timeout=30)
