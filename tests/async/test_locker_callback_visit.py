#!/usr/bin/env python3
"""Execute delayed locker callbacks and writer captures across a change of visit.

The callbacks, room lookup, constructor and writer state machine are production
code. The event queue, inventory moves and persistence sink are controlled so a
player can leave between scheduling, capture and completion deterministically.
"""

import os
import subprocess

from _paths import ROOT, HARNESS_STUBS, extract_function


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "item/storage_lockers.h"
#include "persistence/locker_async.h"
#include "player/player_save_worker.h"
#include "player/player_snapshot_capture.h"
#include "player/player_snapshot_repository.h"
#include "flatfile/flatfile_player_repository.h"
#include "world/events.h"
#include "net/comm.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <map>
#include <string>
#include <vector>

static room_data rooms[3]{};
P_room world = rooms;
extern const int top_of_world = 2;
P_char character_list;
static std::deque<nevent_data> events;
static std::deque<persistence_job_write_fn> writer;
static std::map<P_char, std::vector<uint64_t>> carried;
static std::vector<uint64_t> visible[3];
static std::vector<std::pair<std::string, std::vector<uint64_t>>> written;
static unsigned prepares, restores, notices, extractions;
static bool prepare_ok = true;

void send_to_char(const char *, P_char) { ++notices; }
void logit(const char *, const char *, ...) {}
void persistence_alert(int, const char *, const char *, const char *, const char *,
                       const char *, const char *, ...) {}
void *__malloc(size_t size, const char *, const char *, int) { return calloc(1, size); }
char *str_dup(const char *value) { return strdup(value); }
static bool esc_locker_name_matches_player(const char *, P_char) { return true; }
StorageLocker::~StorageLocker() {
    auto desc = world[GetRealRoom()].ex_description;
    free(desc->keyword); free(desc->next->keyword);
    free(desc->next); free(desc);
    world[GetRealRoom()].ex_description = nullptr;
}
bool StorageLocker::LockerToPFile() {
    ++prepares;
    if (!prepare_ok) return false;
    auto &items = visible[GetRealRoom()];
    auto &destination = carried[GetLockerChar()];
    destination.insert(destination.end(), items.begin(), items.end());
    items.clear();
    return true;
}
void StorageLocker::PFileToLocker() {
    ++restores;
    auto &items = carried[GetLockerChar()];
    auto &destination = visible[GetRealRoom()];
    destination.insert(destination.end(), items.begin(), items.end());
    items.clear();
    m_itemCount = destination.size();
}
P_nevent get_scheduled(P_char holder, event_func func) {
    for (auto &event : events)
        if (event.ch == holder && event.func == func) return &event;
    return nullptr;
}
nevent_schedule_result add_event(event_func func, int, P_char holder, P_char user,
                                 P_obj, int, const void *, int) {
    nevent_data event{};
    event.func = func; event.ch = holder; event.victim = user;
    events.push_back(event);
    return {};
}
static void dispatch() {
    while (!events.empty()) {
        auto event = events.front(); events.pop_front();
        event.func(event.ch, event.victim, nullptr, nullptr);
    }
}
extern "C" int sql_pool_is_active() { return 1; }
player_save_worker_health player_save_worker_health_copy() {
    player_save_worker_health health{}; health.running = true; return health;
}
player_save_submit_result persistence_writer_submit(persistence_job_kind, uint64_t,
                                                    size_t, persistence_job_write_fn job) {
    writer.push_back(std::move(job)); return player_save_submit_result::accepted;
}
player_snapshot_capture_result player_item_snapshot_list_capture(
    P_char holder, bool, bool, bool, std::vector<player_item_snapshot> *items, size_t *bytes) {
    for (uint64_t uid : carried[holder]) {
        player_item_snapshot item{}; item.object_uid = uid; items->push_back(item);
    }
    *bytes = items->size() * sizeof(player_item_snapshot);
    return player_snapshot_capture_result::ok;
}
const char *persistence_mode_flatfile_root() { return nullptr; }
player_save_apply_result flatfile_locker_snapshot_apply(
    const std::string &, const flatfile_locker_save &, std::string *) { std::abort(); }
player_save_apply_result locker_snapshot_repository_apply_from_pool(const locker_snapshot &snapshot) {
    std::vector<uint64_t> items;
    for (const auto &item : snapshot.items) items.push_back(item.object_uid);
    written.emplace_back(snapshot.locker_name, std::move(items));
    return {player_save_apply_outcome::applied, 0, 0};
}
void extract_char(P_char holder) {
    ++extractions;
    for (P_char *link = &character_list; *link; link = &(*link)->next)
        if (*link == holder) { *link = holder->next; break; }
}
static void complete_write() {
    assert(writer.size() == 1);
    auto job = std::move(writer.front()); writer.pop_front(); job();
    locker_async_pulse();
}
'''

BODIES = "\n".join(extract_function("storage_lockers.c", signature) for signature in (
    "static long locker_elapsed_ms(",
    "inline StorageLocker *GetChestList(",
    "static StorageLocker *locker_current(P_char ch)\n{",
    "StorageLocker::StorageLocker(",
    'extern "C" void locker_async_restore_snapshot_view(',
    'extern "C" void locker_async_request_resort(',
    'extern "C" int locker_async_prepare_snapshot(',
    "void StorageLocker::event_resortLocker(",
))

CASES = r'''
int main() {
    char_data holder{}, second_holder{}, user{}, guest{};
    pc_only_data holder_pc{}, second_pc{}, user_pc{};
    holder.player.name = const_cast<char *>("account.first.1.locker");
    second_holder.player.name = const_cast<char *>("guild.1.locker");
    holder.only.pc = &holder_pc; second_holder.only.pc = &second_pc;
    user.only.pc = &user_pc; user_pc.pid = 42;
    holder.runtime_id = 1; second_holder.runtime_id = 2; user.runtime_id = 3;
    holder.next = &second_holder; second_holder.next = &user;
    character_list = &holder;
    rooms[1].room_flags = rooms[2].room_flags = ROOM_LOCKER;
    StorageLocker first(1, &holder, &user), second(2, &second_holder, &user);

    // The actual bank keyword parsed as pointer 0xba in the October 30 core.
    extra_descr_data bank[2]{};
    bank[0].next = &bank[1]; bank[1].keyword = const_cast<char *>("bar bars cell");
    rooms[0].ex_description = bank;
    auto untouched = [&] {
        unsigned before = prepares + restores + notices;
        StorageLocker::event_resortLocker(&holder, &user, nullptr, nullptr);
        StorageLocker::event_resortLocker(&holder, &user, nullptr, reinterpret_cast<void *>(-1));
        locker_async_request_resort(&holder, &user);
        locker_async_restore_snapshot_view(&holder, &user);
        assert(locker_async_prepare_snapshot(&holder, &user));
        assert(prepares + restores + notices == before && events.empty());
    };
    for (int room : {NOWHERE, -2, 0, top_of_world + 1}) {
        user.in_room = room; untouched();
    }
    StorageLocker::event_resortLocker(&holder, nullptr, nullptr, nullptr);
    locker_async_request_resort(&holder, nullptr);
    locker_async_restore_snapshot_view(&holder, nullptr);
    assert(locker_async_prepare_snapshot(&holder, nullptr));

    // A valid refresh can become stale after it was queued.
    user.in_room = 1;
    locker_async_request_resort(&holder, &user);
    locker_async_request_resort(&holder, &user);
    assert(events.size() == 1);
    user.in_room = 0; dispatch();
    assert(prepares == 0 && restores == 0 && notices == 0);
    user.in_room = 1;
    locker_async_request_resort(&holder, &user);
    user.in_room = 2; dispatch(); untouched();

    // Another occupant, and reuse of the same player address, are not this visit.
    user.in_room = 1;
    guest.in_room = 1; guest.runtime_id = 4;
    StorageLocker::event_resortLocker(&holder, &guest, nullptr, nullptr);
    ++user.runtime_id; untouched(); --user.runtime_id;

    // Current automatic and explicit sorts still run, and preparation failure
    // leaves the room intact without attempting restoration.
    visible[1] = {101};
    StorageLocker::event_resortLocker(&holder, &user, nullptr, nullptr);
    assert(prepares == 1 && restores == 1 && notices == 1);
    StorageLocker::event_resortLocker(&holder, &user, nullptr, reinterpret_cast<void *>(-1));
    assert(prepares == 2 && restores == 2 && notices == 2);
    prepare_ok = false;
    assert(!locker_async_prepare_snapshot(&holder, &user));
    StorageLocker::event_resortLocker(&holder, &user, nullptr, nullptr);
    assert(prepares == 4 && restores == 2 && visible[1] == std::vector<uint64_t>{101});
    prepare_ok = true;

    // A terminal capture of the first visit must not collect the second room's
    // items just because the same player has already entered it.
    locker_async_init();
    assert(first.LockerToPFile());
    user.in_room = 2; visible[2] = {202};
    unsigned before = prepares + restores;
    assert(locker_async_mark_dirty(&holder, &user, 1, "departed-visit"));
    locker_async_pulse();
    assert(prepares + restores == before && visible[2] == std::vector<uint64_t>{202});
    complete_write();
    assert(extractions == 1 && !locker_async_name_busy(holder.player.name));
    assert(written.size() == 1 && written[0].first == holder.player.name);
    assert(written[0].second == std::vector<uint64_t>{101});

    // A live save captures and restores its own inventory, then queues a refresh
    // only while that visit is still active.
    assert(locker_async_mark_dirty(&second_holder, &user, 0, "current-visit"));
    locker_async_pulse();
    assert(visible[2] == std::vector<uint64_t>{202} && carried[&second_holder].empty());
    complete_write();
    assert(events.size() == 1);
    user.in_room = 0;
    before = prepares + restores + notices; dispatch();
    assert(prepares + restores + notices == before);
    assert(written.size() == 2 && written[1].first == second_holder.player.name);
    assert(written[1].second == std::vector<uint64_t>{202});

    // Worker completion can also arrive after departure, before any refresh exists.
    user.in_room = 2;
    assert(locker_async_mark_dirty(&second_holder, &user, 0, "late-reply"));
    locker_async_pulse();
    user.in_room = 0; complete_write();
    assert(events.empty());
    locker_async_shutdown();
    rooms[0].ex_description = nullptr;
    puts("PASS locker visits: bank crash, stale dispatch/completion, different holder, user reuse, sorts and terminal capture");
}
'''

build = ROOT / "bin/tests/locker-callback-visit"
build.mkdir(parents=True, exist_ok=True)
cpp = build / "harness.cpp"
cpp.write_text(PRELUDE + BODIES + CASES)
binary = build / "harness"
subprocess.run([
    "g++", "-std=c++20", "-g", "-O1", "-Wall", "-Wextra", "-Werror",
    "-fsanitize=address,undefined", "-fno-sanitize-recover=all", "-fno-omit-frame-pointer",
    "-pthread", "-Isrc", "-I/usr/include/mysql", str(cpp),
    "src/persistence/locker_async.c", str(HARNESS_STUBS), "-o", str(binary),
], cwd=ROOT, check=True)
subprocess.run([str(binary)], cwd=ROOT, check=True, timeout=30,
               env=dict(os.environ, ASAN_OPTIONS="detect_leaks=0:abort_on_error=1"))
