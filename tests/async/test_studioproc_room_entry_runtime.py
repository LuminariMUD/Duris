#!/usr/bin/env python3
"""Execute the real Studio room dispatch and the room-entry portion of char_to_room.

Room/character tables and trigger actions are fixtures. The engine's arrival
hook, record lookup, trigger selection, event classifier, dispatch, and room
adapter are production code, so this catches a mismatch between their event
values without starting a server or touching a live world.
"""

from pathlib import Path
import os
import subprocess
import tempfile

from _paths import ROOT, extract_function


def structure(name):
    return extract_function("studioproc.c", f"struct {name}") + ";"


handler = extract_function("handler.c", "bool char_to_room(")
start = handler.index("\tif (dir < 0) /* flag value, skip aggro checks */")
end = handler.index("\tif ((world[room].sector_type == SECT_FIREPLANE)", start)
arrival_hook = handler[start:end]

PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "cmd/interp.h"
#include "mob/studioproc.h"
#include <cassert>
#include <cctype>
#include <cstdio>
#include <cstring>
#include <initializer_list>

extern P_room world;
extern int top_of_world;
'''

FIXTURE = r'''
#define SP_HASH 128
#define SP_X_FIRED 1
#define SP_X_SELFGONE 2
static room_data rooms[3];
P_room world = rooms;
int top_of_world = 2;
uint64_t character_removal_generation = 0;
struct command_info cmd_info[MAX_CMD_LIST]{};
static struct sp_rec *sp_tab[SP_NUM_T][SP_HASH]{};
static int sp_tcount[SP_NUM_T]{};
static int previous_call, previous_command, previous_result, previous_mode;
static int fires, last_event, fire_mode;
static P_char last_actor;
static int last_room;
static bool member = true;
static P_char tracked_actor = nullptr;

P_char find_character_by_runtime_id(uint64_t id)
{
    return member && tracked_actor && id && tracked_actor->runtime_id == id ? tracked_actor : nullptr;
}
static int sp_on_game_thread() { return 1; }
static void sp_arm_hour() {}
int real_room(int vnum)
{
    for (int i = 0; i <= top_of_world; ++i)
        if (world[i].number == vnum) return i;
    return -1;
}
int char_in_list(const P_char) { return member; }
int number(int low, int) { return low; }
static int sp_char_get(P_char, int, int) { return 0; }
static void sp_char_set(P_char, int, int, int) {}
static int sp_state_get(sp_ctx *, int, int) { return 0; }
static void sp_state_set(sp_ctx *, int, int, int) {}
static int sp_fire(sp_trig *trigger, sp_ctx *ctx)
{
    ++fires;
    last_event = trigger->event;
    last_actor = ctx->actor;
    last_room = ctx->self_room;
    if (fire_mode == 1) ctx->actor->in_room = 2;
    if (fire_mode == 2) SET_POS(ctx->actor, STAT_DEAD);
    if (fire_mode == 3) { member = false; ++character_removal_generation; }
    return SP_X_FIRED;
}
static int previous_room(int, P_char ch, int cmd, char *)
{
    ++previous_call;
    previous_command = cmd;
    if (previous_mode == 1) ch->in_room = 2;
    if (previous_mode == 2) SET_POS(ch, STAT_DEAD);
    if (previous_mode == 3) { member = false; ++character_removal_generation; }
    if (previous_mode == 4) ++ch->runtime_id; // same-address replacement
    return previous_result;
}
'''

DRIVER = r'''
static void reset(char_data &ch, sp_rec &record, sp_trig &trigger, int event)
{
    ch = char_data{};
    ch.in_room = 1;
    ch.runtime_id = 7;
    tracked_actor = &ch;
    SET_POS(&ch, POS_STANDING + STAT_NORMAL);
    record = sp_rec{};
    record.target = SP_T_ROOM;
    record.vnum = 5001;
    record.events = 1u << event;
    record.trigs = &trigger;
    record.prev_room = previous_room;
    trigger = sp_trig{};
    trigger.event = event;
    trigger.chance = 100;
    trigger.arg = 1;
    trigger.cmdnum = -1;
    rooms[0] = room_data{};
    rooms[1] = room_data{};
    rooms[2] = room_data{};
    rooms[0].number = 5000;
    rooms[1].number = 5001;
    rooms[2].number = 5002;
    rooms[1].funct = studioproc_room;
    memset(sp_tab, 0, sizeof(sp_tab));
    memset(sp_tcount, 0, sizeof(sp_tcount));
    sp_tab[SP_T_ROOM][5001 & (SP_HASH - 1)] = &record;
    sp_tcount[SP_T_ROOM] = 1;
    previous_call = fires = fire_mode = 0;
    previous_command = 999;
    previous_result = previous_mode = 0;
    last_event = -1;
    last_room = -1;
    last_actor = nullptr;
    member = true;
    character_removal_generation = 0;
}

int main()
{
    char_data actor{};
    sp_rec record{};
    sp_trig trigger{};
    for (int dir = 0; dir < NUM_EXITS; ++dir)
    {
        reset(actor, record, trigger, SP_EV_ENTER);
        assert(execute_room_entry(&actor, 1, dir));
        assert(previous_call == 1 && previous_command == -50 + dir);
        assert(fires == 1 && last_event == SP_EV_ENTER);
        assert(last_actor == &actor && last_room == 1);
    }
    // Negative directions skip the production arrival hook entirely.
    for (int dir : {-1, -2})
    {
        reset(actor, record, trigger, SP_EV_ENTER);
        assert(execute_room_entry(&actor, 1, dir));
        assert(previous_call == 0 && fires == 0);
    }
    // Other room events retain their original meanings and never become ENTER.
    for (int cmd : {-51, -40, CMD_FROMROOM, -80, -81, CMD_SET_PERIODIC,
                    CMD_PERIODIC, CMD_DEATH, CMD_LOOK})
    {
        reset(actor, record, trigger, SP_EV_ENTER);
        studioproc_room(1, &actor, cmd, nullptr);
        assert(previous_call == 1 && previous_command == cmd);
        assert(fires == 0);
    }
    reset(actor, record, trigger, SP_EV_LEAVE);
    assert(studioproc_room(1, &actor, CMD_FROMROOM, nullptr) == FALSE);
    assert(fires == 1 && last_event == SP_EV_LEAVE);
    reset(actor, record, trigger, SP_EV_LEAVE);
    previous_result = ROOM_PROC_LEAVE_VETO;
    assert(studioproc_room(1, &actor, CMD_FROMROOM, nullptr) == ROOM_PROC_LEAVE_VETO);
    assert(previous_call == 1 && fires == 0);
    // Preserve the old handling of ordinary nonzero legacy proc returns.
    for (int cmd : {CMD_FROMROOM, -50, CMD_LOOK})
    {
        reset(actor, record, trigger, SP_EV_ENTER);
        previous_result = 2;
        assert(studioproc_room(1, &actor, cmd, nullptr) == TRUE);
        assert(previous_call == 1 && previous_command == cmd && fires == 0);
    }
    // A preceding legacy proc can redirect, kill, extract, or replace the entrant.
    // Studio must never run on the old identity, regardless of its return value.
    for (int mode : {1, 2, 3, 4})
    {
        for (int prior_result : {0, 1})
        {
            reset(actor, record, trigger, SP_EV_ENTER);
            previous_mode = mode;
            previous_result = prior_result;
            execute_room_entry(&actor, 1, DIR_NORTH);
            assert(previous_call == 1 && previous_command == -50 && fires == 0);
        }
    }
    // The arrival-hook continuation respects an entry procedure's outcomes.
    for (int mode : {1, 2, 3})
    {
        reset(actor, record, trigger, SP_EV_ENTER);
        fire_mode = mode;
        assert(!execute_room_entry(&actor, 1, DIR_NORTH));
        assert(fires == 1 && last_event == SP_EV_ENTER);
    }
    // Directional room signals do not become mob/object events in the shared dispatcher.
    for (int kind : {SP_T_MOB, SP_T_OBJ})
    {
        reset(actor, record, trigger, SP_EV_ENTER);
        sp_ctx ctx{};
        ctx.targ = kind;
        assert(sp_dispatch(&record, &ctx, -50, nullptr) == FALSE);
        assert(fires == 0);
    }
    std::puts("Studio room entry: 10 directions, veto, legacy lifecycle and interruption cases passed");
}
'''

parts = [
    PRELUDE,
    *(structure(name) for name in ("sp_cond", "sp_action", "sp_trig", "sp_rec", "sp_ctx")),
    FIXTURE,
    extract_function("studioproc.c", "static struct sp_rec *sp_find("),
    extract_function("studioproc.c", "static void sp_strlower("),
    extract_function("studioproc.c", "static int sp_keyword_match("),
    extract_function("studioproc.c", "static void sp_revalidate_actor("),
    extract_function("studioproc.c", "static int sp_run("),
    extract_function("studioproc.c", "static int sp_event_for_cmd("),
    extract_function("studioproc.c", "static int sp_dispatch("),
    extract_function("studioproc.c", "int studioproc_room("),
    "static bool execute_room_entry(P_char ch, int room, int dir) {\n" + arrival_hook + "\nreturn true;\n}",
    DRIVER,
]

build_root = Path(os.environ.get("BIN_ROOT", ROOT / "bin")) / "tests"
build_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="studio-room-entry-", dir=build_root) as directory:
    harness = Path(directory) / "harness.cpp"
    binary = Path(directory) / "harness"
    harness.write_text("\n".join(parts), encoding="utf-8")
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        f"-I{ROOT / 'src'}", str(harness), "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True)
