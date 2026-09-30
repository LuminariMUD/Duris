#!/usr/bin/env python3
"""The zones rows are in memory: the game loop never queries them (persistence step 8).

Every epic stone's periodic call asked the database for its zone's stone count, a touch
asked for the zone's alignment, `epic zones`, the boon and CTF zone lists read every epic
zone, `stat zone` and a new stone read the zone's row, and a no-reset zone's reset read and
wrote its reset chance, all on the game loop. The rows are now read at boot and kept in
memory: the reset chance changes there and is queued, and the alignments, last touches and
rarity, which a stone touch and the maintenance jobs change on other connections, are read
again on the writer after each. The game-loop queries journey runs `epic zones` and
`stat zone`.
"""
from pathlib import Path
import re

from _source_contract import function_bodies, strip_comments

SRC = Path(__file__).resolve().parents[2] / "src"
QUERY = re.compile(r"\b(qry|db_query|db_query_nolog|mysql_query|mysql_store_result)\s*\(")


def body(path, signature):
    bodies = function_bodies((SRC / path).read_text(), signature)
    assert bodies, signature
    return bodies[-1]


for path, name in (("world/epic.c", "epic_zone_done_now"),
                   ("world/epic.c", "get_epic_zone_alignment_mod"),
                   ("world/epic.c", "get_epic_zones"),
                   ("world/db.c", "no_reset_zone_reset"),
                   ("sql/sql.c", "get_zone_info"),
                   ("sql/sql.c", "sql_zones_refresh"),
                   ("sql/sql.c", "sql_set_zone_reset_perc")):
    text = body(path, r"\b" + name + r"\s*\([^;{]*\)\s*(?=\{)")
    assert not QUERY.search(text), f"{name} queries on the game loop"

refresh = body("sql/sql.c", r"\bvoid\s+sql_zones_refresh\s*\(\s*void\s*\)")
assert "sql_read(" in refresh and "reset_perc" not in refresh, refresh
reset = body("sql/sql.c", r"\bvoid\s+sql_set_zone_reset_perc\s*\([^)]*\)")
assert "zone->reset_perc = reset_perc" in reset and "sql_queue(" in reset, reset
assert "sql_zones()" in body("world/epic.c", r"\bvector<epic_zone_data>\s+get_epic_zones\s*\(")

boot = body("sql/sql.c", r"\bint\s+initialize_mysql\s*\(\s*\)")
assert "sql_load_zones();" in boot
assert "sql_load_zones();" in body("sql/sql.c", r"\bvoid\s+update_zone_db\s*\(\s*\)")

touch = body("world/epic.c", r"\bvoid\s+epic_publish_zone_touch\s*\(")
assert "sql_zones_refresh();" in touch and "sql_set_zone_reset_perc(" in touch
comm = strip_comments((SRC / "net/comm.c").read_text())
completions = comm[comm.index("static void maintenance_handle_completions"):]
completions = completions[:completions.index("\n}\n")]
refresh_site = completions[:completions.index("sql_zones_refresh();")]
assert "maintenance_job_id::epic_zone_balance" in refresh_site
assert "maintenance_job_id::epic_zone_modifiers" in refresh_site
print("[PASS] the zones rows are read at boot and kept in memory; the game loop never queries them")
