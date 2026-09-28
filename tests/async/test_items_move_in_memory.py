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


POLICY = (SRC / "item_command_policy.c").read_text()
policy = body(POLICY, "bool item_command_uses_durable_ownership(")
assert "return false;" in policy and "item_ownership_runtime_lookup" not in policy
print("[PASS] get, drop, give, put and empty take their in-memory branches")

HANDLER = (SRC / "handler.c").read_text()
to_char = body(HANDLER, "void obj_to_char(P_obj object, P_char ch)")
assert "item_ownership_runtime_lookup" not in to_char
assert "item_creation_grant_submit_to_player" not in to_char
print("[PASS] obj_to_char places an object without asking the ownership catalog")

# Every other command moves the object directly.
for name in ("rogues.c", "actmove.c", "actoth.c", "actwiz.c", "magic.c", "chaos_materials.c",
             "forced_weapon_drop.c"):
    source = (SRC / name).read_text()
    assert "item_movement_transaction_submit" not in source, name
    assert "item_ownership_runtime_lookup" not in source or name == "magic.c", name
MOVEMENT = (SRC / "item_movement_transaction.c").read_text()
craft = body(MOVEMENT, "bool item_movement_transaction_submit_craft(")
assert "critical_command_coordinator" not in craft and "pending" not in craft
assert "extract_obj(inputs[index])" in craft and "obj_to_char(outputs[index], actor)" in craft
assert craft.index("obj_to_char(outputs[index], actor)") < craft.index("completion(actor, true")
print("[PASS] slip, steal, soulbind, key break, storage, load, pouch, weapon drop and crafts "
      "move in memory")

GET_POLICY = (SRC / "item_get_policy.c").read_text()
assert "item_ownership_runtime" not in GET_POLICY
source_owner = body(GET_POLICY, "bool item_get_source_owner(")
assert "live_placement_owner(actor, object, container, source)" in source_owner
AUCTION = (SRC / "auction_houses.c").read_text()
assert "ownership is still being synchronized" not in AUCTION
SHOP = (SRC / "shop_trade_runtime.c").read_text()
assert "const bool player_held = !creates && !shop_owned(action);" in SHOP
assert "!OBJ_CARRIED_BY(destination, player)" in SHOP
print("[PASS] coin gets, auction listings and shop trades start from the object's real holder")

CLAIM = (SRC / "item_claim.h").read_text()
held = body(CLAIM, "inline bool item_claim_owner_is_memory_held(")
for owner in ("player", "room", "corpse", "locker", "pet"):
    assert f"item_owner_type::{owner}" in held, owner
for owner in ("auction", "shopkeeper", "collector", "system", "destruction"):
    assert f"item_owner_type::{owner}" not in held, owner
CLAIM_REPOSITORY = (SRC / "item_claim_repository.c").read_text()
claim = body(CLAIM_REPOSITORY, "unsigned int claim_transfer_item(")
assert "item_custody_state::destroyed" in claim and "item_claim_owner_is_economy" in claim
assert "INSERT INTO item_owner_audit" in claim
TRANSFER = (SRC / "item_transfer_repository.c").read_text()
execute = body(TRANSFER, "bool item_transfer_repository_execute_at_offset(")
assert "payload.expected_from_revision = from_revision;" in execute
assert "payload.expected_to_revision = to_revision;" in execute
assert execute.count("claim_transfer_item(") == 2
assert "claim_transfer_item(" in (SRC / "auction_repository.c").read_text()
COLLECTOR = (SRC / "collector_repository.c").read_text()
assert COLLECTOR.count("item_claim_owner_is_memory_held(payload.") == 2
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
assert locker_job.index("START TRANSACTION") < locker_job.index("claim_items(") < \
    locker_job.index("apply_sql_script(")
assert "START TRANSACTION" not in body(LOCKER, "static char *build_locker_snapshot_sql(")
SQL_PLAYER = (SRC / "sql_player.c").read_text()
for signature in ("bool sql_save_locker(P_char locker_ch, int owner_pid, int owner_assoc_id)\n{",
                  "bool sql_save_private_chest_items(int locker_id, int chest_id, P_obj chest_obj)\n{"):
    assert "claim_items(DB, chest, held, &claim)" in body(SQL_PLAYER, signature, True), signature
print("[PASS] locker and private chest saves claim what the chest holds")

# A save claims a live coin pile like any item; a spent pile stays spent, and a
# player loads only the piles his own save lists.
leaves = body((SRC / "item_claim.c").read_text(), "bool item_claim_leaves_owner_alone(")
assert "item.type == ITEM_MONEY && recorded == item_custody_state::destroyed" in leaves
LOAD = (SRC / "player_load_repository.c").read_text()
assert "held.pid=\" +" in LOAD and "held.obj_uid=own.item_uid" in LOAD
FLAT_PLAYER = (SRC / "flatfile_player_repository.c").read_text()
assert "flatfile_shop_trade_materialization_prepare_player_remove(" in FLAT_PLAYER
MATERIALIZE = (SRC / "flatfile_shop_trade_materialization.c").read_text()
assert "!record.coin_payload.empty() && held.contains(record.item_uid)" in MATERIALIZE
print("[PASS] saves claim live coin piles, never spent ones, and a login loads only its own piles")
print("[PASS] a flat-file save that carries every held item retires the transfers it replaces")

MAKEFILE = (ROOT / "Makefile").read_text()
assert "tests/async/run_item_transfer_schema_mysql.sh" in MAKEFILE
print("items move in memory contracts passed")
