#!/usr/bin/env python3
"""Source contract for transactional player/account identity persistence."""

from _paths import SRC
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
core_source = (SRC / "sql.c").read_text()
core = core_source.rsplit("int sql_save_player_core(P_char ch)", 1)[1].split(
    "/* Save a variable delta", 1
)[0]

assert "UPDATE player_data SET active=1,account_name='%s' WHERE pid=%d" in core
assert "ch->desc->account->acct_name" in core
assert core.index("account_name") < core.index("sql_update_account_character(ch)")

print("player account identity save contracts passed")
