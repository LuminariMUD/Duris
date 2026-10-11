#!/usr/bin/env python3
"""Drive the real randobj command with recording generators, under ASan/UBSan.

The slot tables, wear words, tokenizer, numeric-word predicate and colour stripping
come from the server. Generators record their inputs; the golden harness separately
proves their output. Recipe rejection and delivery use the real create_recipe(), with
a controlled crafting availability gate. This test never starts a server or changes
world/account data.
"""
import os
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function

HARNESS = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "item/objmisc.h"
#include "economy/tradeskill.h"
#include "economy/crafting.h"
#include "world/db.h"
#include "item/random_equipment.h"
#include "world/vnum.obj.h"
#include "cmd/interp.h"
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <utility>

extern flagDef wear_bits[];
void do_randobj(P_char, char *, int);
static char_data staff{}, generated_mob{};
static pc_only_data player{};
static index_data prototypes[1]{};
P_index obj_index = prototypes;
struct request { std::string kind; int finder_level, source_level, slot; };
static std::vector<request> requests;
static std::vector<P_obj> inventory;
static std::vector<std::pair<int, int>> rolls;
static std::string output;
static int stats, recipes, samples, extracted, maps, removals, zones, fail_at;
static bool reject_recipe;
static std::vector<int> recipe_rejections;

void send_to_char(const char *text, P_char ch) { assert(ch == &staff); output += text; }
void send_to_char_f(P_char ch, const char *format, ...) {
    char buffer[16384];
    va_list args; va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args); va_end(args);
    send_to_char(buffer, ch);
}
void act(const char *text, int, P_char ch, P_obj, void *, int) { send_to_char(text, ch); }
void wizlog(int, const char *, ...) {}
int number(int low, int high) {
    assert(low <= high); rolls.emplace_back(low, high); return high;
}
static void release(P_obj obj) {
    free(obj->name); free(obj->short_description); delete obj;
}
static P_obj object(const char *kind, int finder_level = 0, int source_level = 0, int slot = -1) {
    requests.push_back({kind, finder_level, source_level, slot});
    if (fail_at && static_cast<int>(requests.size()) == fail_at) return nullptr;
    auto *obj = new obj_data{};
    obj->name = strdup("test item"); obj->short_description = strdup("a test item");
    return obj;
}
P_obj create_random_eq(P_char ch, int finder_level, int source_level, int slot, int material) {
    assert(ch == &staff && GET_LEVEL(ch) == 62 && ch->in_room == 123 && material == -1);
    return object("eq", finder_level, source_level, slot);
}
P_obj create_material(P_char ch, int finder_level, int source_level) {
    assert(ch == &staff && GET_LEVEL(ch) == 62);
    return object("piece", finder_level, source_level);
}
P_obj create_stones() { return object("stone"); }
P_obj random_zone_item(P_char ch) {
    assert(ch == &staff);
    P_obj obj = object("zone-item");
    obj_index[0].virtual_number = reject_recipe ? VOBJ_RANDOM_WEAPON : 123;
    reject_recipe = false;
    if (obj && requests.size() <= recipe_rejections.size()) {
        switch (recipe_rejections[requests.size() - 1]) {
        case 1: obj->type = ITEM_CONTAINER; obj->contains = obj; break;
        case 2: obj->type = ITEM_STORAGE; obj->contains = obj; break;
        case 3: obj->bitvector = AFF_STONE_SKIN; break;
        case 4: obj->bitvector2 = AFF2_EARTH_AURA; break;
        case 5: obj->bitvector3 = AFF3_BLUR; break;
        case 6: obj->bitvector4 = AFF4_SANCTUARY; break;
        case 7: obj->affected[MAX_OBJ_AFFECT - 1].location = APPLY_COMBAT_PULSE; break;
        case 8: obj->affected[MAX_OBJ_AFFECT - 1].location = APPLY_SPELL_PULSE; break;
        case 9: obj->value[0] = -1; break; // Crafting availability/level gate rejects it.
        }
    }
    return obj;
}
void obj_to_char(P_obj obj, P_char ch) {
    assert(obj && ch == &staff); inventory.push_back(obj);
    if (obj->type == ITEM_SCROLL) recipes++;
}
void do_stat(P_char ch, char *argument, int command, P_obj obj) {
    assert(ch == &staff && !strcmp(argument, "o") && command == CMD_STAT);
    assert(obj == inventory.back()); stats++;
}
void extract_obj(P_obj obj, int) { assert(obj); extracted++; release(obj); }
P_obj read_object(int vnum, int mode) {
    assert(vnum == 400210 && mode == VIRTUAL);
    auto *obj = new obj_data{};
    obj->type = ITEM_SCROLL; obj->name = strdup("recipe");
    obj->short_description = strdup("a recipe for"); obj->str_mask = STRUNG_DESC2;
    return obj;
}
bool crafting_recipe_target_is_available(P_obj obj) { return obj->value[0] != -1; }
void crafting_configure_recipe_scroll(P_obj recipe, P_obj target) { assert(recipe && target); }
void debug(const char *, ...) {}
int itemvalue(P_obj) { return 1; }
char *str_dup(const char *text) { return strdup(text); }
void __free(void *ptr, const char *, int) { free(ptr); }
int checked_snprintf_at(const char *, int, char *buffer, size_t size, const char *format, ...) {
    va_list args; va_start(args, format);
    int result = vsnprintf(buffer, size, format, args); va_end(args); return result;
}
void describe_encrusted_enhanced(P_obj obj) {
    assert(obj && obj->affected[2].location == APPLY_MOVE_REG); samples++;
}
P_char create_random_mob(int theme, int level) {
    assert(theme == -1); requests.push_back({"mob", level, level, -1});
    if (fail_at && static_cast<int>(requests.size()) == fail_at) return nullptr;
    generated_mob.player.level = level ? level : 37;
    generated_mob.player.name = const_cast<char *>("a test mob");
    return &generated_mob;
}
int reset_lab(int type) { assert(type == removals); removals++; return 0; }
int create_lab(int type) { assert(type == maps); maps++; return 0; }
void create_zone(int theme, int a, int b, int c, int d) {
    assert(theme == 2 && a == 999 && b == 999 && c == 999 && d == 999); zones++;
}
static void reset() {
    for (P_obj obj : inventory) release(obj);
    inventory.clear(); requests.clear(); rolls.clear(); output.clear();
    stats = recipes = samples = extracted = maps = removals = zones = fail_at = 0;
    reject_recipe = false; recipe_rejections.clear();
    staff = {}; staff.only.pc = &player; staff.player.level = 62; staff.in_room = 123;
}
static void run(const std::string &arguments) {
    std::vector<char> text(arguments.begin(), arguments.end()); text.push_back('\0');
    do_randobj(&staff, text.data(), 0);
}
static void rejected(const std::string &arguments) {
    reset(); run(arguments);
    assert(requests.empty() && inventory.empty() && rolls.empty());
    assert(stats == 0 && maps == 0 && removals == 0 && zones == 0);
    assert(output.find("Syntax: randobj") != std::string::npos);
}
static std::string word(const char *name) {
    std::string result = strip_ansi(name);
    for (char &c : result) c = c == ' ' ? '-' : tolower(static_cast<unsigned char>(c));
    return result;
}

int main() {
    reset(); run("eq");
    assert(requests.size() == 1 && requests[0].finder_level == 62 && requests[0].source_level == 62);
    assert(requests[0].slot == -1 && rolls.empty() && inventory.size() == 1 && stats == 1);
    // Shared keywords must not redirect stat output to an older generated item.
    run("eq ring 30 3"); run("eq wield"); run("eq ring");
    assert(inventory.size() == 6 && stats == 3);
    reset(); run("EQ ANY 30 3");
    assert(requests.size() == 3 && inventory.size() == 3 && stats == 0 && rolls.empty());
    for (const auto &r : requests) assert(r.slot == -1 && r.finder_level == 30 && r.source_level == 30);
    assert(output.find("(level 30)") != std::string::npos && output.find("Created 3 equipment items") != std::string::npos);
    reset(); run("eq 50 5");
    assert(requests.size() == 5 && requests[0].slot == -1 && requests[0].finder_level == 50);
    reset(); run("  eq  ring  1  50  ");
    assert(requests.size() == 50 && requests[0].finder_level == 1 && stats == 0);

    // Concrete nouns resolve to their rows. Wear-group aliases are checked below.
    for (int slot = 0; slot < MAX_SLOT; slot++) {
        std::string noun = word(slot_data[slot].m_name);
        bool wear_alias = false;
        for (int bit = 0; wear_bits[bit].flagShort; bit++) {
            const char *name = wear_bits[bit].flagShort;
            if (!strncmp(name, "WEAR_", 5)) name += 5;
            if (word(name) == noun) wear_alias = true;
        }
        if (wear_alias) continue;
        reset(); run("eq " + noun + " 30");
        assert(requests.size() == 1 && word(slot_data[requests[0].slot].m_name) == noun);
        assert(requests[0].finder_level == 30 && stats == 1);
    }
    // Every supported wear location chooses uniformly from just its matching rows.
    for (int bit = 0; wear_bits[bit].flagShort; bit++) {
        std::vector<int> eligible;
        for (int slot = 0; slot < MAX_SLOT; slot++)
            if (static_cast<unsigned>(slot_data[slot].wear_bit) == (1U << bit)) eligible.push_back(slot);
        if (eligible.empty()) continue;
        const char *name = wear_bits[bit].flagShort;
        if (!strncmp(name, "WEAR_", 5)) name += 5;
        reset(); run("eq " + word(name));
        assert(requests.size() == 1 && requests[0].slot == eligible.back());
        if (eligible.size() > 1) assert(rolls.size() == 1 && rolls[0].first == 0 && rolls[0].second == static_cast<int>(eligible.size()) - 1);
        else assert(rolls.empty());
    }
    reset(); run("eq list");
    assert(requests.empty() && rolls.empty());
    for (const char *token : {"any", "finger:", "ring", "wield:", "long-sword", "tower-shield"})
        assert(output.find(token) != std::string::npos);

    reset(); run("piece");
    assert(requests.size() == 1 && requests[0].kind == "piece" && requests[0].finder_level == 62 && stats == 0);
    reset(); run("piece 40 5");
    assert(requests.size() == 5 && requests[0].finder_level == 40 && requests[0].source_level == 40);
    assert(output.find("Created 5 materials") != std::string::npos);
    reset(); run("stone"); assert(requests.size() == 1 && requests[0].kind == "stone");
    reset(); run("stone 50"); assert(requests.size() == 50 && inventory.size() == 50);
    reset(); run("recipe"); assert(recipes == 1 && extracted == 1 && inventory.size() == 1);
    reset(); run("recipe 3"); assert(recipes == 3 && extracted == 3);
    reset(); reject_recipe = true; run("recipe 3");
    assert(requests.size() == 3 && recipes == 2 && extracted == 3);
    assert(output.find("Created 2 recipes") != std::string::npos);
    // The real recipe function can reject otherwise valid zone items. Only delivered
    // scrolls may contribute a success line or the total, including mixed batches.
    for (int rejection = 1; rejection <= 9; rejection++) {
        reset(); recipe_rejections = {rejection, rejection}; run("recipe 2");
        assert(requests.size() == 2 && recipes == 0 && inventory.empty() && extracted == 2);
        assert(output == "Created 0 recipes.\r\n");
        reset(); recipe_rejections = {0, rejection, 0}; run("recipe 3");
        assert(requests.size() == 3 && recipes == 2 && inventory.size() == 2 && extracted == 3);
        assert(output == "Recipe for a test item\r\nRecipe for a test item\r\nCreated 2 recipes.\r\n");
        reset(); recipe_rejections = {rejection}; run("recipe");
        assert(recipes == 0 && inventory.empty() && extracted == 1 && output.empty());
    }
    reset(); run("mob"); assert(requests.size() == 1 && requests[0].finder_level == 0);
    reset(); run("mob 20"); assert(requests.size() == 1 && requests[0].finder_level == 20);
    reset(); run("mob 0 10"); assert(requests.size() == 10 && requests[0].finder_level == 0);
    assert(output.find("Created 10 mobs") != std::string::npos && output.find("level 37") != std::string::npos);
    reset(); run("mob 61 2"); assert(requests.size() == 2 && requests[0].finder_level == 61);
    reset(); run("encrust"); assert(samples == 10 && extracted == 10);
    reset(); run("encrust 1"); assert(samples == 1 && extracted == 1);
    reset(); run("encrust 50"); assert(samples == 50 && extracted == 50);
    reset(); run("map"); assert(maps == 3);
    reset(); run("remove"); assert(removals == 3);
    reset(); run("zone"); assert(zones == 1);

    for (const char *input : {"", "unknown", "eq nonsense", "eq list extra", "eq ring 0", "eq 63", "eq ''", "eq ring '' 1", "stone ''",
         "eq -1", "eq 1 0", "eq 1 51", "eq 30 -2", "eq 1 1 extra", "eq ring from 30", "eq ring 30 1 at",
         "eq 9999999999999999999999999999999", "eq ring 3.5", "eq ring +30", "eq ring -", "eq ring thirty",
         "piece 0", "piece 63", "piece 30 0", "piece 30 51", "piece 30 2 extra", "piece at 30",
         "stone 0", "stone 51", "stone -1", "stone x", "stone 1 extra", "stone 1 with",
         "recipe 0", "recipe 51", "recipe 1 extra", "mob -1", "mob 62", "mob 62 2", "mob 63", "mob 1 0", "mob 1 11", "mob 1 1 extra",
         "encrust 0", "encrust 51", "encrust 1 extra", "map extra", "remove extra", "zone extra"}) rejected(input);
    rejected("eq '" + std::string(MAX_INPUT_LENGTH - 6, 'A'));
    rejected("eq ring '" + std::string(MAX_INPUT_LENGTH - 11, '9'));

    // Missing blanks stop each creation path before any null object is placed or inspected.
    for (const char *input : {"eq", "piece", "stone", "recipe", "encrust", "mob"}) {
        reset(); fail_at = 1; run(input);
        assert(requests.size() == 1 && inventory.empty() && stats == 0 && samples == 0 && recipes == 0);
        assert(output.find("stopped") != std::string::npos);
    }
    for (const char *input : {"eq ring 30 3", "piece 40 3", "stone 3", "recipe 3", "encrust 3", "mob 20 3"}) {
        reset(); fail_at = 2; run(input);
        assert(requests.size() == 2 && stats == 0 && output.find("stopped") != std::string::npos);
        assert(output.find("Created 3") == std::string::npos);
    }
    reset(); staff.player.level = 50; run("eq"); assert(requests.empty());
    reset(); SET_BIT(staff.specials.act, PLR_MORTAL); run("eq"); assert(requests.empty());
    reset(); SET_BIT(staff.specials.act, ACT_ISNPC); run("eq"); assert(requests.empty());
    reset();
    puts("randobj command passed: defaults, every slot, options, limits, rejection, failures and trust");
}
'''


def main():
    common = (ROOT / "src/core/common.c").read_text()
    wear = common[common.index("flagDef wear_bits[]") : common.index("flagDef extra_bits[]")]
    helpers = "\n".join(extract_function(path, signature) for path, signature in (
        ("interp.c", "char *lohrr_chop(char *string, char *arg1)"),
        ("interp.c", "bool is_number(char *str)"),
        ("utility.c", "string strip_ansi(const char *str)"),
        ("drannak.c", "bool create_recipe(P_char ch, P_obj temp)"),
    ))
    output = ROOT / "bin/tests"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="randobj-", dir=output) as directory:
        work = Path(directory)
        harness = work / "harness.cpp"
        harness.write_text(HARNESS + "\n" + wear + helpers)
        binary = work / "randobj"
        subprocess.run([
            "g++", "-std=c++20", "-O1", "-g", "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer", "-I" + str(ROOT / "src"), str(harness),
            str(ROOT / "src/item/randobj.c"), str(ROOT / "src/item/random_equipment_tables.c"),
            "-o", str(binary),
        ], check=True)
        subprocess.run([str(binary)], check=True, timeout=30,
                       env=dict(os.environ, ASAN_OPTIONS="detect_leaks=1:halt_on_error=1",
                                UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1"))


if __name__ == "__main__":
    main()
