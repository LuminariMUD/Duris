#!/usr/bin/env python3
"""Revisioned dirty-player checkpoint contracts."""

from _paths import SRC
from pathlib import Path

text = (SRC / "persistence_checkpoint.c").read_text()

mark_start = text.index("void mark_player_dirty_components(int pid")
mark = text[mark_start:text.index("int get_dirty_player_count(void)", mark_start)]

# The player checkpoint loop; the event goes on to flush Redis floor drops.
flush_start = text.index("void event_flush_dirty_players(")
flush = text[flush_start:text.index("if (cursor < character_ids.size())", flush_start)]

checks = {
    "dirty marks are local and cumulative": "player_save_pipeline_mark(pid, components)" in mark,
    "autosave scans online PCs": "for (P_char character = character_list" in flush,
    "autosave captures only dirty state": "player_save_pipeline_checkpoint_dirty" in flush,
    "Redis is not a durability dependency": "redis_" not in flush,
    "database work is absent": "sql_" not in flush,
    "forked player flush is absent": "fork(" not in flush and "waitpid" not in flush,
}

for label, passed in checks.items():
    print(f"[{'PASS' if passed else 'FAIL'}] {label}")
assert all(checks.values())
print("revisioned dirty checkpoint semantics look correct")
