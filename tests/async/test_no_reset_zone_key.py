#!/usr/bin/env python3
"""A no-reset zone's reset chance is kept on its own zones row.

no_reset_zone_reset() receives the zone's index in zone_table and looked its row up with
`WHERE id = <index>`. The zones row's id is its insertion order, not that index, so it read
and raised another zone's reset chance, while a stone touch sets the chance on the row of
the zone's number. The chance is now kept by the zone's number, as the touch keeps it.
"""
from pathlib import Path
import re

from _source_contract import function_bodies

SRC = Path(__file__).resolve().parents[2] / "src"
body = function_bodies((SRC / "world/db.c").read_text(),
                       r"\bvoid\s+no_reset_zone_reset\s*\(")[0]
assert not re.search(r"WHERE id\b", body), "no_reset_zone_reset keys zones by id"
assert body.count("zone_table[zone_number].number") >= 3, body
print("[PASS] a no-reset zone's reset chance is read and written by its zone number")
