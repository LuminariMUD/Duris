#!/usr/bin/env python3
"""The hall of fame, the leader board and a hardcore death's killer leave the game loop.

hardcore and leaderboard queried player_data on the game loop, and a hardcore
character's final death wrote its killer there, with the killer's name unescaped. The
boards now read on the writer, behind the saves queued before them, and page on a later
pulse while the character is still in the game; the killer is escaped and queued in
capture order with the death's save. The game-loop queries journey runs both boards.
"""
from pathlib import Path
import re

from _source_contract import function_bodies, strip_comments

SRC = Path(__file__).resolve().parents[2] / "src"
QUERY = re.compile(r"\b(qry|db_query|mysql_query|mysql_store_result)\s*\(")
hardcore = (SRC / "world/hardcore.c").read_text()
for name in ("displayHardCore", "displayLeader"):
    body = function_bodies(hardcore, r"\bvoid\s+" + name + r"\s*\(")[0]
    assert "sql_read_for(" in body and not QUERY.search(body), name
fight = strip_comments((SRC / "combat/fight.c").read_text())
killer = fight[fight.index("death_record_killer"):]
killer = killer[:killer.index(";") + 1]
assert "sql_queue(" in killer and "escape_str(GET_NAME(killer))" in killer, killer
print("[PASS] the hardcore boards read on the writer and the killer write is queued")
