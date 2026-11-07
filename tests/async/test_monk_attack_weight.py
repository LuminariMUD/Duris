#!/usr/bin/env python3
"""Execute real martial-arts attacks with equipment-only weight penalties."""

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
#include "abilities/abilities.h"
#include <cassert>
#include <cstdio>
#include <cstring>

static int warnings, martial_rating = 100;
static P_char rider;
int GET_CLASS(P_char ch, unsigned int cls) { return ch->player.m_class & cls; }
int GET_CHAR_SKILL_P(P_char, int) { return martial_rating; }
bool notch_skill(P_char, int, float) { return false; }
int number(int low, int high) { return high == 100 ? low : high; }
static int roll_dice(int count, int) { return count; }
const Rolls live_rolls = {roll_dice, number};
int BOUNDED(int low, int value, int high) { return std::min(high, std::max(low, value)); }
P_char get_linking_char(P_char, unsigned short) { return rider; }
void send_to_char(const char *message, P_char) {
    assert(strstr(message, "reduces your base monk attacks"));
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
    pc_only_data pc{}, other_pc{};
    obj_data bag{}, second_item{}, inventory{}, contents{}, hand_item{};
    monk.only.pc = &pc;
    monk.player.m_class = CLASS_MONK;
    monk.player.level = 50;
    monk.specials.fighting = &opponent;
    opponent.specials.act = ACT_ISNPC;
    opponent.only.pc = &other_pc;
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
            monk.equipment[WEAR_LIGHT] = test.before == 1 ? &hand_item : nullptr;
            warnings = 0;
            const int actual = monk_attacks(&monk, slots);
            if (actual != test.after || warnings != (test.after < test.before)) {
                fprintf(stderr, "STR %d, equipped half-weight %d, inventory %d: "
                        "%d -> %d attacks (expected %d), %d warnings\n",
                        test.strength, test.attack_weight, inventory_weight,
                        test.before, actual, test.after, warnings);
                return 1;
            }
            assert(actual >= 1 && actual <= test.before);
        }
    }

    // Round each equipped item down before summing, not the combined weight.
    monk.equipment[WEAR_LIGHT] = nullptr;
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

    // Negative-weight magical bags have zero effective equipment weight.
    monk.equipment[WEAR_BACK] = &bag;
    bag.weight = -100;
    monk.specials.carry_weight = 500;
    assert(monk_attacks(&monk, slots) == 5 && warnings == 0);

    // The real hand restriction leaves one base attack and suppresses warnings.
    bag.weight = 1000;
    for (int hand : {WIELD, SECONDARY_WEAPON, HOLD, WEAR_SHIELD, WEAR_LIGHT}) {
        monk.equipment[hand] = &hand_item;
        assert(monk_attacks(&monk, slots) == 1 && warnings == 0);
        monk.equipment[hand] = nullptr;
    }

    // Trusted staff and NPC monks retain their existing weight exemptions.
    monk.equipment[WEAR_BACK] = &bag;
    bag.weight = 1000;
    monk.curr_stats.Str = 40;
    monk.specials.carry_weight = 500;
    monk.player.level = MAXLVLMORTAL + 1;
    warnings = 0;
    const int staff_attacks = MonkNumberOfAttacks(&monk);
    assert(monk_attacks(&monk, slots) == staff_attacks && warnings == 0);
    // Staff emulating a mortal must receive the same penalty as other players.
    monk.specials.act = PLR_MORTAL;
    assert(monk_attacks(&monk, slots) == 1 && warnings == 1);
    monk.player.level = 50;
    monk.specials.act = ACT_ISNPC;
    warnings = 0;
    assert(monk_attacks(&monk, slots) == 5 && warnings == 0);

    // The warning describes base attacks: slow can hide the final swing loss.
    monk.specials.act = 0;
    monk.specials.affected_by2 = AFF2_SLOW;
    bag.weight = 0;
    assert(monk_attacks(&monk, slots) == 2 && warnings == 0);
    bag.weight = 60;
    assert(monk_attacks(&monk, slots) == 2 && warnings == 1);

    // PvP consumes pairs of base attacks for a special hit after weight applies.
    monk.specials.affected_by2 = 0;
    opponent.specials.act = 0;
    bag.weight = 0;
    warnings = 0;
    assert(monk_attacks(&monk, slots) == 3 && warnings == 0);
    assert(slots[0] == WEAR_NONE && slots[1] == WEAR_NONE && slots[2] == PRIMARY_WEAPON);
    bag.weight = 60;
    assert(monk_attacks(&monk, slots) == 2 && warnings == 1);
    assert(slots[0] == WEAR_NONE && slots[1] == WEAR_NONE);

    // Real low-skill and high-level attack floors survive weight and inventory.
    opponent.specials.act = ACT_ISNPC;
    struct rating_case { int level, rating, unweighted; };
    for (const auto &test : {rating_case{1, 100, 1}, {30, 100, 3}, {50, 1, 1},
                             {51, 100, 6}, {56, 0, 2}, {56, 100, 7}}) {
        monk.player.level = test.level;
        martial_rating = test.rating;
        bag.weight = 0;
        monk.specials.carry_weight = 500;
        warnings = 0;
        assert(monk_attacks(&monk, slots) == test.unweighted && warnings == 0);
        bag.weight = 1000;
        assert(monk_attacks(&monk, slots) == 1);
        assert(warnings == (test.unweighted > 1));
    }

    // Adversarial properties: more equipped weight cannot add attacks; more
    // Strength cannot remove them. Include zero/negative effective bag weights.
    monk.player.level = 50;
    martial_rating = 100;
    int previous_strength[403]{};
    for (int strength = 1; strength <= 300; ++strength) {
        monk.curr_stats.Str = strength;
        int previous_weight = 5;
        for (int weight = -2; weight <= 400; ++weight) {
            bag.weight = weight;
            warnings = 0;
            const int actual = monk_attacks(&monk, slots);
            assert(actual >= 1 && actual <= previous_weight);
            assert(actual >= previous_strength[weight + 2]);
            assert(warnings == (actual < 5));
            previous_weight = previous_strength[weight + 2] = actual;
        }
    }
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
            extract_function("new_skills.c", "static int monk_attack_rolls("),
            extract_function("new_skills.c", "static int monk_attack_count("),
            extract_function("new_skills.c", "static int monk_attack_roll_limit("),
            extract_function("new_skills.c", "int MonkNumberOfAttacks("),
        ]))
    )
    subprocess.run([
        "g++", "-std=c++20", "-g", "-Og", "-Isrc",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        str(cpp), "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=30)
