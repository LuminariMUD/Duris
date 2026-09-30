#!/usr/bin/env python3
"""Capture the flag leaves the game loop (persistence reset phase 2, step 8).

A capture or a reclaim used to insert its ctf_data row, and `ctf score` read the scores,
on the game thread's connection. The row is queued on the writer now, and the scores are
read there and shown on a later pulse. Only the boot load (ctf_populate_boons) queries.
"""
from _paths import SRC

source = (SRC / "ctf.c").read_text()
mysql = source[source.index("#else", source.index("#ifdef __NO_MYSQL__")):]

entry = mysql[mysql.index("int add_ctf_entry("):mysql.index("void show_ctf(")]
assert "sql_queue(" in entry and "INSERT INTO ctf_data" in entry, entry

score = mysql[mysql.index("void show_ctf_score("):mysql.index("void do_ctf(")]
assert "sql_read_for(ch, dbqry" in score, score

boot = mysql[mysql.index("void ctf_populate_boons()"):mysql.index("int ctf_use_boon(")]
runtime = mysql.replace(boot, "")
for forbidden in ("qry(", "mysql_store_result", "db_query"):
    assert forbidden not in runtime, f"capture the flag still queries the game loop: {forbidden}"

print("capture the flag writer contract passed")
