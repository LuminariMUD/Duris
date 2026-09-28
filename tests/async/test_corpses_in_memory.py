#!/usr/bin/env python3
"""Corpses in memory (step 6 of the persistence reset).

A raise, resurrection, release, unmaking, wall of bones, compaction or destruction
runs the in-memory code that follows each deferral. writeCorpse(), the purge of a
corpse leaving the world and writeSavedItem() queue a job on the one writer, so an
older save of a player cannot claim the items back after them; the job claims what
the corpse or the room holds, on both backends.
"""
from _paths import SRC


def body(source: str, signature: str) -> str:
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for end in range(brace, len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if depth == 0:
            return source[start:end + 1]
    raise AssertionError(signature)


HANDLER = (SRC / "handler.c").read_text()
assert "return false;" in body(HANDLER, "bool durable_corpse_lifecycle_enabled()")
for name in ("raise", "resurrection", "room_release", "unmaking", "wall_of_bones", "compaction",
             "destruction"):
    deferral = body(HANDLER, f"bool persistence_defer_corpse_{name}(")
    assert "durable_corpse_lifecycle_enabled()" in deferral, name
print("[PASS] every corpse deferral falls through to its in-memory code")

FILES = (SRC / "files.c").read_text()
queue = body(FILES, "bool queue_corpse_save(P_obj corpse, bool remove)")
assert "persistence_job_kind::corpse" in queue
assert "corpse_snapshot_repository_apply_from_pool" in queue
assert "flatfile_corpse_snapshot_apply" in queue
write = body(FILES, "void writeCorpse(P_obj corpse)")
assert write.count("queue_corpse_save(corpse,") == 3
assert "stage_corpse_lifecycle" not in FILES
purge = body(FILES, "void PurgeCorpseFile(P_obj corpse)")
assert purge.count("queue_corpse_save(corpse, true)") == 2
saved = body(FILES, "static bool queue_saved_item_save(")
assert "persistence_job_kind::saved_item" in saved
assert "saved_item_snapshot_repository_apply_from_pool" in saved
assert "flatfile_saved_item_snapshot_apply" in saved
assert body(FILES, "void writeSavedItem(P_obj item)").count("queue_saved_item_save(") == 2
print("[PASS] corpse and saved-item saves and deletes go to the one writer on both backends")

REPOSITORY = (SRC / "player_snapshot_repository.c").read_text()
corpse = body(REPOSITORY, "query_result write_corpse(")
assert corpse.index("DELETE FROM corpses") < corpse.index("claim_graph(") < corpse.index(
    "corpse_item_tables")
saved_item = body(REPOSITORY, "query_result write_saved_item(")
assert saved_item.index("claim_graph(") < saved_item.index("saved_item_tables")
FLAT_PLAYER = (SRC / "flatfile_player_repository.c").read_text()
world = body(FLAT_PLAYER, "player_save_apply_result apply_world_snapshot(")
assert world.index("flatfile_item_repository_prepare_claim(") < world.index("prepare(authority")
assert "flatfile_authority_transaction_commit_operations" in world
WORLD = (SRC / "flatfile_world_item_repository.c").read_text()
assert "strip_everywhere(&catalog, corpse.items);" in WORLD
assert "strip_everywhere(&catalog, items);" in WORLD
OWNERSHIP = (SRC / "flatfile_corpse_ownership.c").read_text()
world_filter = body(OWNERSHIP, "flatfile_world_filter_item_ownership(")
assert '"load_skipped"' in world_filter and "items.size() != custody.size()" not in OWNERSHIP
print("[PASS] the jobs claim the items for the corpse or the room in the write's transaction")
print("[PASS] a flat-file corpse or room load skips what another owner holds and logs it")
print("corpses in memory contracts passed")
