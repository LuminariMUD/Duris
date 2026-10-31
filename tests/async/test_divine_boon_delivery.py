#!/usr/bin/env python3
"""Execute prepared PvP math, real publication and real capture deferral."""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function

output_root = ROOT / "bin/tests"
output_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="divine-delivery-", dir=output_root) as directory:
    source = Path(directory) / "delivery.cpp"
    text = (ROOT / "tests/async/divine_boon_delivery_harness.cpp").read_text()
    pipeline = (ROOT / "src/player/player_save_pipeline.c").read_text()
    text = text.replace("// PENDING_WORLD_QUEST_STATE",
                        pipeline[pipeline.index("struct pending_world_quest_save"):
                                 pipeline.index("/** Cache the explicit diagnostic switch")])
    for marker, path, signature in (
        ("CHECKPOINT_BODY", "player/player_save_pipeline.c", "player_save_pipeline_result player_save_pipeline_checkpoint_dirty("),
        ("LOAD_HOLD_BODY", "player/player_save_pipeline.c", "bool player_save_pipeline_load_held("),
        ("ORDINARY_PVP_MATH", "world/epic.c", "int epic_calculate_pvp_award("),
        ("PRECISE_STONE_BASE", "world/epic.c", "static double epic_stone_payout_precise("),
        ("PREPARED_ZONE_MATH", "world/epic.c", "static bool prepare_stone_award("),
        ("PREPARED_PVP_MATH", "world/epic.c", "bool epic_prepare_pvp_award("),
    ):
        text = text.replace("// " + marker, extract_function(path, signature))
    source.write_text(text)
    for backend in ("mariadb", "flatfile"):
        binary = str(Path(directory) / backend)
        subprocess.run(
            ["g++", "-std=c++20", "-g", "-Og", "-Wall", "-Wextra", "-Werror",
             "-fsanitize=address,undefined,float-cast-overflow", "-fno-omit-frame-pointer",
             "-fno-pie", "-no-pie", "-ffunction-sections", "-fdata-sections", "-Isrc",
             *(["-D__NO_MYSQL__", "-Isrc/no_mysql"] if backend == "flatfile" else []),
             str(source), "src/economy/divine_boon_delivery.c", "src/economy/divine_boon.c",
             "src/combat/combat_outcome_command.c", "src/guild/artifact_guild_command.c", "src/world/zone_touch_command.c", "src/world/epic_command.c", "src/persistence/critical_command.c",
             "src/combat/combat_outcome_transaction.c", "src/combat/combat_outcome_intent.c", "src/flatfile/flatfile_store.c",
             "src/economy/currency_command.c", str(HARNESS_STUBS),
             "-Wl,--gc-sections", "-lcrypto", "-o", binary], cwd=ROOT, check=True,
        )
        subprocess.run([binary, str(Path(directory) / backend) + "-journal"], cwd=ROOT, check=True)
