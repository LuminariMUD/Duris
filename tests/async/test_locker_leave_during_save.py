#!/usr/bin/env python3
"""Leaving a locker while an older save is being written keeps the newer contents."""

from _paths import rel
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

HARNESS = r'''
#include "persistence/locker_async.h"
#include "player/player_save_worker.h"
#include "player/player_snapshot_capture.h"
#include "player/player_snapshot_repository.h"
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"

#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <deque>
#include <vector>

P_char character_list = nullptr;
P_room world = nullptr;

// The writer's queue, run one job at a time by the test.
std::deque<persistence_job_write_fn> writer;
// How many items each locker save wrote, in order.
std::vector<size_t> written;
// How many items the locker character holds.
int carried = 0;
bool extracted = false;

void logit(const char *, const char *, ...) {}
void persistence_alert(int, const char *, const char *, const char *, const char *,
                       const char *, const char *, ...)
{
}
int panic_corruption_int(const char *, const char *, ...)
{
    std::abort();
}
extern "C" int sql_pool_is_active(void)
{
    return 1;
}
player_save_worker_health player_save_worker_health_copy(void)
{
    player_save_worker_health health = {};
    health.running = true;
    return health;
}
player_save_submit_result persistence_writer_submit(persistence_job_kind, uint64_t, size_t,
                                                    persistence_job_write_fn write)
{
    writer.push_back(std::move(write));
    return player_save_submit_result::accepted;
}
player_snapshot_capture_result player_item_snapshot_list_capture(
    P_char, bool, bool, bool, std::vector<player_item_snapshot> *items, size_t *bytes)
{
    items->assign(carried, player_item_snapshot{});
    *bytes = 0;
    return player_snapshot_capture_result::ok;
}
player_save_apply_result locker_snapshot_repository_apply_from_pool(const locker_snapshot &locker)
{
    written.push_back(locker.items.size());
    return {player_save_apply_outcome::applied, 0, 0};
}
void extract_char(P_char ch)
{
    extracted = true;
    for (P_char *link = &character_list; *link; link = &(*link)->next)
        if (*link == ch)
        {
            *link = ch->next;
            break;
        }
}
extern "C" void locker_async_request_resort(P_char, P_char) {}
extern "C" void locker_async_restore_snapshot_view(P_char) {}
extern "C" int locker_async_prepare_snapshot(P_char)
{
    return 1;
}

static void run_writer_job()
{
    assert(!writer.empty());
    persistence_job_write_fn job = std::move(writer.front());
    writer.pop_front();
    job();
}

int main()
{
    room_data rooms[2] = {};
    rooms[0].room_flags = ROOM_LOCKER;
    world = rooms;

    char locker_name[] = "Veridian.locker";
    char user_name[] = "Veridian";
    char_data locker = {};
    locker.player.name = locker_name;
    locker.specials.act = ACT_ISNPC;
    pc_only_data pc = {};
    pc.pid = 7;
    char_data user = {};
    user.player.name = user_name;
    user.only.pc = &pc;
    user.in_room = 0;
    locker.next = &user;
    character_list = &locker;

    locker_async_init();

    // An in-stay save of one item starts and goes to the writer.
    carried = 1;
    assert(locker_async_mark_dirty(&locker, &user, 0, "nonterminal"));
    locker_async_pulse();
    assert(writer.size() == 1);

    // While it is being written, a second item goes in and the player leaves.
    carried = 2;
    user.in_room = 1;
    assert(locker_async_mark_dirty(&locker, &user, 1, "leave-terminal"));

    // The older save lands. The locker character must stay until the newer one does.
    run_writer_job();
    locker_async_pulse();
    assert(!extracted);
    assert(writer.size() == 1);

    run_writer_job();
    locker_async_pulse();
    assert((written == std::vector<size_t>{1, 2}));
    assert(extracted);
    assert(!locker_async_name_busy(locker_name));
    std::puts("leaving during an in-flight save writes the newer contents before extracting");
    return 0;
}
'''

with tempfile.TemporaryDirectory() as temp_dir:
    source = Path(temp_dir) / "harness.cpp"
    binary = Path(temp_dir) / "harness"
    source.write_text(HARNESS)
    subprocess.run(
        [
            "g++",
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-Wno-unused-parameter",
            "-Wno-missing-field-initializers",
            "-pthread",
            "-Isrc",
            "-I/usr/include/mysql",
            str(source),
            rel("locker_async.c"),
            "-o",
            str(binary),
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run([str(binary)], check=True, timeout=60)
print("[PASS] a locker left during an in-flight save keeps its newer contents")
