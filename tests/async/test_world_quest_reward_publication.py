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
bool obj_to_char(P_obj object, P_char actor) {
    assert(OBJ_NOWHERE(object)); ++attachments;
    object->loc_p = LOC_CARRIED; object->loc.carrying = actor;
    gmcp_items_changed(actor);
    return true;
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
