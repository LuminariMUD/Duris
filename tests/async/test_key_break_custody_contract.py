#!/usr/bin/env python3
"""A key that breaks in a lock is extracted in memory, and its holder's next save
no longer writes it."""

from _paths import SRC

actmove = (SRC / "actmove.c").read_text()

helper_start = actmove.index("static bool break_key(")
helper_end = actmove.index("static void telemetry_gameplay_context_changed", helper_start)
helper = actmove[helper_start:helper_end]
unlock_start = actmove.index("void do_unlock(")
unlock_end = actmove.index("void do_pick(", unlock_start)
unlock = actmove[unlock_start:unlock_end]

assert "item_movement_transaction_submit" not in actmove
assert "item_ownership_runtime" not in actmove
assert helper.index("unequip_char(actor, HOLD)") < helper.index("extract_obj(key, TRUE)")
assert helper.index("extract_obj(key, TRUE)") < helper.index("mark_player_dirty_components")
assert unlock.count("break_key(ch, key_obj);") == 2
assert "extract_obj(key_obj" not in unlock

print("broken key contract passed")
