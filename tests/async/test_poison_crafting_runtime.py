#!/usr/bin/env python3
"""Run real poison recipes, ingredient selection, mixing and apply commands.

Object allocation/custody and visibility are fixtures. Recipe data, full command
bodies and input selection are production code; vial dose data is read from the
checked-in world prototypes. Run under ASan/UBSan.
"""

from pathlib import Path
import json
import os
import re
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function, source


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "net/comm.h"
#include "world/db.h"
#include "world/vnum.obj.h"
#include "item/objmisc.h"
#include "classes/salchemist.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <map>
#include <set>
#include <string>
#include <vector>

static char_data crafter{}, recipient{};
static int mixing, applying, next_index, extracted, waits, fail_vnum;
static index_data indices[128]{};
P_index obj_index = indices;
static std::map<int, int> object_indices;
static std::map<int, std::string> prototype_names;
static std::set<P_obj> live_objects;
static std::set<const char *> owned_strings;
static std::map<P_obj, P_char> carrying;
static std::string output;
const char *fill_words[] = {"in", "from", "with", "the", "on", "at", "to", "\n"};

int GET_CHAR_SKILL_P(P_char, int skill) {
    return skill == SKILL_MIXPOISON ? mixing : skill == SKILL_APPLY_POISON ? applying : 0;
}
bool notch_skill(P_char, int, float) { return false; }
void CharWait(P_char, int duration) { waits += duration; }
void send_to_char(const char *text, P_char) { output += text; }
void act(const char *text, int, P_char, P_obj, void *, int) { output += text; }
char *str_dup(const char *text) {
    char *copy = strdup(text); assert(copy); owned_strings.insert(copy); return copy;
}
static void release_string(const char *text) {
    if (owned_strings.erase(text)) std::free(const_cast<char *>(text));
}
void set_short_description(P_obj obj, const char *text) {
    release_string(obj->short_description); obj->short_description = str_dup(text);
}
void obj_from_char(P_obj obj) {
    if (!carrying.count(obj)) return;
    auto *ch = carrying[obj];
    for (auto **at = &ch->carrying; *at; at = &(*at)->next_content) if (*at == obj) {
        *at = obj->next_content; obj->next_content = nullptr; carrying.erase(obj); return;
    }
    assert(false);
}
void obj_to_char(P_obj obj, P_char ch) {
    assert(!carrying.count(obj)); obj->next_content = ch->carrying; ch->carrying = obj;
    carrying[obj] = ch;
}
void extract_obj(P_obj obj, int) {
    assert(live_objects.erase(obj)); obj_from_char(obj);
    release_string(obj->name); release_string(obj->short_description); delete obj; ++extracted;
}
void weight_change_object(P_obj obj, int difference) { obj->weight += difference; }
void name_from_drinkcon(P_obj) {}
static int object_index(int vnum) {
    if (!object_indices.count(vnum)) {
        assert(next_index < 128); object_indices[vnum] = next_index;
        indices[next_index++].virtual_number = vnum;
    }
    return object_indices[vnum];
}
int get_id_for(P_obj obj) { return OBJ_VNUM(obj); }
'''


SUPPORT = r'''
P_obj read_object(int vnum, int) {
    if (!vnum || vnum == fail_vnum) return nullptr;
    auto *obj = new obj_data{}; live_objects.insert(obj);
    obj->R_num = object_index(vnum);
    prototype_names.try_emplace(vnum, "ingredient" + std::to_string(vnum));
    obj->name = obj->short_description = prototype_names[vnum].data();
    obj->weight = 3;
    if (vnum == VOBJ_POISON_VIALS) {
        obj->type = ITEM_DRINKCON; obj->name = const_cast<char *>("vial");
    }
    for (auto &entry : poison_data) if (vnum == entry.vnum) {
        const auto &prototype = vial_prototypes.at(vnum);
        obj->type = ITEM_DRINKCON; obj->name = const_cast<char *>(prototype.name);
        obj->short_description = const_cast<char *>(prototype.description);
        obj->weight = prototype.weight;
        for (int i = 0; i < 8; ++i) obj->value[i] = prototype.values[i];
    }
    return obj;
}
P_obj get_obj_in_list_vis(P_char, const char *name, P_obj list, bool) {
    for (; list; list = list->next_content) if (isname(name, list->name)) return list;
    return nullptr;
}
'''


def production():
    text = source("salchemist.c").read_text()
    start = text.index("struct poison\n{")
    end = text.index("\n};", text.index("struct poison poison_data[]", start)) + 3
    code = text[start:end] + "\n"
    code += "struct vial_prototype { const char *name, *description; int values[8]; int weight; };\n"
    code += "static const std::map<int, vial_prototype> vial_prototypes = {\n"
    objects = (ROOT / "areas/obj/heavens.obj").read_text()
    for vnum in range(470, 477):
        block = re.search(rf"(?ms)^#{vnum}\n(.*?)(?=^#\d+\n)", objects)[1].splitlines()
        values = ",".join(block[5].split())
        weight = block[6].split()[0]
        code += "{" + str(vnum) + ",{" + json.dumps(block[0][:-1]) + "," + json.dumps(block[1][:-1]) + ",{" + values + "}," + weight + "}},\n"
    code += "};\n" + SUPPORT
    code += "\n".join(extract_function(file, signature) for file, signature in [
        ("handler.c", "bool isname(const char *str, const char *namelist)"),
        ("utility.c", "int strn_cmp("),
        ("interp.c", "int search_block("),
        ("interp.c", "int fill_word("),
        ("interp.c", "char *one_argument("),
        ("interp.c", "void argument_interpreter("),
        ("salchemist.c", "bool collect_required_objects("),
        ("salchemist.c", "P_obj get_vial("),
        ("salchemist.c", "char *print_poison_ingredients("),
        ("salchemist.c", "void do_mixpoison("),
        ("actobj.c", "void do_apply_poison("),
    ])
    return code


DRIVER = r'''
static void reset(int level = 56, int skill = 100) {
    while (!live_objects.empty()) extract_obj(*live_objects.begin());
    assert(carrying.empty() && owned_strings.empty());
    crafter = {}; recipient = {};
    for (auto *ch : {&crafter, &recipient}) {
        SET_POS(ch, POS_STANDING + STAT_NORMAL); ch->player.level = level;
        ch->player.name = const_cast<char *>("Crafter");
    }
    mixing = skill; applying = 100; extracted = waits = fail_vnum = 0; output.clear();
}
static P_obj supply(int vnum, P_char ch = &crafter) {
    auto *obj = read_object(vnum, VIRTUAL); assert(obj); obj_to_char(obj, ch); return obj;
}
static int count(P_char ch) {
    int count = 0; for (auto *obj = ch->carrying; obj; obj = obj->next_content) ++count; return count;
}
static void inputs(poison &recipe, bool vial = true, bool missing = false) {
    if (vial) supply(VOBJ_POISON_VIALS);
    for (int i = 0; recipe.ingredients[i]; ++i) if (!missing || i) supply(recipe.ingredients[i]);
}
static void mix(const char *argument = "") {
    char command[64]; std::strcpy(command, argument); do_mixpoison(&crafter, command, 0);
}
static void boundaries() {
    struct expected { int type, level, skill; } matrix[] = {
        {POISON_LIFELEAK,30,1}, {POISON_WEAKNESS,30,1}, {POISON_MOVELEAK,36,50},
        {POISON_SLOWNESS,41,70}, {POISON_NEUROTOXIN,46,80},
        {POISON_HEART_TOXIN,46,80}, {POISON_MADNESS,51,100}
    };
    for (auto entry : matrix) {
        poison *recipe = nullptr;
        for (auto &row : poison_data) if (row.poison_type == entry.type) recipe = &row;
        assert(recipe && recipe->level_required == entry.level && recipe->skill_required == entry.skill);
        for (int level : {entry.level-1, entry.level, entry.level+1})
        for (int skill : {entry.skill-1, entry.skill, entry.skill+1}) {
            if (skill > 100) continue;
            reset(level, skill); inputs(*recipe); int before = count(&crafter);
            mix("list");
            bool eligible = level >= entry.level && skill >= entry.skill;
            assert((output.find(vial_prototypes.at(recipe->vnum).description) != std::string::npos) == eligible);
            assert(count(&crafter) == before);
            output.clear(); mix();
            if (eligible) {
                assert(count(&crafter) == 1 && OBJ_VNUM(crafter.carrying) == recipe->vnum);
                assert(extracted >= before && crafter.carrying->value[1] == 3);
                assert(crafter.carrying->value[3] == recipe->poison_type);
                assert(output.find("finish mixing") != std::string::npos);
            } else assert(count(&crafter) == before);
        }
    }
}
static void conservation() {
    auto &recipe = poison_data[0];
    reset(); fail_vnum = recipe.vnum;
    mix("list");
    assert(output.find(vial_prototypes.at(recipe.vnum).description) == std::string::npos);
    for (int failure : {0,1,2}) {
        reset(); inputs(recipe, failure != 0, failure == 1);
        int before = count(&crafter); if (failure == 2) fail_vnum = recipe.vnum;
        mix(); assert(count(&crafter) == before && extracted == 0);
    }
    reset(); supply(VOBJ_POISON_VIALS);
    std::set<int> ingredients;
    for (auto &row : poison_data) for (int value : row.ingredients) if (value) ingredients.insert(value);
    for (int value : ingredients) supply(value);
    int before = count(&crafter), used = 1;
    for (int value : recipe.ingredients) used += value != 0;
    mix();
    assert(OBJ_VNUM(crafter.carrying) == recipe.vnum);
    assert(count(&crafter) == before - used + 1 && extracted == used);
    assert(waits == 2 * PULSE_VIOLENCE);
    printf("First eligible recipe consumes %d inputs and makes 3 doses; mixing wait=%d pulses\n", used, waits);
}
static void transfer_and_apply() {
    reset(); auto *vial = supply(VOBJ_POISON_VIAL_MADNESS);
    obj_from_char(vial); obj_to_char(vial, &recipient);
    recipient.player.level = 30; mixing = 1;
    auto *weapon = supply(22810, &recipient); weapon->type = ITEM_WEAPON; weapon->name = const_cast<char *>("weapon");
    char argument[] = "madness weapon";
    do_apply_poison(&recipient, argument, 0);
    assert(weapon->value[4] == POISON_MADNESS && vial->value[1] == 2 && vial->weight == -1);
    assert(GET_OBJ_WEIGHT(vial) == 0); // Production vials are weightless; effective weight clamps at zero.
    // Already coated weapons carry only the ID when handed to another user.
    obj_from_char(weapon); obj_to_char(weapon, &crafter);
    assert(weapon->value[4] == POISON_MADNESS);
    reset(); vial = supply(VOBJ_POISON_VIAL_LIFELEAK); vial->value[1] = 1;
    weapon = supply(22810); weapon->type = ITEM_WEAPON; weapon->name = const_cast<char *>("weapon");
    char last[] = "lifeleak weapon";
    do_apply_poison(&crafter, last, 0);
    assert(weapon->value[4] == POISON_LIFELEAK && vial->value[1] == 0 && vial->value[2] == 0 && vial->value[3] == 0);
    vial->value[1] = 1; vial->value[2] = LIQ_POISON; vial->value[3] = POISON_WEAKNESS;
    vial->extra_flags |= ITEM_TRANSIENT;
    do_apply_poison(&crafter, last, 0);
    assert(!live_objects.count(vial) && weapon->value[4] == POISON_WEAKNESS);
}
int main() {
    boundaries(); conservation(); transfer_and_apply(); reset();
    puts("Poison crafting progression, conservation, transfer and apply regressions passed");
}
'''


def main():
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="poison-crafting-", dir=build) as directory:
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
