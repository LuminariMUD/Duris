#!/usr/bin/env python3
"""Run the real eat command and affect countdown against maintained fish data.

Object custody, affect allocation and unrelated game services are fixtures.
No shared server, database or checkout .env is used.
"""

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "magic/spells.h"
#include "world/events.h"
#include "world/falling.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>

static char_data eater{};
static pc_only_data pc{};
static std::string output;
static int consumed;
static index_data indices[12]{};
P_index obj_index = indices;
P_char character_list = &eater;
P_room world = nullptr;
extern const struct racial_data_type racial_data[];
const struct racial_data_type racial_data[LAST_RACE + 1] = {};
const char *fill_words[] = {"in", "from", "with", "the", "on", "at", "to", "\n"};

void act(const char *text, int, P_char, P_obj, void *, int) { output += text; }
void send_to_char(const char *text, P_char) { output += text; }
void send_to_char_f(P_char, const char *, ...) { assert(false); }
P_obj get_obj_in_list_vis(P_char, const char *name, P_obj list, bool) {
    for (; list; list = list->next_content) if (isname(name, list->name)) return list;
    return nullptr;
}
void extract_obj(P_obj obj, int) {
    auto **at = &eater.carrying;
    while (*at && *at != obj) at = &(*at)->next_content;
    assert(*at == obj); *at = obj->next_content; delete obj; ++consumed;
}
affected_type *affect_to_char(P_char ch, affected_type *af) {
    auto *copy = new affected_type(*af);
    copy->next = ch->affected; ch->affected = copy; return copy;
}
void affect_remove(P_char ch, affected_type *af) {
    auto **at = &ch->affected;
    while (*at && *at != af) at = &(*at)->next;
    assert(*at == af); *at = af->next; delete af;
}
void wear_off_message(P_char, affected_type *) {}
int hit_regen(P_char, bool) { assert(false); return 0; }
void StartRegen(P_char, regen_resource) { assert(false); }
void remove_disguise(P_char, bool) { assert(false); }
P_char un_morph(P_char) { assert(false); return nullptr; }
bool char_falling(P_char) { return false; }
falling_start_result falling_start(P_char) { assert(false); return {}; }
struct time_info_data age(P_char) { return {}; }
int IS_MORPH(P_char) { return false; }
int GET_CLASS(P_char, uint) { return 0; }
int GET_PRIME_CLASS(P_char, uint) { return 0; }
int GET_SECONDARY_CLASS(P_char, uint) { return 0; }
void advance_level(P_char) { assert(false); }
bool do_save_silent(P_char, int) { assert(false); return false; }
void arti_clear_sql(P_char, char *) { assert(false); }
int char_light(P_char) { return 0; }
int room_light(int, int) { return 0; }
int real_room(int room) { return room; }
int number(int low, int) { return low; }
'''


def production():
    objects = (ROOT / "areas/obj/heavens.obj").read_text()
    code = "struct fish_prototype { int vnum, type; const char *name; int values[8]; };\n"
    code += "static const fish_prototype prototypes[] = {\n"
    for vnum in (293, 294, 295, 318, 319, 330, 332, 333, 334, 335, 355, 356):
        block = re.search(rf"(?ms)^#{vnum}\n(.*?)(?=^#\d+\n)", objects)[1].splitlines()
        values = ",".join(block[5].split())
        code += "{" + str(vnum) + "," + block[4].split()[0] + "," + json.dumps(block[0][:-1]) + ",{" + values + "}},\n"
    code += "};\n"
    code += "\n".join(extract_function(file, signature) for file, signature in (
        ("utility.c", "int strn_cmp("),
        ("sparser.c", "char *skip_spaces("),
        ("handler.c", "bool isname(const char *str, const char *namelist)"),
        ("interp.c", "int search_block("),
        ("interp.c", "int fill_word("),
        ("interp.c", "char *one_argument("),
        ("affects.c", "bool affected_by_spell(P_char ch, int skill)"),
        ("handler.c", "unsigned int char_slice(P_char c, unsigned int slices)"),
        ("actobj.c", "void do_eat("),
    ))
    code += "\n#define AFFECT_UPDATE_SLICES 20\n"
    return code + extract_function("affects.c", "void affect_update(int pulse)")


DRIVER = r'''
static void reset() {
    while (eater.carrying) extract_obj(eater.carrying);
    while (eater.affected) affect_remove(&eater, eater.affected);
    eater = {}; pc = {}; eater.only.pc = &pc;
    eater.player.level = 30; eater.player.race = RACE_HUMAN;
    eater.player.name = const_cast<char *>("Perchtest");
    consumed = 0; output.clear();
}
static P_obj supply(int vnum) {
    for (int i = 0; i < 12; ++i) if (prototypes[i].vnum == vnum) {
        const auto &p = prototypes[i];
        auto *obj = new obj_data{};
        indices[i].virtual_number = vnum;
        obj->R_num = i; obj->type = p.type; obj->name = const_cast<char *>(p.name);
        std::memcpy(obj->value, p.values, sizeof(obj->value));
        obj->next_content = eater.carrying; eater.carrying = obj;
        return obj;
    }
    assert(false); return nullptr;
}
static void eat(const char *name) {
    char argument[64]; std::strcpy(argument, name); do_eat(&eater, argument, 0);
}
static int food_bonus(int location) {
    int value = 0;
    for (auto *af = eater.affected; af; af = af->next)
        if (af->location == location) value += af->modifier;
    return value;
}
static void perch() {
    reset(); supply(356); eat("perch");
    assert(consumed == 1 && !eater.carrying);
    assert(food_bonus(APPLY_HIT_REG) == 30 && food_bonus(APPLY_MOVE_REG) == 15);
    int count = 0;
    for (auto *af = eater.affected; af; af = af->next) {
        assert(af->type == TAG_EATEN && af->duration == 10);
        assert(af->location == APPLY_HIT_REG || af->location == APPLY_MOVE_REG);
        ++count;
    }
    assert(count == 2 && food_bonus(APPLY_HITROLL) == 0 && food_bonus(APPLY_DAMROLL) == 0);
    auto *second = supply(356); output.clear(); eat("perch");
    assert(output.find("sated already") != std::string::npos);
    assert(consumed == 1 && eater.carrying == second);
    assert(food_bonus(APPLY_HIT_REG) == 30 && food_bonus(APPLY_MOVE_REG) == 15);

    // Use the shared countdown unchanged: ordinary affects reach zero before
    // being removed on the following tick boundary.
    for (int remaining = 9; remaining >= 0; --remaining) {
        affect_update(0);
        for (auto *af = eater.affected; af; af = af->next) assert(af->duration == remaining);
        assert(food_bonus(APPLY_HIT_REG) == 30 && food_bonus(APPLY_MOVE_REG) == 15);
    }
    affect_update(0); assert(!eater.affected);
    eat("perch"); assert(consumed == 2 && food_bonus(APPLY_HIT_REG) == 30);
}
static void retained_instance() {
    reset(); auto *old = supply(356);
    old->value[1] = old->value[2] = 0; // Previously caught instance's stored values.
    eat("perch");
    assert(consumed == 1 && food_bonus(APPLY_HIT_REG) == 15 && food_bonus(APPLY_MOVE_REG) == 15);
    auto *fresh = supply(356); output.clear(); eat("perch");
    assert(output.find("sated already") != std::string::npos && eater.carrying == fresh);
    while (eater.affected) affect_remove(&eater, eater.affected);
    eat("perch");
    assert(consumed == 2 && food_bonus(APPLY_HIT_REG) == 30 && food_bonus(APPLY_MOVE_REG) == 15);
}
static void neighboring_fish() {
    struct { int vnum, hp, movement, hitdam, duration; } expected[] = {
        {293,135,9,0,18}, {294,150,9,0,9}, {295,105,7,0,10}, {318,90,8,2,12},
        {319,120,6,0,15}, {330,90,6,0,7}, {332,120,6,0,4}, {333,120,6,1,4},
        {334,60,4,0,4}, {335,75,5,0,3}, {355,45,5,0,10},
    };
    for (auto entry : expected) {
        reset(); supply(entry.vnum); eat("fish");
        assert(consumed == 1 && food_bonus(APPLY_HIT_REG) == entry.hp);
        assert(food_bonus(APPLY_MOVE_REG) == entry.movement);
        assert(food_bonus(APPLY_HITROLL) == entry.hitdam && food_bonus(APPLY_DAMROLL) == entry.hitdam);
        for (auto *af = eater.affected; af; af = af->next) assert(af->duration == entry.duration);
    }
}
int main() {
    perch(); retained_instance(); neighboring_fish(); reset();
    puts("Perch +30 HP/+15 movement, duration 10, expiry, sated rejection, retained values and other fish passed");
}
'''


def main():
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="perch-food-", dir=build) as directory:
        cpp, binary = Path(directory) / "harness.cpp", Path(directory) / "harness"
        cpp.write_text(PRELUDE + production() + DRIVER)
        subprocess.run([
            "g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
            "-Wno-unused-parameter", "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
            "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
            "-I" + str(ROOT / "src"), str(cpp), str(HARNESS_STUBS), "-o", str(binary),
        ], check=True)
        subprocess.run([str(binary)], check=True, env={**os.environ,
            "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1",
            "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1"})


if __name__ == "__main__":
    main()
