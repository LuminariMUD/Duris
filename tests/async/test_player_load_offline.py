#!/usr/bin/env python3
"""Native offline completion separates raw inspection from object materialization."""
import os
from pathlib import Path
import subprocess
import tempfile
from _paths import extract_function

ROOT = Path(__file__).resolve().parents[2]
HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/mm.h"
#include "player/player_load_offline.h"
#include "player/player_load_pipeline.h"
#include "player/player_load_materialize.h"
#include "player/player_load_items.h"
#include "persistence/persistence_observability.h"
#include "sql/sql_player.h"
#include <cassert>
#include <cstdlib>
#include <cstring>

namespace {
mm_ds character_pool = {}, pc_pool = {};
P_char actor = nullptr;
bool online = false, submit_allowed = true, populate_items = false;
bool target_online = false, target_loading = false;
uint64_t request_id = 0;
player_load_request submitted;
size_t allocated = 0, released = 0, extracted = 0, completed = 0;

P_obj item(uint64_t uid) {
    auto object = static_cast<P_obj>(std::calloc(1, sizeof(obj_data)));
    assert(object);
    object->obj_uid = uid;
    ++allocated;
    return object;
}
void release_tree(P_obj object) {
    assert(object->obj_uid == 0); // discard must not remove stored custody/floor state
    while (object->contains) {
        P_obj child = object->contains;
        object->contains = child->next_content;
        release_tree(child);
    }
    ++extracted;
    std::free(object);
}
}
P_desc descriptor_list = nullptr;
mm_ds *dead_mob_pool = &character_pool;
mm_ds *dead_pconly_pool = &pc_pool;
void *_mm_get(mm_ds *pool, const char *, int) {
    return std::calloc(1, pool == dead_mob_pool ? sizeof(char_data) : sizeof(pc_only_data));
}
void mm_release(mm_ds *, void *memory) { std::free(memory); }
void ensure_pconly_pool() {}
void clear_char(P_char character) { *character = {}; character->in_room = NOWHERE; }
void free_char(P_char character) {
    assert(!character->carrying && "abandoned offline load retained its inventory");
    for (auto object : character->equipment)
        assert(!object && "abandoned offline load retained its equipment");
    ++released;
    std::free(character->only.pc);
    std::free(character);
}
void artifact_object_extracted(P_obj object, bool retired) {
    assert(!retired && object->obj_uid); // detach before discarding the saved UID
}
void extract_obj(P_obj object, int gone_for_good) {
    assert(!gone_for_good); // inspection cleanup cannot retire a saved artifact
    assert(OBJ_NOWHERE(object));
    release_tree(object);
}
// OWNER_BUSY
bool valid_snapshot(const player_load_result &result) { return result.outcome==player_load_outcome::applied; }
bool player_load_materialize(P_char character, const player_load_result &result) {
    P_char ch=character; const auto &loaded=result;
    // PRODUCTION_PID_GATE
    character->only.pc->pid = result.pid;
    if (populate_items) {
        P_obj worn = item(1001), bag = item(1002), child = item(1003), loose = item(1004);
        worn->extra_flags = ITEM_ARTIFACT;
        character->equipment[0] = worn;
        worn->loc_p = LOC_WORN; worn->loc.wearing = character;
        character->carrying = bag;
        bag->loc_p = LOC_CARRIED; bag->loc.carrying = character;
        bag->next_content = loose;
        loose->loc_p = LOC_CARRIED; loose->loc.carrying = character;
        bag->contains = child;
        child->loc_p = LOC_INSIDE; child->loc.inside = bag;
        GET_CARRYING_W(character) = 4; IS_CARRYING_N(character) = 2;
    }
    return true;
}
int sql_get_player_pid(const char *) { return 42; }
uint64_t player_load_pipeline_next_request_id() { return ++request_id; }
player_load_submit_outcome player_load_pipeline_submit(player_load_request request) {
    submitted = std::move(request);
    return submit_allowed ? player_load_submit_outcome::accepted : player_load_submit_outcome::unavailable;
}
uint64_t persistence_observability_now_usec() { return 100; }
P_char find_character_by_runtime_id(uint64_t id) {
    return online && actor && id == actor->runtime_id ? actor : nullptr;
}
void logit(const char *,const char *,...) {}
void send_to_char(const char *, P_char) {}
void send_to_char_f(P_char,const char *,...) {}
bool is_pid_online(int,bool) { return target_online; }
bool player_load_pipeline_pid_pending(int) { return target_loading; }

int main() {
    char_data staff = {}; staff.runtime_id = 77; actor = &staff;
    // The actor leaves before completion: no character or items may be constructed.
    populate_items = true;
    assert(player_load_offline_for(actor, "Offline", true, [](P_char, P_char) { ++completed; }));
    assert(submitted.pid == 42 && submitted.include_items && !submitted.include_pets);
    player_load_result result = {}; result.request_id = request_id;
    result.outcome = player_load_outcome::applied; result.pid = 42;
    assert(player_load_offline_complete(result));
    assert(completed == 0 && released == 0 && allocated == 0 && extracted == 0);
    assert(!player_load_offline_complete(result));

    // A live actor receives ownership unchanged and releases it through the real item discard.
    online = true;
    assert(player_load_offline_for(actor, "Offline", true, [](P_char live, P_char loaded) {
        assert(live == actor && loaded && loaded->equipment[0]->obj_uid == 1001);
        assert(loaded->carrying->contains->obj_uid == 1003);
        ++completed;
        player_load_items_discard(loaded);
        assert(GET_CARRYING_W(loaded) == 0 && IS_CARRYING_N(loaded) == 0);
        free_char(loaded);
    }));
    result.request_id = request_id;
    assert(player_load_offline_complete(result));
    assert(completed == 1 && released == 1 && allocated == 4 && allocated == extracted);

    online = false; populate_items = false;
    assert(player_load_offline_for(actor, "Offline", false, [](P_char, P_char) { ++completed; }));
    result.request_id = request_id;
    assert(player_load_offline_complete(result));
    assert(released == 1 && completed == 1);
    // Failed load hands no temporary owner to cancellation; rejected submissions never complete.
    assert(player_load_offline_for(actor, "Offline", true, [](P_char, P_char) { ++completed; }));
    result.request_id = request_id; result.outcome = player_load_outcome::not_found;
    assert(player_load_offline_complete(result));
    assert(released == 1);
    // Inspection receives the raw result without constructing any gameplay owner.
    online = true; populate_items = true;
    const auto before_allocated=allocated, before_released=released;
    size_t inspected=0;
    assert(player_load_offline_inspect_for(actor,"Offline",[&](P_char live,const player_load_result &cut) {
        assert(live==actor && cut.item_sources.size()==1 && cut.item_sources[0].quantity==7);
        assert(allocated==before_allocated && released==before_released);
        ++inspected;
    }));
    result.request_id=request_id; result.outcome=player_load_outcome::applied;
    player_load_source_item raw; raw.row_id=10; raw.quantity=7; result.item_sources={raw};
    assert(player_load_offline_complete(result) && inspected==1);
    online=false;
    assert(player_load_offline_inspect_for(actor,"Offline",[&](P_char,const player_load_result &) { ++inspected; }));
    result.request_id=request_id;
    assert(player_load_offline_complete(result) && inspected==1 && allocated==before_allocated);
    online=true;
    assert(player_load_offline_inspect_for(actor,"Offline",[&](P_char,const player_load_result &cut) {
        assert(cut.outcome==player_load_outcome::timed_out); ++inspected;
    }));
    result.request_id=request_id; result.outcome=player_load_outcome::timed_out;
    assert(player_load_offline_complete(result) && inspected==2 && allocated==before_allocated);
    assert(!player_load_offline_inspect_for(nullptr,"Offline",[](P_char,const player_load_result &) {}));
    assert(!player_load_offline_inspect_for(actor,"Offline",{}));
    // Another copy entered or began loading while this read was in flight.
    result.outcome=player_load_outcome::applied;
    for(bool loading: {false,true}) {
        target_online=!loading; target_loading=loading;
        assert(player_load_offline_for(actor,"Offline",true,[](P_char,P_char) { assert(false); }));
        result.request_id=request_id;
        assert(player_load_offline_complete(result) && allocated==before_allocated);
        bool direct_refused=false;
        assert(player_load_offline("Offline",true,[&](P_char loaded) { assert(!loaded); direct_refused=true; }));
        result.request_id=request_id;
        assert(player_load_offline_complete(result) && direct_refused && allocated==before_allocated);
    }
    target_online=target_loading=false;
    // A fully loaded body waiting at character confirmation is not in the world
    // list or read queue, but already owns the PID and its physical item graph.
    char_data selected={}; pc_only_data selected_pc={}; selected.only.pc=&selected_pc; selected_pc.pid=42;
    descriptor_data selection={}; selection.connected=CON_ACCT_SELECT_CHAR; selection.character=&selected;
    descriptor_list=&selection;
    char_data candidate={}; pc_only_data candidate_pc={}; candidate.only.pc=&candidate_pc;
    result.snapshot.components=PLAYER_LOAD_SESSION02_COMPONENTS;
    assert(!player_load_materialize(&candidate,result) && !candidate_pc.pid && allocated==before_allocated);
    assert(player_load_pid_busy(42,nullptr) && !player_load_pid_busy(42,&selected));
    for(bool switched: {false,true}) {
        selection.character=switched ? nullptr : &selected;
        selection.original=switched ? &selected : nullptr;
        assert(player_load_offline_for(actor,"Offline",true,[](P_char,P_char) { assert(false && "leased character was materialized twice"); }));
        result.request_id=request_id;
        assert(player_load_offline_complete(result) && allocated==before_allocated);
    }
    bool leased_inspected=false;
    assert(player_load_offline_inspect_for(actor,"Offline",[&](P_char,const player_load_result &) { leased_inspected=true; }));
    result.request_id=request_id;
    assert(player_load_offline_complete(result) && leased_inspected && allocated==before_allocated);
    descriptor_list=nullptr;
    submit_allowed = false;
    assert(!player_load_offline_for(actor, "Offline", true, [](P_char, P_char) { ++completed; }));
    result.request_id = request_id;
    assert(!player_load_offline_complete(result));
    assert(completed == 1 && allocated == extracted);
}
'''
owner_busy = extract_function("player_load_materialize.c", "bool player_load_pid_busy(")
entry = extract_function("player_load_materialize.c", "bool player_load_materialize(")
entry_gate = entry[entry.index("{\n") + 2 : entry.index("player_load_result qualified;")]
HARNESS = HARNESS.replace("// OWNER_BUSY", owner_busy).replace("// PRODUCTION_PID_GATE", entry_gate)

with tempfile.TemporaryDirectory(prefix='duris-offline-cleanup-') as temporary:
    source = Path(temporary) / 'test.cpp'
    binary = Path(temporary) / 'test'
    source.write_text(HARNESS)
    subprocess.run(['g++', '-std=c++20', '-g', '-O1', '-Wall', '-Wextra', '-Werror',
                    '-ffunction-sections', '-fdata-sections', '-fsanitize=address,undefined',
                    '-fno-sanitize-recover=all', '-fno-pie', '-no-pie', '-Isrc', '-D__NO_MYSQL__', str(source),
                    'src/player/player_load_offline.c', 'src/player/player_load_items.c',
                    '-Wl,--gc-sections', '-o', str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, cwd=ROOT, timeout=20,
                   env={**os.environ, 'ASAN_OPTIONS': 'detect_leaks=1'})
print('native offline callback and temporary item cleanup passed')
