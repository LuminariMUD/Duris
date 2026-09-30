#!/usr/bin/env python3
"""The polls are in memory on MariaDB: the game loop never queries them (step 8).

poll list, view, results, vote and close, and the websocket poll list, view and vote read
the polls, their options and every vote count on the game loop, and creating a poll,
voting and closing wrote there. Only the game writes the polls (the maintenance job closes
expired ones, which memory matches by their expiry), so they are read at boot and kept in
memory; a new poll takes its ids from memory, and every write is queued on the writer. The
game-loop queries journey creates a poll, votes, lists and closes it, and finds the rows
after shutdown.
"""
from pathlib import Path
import re

from _source_contract import function_bodies

SRC = Path(__file__).resolve().parents[2] / "src"
text = (SRC / "net/poll.c").read_text()
QUERY = re.compile(r"\b(qry|db_query|mysql_query|mysql_store_result|mysql_insert_id)\s*\(")

for name in ("poll_has_voted", "poll_get_all", "poll_get_by_id", "poll_create", "poll_close",
             "poll_record_votes"):
    body = function_bodies(text, r"\b" + name + r"\s*\([^;{]*\)\s*(?=\{)")[0]
    mariadb = body[body.index("#else"):] if "#else" in body else body
    assert not QUERY.search(mariadb), f"{name} queries on the game loop"
create = function_bodies(text, r"\bbool\s+poll_create\s*\(")[0]
assert "next_poll_id" in create and "sql_queue_statements(" in create
load = function_bodies(text, r"\bbool\s+polls_load\s*\(")[0]
assert QUERY.search(load), "the boot read loads the polls"
boot = function_bodies((SRC / "sql/sql.c").read_text(), r"\bint\s+initialize_mysql\s*\(\s*\)")[-1]
assert "polls_load()" in boot
print("[PASS] the polls are read at boot and kept in memory; their writes are queued")
