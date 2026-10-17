#!/usr/bin/env python3
"""Native asynchronous offline completion releases abandoned temporary item trees."""
import os
from pathlib import Path
import subprocess
import tempfile
from _paths import HARNESS_STUBS

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
void extract_obj(P_obj object, int gone_for_good) {
    assert(!gone_for_good); // inspection cleanup cannot retire a saved artifact
    assert(OBJ_NOWHERE(object));
    release_tree(object);
}
bool player_load_materialize(P_char character, const player_load_result &result) {
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
void send_to_char(const char *, P_char) {}

int main() {
    char_data staff = {}; staff.runtime_id = 77; actor = &staff;
    // The actor leaves before include-items completion: actual callback must discard first.
    populate_items = true;
    assert(player_load_offline_for(actor, "Offline", true, [](P_char, P_char) { ++completed; }));
    assert(submitted.pid == 42 && submitted.include_items && !submitted.include_pets);
    player_load_result result = {}; result.request_id = request_id;
    result.outcome = player_load_outcome::applied; result.pid = 42;
    assert(player_load_offline_complete(result));
    assert(completed == 0 && released == 1 && allocated == 4 && extracted == 4);
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
    assert(completed == 1 && released == 2 && allocated == extracted);

    online = false; populate_items = false;
    assert(player_load_offline_for(actor, "Offline", false, [](P_char, P_char) { ++completed; }));
    result.request_id = request_id;
    assert(player_load_offline_complete(result));
    assert(released == 3 && completed == 1);
    // Failed load hands no temporary owner to cancellation; rejected submissions never complete.
    assert(player_load_offline_for(actor, "Offline", true, [](P_char, P_char) { ++completed; }));
    result.request_id = request_id; result.outcome = player_load_outcome::not_found;
    assert(player_load_offline_complete(result));
    assert(released == 3);
    submit_allowed = false;
    assert(!player_load_offline_for(actor, "Offline", true, [](P_char, P_char) { ++completed; }));
    result.request_id = request_id;
    assert(!player_load_offline_complete(result));
    assert(completed == 1 && allocated == extracted);
}
'''
with tempfile.TemporaryDirectory(prefix='duris-offline-cleanup-') as temporary:
    source = Path(temporary) / 'test.cpp'
    binary = Path(temporary) / 'test'
    source.write_text(HARNESS)
    subprocess.run(['g++', '-std=c++20', '-g', '-O1', '-Wall', '-Wextra', '-Werror',
                    '-ffunction-sections', '-fdata-sections', '-fsanitize=address,undefined',
                    '-fno-sanitize-recover=all', '-fno-pie', '-no-pie', '-Isrc', '-D__NO_MYSQL__', str(source),
                    'src/player/player_load_offline.c', 'src/player/player_load_items.c', str(HARNESS_STUBS),
                    '-Wl,--gc-sections', '-o', str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, cwd=ROOT, timeout=20,
                   env={**os.environ, 'ASAN_OPTIONS': 'detect_leaks=1'})
print('native offline callback and temporary item cleanup passed')
