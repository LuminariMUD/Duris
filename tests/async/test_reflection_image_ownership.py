#!/usr/bin/env python3
"""Create and clean up real Reflection images without damaging shared prototype strings."""

import os
import subprocess
import tempfile
from pathlib import Path

from _paths import HARNESS_STUBS, ROOT, extract_function


prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "classes/necromancy.h"
#include "combat/training_dummy.h"
#include "economy/collector_presence.h"
#include "magic/spells.h"
#include "net/comm.h"

#include <algorithm>
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <set>
#include <string>
#include <vector>

room_data rooms[1]{};
P_room world = rooms;
index_data indexes[1]{};
P_index mob_index = indexes;
const race_names race_names_table[LAST_RACE + 2] = {
    {"None", "None", "None", "NO"},
};

static char prototype_keys[] = "reflection image";
static char prototype_long[] = "A reflection image stands here.\r\n";
static char prototype_short[] = "a reflection image";
static std::set<const char *> owned_strings;
static std::vector<P_char> images;
static int random_call;

int BOUNDED(int low, int value, int high) { return std::max(low, std::min(value, high)); }
int number(int low, int high) {
    if (low == 0 && high == 3)
        return random_call++ == 0 ? 0 : 1;
    return low;
}
bool collector_presence_is_npc(P_char) { return false; }
bool training_dummy_capture_target_allowed(P_char) { return true; }
bool has_innate(P_char, int) { return false; }
P_obj get_globe(P_char) { return nullptr; }
P_char get_linked_char(P_char, ush_int) { return nullptr; }
void linked_affect_to_char(P_char mob, affected_type *af, P_char ch, int) {
    auto *copy = new affected_type(*af);
    copy->next = mob->affected;
    mob->affected = copy;
    mob->following = ch;
}
void remove_plushit_bits(P_char) {}
void clearMemory(P_char) {}
void remember(P_char, P_char) {}
void balance_affects(P_char) {}
void affect_remove(P_char ch, affected_type *af) {
    assert(ch->affected == af);
    ch->affected = af->next;
    delete af;
}
void stop_fighting(P_char ch) { ch->specials.fighting = nullptr; }
void StopAllAttackers(P_char) {}
void set_fighting(P_char ch, P_char victim) { ch->specials.fighting = victim; }
void char_from_room(P_char ch) { ch->in_room = NOWHERE; }
bool char_to_room(P_char ch, int room, int) { ch->in_room = room; return true; }
void add_follower(P_char mob, P_char ch) {
    auto *follow = new follow_type{};
    follow->follower = mob;
    follow->next = ch->followers;
    ch->followers = follow;
    mob->following = ch;
}
int real_mobile(int vnum) { return vnum == 250 ? 0 : -1; }
P_char read_mobile(int nr, int) {
    assert(nr == 0);
    auto *mob = new char_data{};
    mob->only.npc = new npc_only_data{};
    mob->only.npc->R_num = nr;
    mob->specials.act = ACT_ISNPC;
    SET_POS(mob, STAT_NORMAL + POS_STANDING);
    mob->player.name = indexes[nr].keys;
    mob->player.long_descr = indexes[nr].desc1;
    mob->player.short_descr = indexes[nr].desc2;
    images.push_back(mob);
    return mob;
}
void extract_char(P_char) { assert(false); }
char *str_dup(const char *text) {
    char *copy = strdup(text);
    assert(copy && owned_strings.insert(copy).second);
    return copy;
}
void str_free(const char *text) {
    assert(text && owned_strings.erase(text) == 1);
    free(const_cast<char *>(text));
}
'''

production = "\n".join([
    extract_function("necromancy.c", "int setup_pet("),
    extract_function("sillusionist.c", "void spell_reflection("),
])

driver = r'''
static void assert_prototype_unchanged() {
    assert(indexes[0].keys == prototype_keys);
    assert(indexes[0].desc1 == prototype_long);
    assert(indexes[0].desc2 == prototype_short);
    assert(!strcmp(indexes[0].keys, "reflection image"));
    assert(!strcmp(indexes[0].desc1, "A reflection image stands here.\r\n"));
    assert(!strcmp(indexes[0].desc2, "a reflection image"));
}

static void assert_images_and_cleanup(P_char caster) {
    assert(images.size() == 4);
    assert_prototype_unchanged();
    std::string expected_name = "image " + std::string(caster->player.name) + " None";
    std::string expected_long = std::string(caster->player.name) + " stands here.\r\n";

    for (P_char image : images) {
        assert(image->only.npc->str_mask ==
               (STRUNG_KEYS | STRUNG_DESC1 | STRUNG_DESC2));
        assert(image->player.name != indexes[0].keys);
        assert(image->player.long_descr != indexes[0].desc1);
        assert(image->player.short_descr != indexes[0].desc2);
        assert(!strcmp(image->player.name, expected_name.c_str()));
        assert(!strcmp(image->player.long_descr, expected_long.c_str()));
        assert(!strcmp(image->player.short_descr, caster->player.name));

        str_free(image->player.name);
        str_free(image->player.long_descr);
        str_free(image->player.short_descr);
        while (image->affected)
            affect_remove(image, image->affected);
        delete image->only.npc;
        delete image;
    }
    while (caster->followers) {
        follow_type *next = caster->followers->next;
        delete caster->followers;
        caster->followers = next;
    }
    images.clear();
    assert(owned_strings.empty());
    assert_prototype_unchanged();
}

int main() {
    indexes[0].virtual_number = 250;
    indexes[0].keys = prototype_keys;
    indexes[0].desc1 = prototype_long;
    indexes[0].desc2 = prototype_short;

    char_data player_caster{};
    pc_only_data player{};
    player_caster.only.pc = &player;
    player_caster.player.name = const_cast<char *>("Mirror");
    player_caster.player.level = 46;
    player_caster.in_room = 0;
    SET_POS(&player_caster, STAT_NORMAL + POS_STANDING);

    random_call = 0;
    spell_reflection(46, &player_caster, nullptr, 0, &player_caster, nullptr);
    assert_images_and_cleanup(&player_caster);

    char_data npc_caster{};
    npc_only_data npc{};
    npc_caster.only.npc = &npc;
    npc_caster.specials.act = ACT_ISNPC;
    npc_caster.player.name = const_cast<char *>("Echo");
    npc_caster.player.level = 46;
    npc_caster.in_room = 0;
    SET_POS(&npc_caster, STAT_NORMAL + POS_STANDING);

    random_call = 0;
    spell_reflection(46, &npc_caster, nullptr, 0, &npc_caster, nullptr);
    assert_images_and_cleanup(&npc_caster);

    puts("Reflection image loops preserved shared prototype strings and released every private name.");
}
'''

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="reflection-ownership-", dir=build) as directory:
    cpp = Path(directory) / "harness.cpp"
    binary = Path(directory) / "harness"
    cpp.write_text(prelude + production + driver)
    subprocess.run([
        "g++", "-std=c++20", "-g", "-ffunction-sections", "-fdata-sections",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        "-I" + str(ROOT / "src"), str(cpp), str(HARNESS_STUBS),
        "-Wl,--gc-sections", "-lbsd", "-o", str(binary),
    ], check=True)
    subprocess.run([str(binary)], check=True,
                   env={**os.environ, "ASAN_OPTIONS": "detect_leaks=0:halt_on_error=1"})
