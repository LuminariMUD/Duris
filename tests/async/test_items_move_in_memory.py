#!/usr/bin/env python3
"""Items move in memory (step 4 of the persistence reset).

Commands move the object at once and the next save of each owner records where
it went. The economy, which still moves items through its own transactions until
Phase 2, takes what memory says a player, room, corpse, locker or pet holds: its
repositories claim the items instead of refusing a stale ownership record.
"""
from _paths import ROOT, SRC


def body(source: str, signature: str, last: bool = False) -> str:
    start = source.rindex(signature) if last else source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for end in range(brace, len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if depth == 0:
            return source[start:end + 1]
    raise AssertionError(signature)


ACTOBJ = (SRC / "actobj.c").read_text()
for name in ("item_movement_transaction_submit", "item_ownership_runtime",
             "item_command_uses_durable_ownership"):
    assert name not in ACTOBJ, name
print("[PASS] get, drop, give, put and empty move the object in memory")

HANDLER = (SRC / "handler.c").read_text()
to_char = body(HANDLER, "void obj_to_char(P_obj object, P_char ch)")
assert "item_ownership_runtime_lookup" not in to_char
assert "item_creation_grant_submit_to_player" not in to_char
print("[PASS] obj_to_char places an object without asking the ownership catalog")

# Every other command moves the object directly.
for name in ("rogues.c", "actmove.c", "actoth.c", "actwiz.c", "magic.c", "chaos_materials.c",
             "forced_weapon_drop.c", "salchemist.c", "drannak.c"):
    source = (SRC / name).read_text()
    assert "item_movement_transaction_submit" not in source, name
    assert "item_ownership_runtime_lookup" not in source or name == "magic.c", name
print("[PASS] slip, steal, soulbind, key break, storage, load, pouch, weapon drop and crafts "
      "move in memory")

AUCTION = (SRC / "auction_houses.c").read_text()
assert "ownership is still being synchronized" not in AUCTION
SHOP = (SRC / "shop_trade_runtime.c").read_text()
assert "const bool player_held = !creates && !shop_owned(action);" in SHOP
assert "!OBJ_CARRIED_BY(destination, player)" in SHOP
print("[PASS] auction listings and shop trades start from the object's real holder")

CLAIM = (SRC / "item_claim.h").read_text()
held = body(CLAIM, "inline bool item_claim_owner_is_memory_held(")
for owner in ("player", "room", "corpse", "locker", "pet"):
    assert f"item_owner_type::{owner}" in held, owner
for owner in ("auction", "shopkeeper", "collector", "system", "destruction"):
    assert f"item_owner_type::{owner}" not in held, owner
CLAIM_REPOSITORY = (SRC / "item_claim_repository.c").read_text()
claim = body(CLAIM_REPOSITORY, "unsigned int claim_transfer_item(")
assert "item_claim_leaves_out(" in claim
# The economy takes its items out of memory before its command, so a save or a transfer
# claims whatever its owner holds, the economy's records included.
assert "item_claim_owner_is_economy" not in (SRC / "item_claim.h").read_text()
assert "INSERT INTO item_owner_audit" in claim
TRANSFER = (SRC / "item_transfer_repository.c").read_text()
execute = body(TRANSFER, "bool item_transfer_repository_execute_at_offset(")
assert "payload.expected_from_revision = from_revision;" in execute
assert "payload.expected_to_revision = to_revision;" in execute
assert execute.count("claim_transfer_item(") == 2
assert "claim_transfer_item(" in (SRC / "auction_repository.c").read_text()
COLLECTOR = (SRC / "collector_repository.c").read_text()
# The owners' revisions, and the collected items' revisions, come from what is stored.
assert COLLECTOR.count("item_claim_owner_is_memory_held(payload.") == 3
FLAT = (SRC / "flatfile_item_repository.c").read_text()
flat_transfer = body(FLAT, "unsigned int apply_transfer(ownership_catalog *catalog,")
assert flat_transfer.count("claim_catalog_item(") == 2
assert "claim_catalog_item(" in body(
    FLAT, "flatfile_item_repository_result flatfile_item_repository_prepare_auction_transfer(")
collector = body(FLAT, "flatfile_item_repository_result flatfile_item_repository_prepare_collector_transfer(")
assert "claim_catalog_item(" not in collector
assert "item_claim_owner_is_memory_held(payload.from_owner.type)" in collector
RUNTIME = (SRC / "item_ownership_runtime.c").read_text()
assert "const bool memory_held = item_claim_owner_is_memory_held(payload.from_owner.type);" in RUNTIME
print("[PASS] item and auction transfers claim what memory holds and collector transfers "
      "stop fencing on memory owners, on both backends")

LOCKER = (SRC / "locker_async.c").read_text()
locker_job = body(LOCKER, "static player_save_apply_result locker_write_job(")
assert "write_locker(*job.snapshot)" in locker_job
write_locker = body(LOCKER, "static player_save_apply_result write_locker(")
assert "locker_snapshot_repository_apply_from_pool(snapshot)" in write_locker
# On flat-file the locker's items are claimed with its catalog record, as a corpse's are.
assert "flatfile_locker_snapshot_apply(root, save, &error)" in write_locker
FLAT_PLAYER = (SRC / "flatfile_player_repository.c").read_text()
assert "apply_world_snapshot(" in body(
    FLAT_PLAYER, "player_save_apply_result flatfile_locker_snapshot_apply(")
# The writer finds the locker, then deletes, claims and writes in one transaction.
REPOSITORY = (SRC / "player_snapshot_repository.c").read_text()
apply_locker = body(REPOSITORY, "player_save_apply_result apply_locker(MYSQL")
assert "apply_owner_write(" in apply_locker
assert apply_locker.index("find_locker(") < apply_locker.index("DELETE FROM locker_items") < \
    apply_locker.index("claim_graph(") < apply_locker.index("insert_item_rows(")
SQL_PLAYER = (SRC / "sql_player.c").read_text()
# A private chest's save is a writer job only; the writer's chest apply claims its items.
private_chest = body(SQL_PLAYER, "bool sql_save_private_chest_items(int locker_id, int chest_id, P_obj chest_obj)\n{", True)
assert "locker_chest_snapshot_repository_apply_from_pool" in private_chest
assert "DELETE FROM locker_items" not in private_chest and "claim_items(DB" not in private_chest
assert "bool sql_save_locker(" not in SQL_PLAYER
print("[PASS] locker and private chest saves go to the writer, which claims what the chest holds")

# A save claims a live coin pile like any item; a spent pile, like any destroyed
# item, stays destroyed and is left out, and a login loads the amount the save wrote,
# never an older custody amount.
leaves = body((SRC / "item_claim.c").read_text(), "bool item_claim_leaves_out(")
assert "return state == item_custody_state::destroyed;" in leaves and "ITEM_MONEY" not in leaves
assert "item_claim_leaves_owner_alone" not in (SRC / "item_claim_repository.c").read_text()
LOAD = (SRC / "player_load_repository.c").read_text()
assert "coin_payload" not in LOAD
FLAT_PLAYER = (SRC / "flatfile_player_repository.c").read_text()
assert "flatfile_shop_trade_materialization_prepare_player_remove(" in FLAT_PLAYER
MATERIALIZE = (SRC / "flatfile_shop_trade_materialization.c").read_text()
assert "coin_payload" not in MATERIALIZE
print("[PASS] saves claim live coin piles, never spent ones, and a login loads the saved amount")
print("[PASS] a flat-file save that carries every held item retires the transfers it replaces")

assert "tests/async/run_item_transfer_schema_mysql.sh" in (
    ROOT / "tests/run_db_tests.sh").read_text()
print("items move in memory contracts passed")
