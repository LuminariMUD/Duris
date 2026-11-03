#!/usr/bin/env python3
"""Staff creation supplies account authority to the atomic first-save writer."""
from pathlib import Path
import re

from _source_contract import function_bodies

SRC = Path(__file__).resolve().parents[2] / "src"
body = function_bodies((SRC / "account/wiz_newchar.c").read_text(), r"\bvoid\s+do_newchar\s*\(")[0]
assert "creation_context.account = ch->desc->account" in body
assert "creation_context.character = newch" in body
capture = body.index("writeCharacter(newch")
assert body.index("newch->desc = &creation_context") < capture
assert capture < body.index("newch->desc = nullptr") < body.index("if (!saved)")
assert "INSERT INTO account_characters" not in body, "membership belongs to the initial save"
assert "find_char_in_list" in body and "add_char_to_account(&creation_context)" in body
assert not re.search(r"\b(db_query|qry|mysql_str)\s*\(", body), "newchar queries on the game loop"
print("[PASS] newchar captures account authority and reuses atomic initial membership")
