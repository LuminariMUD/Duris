#!/usr/bin/env python3
"""Execute real refill selection, catalog/custody commit, and runtime hydration."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, rel, HARNESS_STUBS

Path(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="duris-shop-restock-", dir=ROOT / "bin/tests") as temporary:
    binary = Path(temporary) / "restock"
    sources = ["tests/async/flatfile_shopkeeper_restock_harness.cpp", str(HARNESS_STUBS)] + [rel(name) for name in (
        "flatfile_shopkeeper_restock.c", "shopkeeper_restock.c", "flatfile_shopkeeper_repository.c",
        "flatfile_shopkeeper_ownership.c", "flatfile_item_repository.c", "flatfile_authority_transaction.c",
        "flatfile_store.c", "player_snapshot_codec.c", "item_ownership_runtime.c", "item_claim.c",
        "shop_trade_command.c", "item_transfer_command.c", "currency_command.c", "critical_command.c")]
    subprocess.run(["g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror", "-Isrc",
                    "-ffunction-sections", "-fdata-sections", "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
                    *sources, "-Wl,--gc-sections", "-lcrypto", "-pthread", "-o", str(binary)], cwd=ROOT, check=True)
    for mode in ("refill", "collision", "stale", "storage-failure", "publication-failure"):
        subprocess.run([str(binary), str(Path(temporary) / mode), mode], cwd=ROOT, check=True, timeout=30)
