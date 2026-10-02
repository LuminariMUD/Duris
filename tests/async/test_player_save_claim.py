#!/usr/bin/env python3
"""Saves never refuse: a save claims what its owner holds (persistence reset step 2).

The flat-file leg runs here. The MariaDB leg, tests/async/run_player_save_claim_mysql.sh,
runs under `make test-db` because it needs Docker.
"""

import re
from _paths import SRC, rel
import pathlib
import subprocess
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
REPOSITORY = (SRC / "player_snapshot_repository.c").read_text()
CLAIM = (SRC / "item_claim_repository.c").read_text()
FLAT_PLAYER = (SRC / "flatfile_player_repository.c").read_text()
FLAT_ITEMS = (SRC / "flatfile_item_repository.c").read_text()
DATABASE_TESTS = (ROOT / "tests/run_db_tests.sh").read_text()

SOURCES = [
    "flatfile_player_repository.c", "player_load_topology.c", "flatfile_identity_repository.c",
    "flatfile_item_repository.c", "item_claim.c", "dupe_log.c", "flatfile_collector_repository.c",
    "collector_command.c", "collector_codec.c", "collector_policy.c",
    "flatfile_player_snapshot_file.c",
    "flatfile_locker_repository.c", "flatfile_world_item_repository.c",
    "flatfile_artifact_repository.c", "flatfile_shop_trade_repository.c",
    "flatfile_shop_trade_materialization.c", "flatfile_shopkeeper_repository.c",
    "flatfile_auction_repository.c", "flatfile_boon_repository.c",
    "flatfile_player_domain_repository.c", "flatfile_authority_transaction.c",
    "player_snapshot_codec.c", "flatfile_store.c", "item_transfer_command.c",
    "shop_trade_command.c", "critical_command.c",
    "epic_command.c", "currency_command.c", "auction_command.c", "combat_outcome_command.c",
    "boon_reward_command.c", "boon_shop_command.c", "persistence_observability.c",
    "persistence_mode.c", "flatfile_ip_activity_repository.c",
]

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="flat-claim-test-", dir=ROOT / "bin/tests") as temporary:
    work = pathlib.Path(temporary)
    binary = work / "flatfile_player_save_claim"
    built = subprocess.run(
        ["g++", "-std=c++20", "-Wall", "-Wextra", "-Wpedantic", "-Werror", "-D__NO_MYSQL__",
         "-Isrc", "-Isrc/no_mysql", "tests/async/flatfile_player_save_claim_harness.cpp",
         *[rel(name) for name in SOURCES], "-lcrypto", "-pthread", "-o", str(binary)],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if built.returncode:
        raise SystemExit(built.stdout)
    subprocess.run([str(binary), str(work / "root")], check=True, timeout=120)
print("[PASS] flat-file saves claim what the player and its pets hold, in one transaction")
print("[PASS] the auction keeps what it holds; the dupe and claim logs name each item")
print("[PASS] a destroyed item stays destroyed and is left out of a save captured before")
print("[PASS] a flat-file load skips what another owner holds and logs it")

# One claim helper for every item graph; the custody checks that refused saves are gone.
for retired in ("verify_player_item_custody", "verify_player_death_item_payload",
                "verify_pet_custody", "PLAYER_SAVE_ERROR_CUSTODY_PAYLOAD_MISMATCH",
                "read_durable_revision"):
    assert retired not in REPOSITORY, retired
assert REPOSITORY.count("claim_items(connection, owner, items, &claim.outcome)") == 1
assert "claim_graph(connection, owner, snapshot.items, claims, &written)" in REPOSITORY
assert "claim_graph(connection, owner, pet.items, claims, &written)" in REPOSITORY
assert "INSERT INTO item_owner_audit" in CLAIM
assert "flatfile_item_repository_prepare_claim(" in FLAT_PLAYER
assert "item_claim_leaves_out(record->state)" in FLAT_ITEMS
assert "establish_item_baseline" not in FLAT_PLAYER
assert "replay_fence" not in REPOSITORY and "legacy_replay" not in FLAT_PLAYER
assert "ensure_player_row(connection, snapshot, &created)" in REPOSITORY
# A new character's first save goes through the writer: the row it creates gets the
# opening baselines the accounting ledgers start from, and nanny no longer forces a
# synchronous first save on MariaDB.
assert "if (query.ok && created)\n\t\tquery = insert_opening_baselines(connection, snapshot.pid);" in REPOSITORY
NANNY = (SRC / "nanny.c").read_text()
new_player = NANNY[NANNY.index("ch->only.pc->pid = getNewPCidNumb();"):]
new_player = new_player[:new_player.index("SET_BIT(ch->runtime_flags, CHAR_RFLAG_NO_DB_BASELINE);")]
assert new_player.rstrip().endswith("#ifdef __NO_MYSQL__") or "#ifdef __NO_MYSQL__" in new_player.split("sql_player_names_set")[1]
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
assert "player_save_apply_outcome::terminal_failure, 0, query.error_code" in work
print("[PASS] a bank delta is written once: in a transaction, never retried after an unknown commit")

LOAD_REPOSITORY = (SRC / "player_load_repository.c").read_text()
SQL = (SRC / "sql.c").read_text()
# Loads take a row only when the ownership table has no row for it or names the
# loading owner; any other owner's row is skipped and logged, in every loader.
assert re.search(r'dupe_log_item\(\s*"load_skipped"', LOAD_REPOSITORY)
assert 'dupe_log_item("load_skipped"' in FLAT_PLAYER
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
