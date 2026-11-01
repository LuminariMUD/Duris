#!/usr/bin/env python3
"""Execute the production M-reset branch and batched SQL restore with fake world/DB I/O."""

from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
db = (ROOT / "src/world/db.c").read_text()
files = (ROOT / "src/core/files.c").read_text()
sql = (ROOT / "src/sql/sql_player.c").read_text()
helper_start = db.find("static bool room_has_shopkeeper(")
helper = "" if helper_start < 0 else db[helper_start:db.index("/* force_item_repop", helper_start)]
reset_start = db.index("case 'M': /* read a mobile */", db.index("void reset_zone("))
reset = db[reset_start:db.index("case 'O':", reset_start)]
restore_start = sql.index("struct shopkeeper_temp")
restore = sql[restore_start:sql.index("// True while the periodic save's next pulse", restore_start)]
harness = (ROOT / "tests/async/shopkeeper_population_harness.cpp").read_text()
harness = harness.replace("// PRODUCTION_HELPER", helper)
harness = harness.replace("// PRODUCTION_RESET", reset)
harness = harness.replace("// PRODUCTION_RESTORE", restore)
stock = (ROOT / "src/economy/shopkeeper_restock.c").read_text()
harness = harness.replace("// PRODUCTION_RESTOCK", stock[stock.index("std::vector<P_obj> shopkeeper_reboot_stock"):])

build_root = ROOT / "bin/tests"
build_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="shopkeeper-population-", dir=build_root) as temporary:
    source = Path(temporary) / "harness.cpp"
    binary = Path(temporary) / "harness"
    source.write_text(harness)
    subprocess.run([
        "g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        "-I", str(ROOT / "src"),
        str(source), "-o", str(binary),
    ], check=True)
    for scenario in ("reset", "shared", "duplicate", "cleanup", "invalid",
                     "refill", "unsold", "excess", "recovery", "refill-failure"):
        subprocess.run([str(binary), scenario], check=True, env={
            **os.environ, "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1",
        })
        print(f"shopkeeper population: {scenario} passed", flush=True)

assert "ORDER BY save_time DESC, id DESC" in restore, "duplicate rows must prefer the newest snapshot"
assert "bool sql_restore_shopkeepers(bool refill)" in sql
assert "static bool sql_restore_shopkeeper_catalog(int only_shop, P_char *restored, bool refill)" in restore
assert "return sql_restore_shopkeeper_catalog(-1, nullptr, refill);" in restore
assert "if (!sql_restore_shopkeepers(shopkeeper_boot_restock()))" in files
assert "SQL shopkeeper restore incomplete; refusing to publish partial stock" in files
