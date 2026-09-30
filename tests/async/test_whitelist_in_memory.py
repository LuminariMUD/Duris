#!/usr/bin/env python3
"""The multiplay whitelist is in memory on MariaDB (persistence step 8).

Every login that checked for multiplaying read the whole whitelist on the game loop, and
whitelist, whitelist add and whitelist remove read and wrote it there, with the staff
member's name, the player and the pattern unescaped. Only the game writes the whitelist,
so it is read at boot and kept in memory, and each change updates memory once its escaped
write is queued on the writer. The game-loop queries journey adds two entries, removes
one, lists the other and finds it stored after shutdown.
"""
from pathlib import Path
import re

from _source_contract import function_bodies

SRC = Path(__file__).resolve().parents[2] / "src"
text = (SRC / "account/multiplay_whitelist.c").read_text()
QUERY = re.compile(r"\b(qry|db_query|mysql_query|mysql_store_result|mysql_real_escape_string)\s*\(")
for name in ("get_whitelist", "add_to_whitelist", "remove_from_whitelist", "whitelisted_host"):
    body = function_bodies(text, r"\b" + name + r"\s*\([^;{]*\)\s*(?=\{)")[0]
    mariadb = body[body.index("#else"):] if "#else" in body else body
    assert not QUERY.search(mariadb), f"{name} queries on the game loop"
for name in ("add_to_whitelist", "remove_from_whitelist"):
    body = function_bodies(text, r"\b" + name + r"\s*\([^;{]*\)\s*(?=\{)")[0]
    mariadb = body[body.index("#else"):]
    assert "sql_queue(" in mariadb and "escape_str(" in mariadb, name
    assert mariadb.index("sql_queue(") < mariadb.index("stored_whitelist"), name
boot = function_bodies((SRC / "sql/sql.c").read_text(), r"\bint\s+initialize_mysql\s*\(\s*\)")[-1]
assert "whitelist_load()" in boot
print("[PASS] the multiplay whitelist is read at boot and kept in memory")
