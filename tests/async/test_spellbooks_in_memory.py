#!/usr/bin/env python3
"""The spellbooks are in memory on MariaDB: the game loop never queries them (step 8).

conjure listed the summoner's spellbook, and learning a minion checked it, on the game
loop; learning, removing and the first conjure's default minion wrote there. Only the game
writes the spellbooks, so every spellbook is read at boot and kept in memory, and each
change updates memory once its write is queued on the writer.
"""
from pathlib import Path
import re

from _source_contract import function_bodies

SRC = Path(__file__).resolve().parents[2] / "src"
text = (SRC / "sql/sql_player.c").read_text()
mariadb = text[text.index("// Every character's spellbook"):]
QUERY = re.compile(r"\b(qry|db_query|sql_run_query|mysql_query|mysql_store_result)\s*\(")
for name in ("sql_add_spellbook_mob", "sql_remove_spellbook_mob", "sql_has_spellbook_mob",
             "sql_get_spellbook_mobs"):
    body = function_bodies(mariadb, r"\b" + name + r"\s*\([^;{]*\)\s*(?=\{)")[0]
    assert not QUERY.search(body), f"{name} queries on the game loop"
for name in ("sql_add_spellbook_mob", "sql_remove_spellbook_mob"):
    body = function_bodies(mariadb, r"\b" + name + r"\s*\([^;{]*\)\s*(?=\{)")[0]
    assert body.index("sql_queue(") < body.index("spellbooks[pid]"), body
boot = function_bodies((SRC / "sql/sql.c").read_text(), r"\bint\s+initialize_mysql\s*\(\s*\)")[-1]
assert "sql_spellbooks_load()" in boot
print("[PASS] the spellbooks are read at boot and kept in memory; changes are queued")
