#!/usr/bin/env python3
"""Regression check for the ship owner update."""
from _paths import SRC
from pathlib import Path
import re
from contract_text import contains

root = Path(__file__).resolve().parents[2]

# A ship save inserts or updates its row by id, so a rename's owner_name is
# persisted (behaviour: test_ship_save_ids_in_memory.py).
sql_player = (SRC / "sql_player.c").read_text()
assert contains(sql_player, "on duplicate key update owner_name=values(owner_name), ship_name=values(ship_name)")

print("ship owner update check passed")
