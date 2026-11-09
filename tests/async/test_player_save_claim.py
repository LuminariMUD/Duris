#!/usr/bin/env python3
"""Saves never refuse: a save claims what its owner holds (persistence reset step 2).

The MariaDB leg, tests/async/run_player_save_claim_mysql.sh, runs under `make test-db`
because it needs Docker.
"""

import re
from _paths import SRC
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[2]
REPOSITORY = (SRC / "player_snapshot_repository.c").read_text()
CLAIM = (SRC / "item_claim_repository.c").read_text()
DATABASE_TESTS = (ROOT / "tests/run_db_tests.sh").read_text()

# One claim helper for every item graph; the custody checks that refused saves are gone.
for retired in ("verify_player_item_custody", "verify_player_death_item_payload",
                "verify_pet_custody", "PLAYER_SAVE_ERROR_CUSTODY_PAYLOAD_MISMATCH",
                "read_durable_revision"):
    assert retired not in REPOSITORY, retired
assert REPOSITORY.count("claim_items(connection, owner, items, &claim.outcome)") == 1
assert "claim_graph(connection, owner, snapshot.items, claims, &written)" in REPOSITORY
assert "claim_graph(connection, owner, pet.items, claims, &written)" in REPOSITORY
assert "INSERT INTO item_owner_audit" in CLAIM
assert "replay_fence" not in REPOSITORY
assert "query = ensure_player_row(connection, snapshot, &created," in REPOSITORY
# A new character's first save goes through the writer: the row it creates gets the
# opening baselines the accounting ledgers start from, and nanny no longer forces a
# synchronous first save on MariaDB.
assert "if (query.ok && created)\n\t\tquery = insert_opening_baselines(connection, snapshot.pid);" in REPOSITORY
NANNY = (SRC / "nanny.c").read_text()
assert "CHAR_RFLAG_NO_DB_BASELINE" not in NANNY
print("[PASS] custody checks and the revision fence are gone; a missing row is created")

PIPELINE = (SRC / "player_save_pipeline.c").read_text()
CAPTURE = (SRC / "player_snapshot_capture.c").read_text()
# Equipment and inventory are one item graph: a save always writes both halves.
mark = PIPELINE[PIPELINE.index("bool player_save_pipeline_mark("):]
mark = mark[: mark.index("\n}\n")]
assert "components |= PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY;" in mark
# A failed save is not recaptured in a loop: it is reported once and the owner is
# marked dirty for its next checkpoint.
assert "custody_recapture_armed" not in PIPELINE
assert "custody-mismatch-recapture" not in PIPELINE
assert "player_save_pipeline_mark(completion.pid, completion.components)" in PIPELINE
# A lossy NORENT flag cannot drop an item the ownership record gives the player.
capture_tree = CAPTURE[CAPTURE.index("capture_item_tree("):]
assert "active_durable_custody" in capture_tree and "durable_norent_included" in capture_tree
print("[PASS] item graphs are saved whole, and a failed save is not recaptured in a loop")

# A bank delta is written in a transaction: a lost connection before the commit is
# retried safely, and a commit whose outcome is unknown is reported, never retried.
bank = REPOSITORY[REPOSITORY.index("player_save_apply_result apply_bank_delta("):]
bank = bank[:bank.index("\n}\n")]
assert "return apply_sql_work(connection," in bank
work = REPOSITORY[REPOSITORY.index("player_save_apply_result apply_sql_work("):]
work = work[:work.index("\n}\n")]
assert "if (connection_error(query.error_code))" in work
assert "bool retry_ambiguous_commit = false" in work
assert "retry_ambiguous_commit ? player_save_apply_outcome::ambiguous_commit" in work
assert "player_save_apply_outcome::terminal_failure" in work
print("[PASS] a bank delta is written once: in a transaction, never retried after an unknown commit")

LOAD_REPOSITORY = (SRC / "player_load_repository.c").read_text()
SQL = (SRC / "sql.c").read_text()
# Loads take a row only when the ownership table has no row for it or names the
# loading owner; any other owner's row is skipped and logged, in every loader.
assert re.search(r'dupe_log_item\(\s*"load_skipped"', LOAD_REPOSITORY)
assert 'dupe_log_item("load_skipped", item_uid, entry.vnum, expected, entry.owner)' in SQL
RUNNER = (ROOT / "tests/async/run_player_save_claim_mysql.sh").read_text()
assert "player_load_filter_mysql_harness" in RUNNER
# A skipped container never takes the rest of the graph with it: in the corpse,
# locker and saved-item loaders what it contains moves up a level.
SQL_PLAYER = (SRC / "sql_player.c").read_text()
assert SQL_PLAYER.count("if (container_map[i] != -1)") == 2
assert "if (container_map[i] == 0)\n\t\t\t{" not in SQL_PLAYER
locker = SQL_PLAYER[SQL_PLAYER.index("static P_obj locker_items_from_index("):]
locker = locker[: locker.index("\n}\n")]
assert "append_loaded_objects(&first_obj, &last_obj, orphans);" in locker
assert "obj_to_obj(orphans, chest_obj)" in locker
room = SQL_PLAYER[SQL_PLAYER.index("static P_obj sql_load_saved_item_contents("):]
room = room[: room.index("\n}\n")]
assert "append_loaded_objects(&first_obj, &last_obj,\n" in room
owner_check = room[room.index("sql_persistence_item_owner_matches(obj->obj_uid"):]
assert "*valid = false" not in owner_check[: owner_check.index("continue;")]
print("[PASS] player, pet, corpse, locker and saved-item loads use the same filter")

assert "tests/async/run_player_save_claim_mysql.sh" in DATABASE_TESTS
# Every leg that links the player loader runs there too, so a loader change
# cannot leave one of them unbuildable again.
for leg in ("run_experience_trophy_mysql.sh", "run_output_preferences_mysql.sh"):
    assert "tests/async/" + leg in DATABASE_TESTS, leg
print("[PASS] the MariaDB claim and loader legs run under make test-db")
print("player save claim contracts passed")
