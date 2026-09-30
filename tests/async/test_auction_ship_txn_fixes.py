#!/usr/bin/env python3
"""Regression checks for the auction bid transaction leak and the ship owner update."""
from _paths import SRC
from pathlib import Path
import re
from contract_text import contains

root = Path(__file__).resolve().parents[2]

# 1. Auction bid failure paths must rollback owned transactions
auction = (SRC / "auction_houses.c").read_text()
assert contains(auction, "if (own_txn) sql_rollback();")
assert auction.count("sql_rollback();") >= 10

# 3. A ship save inserts or updates its row by id, so a rename's owner_name is
# persisted (behaviour: test_ship_save_ids_in_memory.py).
sql_player = (SRC / "sql_player.c").read_text()
assert contains(sql_player, "on duplicate key update owner_name=values(owner_name), ship_name=values(ship_name)")

# 4. Auction finalization still has the atomic claim
assert contains(auction, "UPDATE auctions SET status = %d WHERE id = '%d' AND status <> %d")
assert contains(auction, "mysql_affected_rows(DB) != 1")

print("auction bid leak and ship owner update checks passed")
