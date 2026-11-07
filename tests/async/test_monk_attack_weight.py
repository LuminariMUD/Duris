#!/usr/bin/env python3
"""Execute monk attacks with half-weight equipment and unrestricted inventory."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function


attacks = extract_function("fight.c", "int calculate_attacks(")
monk_branch = attacks[attacks.index("\tif (GET_CLASS(ch, CLASS_MONK))") :]
monk_branch = monk_branch.split("\n\telse\n\t{ // not MONK", 1)[0]

PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include <cassert>
#include <cstdio>
#include <cstring>

static int base_attacks, warnings;
static P_char rider;
int MonkNumberOfAttacks(P_char) { return base_attacks; }
int GET_CLASS(P_char ch, unsigned int cls) { return ch->player.m_class & cls; }
int number(int, int high) { return high; }
P_char get_linking_char(P_char, unsigned short) { return rider; }
void send_to_char(const char *message, P_char) {
    assert(strstr(message, "causing you to lose attacks"));
    ++warnings;
}

WEIGHT_FUNCTIONS

#define ADD_ATTACK(slot) (attacks[number_attacks++] = (slot))
static int monk_attacks(P_char ch, int attacks[]) {
    int number_attacks = 0;
MONK_BRANCH
    return number_attacks;
}
#undef ADD_ATTACK

int main() {
    char_data monk{}, opponent{}, passenger{};
    pc_only_data pc{};
    obj_data bag{}, second_item{}, inventory{}, contents{};
    monk.only.pc = &pc;
    monk.player.m_class = CLASS_MONK;
    monk.player.level = 50;
    monk.specials.fighting = &opponent;
    opponent.specials.act = ACT_ISNPC;
    monk.equipment[WEAR_BACK] = &bag;
    monk.equipment[WEAR_FINGER_L] = &second_item;
    monk.carrying = &inventory;
    int slots[16]{};
    struct test_case {
        int strength, attack_weight, before, after;
    };
    const test_case cases[] = {
        {100, 0, 5, 5}, {100, 49, 5, 5}, {100, 50, 5, 5},
        {100, 59, 5, 5}, {100, 60, 5, 4}, {100, 69, 5, 4},
        {100, 70, 5, 3}, {100, 500, 5, 1}, {100, 500, 1, 1},
        {60, 30, 5, 5}, {60, 39, 5, 5}, {60, 40, 5, 4},
        {40, 10, 5, 5}, {40, 20, 5, 5}, {40, 29, 5, 5},
        {40, 30, 5, 4}, {101, 60, 5, 4},
        {102, 60, 5, 5}, {102, 61, 5, 4},
    };
    for (const auto &test : cases) {
        // The back item contributes half its weight, independently of inventory.
        for (int inventory_weight : {0, 500}) {
            monk.curr_stats.Str = test.strength;
            bag.weight = test.attack_weight * 2;
            inventory.weight = inventory_weight;
            monk.specials.carry_weight = test.attack_weight + inventory_weight;
            base_attacks = test.before;
            warnings = 0;
            const int actual = monk_attacks(&monk, slots);
            if (actual != test.after || warnings != (test.after < test.before)) {
                fprintf(stderr, "STR %d, equipped half-weight %d, inventory %d: "
                        "%d -> %d attacks (expected %d), %d warnings\n",
                        test.strength, test.attack_weight, inventory_weight,
                        test.before, actual, test.after, warnings);
                return 1;
            }
            assert(actual >= 1 && actual <= base_attacks);
        }
    }

    // Round each equipped item down before summing, not the combined weight.
    base_attacks = 5;
    monk.curr_stats.Str = 100;
    bag.weight = 119;
    second_item.weight = 1;
    warnings = 0;
    assert(monk_attacks(&monk, slots) == 5 && warnings == 0);
    second_item.weight = 3;
    assert(monk_attacks(&monk, slots) == 4 && warnings == 1);

    // A worn bag includes its contents, using the real weight propagation.
    second_item.weight = 0;
    bag.weight = 100;
    bag.loc_p = LOC_WORN;
    bag.loc.wearing = &monk;
    bag.contains = &contents;
    contents.loc_p = LOC_INSIDE;
    contents.loc.inside = &bag;
    monk.specials.carry_weight = 50;
    warnings = 0;
    assert(monk_attacks(&monk, slots) == 5 && warnings == 0);
    add_weight(&contents, 20);
    assert(bag.weight == 120 && monk.specials.carry_weight == 60);
    assert(monk_attacks(&monk, slots) == 4 && warnings == 1);

    // Carrying that same loaded bag in inventory costs no monk attacks.
    monk.equipment[WEAR_BACK] = nullptr;
    monk.carrying = &bag;
    bag.loc_p = LOC_CARRIED;
    bag.loc.carrying = &monk;
    monk.specials.carry_weight = bag.weight;
    warnings = 0;
    add_weight(&contents, 20);
    assert(bag.weight == 140 && monk.specials.carry_weight == 140);
    assert(monk_attacks(&monk, slots) == 5 && warnings == 0);

    // A linked rider's weight is not equipped weight either.
    passenger.player.weight = 200;
    passenger.specials.carry_weight = 500;
    rider = &passenger;
    assert(total_carried_weight(&monk) == 840);
    assert(monk_attacks(&monk, slots) == 5 && warnings == 0);
    rider = nullptr;

    // Trusted staff and NPC monks retain their existing weight exemptions.
    monk.equipment[WEAR_BACK] = &bag;
    bag.weight = 1000;
    monk.curr_stats.Str = 40;
    monk.specials.carry_weight = 500;
    monk.player.level = MAXLVLMORTAL + 1;
    warnings = 0;
    assert(monk_attacks(&monk, slots) == 5 && warnings == 0);
    monk.player.level = 50;
    monk.specials.act = ACT_ISNPC;
    assert(monk_attacks(&monk, slots) == 5 && warnings == 0);

    // Slow still applies after the weight reduction.
    monk.specials.act = 0;
    bag.weight = 60;
    monk.specials.carry_weight = 30;
    monk.specials.affected_by2 = AFF2_SLOW;
    assert(monk_attacks(&monk, slots) == 2 && warnings == 1);
    puts("monk equipped half-weight, inventory, bags, thresholds, warnings and exemptions passed");
}
'''

directory = ROOT / "bin/tests"
directory.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="monk-weight-", dir=directory) as temporary:
    cpp = Path(temporary) / "monk_weight.cpp"
    binary = Path(temporary) / "monk_weight"
    cpp.write_text(
        PRELUDE.replace("MONK_BRANCH", monk_branch).replace("WEIGHT_FUNCTIONS", "\n".join([
            extract_function("utility.c", "int total_carried_weight("),
            extract_function("handler.c", "static void encumbrance_adjust("),
            extract_function("handler.c", "void add_weight(P_obj obj, int weight)\n{"),
        ]))
    )
    subprocess.run([
        "g++", "-std=c++20", "-g", "-Og", "-Isrc",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        str(cpp), "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=30)
