#!/usr/bin/env python3
"""Source contract for catalog-wide shopkeeper staging and publication."""

from _paths import SRC, rel, HARNESS_STUBS
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (SRC / "flatfile_shopkeeper_restore.c").read_text()

for token in (
    "flatfile_shopkeeper_list(root, &records, error)",
    "valid_shop_binding(record)",
    "shop_index[record.shop_id].keeper != mobile_rnum",
    "number_items_produced",
    "PLAYER_SNAPSHOT_NO_PARENT",
    "flatfile_shopkeeper_materialize(root, record",
    "staged.push_back(materialized)",
    "char_to_room(staged[index].character, staged[index].room_rnum, 0)",
    "staged[index].character->in_room != staged[index].room_rnum",
    "discard_staged(&staged, records)",
    "item_ownership_runtime_forget(item.object_uid)",
    "shop_trade_runtime_replace_revisions(records)",
    "replacements.find(existing) != replacements.end()",
    # The incumbents are the shop's live keepers (world_singletons_harness.cpp checks that
    # live_shopkeepers() names what singleton_shop_id() names).
    "live_shopkeepers(static_cast<int>(record.shop_id))",
    "shop_index[record.shop_id].dirty = 1",
):
    if token not in SOURCE:
        raise SystemExit(f"shopkeeper catalog restore contract is missing {token}")

stage = SOURCE.index("flatfile_shopkeeper_materialize(root, record")
place = SOURCE.index("char_to_room(staged[index].character")
replace = SOURCE.index("extract_char(incumbent)")
revisions = SOURCE.rindex("shop_trade_runtime_replace_revisions(records)")
if not stage < place < revisions < replace:
    raise SystemExit("shopkeepers are not fully staged and placed before incumbent replacement")

print("flat-file shopkeeper catalog restore contract passed")

# Execute the real metadata-only restore and real trade revision map together.
harness = r"""
#include "flatfile/flatfile_shopkeeper_restore.h"
#include "flatfile/flatfile_shopkeeper_materialize.h"
#include "economy/shop_trade_runtime.h"
#include "world/world_singletons.h"
#include "core/prototypes.h"
#include "core/structs.h"
#include <cassert>
#include <vector>
P_char character_list=nullptr;
index_data mobs[1]={}, objects[1]={}; P_index mob_index=mobs, obj_index=objects;
shop_data shops[1]={}; shop_data *shop_index=shops;
int number_of_shops=1, top_of_objt=0, top_of_world=0;
room_data rooms[1]={}; P_room world=rooms;
std::vector<flatfile_shopkeeper_record> records;
flatfile_shopkeeper_result listing=flatfile_shopkeeper_result::ok;
int body_calls=0;
int real_mobile(int vnum) { return vnum==2000 ? 0 : -1; }
int real_room(int vnum) { return vnum==2300 ? 0 : -1; }
flatfile_shopkeeper_result flatfile_shopkeeper_list(const std::string &,std::vector<flatfile_shopkeeper_record> *out,std::string *) { *out=records; return listing; }
flatfile_shopkeeper_materialize_result flatfile_shopkeeper_materialize(const std::string &,const flatfile_shopkeeper_record &,flatfile_materialized_shopkeeper *,player_load_item_materialize_metrics *,std::string *) { ++body_calls; assert(false); return flatfile_shopkeeper_materialize_result::invalid; }
void item_ownership_runtime_forget(uint64_t) { assert(false); }
void extract_char(P_char) { assert(false); }
bool char_to_room(P_char,int,int) { assert(false); return false; }
std::vector<P_char> live_shopkeepers(int) { assert(false); return {}; }
int main() {
 shops[0].keeper=0; shops[0].in_room=2300; mobs[0].virtual_number=2000; rooms[0].number=2300;
 uint64_t revision=0; assert(!shop_trade_runtime_revision(0,&revision));
 flatfile_shopkeeper_record record={}; record.shop_id=0; record.mob_vnum=2000; record.room_vnum=2300; record.revision=7;
 records={record}; std::string error;
 assert(flatfile_shopkeeper_restore_catalog("fixture",&error,false)==flatfile_shopkeeper_restore_result::ok);
 assert(shop_trade_runtime_revision(0,&revision) && revision==7 && shop_trade_runtime_can_advance(0,7,8));
 assert(body_calls==0 && !character_list);
 records.push_back(record);
 assert(flatfile_shopkeeper_restore_catalog("fixture",&error,false)==flatfile_shopkeeper_restore_result::invalid);
 assert(shop_trade_runtime_revision(0,&revision) && revision==7);
 records={record}; records[0].mob_vnum=999;
 assert(flatfile_shopkeeper_restore_catalog("fixture",&error,false)==flatfile_shopkeeper_restore_result::invalid);
 records={record}; records[0].revision=0;
 assert(flatfile_shopkeeper_restore_catalog("fixture",&error,false)==flatfile_shopkeeper_restore_result::io_error);
 assert(shop_trade_runtime_revision(0,&revision) && revision==7 && !body_calls);
}
"""
output=ROOT/"bin/tests"; output.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix="shop-revision-restore-",dir=output) as directory:
    source=Path(directory)/"restore.cpp"; binary=Path(directory)/"restore"
    source.write_text(harness)
    subprocess.run(["g++","-std=c++20","-Wall","-Wextra","-Werror","-Isrc",
        "-ffunction-sections","-fdata-sections","-fsanitize=address,undefined",
        str(source),rel("flatfile_shopkeeper_restore.c"),rel("shop_trade_runtime.c"),str(HARNESS_STUBS),
        "-Wl,--gc-sections","-o",str(binary)],cwd=ROOT,check=True)
    subprocess.run([str(binary)],cwd=ROOT,check=True,timeout=30)
print("native copyover loads validated shop revisions without replaying bodies")
