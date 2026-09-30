#!/usr/bin/env python3
"""whois reads on the writer (persistence step 8).

whois queried a character's addresses, its last address and the names seen at an address
on the game loop. The two reads now run on the writer, behind the saves and log rows
queued before them, and print on a later pulse while the staff member is still in the
game. The game-loop queries journey runs whois by name and by address.
"""
from pathlib import Path
import re

from _source_contract import function_bodies

SRC = Path(__file__).resolve().parents[2] / "src"
text = (SRC / "cmd/actwiz.c").read_text()
QUERY = re.compile(r"\b(qry|db_query|mysql_query|mysql_store_result)\s*\(")
by_name = function_bodies(text, r"\bvoid\s+do_whois\s*\(")[0]
by_address = function_bodies(text, r"\bvoid\s+whois_ip\s*\(")[0]
assert "sql_read_work_for(" in by_name and "sql_read_for(" in by_address
for body in (by_name, by_address):
    assert not QUERY.search(body)
print("[PASS] whois reads on the writer")
