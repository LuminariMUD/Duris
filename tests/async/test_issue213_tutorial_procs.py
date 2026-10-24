#!/usr/bin/env python3
"""Execute original/copied tutorial procedures with controlled engine boundaries."""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function

prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "cmd/interp.h"
#include "world/events.h"
#include "world/vnum.mob.h"
#include "world/vnum.obj.h"
#include "world/vnum.room.h"
#include "magic/spells.h"
#include <cassert>
#include <cstring>
#include <sstream>
#include <string>

room_data rooms[4]{};
P_room world = rooms;
index_data mobiles[6]{}, objects[8]{};
P_index mob_index = mobiles, obj_index = objects;
P_char guide = nullptr;
P_obj found = nullptr, requested = nullptr;
obj_data reward{};
nevent_data bandage{};
int reads = 0, last_read = 0, gifts = 0, xp = 0, extracted = 0, next_home = 0;
int armor_buffs = 0, bless_buffs = 0;
bool gate = true;
std::string output;
bool affected_by_spell(P_char, int tag) { assert(tag == TAG_LIFESTREAMNEWBIE); return gate; }
void affect_from_char(P_char, int tag) { assert(tag == TAG_LIFESTREAMNEWBIE); gate = false; }
char *one_argument(char *argument, char *word) {
    while (*argument == ' ') ++argument;
    while (*argument && *argument != ' ') *word++ = *argument++;
    *word = 0;
    while (*argument == ' ') ++argument;
    return argument;
}
P_char get_char_room_vis(P_char, const char *) { return guide; }
P_obj read_object(int vnum, int) { ++reads; last_read = vnum; return &reward; }
void act(const char *message, int, P_char, P_obj, void *, int) { output += message; }
void mobsay(P_char, const char *message) { output += message; }
void send_to_char(const char *message, P_char) { output += message; }
void do_look(P_char, char *, int) {}
void spell_armor(int, P_char, char *, int, P_char, P_obj) { ++armor_buffs; }
void spell_bless(int, P_char, char *, int, P_char, P_obj) { ++bless_buffs; }
void obj_to_char(P_obj, P_char) { ++gifts; }
int generic_find(const char *, int, P_char, P_char *character, P_obj *object) {
    *character = nullptr; *object = found; return FIND_OBJ_ROOM;
}
int real_room(int vnum) {
    if (vnum == 29201) return 1;
    if (vnum == VROOM_WUTVR_ENTRY) return 2;
    return 3;
}
void char_from_room(P_char ch) { ch->in_room = NOWHERE; }
bool char_to_room(P_char ch, int room, int) { ch->in_room = room; return true; }
void teleport_to(P_char ch, int room, int) { ch->in_room = room; }
void find_starting_location(P_char ch, int home) { assert(home == 0); GET_HOME(ch) = next_home; }
bool isname(const char *argument, const char *names) {
    std::istringstream words(argument);
    std::string word;
    while (words >> word) if (std::string(names).find(word) == std::string::npos) return false;
    return true;
}
P_obj get_obj_in_list_vis(P_char, const char *, P_obj, bool) { return requested; }
void obj_from_room(P_obj) {}
void obj_to_room(P_obj object, int room) { assert(object == &reward); assert(room == 0); }
P_nevent get_scheduled(P_char, event_func) { return &bandage; }
void event_bandage_check(P_char, P_char, P_obj, void *) {}
void do_stand(P_char, char *, int) {}
void do_say(P_char, char *, int) {}
void extract_char(P_char) { ++extracted; }
int gain_exp(P_char, P_char, int amount, int kind) { assert(kind == EXP_QUEST); xp += amount; return amount; }
'''

cases = r'''
int main() {
    char_data player{}, teacher{}, wife{}, man{};
    npc_only_data teacher_npc{}, wife_npc{}, man_npc{};
    teacher.only.npc = &teacher_npc;
    wife.only.npc = &wife_npc;
    man.only.npc = &man_npc;
    for (auto *ch : {&teacher, &wife, &man}) {
        ch->specials.act = ACT_ISNPC;
        ch->specials.position = STAT_NORMAL;
    }
    player.specials.position = STAT_NORMAL;
    player.points.max_hit = 100;
    guide = &teacher;
    obj_data controller{}, item{};
    controller.R_num = 0;
    found = &controller;
    for (int cmd : {CMD_LOOK, CMD_EXAMINE, CMD_READ}) {
        char sign[] = "sign";
        assert(newbie_sign1(&controller, &player, cmd, sign));
        assert(newbie_sign2(&controller, &player, cmd, sign));
    }
    assert(armor_buffs == 3 && bless_buffs == 3);
    for (bool copied : {false, true}) {
        mobiles[0].virtual_number = copied ? VMOB_CHAOS_GUIDE : 22801;
        objects[0].virtual_number = copied ? VOBJ_CHAOS_STREAM : 22803;
        gate = true; reads = gifts = 0;
        char enter[] = "stream", ask[] = "reaver racewars";
        player.in_room = 0;
        player.points.hit = 1;
        assert(stream_of_life(&controller, &player, CMD_ENTER, enter));
        assert(player.in_room == 0 && player.points.hit == 1 && gifts == 0);
        assert(newbie_paladin(&teacher, &player, CMD_ASK, ask));
        assert(!gate && reads == 1 && gifts == 1);
        assert(last_read == (copied ? VOBJ_CHAOS_SWORD_BLESSED : VOBJ_NEWBIE2_SWORD_BLESSED));
        assert(newbie_paladin(&teacher, &player, CMD_ASK, ask));
        assert(reads == 1 && gifts == 1);
        assert(stream_of_life(&controller, &player, CMD_ENTER, enter));
        assert(player.in_room == (copied ? 2 : 1) && player.points.hit == 100);
        assert(reads == 1 && gifts == 1); // entering the next stage grants no second kit

        player.in_room = 0;
        next_home = copied ? 15296 : 39100;
        assert(newbie_portal(&controller, &player, CMD_ENTER, enter));
        assert(GET_HOME(&player) == next_home);
        assert(GET_BIRTHPLACE(&player) == next_home && GET_ORIG_BIRTHPLACE(&player) == next_home);

        objects[0].virtual_number = copied ? VOBJ_WUTVR_MAP_PROC : 29328;
        char map[] = "grubruk map", original_map[] = "burbul map";
        reads = gifts = 0;
        assert(burbul_map_obj(&controller, &player, CMD_ASK, copied ? map : original_map));
        assert(last_read == (copied ? VOBJ_WUTVR_MAP : 29201) && gifts == 1);

        // The requested item differs from the bound search-controller object.
        // Both replenishment cases must retain the controller's copied context.
        objects[0].virtual_number = copied ? VOBJ_WUTVR_SEARCH_PROC : 29329;
        player.in_room = 0;
        requested = &item;
        for (bool salt : {false, true}) {
            reward.extra_flags = 0;
            char salt_name[] = "salt", tears_name[] = "tears";
            assert(chyron_search_obj(&controller, &player, CMD_GET, salt ? salt_name : tears_name));
            assert(last_read == (salt ? (copied ? VOBJ_WUTVR_SALT : 29220) :
                                             (copied ? VOBJ_WUTVR_TEARS : 29221)));
            assert(IS_SET(reward.extra_flags, ITEM_SECRET));
        }

        wife_npc.R_num = 1; man_npc.R_num = 2;
        mobiles[1].virtual_number = copied ? VMOB_WUTVR_WIFE : VMOB_AILVIO_WIFE;
        mobiles[2].virtual_number = copied ? VMOB_AILVIO_INCAPACITATED : VMOB_WUTVR_INCAPACITATED;
        rooms[0].people = &player;
        bandage.victim = &man;
        xp = extracted = 0;
        bandage_reward_mob(&wife, &player, CMD_PERIODIC, nullptr);
        assert(xp == 0 && extracted == 0); // the other tutorial's victim is not ours
        mobiles[2].virtual_number = copied ? VMOB_WUTVR_INCAPACITATED : VMOB_AILVIO_INCAPACITATED;
        bandage_reward_mob(&wife, &player, CMD_PERIODIC, nullptr);
        assert(xp == 1000 && extracted == 2);
    }
}
'''

functions = [extract_function("specs.object.c", signature) for signature in (
    "int stream_of_life(", "int newbie_portal(", "int newbie_sign1(", "int newbie_sign2(",
)]
functions += [extract_function("specs.mobile.c", "int newbie_paladin(")]
functions += [extract_function("specs.ailvio.c", signature) for signature in (
    "int burbul_map_obj(", "int chyron_search_obj(", "int bandage_reward_mob(",
)]
directory = ROOT / "bin/tests"
directory.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="tutorial-procs-", dir=directory) as temporary:
    root = Path(temporary)
    program = root / "harness.cpp"
    program.write_text(prelude + "\n".join(functions) + cases)
    binary = root / "harness"
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Isrc",
                    "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
                    str(program), str(HARNESS_STUBS), "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=10)
print("original/copied tutorial gate, rewards, routing, map/search and bandage dispatch passed")
