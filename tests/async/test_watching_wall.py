#!/usr/bin/env python3
"""Preserve Watching Wall's existing views, hits, passage and two-sided cleanup.

Execute the real creation spell and create_walls, wall_generic's unchanged
decay/view/hit/movement prefix and watching/iron/outpost passage cases, and
dispel magic's wall branch. Clock, RNG, allocation, scheduling, output, damage
and movement are controlled fixtures, not a running server.
"""

import os
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, HARNESS_STUBS, extract_function, source


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "cmd/interp.h"
#include "magic/spells.h"
#include "abilities/abilities.h"
#include "combat/damage.h"
#include "combat/justice.h"
#include "world/events.h"
#include "world/specs.prototypes.h"
#include "world/vnum.obj.h"
#include "net/comm.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>

static room_data rooms[3]{};
P_room world = rooms;
static zone_data zones[1]{};
zone_data *zone_table = zones;
P_char character_list;
const char *dirs[] = {"north", "east", "south", "west", "up", "down"};
extern const int rev_dir[] = {2, 3, 0, 1, 5, 4};
static char_data owner{}, actor{};
static pc_only_data owner_pc{}, actor_pc{};
static room_direction_data exits[2]{};
static std::map<P_obj, int> timers;
static time_t now = 100;
static int roll, draws, views, moves, hurt, lag;
static bool visible = true, climbing = false;

static time_t wall_time(time_t *) { return now; }
int number(int low, int high) { ++draws; return roll >= low && roll <= high ? roll : low; }
int dice(int, int) { assert(false); return 0; }
const Rolls live_rolls = {dice, number};
void act(const char *, int, P_char, P_obj, void *, int) {}
void send_to_char(const char *text, P_char ch) {
    if (std::strstr(text, "vision from elsewhere")) assert(ch == &owner);
}
void send_to_room(const char *, int) {}
void new_look(P_char ch, const char *, int cmd, int room) {
    assert(ch == &owner && cmd == CMD_LOOK && room == actor.in_room);
    ++views;
}
void logit(int, const char *, ...) { assert(false); }
void CharWait(P_char, int ticks) { lag = ticks; }
int damage(P_char ch, P_char victim, int amount, int) {
    assert(ch == &actor && victim == ch); hurt = amount; return 0;
}
bool ac_can_see_obj(P_char, P_obj, int) { return visible; }
bool has_innate(P_char, int innate) { assert(innate == INNATE_WALL_CLIMBING); return climbing; }
int real_room0(const int room) { return room - 1000; }
int leave_by_exit(P_char, int) { return true; }
int do_simple_move_skipping_procs(P_char ch, int dir, int) {
    ch->in_room = EXIT(ch, dir)->to_room; ++moves; return true;
}
int dir_from_keyword(char *arg) {
    if (!strcmp(arg, "north")) return DIR_NORTH;
    if (!strcmp(arg, "south")) return DIR_SOUTH;
    return -1;
}
int cmd_to_exitnumb(int cmd) {
    if (cmd == CMD_NORTH) return DIR_NORTH;
    if (cmd == CMD_SOUTH) return DIR_SOUTH;
    return -1;
}
char *one_argument(const char *arg, char *out) { strcpy(out, arg); return out + strlen(out); }
void argument_split_2(const char *arg, char *first, char *second) {
    assert(sscanf(arg, "%511s %511s", first, second) == 2);
}
int check_wall(int room, int dir) {
    return dir >= 0 && IS_SET(VIRTUAL_EXIT(room, dir)->exit_info, EX_WALLED);
}
P_obj read_object(int vnum, int mode) {
    assert(vnum == VOBJ_WALLS && mode == VIRTUAL);
    auto *obj = new obj_data{}; obj->R_num = vnum; return obj;
}
char *str_dup(const char *text) { return strdup(text); }
void obj_to_room(P_obj obj, int room) {
    obj->loc_p = LOC_ROOM; obj->loc.room = room;
    obj->next_content = world[room].contents; world[room].contents = obj;
}
void set_obj_affected(P_obj obj, int ticks, sh_int tag, sh_int) {
    assert(tag == TAG_OBJ_DECAY); timers[obj] = ticks;
}
void event_falling_obj(P_char, P_char, P_obj, void *) { assert(false); }
nevent_schedule_result add_event(event_func, int, P_char, P_char, P_obj, int, const void *, int) {
    assert(false); return {};
}
int wall_generic(P_obj, P_char, int, char *);
void Decay(P_obj obj) {
    assert(wall_generic(obj, nullptr, CMD_DECAY, nullptr));
    P_obj *link = &world[obj->loc.room].contents;
    while (*link != obj) { assert(*link); link = &(*link)->next_content; }
    *link = obj->next_content;
    timers.erase(obj);
    free(obj->description); free(obj->short_description); delete obj;
}
'''


def production():
    code = "\n".join(extract_function(file, signature) for file, signature in [
        ("sillusionist.c", "static int illusion_wall_decay("),
        ("sillusionist.c", "static int watching_wall_strength("),
        ("sillusionist.c", "int watching_wall_vision_roll("),
        ("sillusionist.c", "int watching_wall_vision_gap("),
        ("magic/spells.c", "int wall_climb_roll("),
        ("magic/spells.c", "int wall_climb_above("),
        ("magic/spells.c", "int wall_hit_lag("),
        ("magic/spells.c", "\nbool create_walls("),
        ("magic/spells.c", "\nbool exit_wallable("),
        ("sillusionist.c", "void spell_watching_wall("),
        ("magic.c", "static int dispel_magic_wall_damage("),
    ])
    dispel = extract_function("magic.c", "void spell_dispel_magic(")
    start = dispel.index("\tif (obj->R_num == real_object(VOBJ_WALLS))")
    end = dispel.index('\n\t/* casting is on a "normal" object', start)
    code += "\nint real_object(int vnum) { return vnum; }\n"
    code += "void spell_dispel_magic(int level, P_char ch, char *, int, P_char, P_obj obj) { P_obj temp_wall, next_obj;\n"
    code += dispel[start:end] + "assert(false); }\n"
    wall = extract_function("specs.object.c", "int wall_generic(")
    # Keep the actual control flow leading into the relevant passage cases.
    prefix_end = wall.index("\tswitch (type)")
    start = wall.index("\tcase WALL_OUTPOST:", prefix_end)
    end = wall.index("\tcase WALL_OF_STONE:", start)
    code += "\n#define time wall_time\n" + wall[:prefix_end]
    code += "switch (type) {\n" + wall[start:end] + "default: assert(false); } return FALSE; }\n#undef time\n"
    return code


DRIVER = r'''
static void reset() {
    for (int room = 0; room < 3; ++room) {
        while (world[room].contents) Decay(world[room].contents);
        rooms[room] = {}; rooms[room].number = 1000 + room;
    }
    assert(timers.empty());
    exits[0] = {}; exits[1] = {};
    exits[0].to_room = 1; exits[1].to_room = 0;
    rooms[0].dir_option[DIR_NORTH] = &exits[0];
    rooms[1].dir_option[DIR_SOUTH] = &exits[1];
    owner = {}; actor = {}; owner_pc = {}; actor_pc = {};
    owner.only.pc = &owner_pc; owner_pc.pid = 7; owner.in_room = 0;
    actor.only.pc = &actor_pc; actor_pc.pid = 8; actor.in_room = 0;
    owner.player.level = 50; actor.player.level = 40; actor.points.damroll = 8;
    character_list = &owner; owner.next = &actor;
    now = 100; roll = draws = views = moves = hurt = lag = 0;
    visible = true; climbing = false;
    char direction[] = "north";
    spell_watching_wall(50, &owner, direction, SPELL_TYPE_SPELL, nullptr, nullptr);
    for (int room = 0; room < 2; ++room) {
        P_obj obj = rooms[room].contents;
        assert(obj && !obj->next_content);
        assert(obj->value[0] == 1000 + (1 - room));
        assert(obj->value[1] == (room ? DIR_SOUTH : DIR_NORTH));
        assert(obj->value[2] == 50 && obj->value[3] == WATCHING_WALL);
        assert(obj->value[4] == 50 && obj->value[5] == 7);
        assert(timers.at(obj) == 1800);
        assert(IS_SET(exits[room].exit_info, EX_WALLED));
        assert(IS_SET(exits[room].exit_info, EX_BREAKABLE));
    }
    owner.in_room = 2;
}
static bool hit(P_obj wall, P_char ch = &actor) {
    char arg[] = "wall north";
    return wall_generic(wall, ch, CMD_HIT, arg);
}
static void vision() {
    // An eligible hit can show one room view and still damages the wall.
    for (int result : {0, 1, 2}) {
        reset(); roll = result; P_obj wall = rooms[0].contents;
        assert(hit(wall));
        assert(views == int(result == 0) && draws == 1);
        assert(wall->value[2] == 32 && wall->value[6] == now);
        assert(hurt == 20 && lag == wall_hit_lag());
        now = 110; assert(hit(wall)); // exactly 10 seconds remains in cooldown
        assert(views == int(result == 0) && draws == 1 && wall->value[2] == 14);
    }
    reset(); P_obj wall = rooms[0].contents;
    assert(!wall_generic(wall, &actor, CMD_LOOK, nullptr));
    assert(views == 1 && draws == 1);
    now = 110; wall_generic(wall, &actor, CMD_LOOK, nullptr);
    assert(views == 1 && draws == 1);
    now = 111; wall_generic(wall, &actor, CMD_LOOK, nullptr);
    assert(views == 2 && draws == 2);
    actor.in_room = 1; wall_generic(rooms[1].contents, &actor, CMD_LOOK, nullptr);
    assert(views == 3 && draws == 3); // each side has its own clock

    for (int condition = 0; condition < 4; ++condition) {
        reset(); wall = rooms[0].contents;
        if (condition == 0) character_list = &actor; // absent owner
        if (condition == 1) owner.in_room = actor.in_room;
        if (condition == 2) actor.player.level = MAXLVLMORTAL + 1;
        if (condition == 3) actor.specials.z_cord = 1;
        wall_generic(wall, &actor, CMD_LOOK, nullptr);
        assert(views == 0 && draws == 0);
        assert(wall->value[6] == (condition < 2 ? now : 0));
        if (condition < 2) {
            assert(hit(wall)); // owner availability must never gate wall damage
            assert(wall->value[2] == 32 && views == 0);
        }
    }
}
static void hits() {
    for (int type : {WATCHING_WALL, WALL_OF_STONE, WALL_OF_BONES, WALL_OF_ICE,
                     WALL_OF_IRON, WALL_OF_FORCE, WALL_OUTPOST}) {
        reset(); P_obj wall = rooms[0].contents;
        wall->value[3] = type; wall->value[6] = now;
        const int wear = type == WALL_OF_IRON ? 14 : type == WALL_OF_FORCE ? 12 :
                         type == WALL_OUTPOST ? 1 : 18;
        assert(hit(wall) && wall->value[2] == 50 - wear);
        assert(views == 0 && draws == 0);
    }
    reset(); P_obj wall = rooms[0].contents; visible = false;
    wall->value[6] = now;
    assert(hit(wall) && wall->value[2] == 44);
    char wrong[] = "wall south";
    assert(!wall_generic(wall, &actor, CMD_HIT, wrong));
    assert(wall->value[2] == 44);
    assert(!wall_generic(wall, &actor, CMD_HIT, nullptr));
}
static void passage() {
    for (int type : {WATCHING_WALL, WALL_OF_IRON, WALL_OUTPOST}) {
        for (int result : {0, 60, 61, 100}) {
            reset(); roll = result;
            rooms[0].contents->value[3] = type;
            rooms[0].contents->value[6] = now;
            climbing = result != 0;
            assert(wall_generic(rooms[0].contents, &actor, CMD_NORTH, nullptr));
            assert(moves == int(result > 60) && actor.in_room == int(result > 60));
        }
    }
    for (bool trusted : {false, true}) {
        reset(); rooms[0].contents->value[6] = now;
        if (trusted) actor.player.level = MAXLVLMORTAL + 1;
        else SET_BIT(actor.specials.affected_by, AFF_WRAITHFORM);
        assert(wall_generic(rooms[0].contents, &actor, CMD_NORTH, nullptr));
        assert(actor.in_room == 1 && moves == 1);
    }
    reset(); rooms[0].contents->value[6] = now;
    assert(!wall_generic(rooms[0].contents, &actor, CMD_SOUTH, nullptr));
    assert(moves == 0);
}
static void cleanup() {
    for (int mode = 0; mode < 3; ++mode) {
        reset(); P_obj wall = rooms[0].contents;
        // Expiry runs the decay proc for each of the two scheduled objects.
        if (mode == 0) { Decay(wall); Decay(rooms[1].contents); }
        // These hits run the production wall-dispel branch, which removes both.
        if (mode == 1) { owner.in_room = 0; assert(hit(wall, &owner)); }
        if (mode == 2) { wall->value[2] = 1; assert(hit(wall)); }
        assert(!rooms[0].contents && !rooms[1].contents && timers.empty());
        for (const auto &exit : exits)
            assert(!IS_SET(exit.exit_info, EX_WALLED | EX_BREAKABLE | EX_ILLUSION));
    }
}
int main() {
    vision(); hits(); passage(); cleanup();
    puts("Watching Wall: views, hits, passage, expiry and dispel passed");
}
'''


def main():
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="watching-wall-", dir=build) as directory:
        cpp, binary = Path(directory) / "wall.cpp", Path(directory) / "wall"
        cpp.write_text(PRELUDE + production() + DRIVER)
        subprocess.run([
            "g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
            "-Wno-unused-parameter", "-Wno-unused-variable", "-Wno-unused-but-set-variable",
            "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
            "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
            "-ffunction-sections", "-fdata-sections", "-I" + str(ROOT / "src"),
            str(cpp), str(HARNESS_STUBS), str(source("safe_format.c")),
            "-Wl,--gc-sections", "-o", str(binary),
        ], check=True)
        subprocess.run([str(binary)], check=True, env={**os.environ,
            "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1",
            "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1"})


if __name__ == "__main__":
    main()
