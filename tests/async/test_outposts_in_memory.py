#!/usr/bin/env python3
"""The outposts are in memory on MariaDB: the game loop never queries them (step 8).

Every outpost read (the owner, hit points, golems, archers, the outpost list) selected all
three rows on the game loop, and every change (a new owner, hit points after a fight or a
repair, the portal, golems, archers, the meurtriere, a reset, test clearoutposts) updated
them there. Only the game writes the outposts, so they are read at boot and kept in
memory, and each change updates memory once its write is queued on the writer. Both
backends now change a record the same way: load it, change it, save it.
"""
from pathlib import Path
import re

from _source_contract import function_bodies, strip_comments

SRC = Path(__file__).resolve().parents[2] / "src"
text = (SRC / "world/outposts.c").read_text()
code = strip_comments(text)
QUERY = re.compile(r"\b(qry|db_query|mysql_query|mysql_store_result)\s*\(")

load = function_bodies(text, r"\bbool\s+load_outpost_records\s*\(")[0]
mariadb = load[load.index("#else"):]
boot = mariadb[mariadb.index("if (establish)"):mariadb.index("*records = stored_outposts;")]
assert QUERY.search(boot) and not QUERY.search(mariadb.replace(boot, "")), mariadb

saves = function_bodies(text, r"\bbool\s+save_outpost_record\s*\(")
assert len(saves) == 2, "each backend has its save"
queued = saves[1]
assert queued.index("sql_queue(") < queued.index("stored = record;"), queued

# Outside the boot read, only the resource functions nothing calls still query.
rest = code.replace(strip_comments(load), "")
for dead in ("get_guild_resources", "outpost_update_resources"):
    rest = rest.replace(strip_comments(function_bodies(text, r"\b" + dead + r"\s*\([^;{]*\)")[0]), "")
assert not QUERY.search(rest), QUERY.search(rest)
assert "UPDATE outposts" not in strip_comments((SRC / "cmd/testcmd.c").read_text())
assert "clear_outposts()" in (SRC / "cmd/testcmd.c").read_text()
print("[PASS] the outposts are read at boot and kept in memory; changes are queued")
