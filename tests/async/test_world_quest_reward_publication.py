#!/usr/bin/env python3
"""Exercise the production committed-reward publication boundary under ASan/UBSan."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, source, extract_function

sql = source("sql/sql.c").read_text()
start = sql.index("struct world_quest_reward_publication\n")
end = sql.index("// End world quest reward publication.", start)
production = (
    extract_function('gmcp.c', 'static void gmcp_items_reset(P_desc d)\n{') + '\n' +
    extract_function('gmcp.c', 'void gmcp_items_changed(P_char ch)\n{') + '\n' +
    sql[start:end]
)
prelude = r'''
#include "core/prototypes.h"
#include "net/gmcp.h"
#include "core/utils.h"
#include "item/item_ownership_runtime.h"
#include "player/player_load_items.h"
#include "sql/sql_async.h"
#include <algorithm>
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <memory>
#include <string>
#include <vector>

P_obj object_list = nullptr;
static std::function<void(bool, const sql_rows &)> read_done;
static std::string last_query;
static bool accept_read = true, throw_read = false, allow_hydration = true, allow_restore = false;
static int hydrations = 0, attachments = 0, extractions = 0, restores = 0;
static obj_data restored[2]{};
static bool multiple = false, wrong_root = false;

bool sql_read_at(persistence_query_site, std::string query,
                 std::function<void(bool, const sql_rows &)> done) {
    assert(!read_done); last_query = std::move(query);
    if (throw_read) throw std::bad_alloc();
    if (!accept_read) return false;
    read_done = std::move(done); return true;
}
bool item_ownership_runtime_hydrate_many_atomic(const item_ownership_runtime_entry *entries,
                                                size_t count) {
    ++hydrations; assert(count == (multiple ? 4 : 2) && entries[0].owner.id == 42);
    return allow_hydration;
}
void obj_to_char(P_obj object, P_char actor) {
    assert(OBJ_NOWHERE(object)); ++attachments;
    object->loc_p = LOC_CARRIED; object->loc.carrying = actor;
    gmcp_items_changed(actor);
}
void extract_obj(P_obj object, int gone) {
    assert(OBJ_NOWHERE(object) && !gone); ++extractions;
    P_obj *link = &object_list;
    while (*link && *link != object) link = &(*link)->next;
    assert(*link == object); *link = object->next;
}
bool player_load_item_graph_materialize_detached(
    const std::vector<player_item_snapshot> &items,
    const std::vector<player_load_item_identity> &identities,
    const item_owner_identity &owner, uint64_t revision, bool hydrate, bool complete,
    std::vector<P_obj> *roots, player_load_item_materialize_metrics *) {
    ++restores; assert(owner.id == 42 && revision == 7 && !hydrate && complete);
    assert(items.size() == 2 && identities.size() == 2 && items[0].equipment_slot == -1 &&
           identities[1].serialized_parent_id == identities[0].database_id);
    if (!allow_restore) return false;
    auto &root = restored[items[0].object_uid == 100 ? 0 : 1];
    root = {}; root.obj_uid = items[0].object_uid; root.loc_p = LOC_NOWHERE;
    root.next = object_list; object_list = &root; roots->push_back(&root); return true;
}
'''
driver = r'''
static sql_rows rows(bool wrong_owner = false) {
    sql_rows result = { { {"100", "100", "0", "1", wrong_owner ? "99" : "42", "0", "1", "1001", "1", "7"} },
             { {"101", "100", "100", "1", "42", "0", "1", "1002", "1", "7"} } };
    if (multiple) {
        result.push_back({{"200", wrong_root ? "100" : "200", "0", "1", "42", "0", "1", "1001", "1", "7"}});
        result.push_back({{"201", "200", "200", "1", "42", "0", "1", "1002", "1", "7"}});
    }
    return result;
}
static void finish(bool ok, bool wrong_owner = false) {
    assert(read_done); auto done = std::move(read_done); read_done = {};
    done(ok, rows(wrong_owner));
}
int main() {
    auto state = std::make_shared<world_quest_reward_publication>();
    state->pid = 42;
    player_item_snapshot first{}, second{};
    first.object_uid=100; first.vnum=1001; first.parent_index=PLAYER_SNAPSHOT_NO_PARENT;
    second.object_uid=101; second.vnum=1002; second.parent_index=0;
    state->items={first,second};
    obj_data root{}, child{}; root.obj_uid=100; root.loc_p=LOC_NOWHERE;
    child.obj_uid=101; root.next=&child; object_list=&root;
    char_data actor{}; actor.specials.position=POS_STANDING|STAT_NORMAL;

    accept_read=false;
    assert(!world_quest_publish_reward(&actor,state) && !state->reading && !read_done);
    accept_read=true; throw_read=true;
    assert(!world_quest_publish_reward(&actor,state) && !state->reading && !read_done);
    throw_read=false;
    assert(!world_quest_publish_reward(&actor,state) && state->reading);
    assert(last_query.find("100,101") != std::string::npos);
    finish(true,true); // a changed owner cannot be published
    assert(!state->ready && !world_quest_publish_reward(&actor,state));
    finish(true);
    allow_hydration=false;
    assert(!world_quest_publish_reward(&actor,state) && !state->ready && attachments==0);
    allow_hydration=true;
    assert(!world_quest_publish_reward(&actor,state));
    finish(true);
    assert(world_quest_publish_reward(&actor,state) && OBJ_CARRIED_BY(&root,&actor));
    assert(attachments==1 && hydrations==2 && actor.gmcp_items_epoch==1);
    assert(world_quest_publish_reward(&actor,state) && attachments==1);

    // A departed actor leaves the durable reward for login, without a stale body.
    obj_data offline{}; offline.obj_uid=100; offline.loc_p=LOC_NOWHERE; object_list=&offline;
    assert(world_quest_publish_reward(nullptr,state) && extractions==1 && !object_list);

    // If the detached body disappeared, reconstruct from the committed image.
    state->ready=true; object_list=nullptr; allow_restore=true;
    assert(world_quest_publish_reward(&actor,state));
    assert(restores==1 && OBJ_CARRIED_BY(&restored[0],&actor));

    // Two roots with a child each share one committed publication. The second
    // root is restored while the first is already attached from an earlier try.
    multiple=true;
    player_item_snapshot third=first, fourth=second;
    third.object_uid=200; fourth.object_uid=201; fourth.parent_index=2;
    state->items={first,second,third,fourth}; state->ready=false;
    wrong_root=true;
    assert(!world_quest_publish_reward(&actor,state)); finish(true);
    assert(!state->ready && attachments==2);
    wrong_root=false;
    assert(!world_quest_publish_reward(&actor,state)); finish(true);
    assert(world_quest_publish_reward(&actor,state));
    assert(restores==2 && attachments==3 && OBJ_CARRIED_BY(&restored[1],&actor));
    assert(world_quest_publish_reward(&actor,state) && attachments==3 && restores==2);

    // A later root held elsewhere prevents any new attachment.
    restored[0].loc_p=LOC_NOWHERE; restored[1].loc_p=LOC_ROOM;
    assert(!world_quest_publish_reward(&actor,state) && attachments==3);
    restored[1].loc_p=LOC_NOWHERE;
    assert(world_quest_publish_reward(nullptr,state));
    assert(extractions==3 && !object_list);
    puts("world quest committed reward publication passed");
}
'''

flat_prelude = r'''
#include "flatfile/flatfile_item_repository.h"
#include "persistence/persistence_mode.h"
#include "player/player_snapshot_capture.h"
#include "net/unicode.h"
#include <ctime>
P_index obj_index = nullptr;
int panic_corruption_int(const char *, const char *, ...) { std::abort(); }
static player_pending_world_quest captured;
static bool reject_second = false;
static size_t capture_bytes = 100, capture_nodes = 2;
const char *persistence_mode_flatfile_root() { return "unused"; }
flatfile_item_repository_result flatfile_item_repository_load_owner(
    const std::string &, const item_owner_identity &owner, uint64_t *revision,
    std::vector<flatfile_item_ownership_record> *records, std::string *) {
    assert(owner.id == 42); *revision=7;
    for (uint64_t uid : {100,101,200,201}) {
        flatfile_item_ownership_record row;
        row.item_uid=uid; row.root_item_uid=uid < 200 ? 100 : 200;
        if (wrong_root && uid==200) row.root_item_uid=100;
        row.parent_item_uid=uid % 100 == 1 ? uid-1 : 0;
        row.owner=owner; row.item_revision=1; row.vnum=uid % 100 == 1 ? 1002 : 1001;
        row.state=item_custody_state::active; records->push_back(row);
    }
    return flatfile_item_repository_result::ok;
}
player_snapshot_capture_result player_item_snapshot_tree_capture(
    P_obj object, std::vector<player_item_snapshot> *items, size_t *bytes) {
    if (reject_second && object->obj_uid==200) return player_snapshot_capture_result::limit_exceeded;
    player_item_snapshot root{}, child{};
    root.object_uid=object->obj_uid; root.vnum=1001; root.parent_index=PLAYER_SNAPSHOT_NO_PARENT;
    child.object_uid=root.object_uid+1; child.vnum=1002; child.parent_index=0;
    *items={root,child};
    if (capture_nodes != 2) {
        items->resize(capture_nodes,child);
        for (size_t index=1; index<items->size(); ++index)
            (*items)[index].object_uid=root.object_uid*10000+index;
    }
    *bytes=capture_bytes; return player_snapshot_capture_result::ok;
}
bool player_save_pipeline_submit_world_quest(P_char, const player_pending_world_quest &quest,
    std::function<bool(P_char,const player_pending_world_quest &)>) {
    captured=quest; return true;
}
'''
flat_driver = r'''
int main() {
    multiple=true;
    pc_only_data pc{}; pc.pid=42; pc.quest_mob_vnum=500;
    char_data actor{}; actor.only.pc=&pc; actor.player.name=const_cast<char *>("Tester");
    actor.specials.position=POS_STANDING|STAT_NORMAL;
    obj_data first{}, second{}; first.obj_uid=100; second.obj_uid=200;
    first.R_num=second.R_num=-1; first.loc_p=second.loc_p=LOC_NOWHERE;
    first.next=&second; object_list=&first;
    assert(sql_world_quest_finish_async(&actor,{&first,&second},true,true,{},0,
        [](P_char){return true;}));
    assert(captured.reward_items.size()==4 && captured.reward_encoded_size==200);
    assert(captured.reward_items[2].parent_index==PLAYER_SNAPSHOT_NO_PARENT &&
           captured.reward_items[3].parent_index==2);
    captured={}; reject_second=true;
    assert(!sql_world_quest_finish_async(&actor,{&first,&second},true,true,{},0,
        [](P_char){return true;}));
    assert(!captured.present); // no partially captured batch was submitted
    reject_second=false; capture_bytes=PLAYER_SNAPSHOT_MAX_BYTES/2+1;
    assert(!sql_world_quest_finish_async(&actor,{&first,&second},true,true,{},0,
        [](P_char){return true;}) && !captured.present);
    capture_bytes=100; capture_nodes=PLAYER_SNAPSHOT_MAX_OBJECTS;
    assert(!sql_world_quest_finish_async(&actor,{&first,&second},true,true,{},0,
        [](P_char){return true;}) && !captured.present);
    capture_nodes=2;

    auto state=std::make_shared<world_quest_reward_publication>(); state->pid=42;
    reject_second=false;
    assert(sql_world_quest_finish_async(&actor,{&first,&second},true,true,{},0,
        [](P_char){return true;}));
    state->items=captured.reward_items;
    wrong_root=true;
    assert(!world_quest_publish_reward(&actor,state) && !state->ready && attachments==0);
    wrong_root=false;
    assert(!world_quest_publish_reward(&actor,state) && state->ready);
    assert(world_quest_publish_reward(&actor,state) && attachments==2);
    assert(world_quest_publish_reward(&actor,state) && attachments==2);
    object_list=nullptr; allow_restore=true;
    assert(world_quest_publish_reward(&actor,state) && restores==2 && attachments==4);
    puts("world quest flatfile batch capture and publication passed");
}
'''

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="quest-reward-publish-", dir=ROOT / "bin/tests") as tmp:
    cpp = Path(tmp) / "test.cpp"
    binary = Path(tmp) / "test"
    cpp.write_text(prelude + production + driver)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-g",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie",
                    "-no-pie", "-Isrc", "-I/usr/include/mysql", "-I/usr/include/libxml2",
                    str(cpp), "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True)
    cpp.write_text(prelude + flat_prelude + production +
                   extract_function("sql/sql.c", "bool sql_world_quest_finish_async(") + flat_driver)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-g",
                    "-D__NO_MYSQL__", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    "-fno-pie", "-no-pie", "-Isrc", "-Isrc/no_mysql", "-I/usr/include/libxml2",
                    str(cpp), "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True)
