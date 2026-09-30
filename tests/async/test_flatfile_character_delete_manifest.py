#!/usr/bin/env python3
"""Validate the character-delete disposition inventory and runtime fence."""

from _paths import SRC
import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "tests/async/flatfile_character_delete_manifest.json"

required_ids = {
    "identity",
    "account_membership",
    "player_snapshot",
    "player_domain",
    "item_custody",
    "boons",
    "recipes",
    "spellbook",
    "offline_messages",
    "auctions",
    "artifacts",
    "locker_access",
    "association_membership",
    "frag_leaderboard",
    "locker_contents",
    "ships_and_cargo",
    "corpses_and_saved_items",
    "account_bound_summons",
    "shop_trade_materializations",
    "historical_operation_ledgers",
}
allowed_dispositions = {
    "prepared_tombstone",
    "prepared_remove",
    "prepared_rewrite",
    "checked_empty",
    "covered_by_identity",
    "retain_history",
    "unimplemented",
}
manifest = json.loads(MANIFEST.read_text())
if manifest.get("schema_version") != 1:
    raise SystemExit("unsupported character-delete manifest version")
entries = manifest.get("entries")
if not isinstance(entries, list):
    raise SystemExit("character-delete manifest entries are missing")
entry_ids = [entry.get("id") for entry in entries]
if len(entry_ids) != len(set(entry_ids)):
    raise SystemExit("character-delete manifest contains duplicate IDs")
if set(entry_ids) != required_ids:
    missing = sorted(required_ids - set(entry_ids))
    extra = sorted(set(entry_ids) - required_ids)
    raise SystemExit(f"character-delete manifest coverage drift: missing={missing} extra={extra}")

for entry in entries:
    if entry.get("disposition") not in allowed_dispositions:
        raise SystemExit(f"invalid disposition for {entry['id']}")
    evidence = entry.get("evidence", {})
    relative = pathlib.PurePosixPath(evidence.get("path", ""))
    if relative.is_absolute() or ".." in relative.parts:
        raise SystemExit(f"unsafe evidence path for {entry['id']}")
    path = ROOT / relative
    token = evidence.get("token")
    if not path.is_file() or not isinstance(token, str) or not token or token not in path.read_text():
        raise SystemExit(f"stale evidence for {entry['id']}")

blockers = {entry["id"] for entry in entries if entry["disposition"] == "unimplemented"}
if blockers and manifest.get("runtime_exposure") != "fenced":
    raise SystemExit("incomplete character deletion is not fenced")
if not blockers and manifest.get("runtime_exposure") not in {"fenced", "enabled"}:
    raise SystemExit("complete character deletion has an invalid exposure state")

files_source = (SRC / "files.c").read_text()
forget_start = files_source.index("character_delete_result forget_deleted_character(")
forget_body = files_source[forget_start : files_source.index("\n}\n", forget_start)]
start = files_source.index("void delete_character(P_char ch, bool delete_locker,")
end = files_source.index("void PurgeCorpseFile", start)
delete_body = files_source[start:end]
# MariaDB: one writer job runs every statement in one transaction; memory lets go of
# the character only once it commits.
runtime_calls = [
    "UPDATE account_characters SET deleted_at = NOW()",
    "UPDATE frag_leaderboard SET deleted_at = NOW()",
    "remove_all_locker_access_statement(deleted.name.c_str())",
    "remove_all_artifacts_sql(deleted.pid)",
    "GET_ASSOC(ch)->statements_without_member(ch)",
    "sql_delete_locker_statement(deleted.pid, 0)",
    "sql_delete_ship_statement(deleted.name.c_str())",
    "DELETE FROM player_data WHERE pid=%d",
    "sql_read_work(",
    "sql_delete_ship(deleted.name.c_str())",
    "done(forget_deleted_character(deleted));",
]
forget_calls = [
    "player_revision_forget(deleted.pid)",
    "sql_player_names_forget(deleted.pid)",
    "artifacts_forget_deleted_character(deleted.pid)",
    "guild->forget_deleted_member(deleted.name.c_str(), deleted.frags)",
    "remove_char_from_list(d->account, deleted.name.c_str(), false)",
    "delete_ship_runtime(deleted.name.c_str())",
]
positions = [delete_body.find(call, delete_body.find("#else")) for call in runtime_calls]
forget_positions = [forget_body.find(call) for call in forget_calls]
if any(position < 0 for position in positions + forget_positions) or \
        positions != sorted(positions) or forget_positions != sorted(forget_positions):
    raise SystemExit("live character-delete call graph drifted from the manifest")
exposure = manifest.get("runtime_exposure")
if exposure == "fenced" and "flatfile_character_delete" in delete_body:
    raise SystemExit("fenced flat character deletion was exposed through the live route")
if exposure == "enabled":
    route_tokens = [
        "#ifdef __NO_MYSQL__",
        "!delete_locker",
        "flatfile_character_delete(persistence_mode_flatfile_root()",
        "done(forget_deleted_character(deleted));",
        "#else",
    ]
    route_positions = [delete_body.find(token) for token in route_tokens]
    if any(position < 0 for position in route_positions) or route_positions != sorted(route_positions):
        raise SystemExit("enabled flat character deletion route is incomplete or misordered")
    if route_positions[2] > positions[0]:
        raise SystemExit("flat character deletion does not bypass the legacy SQL mutations")

coordinator = (SRC / "flatfile_character_delete.c").read_text()
prepared_order = [
    "flatfile_account_reward_summon_prepare_player_remove",
    "flatfile_world_item_prepare_player_remove",
    "flatfile_artifact_prepare_player_release",
    "flatfile_frag_leaderboard_prepare_tombstone",
    "flatfile_locker_prepare_player_remove",
    "flatfile_association_prepare_player_remove",
    "flatfile_ship_prepare_player_remove",
    "flatfile_player_snapshot_prepare_remove",
    "flatfile_player_domain_prepare_remove",
    "flatfile_item_repository_prepare_player_and_custody_remove",
    "append_operation(&operations, &locker_removal.operation)",
    "append_operation(&operations, &world_item_removal.operation)",
    "flatfile_shop_trade_materialization_prepare_player_remove",
    "flatfile_boon_prepare_player_remove",
    "flatfile_recipe_prepare_clear",
    "flatfile_spellbook_prepare_clear",
    "flatfile_offline_message_prepare_remove",
    "append_operation(&operations, &identity_operation)",
]
positions = [coordinator.find(token) for token in prepared_order]
if any(position < 0 for position in positions) or positions != sorted(positions):
    raise SystemExit("core delete operation order drifted or identity is not success-last")

print(f"flat-file character-delete manifest passed with {len(blockers)} runtime blockers")
