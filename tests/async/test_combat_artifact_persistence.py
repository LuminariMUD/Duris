#!/usr/bin/env python3
"""Combat and artifact persistence-boundary source contracts."""

from _paths import SRC
from pathlib import Path

root = Path(__file__).resolve().parents[2]
fight_text = (SRC / "fight.c").read_text()
sql_text = (SRC / "sql.c").read_text()
sql_header = (SRC / "sql.h").read_text()
artifact_text = (SRC / "artifact.c").read_text()


def function(text: str, signature: str, next_signature: str) -> str:
    start = text.rfind(signature)
    assert start >= 0, signature
    end = text.find(next_signature, start)
    assert end >= 0, next_signature
    return text[start:end]


add_frags = function(fight_text, "void AddFrags(P_char ch, P_char victim)\n{", "unsigned int calculate_ch_state")
assert "submit_pvp_outcome(ch, victim, true)" in add_frags
for forbidden in ("sql_modify_frags", "redis_invalidate_fraglist", "ADD_MONEY", "epic_frag"):
    assert forbidden not in add_frags
assert "combat_outcome_transaction_submit(payload, combat_outcome_committed, &operation_id)" in fight_text
print("[PASS] combat mutations publish only through the transactional outcome command")

assert "bool sql_get_bind_data(int vnum, int *owner_pid, int *timer);" in sql_header
# On MariaDB the souls are held in memory with the artifacts (artifact.c): read there,
# changed there at once and queued on the writer, never queried on the game loop.
assert "artifact_bind WHERE vnum" not in sql_text and "INTO artifact_bind" not in sql_text
bind_lookup = function(
    artifact_text,
    "bool sql_get_bind_data(int vnum, int *owner_pid, int *timer)\n{",
    "void sql_update_bind_data",
)
bind_update = function(artifact_text, "void sql_update_bind_data", "#else")
store = function(artifact_text, "void artifact_bind_store(", "// Frees vnum's soul")
checks = {
    "reads memory": "artifact_binds.find(vnum)" in bind_lookup and "qry(" not in bind_lookup,
    "no soul yet is owner 0, timer 0": bind_lookup.count("? 0 :") == 2
    and "return true;" in bind_lookup,
    "update goes through the store": "artifact_bind_store(vnum, *owner_pid, *timer);" in bind_update,
    "store changes memory, then queues": store.index("artifact_binds[vnum] =")
    < store.index("sql_queue(")
    and "ON DUPLICATE KEY UPDATE" in store,
}
for label, passed in checks.items():
    print(f"[{'PASS' if passed else 'FAIL'}] bind data: {label}")
assert all(checks.values())

stub_start = sql_text.index("bool sql_get_bind_data(int vnum, int *owner_pid, int *timer)\n{")
stub_end = sql_text.index("bool sql_pwipe", stub_start)
stub = sql_text[stub_start:stub_end]
assert "*owner_pid = 0;" in stub
assert "*timer = 0;" in stub
assert "return false;" in stub
print("[PASS] no-MySQL bind lookup initializes outputs and reports failure")

assert artifact_text.count("if (!sql_get_bind_data(") == 2
for caller, next_caller in (
    ("void artifact_switch_check", "void artifact_update_sql"),
    ("void artifact_feed_sql", "void poof_artifact"),
):
    body = function(artifact_text, caller, next_caller)
    failure = body.index("if (!sql_get_bind_data(")
    failure_block = body[failure:body.index("}", failure) + 1]
    assert "return;" in failure_block or "continue;" in failure_block
print("[PASS] all artifact bind callers fail closed before ownership decisions")

# The repair names each artifact it rebinds, so the display copy leaves only once, after that.
fixit = function(artifact_text, "void arti_fixit_sql", "void arti_sync_sql")
fixit = fixit[fixit.index("#else"):]
assert fixit.count("extract_obj(") == 1
assert fixit.index("OBJ_SHORT(") < fixit.index("extract_obj(")
print("[PASS] the bind repair extracts each display copy once, after naming it")

print("combat and artifact persistence source contracts passed")
