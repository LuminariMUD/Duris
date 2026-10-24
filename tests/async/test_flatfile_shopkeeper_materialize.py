#!/usr/bin/env python3
"""Source contract for fail-closed detached shopkeeper materialization."""

from _paths import SRC, rel, HARNESS_STUBS
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HEADER = (SRC / "flatfile_shopkeeper_materialize.h").read_text()
SOURCE = (SRC / "flatfile_shopkeeper_materialize.c").read_text()

for token in (
    "real_mobile(record.mob_vnum)",
    "real_room(record.room_vnum)",
    "flatfile_shopkeeper_load_item_ownership(",
    "read_mobile(mobile_rnum, REAL)",
    "shop_index[record.shop_id].keeper != mobile_rnum",
    "GET_BIRTHPLACE(character) = record.room_vnum",
    "affect_to_char(character, &affect)",
    "player_load_item_graph_materialize_for_owner(",
    "flatfile_shopkeeper_item_owner(record.shop_id)",
    "owner_revision, true, true",
    "staged.release()",
    "*materialized = output",
):
    if token not in SOURCE:
        raise SystemExit(f"shopkeeper materializer contract is missing {token}")

if SOURCE.index("flatfile_shopkeeper_load_item_ownership(") > SOURCE.index(
    "read_mobile(mobile_rnum, REAL)"
):
    raise SystemExit("shopkeeper is allocated before authority reconciliation succeeds")
if SOURCE.index("player_load_item_graph_materialize_for_owner(") > SOURCE.index(
    "staged.release()"
):
    raise SystemExit("shopkeeper is released before item materialization succeeds")
if SOURCE.index("staged.release()") > SOURCE.index("*materialized = output"):
    raise SystemExit("shopkeeper output is published before staged ownership is released")
if "extract_char(character)" not in SOURCE or "~staged_shopkeeper()" not in SOURCE:
    raise SystemExit("shopkeeper materializer lacks failure cleanup")

for token in (
    "flatfile_shopkeeper_materialize_result",
    "flatfile_materialized_shopkeeper",
    "player_load_item_materialize_metrics *item_metrics",
):
    if token not in HEADER:
        raise SystemExit(f"shopkeeper materializer header is missing {token}")

print("flat-file detached shopkeeper materialization contract passed")

# Execute the real materializer with a legitimate table-bound keeper whose
# command procedure is a quest service, and reject mismatched identities.
harness = r'''
#include "flatfile/flatfile_shopkeeper_materialize.h"
#include "flatfile/flatfile_shopkeeper_ownership.h"
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include <cassert>
shop_data shops[1]{}; shop_data *shop_index = shops;
int number_of_shops = 1;
index_data mobs[1]{}; P_index mob_index = mobs;
char_data keeper{};
npc_only_data npc{};
int allocations = 0;
int quest_proc(P_char, P_char, int, char *) { return 0; }
int shop_keeper(P_char, P_char, int, char *) { return 0; }
int real_mobile(int vnum) { return vnum == 1000 ? 0 : -1; }
int real_room(int vnum) { return vnum == 2000 ? 0 : -1; }
P_char read_mobile(int, int) { ++allocations; return &keeper; }
void extract_char(P_char) { assert(false); }
affected_type *affect_to_char(P_char, affected_type *) { assert(false); return nullptr; }
void bind_shopkeeper(P_char ch, int shop) { assert(ch == &keeper && shop == 0); }
item_owner_identity flatfile_shopkeeper_item_owner(uint32_t id) {
    return {item_owner_type::shopkeeper, static_cast<uint64_t>(id) + 1, 0};
}
flatfile_shopkeeper_ownership_result flatfile_shopkeeper_load_item_ownership(
    const std::string &, const flatfile_shopkeeper_record &, uint64_t *revision,
    std::vector<player_load_item_identity> *, std::string *) {
    *revision = 1; return flatfile_shopkeeper_ownership_result::ok;
}
bool player_load_item_graph_materialize_for_owner(P_char ch,
    const std::vector<player_item_snapshot> &, const std::vector<player_load_item_identity> &,
    const item_owner_identity &, uint64_t revision, bool hydrate, bool complete,
    player_load_item_materialize_metrics *) {
    assert(ch == &keeper && revision == 1 && hydrate && complete); return true;
}
int main() {
    keeper.only.npc = &npc; keeper.specials.act = ACT_ISNPC;
    mobs[0].func.mob = quest_proc; shops[0].keeper = 0;
    assert(!IS_SHOPKEEPER(&keeper));
    flatfile_shopkeeper_record record{};
    record.mob_vnum = 1000; record.room_vnum = 2000; record.revision = 1;
    flatfile_materialized_shopkeeper output{};
    assert(flatfile_shopkeeper_materialize("fixture", record, &output, nullptr, nullptr) == flatfile_shopkeeper_materialize_result::ok);
    assert(output.character == &keeper && allocations == 1);
    record.shop_id = 1;
    assert(flatfile_shopkeeper_materialize("fixture", record, &output, nullptr, nullptr) == flatfile_shopkeeper_materialize_result::invalid);
    record.shop_id = 0; shops[0].keeper = 1;
    assert(flatfile_shopkeeper_materialize("fixture", record, &output, nullptr, nullptr) == flatfile_shopkeeper_materialize_result::invalid);
    assert(allocations == 1);
}
'''
with tempfile.TemporaryDirectory(prefix="shop-materialize-binding-") as directory:
    source = Path(directory) / "binding.cpp"
    binary = Path(directory) / "binding"
    source.write_text(harness)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Isrc",
        "-ffunction-sections", "-fdata-sections", "-fsanitize=address,undefined",
        str(source), rel("flatfile_shopkeeper_materialize.c"), str(HARNESS_STUBS),
        "-Wl,--gc-sections", "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True)
print("quest-procedure shopkeepers restore through their real table binding")
