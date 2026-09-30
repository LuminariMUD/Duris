#!/usr/bin/env python3
"""newchar links its character to the account on the writer (persistence step 8).

newchar inserted the account_characters row on the game loop, with the pid passed to %ld
from an int. The row is now queued on the writer behind the character's first save,
format-checked, with the pid as %d and the names escaped.
"""
from pathlib import Path
import re

from _source_contract import function_bodies

SRC = Path(__file__).resolve().parents[2] / "src"
body = function_bodies((SRC / "account/wiz_newchar.c").read_text(), r"\bvoid\s+do_newchar\s*\(")[0]
link = body[body.index("INSERT INTO account_characters") - 200:]
link = link[:link.index("delete_character(newch")]
assert "sql_queue(" in link and "VALUES('%s', %d, '%s'" in link, link
assert link.count("escape_str(") == 2, link
assert not re.search(r"\b(db_query|qry|mysql_str)\s*\(", body), "newchar queries on the game loop"
print("[PASS] newchar queues the account link on the writer")
