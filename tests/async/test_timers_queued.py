#!/usr/bin/env python3
"""A timer write is queued on the writer (persistence step 8).

set_timer() replaced its timers row on the game loop, so the staff cargo update waited on
the database. It is now queued on the writer, in capture order with the saves. get_timer()
still queries: only the boot reads a timer (the cargo market's last updates); the
periodic callers of has_elapsed() have no caller left.
"""
from pathlib import Path
import re

from _source_contract import function_bodies

SRC = Path(__file__).resolve().parents[2] / "src"
text = (SRC / "world/timers.c").read_text()
mariadb = text[text.index("#else\nvoid set_timer(const char *name)"):]
write = function_bodies(mariadb, r"\bvoid\s+set_timer\s*\(\s*const\s+char\s*\*\s*name\s*,\s*int\s+date\s*\)")[0]
assert "sql_queue(" in write and not re.search(r"\bqry\s*\(", write), write
cargo = (SRC / "ships/ship_cargo.c").read_text()
boot = function_bodies(cargo, r"\bvoid\s+initialize_ship_cargo\s*\(")[0]
assert "get_timer(" in boot
print("[PASS] set_timer queues its write; only the boot reads a timer")
