#!/usr/bin/env python3
"""The zone-story state is saved on the writer (persistence step 8).

Every zone-story change (a remembered character, a daily assignment, a completion, an
erase) wrote the whole state on the game loop. The state is already in memory, so the save
is now queued on the writer, in capture order with the saves; a save that cannot be
queued still rolls the change back. The stored state is read only at boot.
"""
from pathlib import Path
import re

from _source_contract import function_bodies

SRC = Path(__file__).resolve().parents[2] / "src"
text = (SRC / "sql/zone_story_quest_state_repository.c").read_text()
save = function_bodies(text, r"\bsql_zone_story_quest_state_save\s*\(")[0]
mariadb = save[save.index("#else"):]
assert "sql_queue_sized_work(" in mariadb and not re.search(r"\b(qry|db_query)\s*\(", mariadb), mariadb
# The writer escapes and formats the multi-megabyte document, not the game thread (#807).
assert "sql_escape_string" not in save and "mysql_real_escape_string(connection" in mariadb, save
runtime = (SRC / "world/zone_story_quest_runtime.c").read_text()
load_callers = [m.start() for m in re.finditer(r"\bpersisted_state_absent\s*\(|\bload_persisted_state\s*\(", runtime)]
boot = function_bodies(runtime, r"\bbool\s+bootstrap\s*\(")[0]
note = function_bodies(runtime, r"\bvoid\s+note_stored_state\s*\(")[0]
assert "persisted_state_absent(" in note and "load_persisted_state(" in boot
assert len(load_callers) == 4, "only the boot reads the stored state"
# A completion builds the shared document once, for its save; rollback must not (#807).
completion = function_bodies(runtime, r"\bbool\s+record_authoritative_completion\s*\(")[0]
assert "serialize_state" not in completion and "deserialize_state" not in completion, completion
save_state = function_bodies(runtime, r"\bbool\s+save_persisted_state\s*\(")[0]
sql_branch = save_state[save_state.index("capture_state"):]
assert "serialize_state" not in sql_branch, save_state
assert "undo_last_completion()" in completion, completion
feature = (SRC / "world/zone_story_quest_feature.c").read_text()
record = function_bodies(feature, r"\bresult\s+service::record_completion\s*\(")[0]
assert "serialize_state" not in record and "deserialize_state" not in record, record
print("[PASS] the zone-story state is saved on the writer and read only at boot")
