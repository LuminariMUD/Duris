#!/usr/bin/env python3
"""`epic` and `epic trophy` read on the writer (persistence step 8).

The epic player list queried each side's top players on the game loop, and the trophy
queried the character's zone awards there. Both now read on the writer, behind the saves
queued before them, and print on a later pulse while the character is still in the game.
The unused modify_by_epic_trophy() went with the synchronous trophy read. The game-loop
queries journey runs both commands.
"""
from pathlib import Path
import re

from _source_contract import function_bodies, strip_comments

SRC = Path(__file__).resolve().parents[2] / "src"
epic = (SRC / "world/epic.c").read_text()
QUERY = re.compile(r"\b(qry|db_query|mysql_query|mysql_store_result)\s*\(")

listing = function_bodies(epic, r"\bvoid\s+do_epic\s*\(")[0]
assert "sql_read_work_for(" in listing and "show_epic_players" in listing
trophy = function_bodies(epic, r"\bvoid\s+do_epic_trophy\s*\(")[0]
assert "sql_read_for(" in trophy and "epic_zone_trophy(rows)" in trophy
for body in (listing, trophy):
    assert not QUERY.search(body)
code = strip_comments(epic) + strip_comments((SRC / "world/epic.h").read_text())
for gone in ("get_epic_players", "get_epic_zone_trophy", "modify_by_epic_trophy"):
    assert gone not in code, gone
print("[PASS] epic and epic trophy read on the writer")
