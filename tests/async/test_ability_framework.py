#!/usr/bin/env python3
"""Shared ability numbers: rolls match the old handler code, ranges are exact, facts never roll.

Builds src/abilities/abilities.c and the real RNG with the converted abilities' shared
functions extracted from their handler files, under sanitizers. The pre-conversion
expressions are kept below as the oracle.
"""
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source
from _source_contract import function_bodies, strip_comments

HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "abilities/abilities.h"
#include <cassert>
#include <climits>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <string>

void randomize(uint64_t seed);
struct str_app_type str_app[52];

// The next draw after a roll; equal fingerprints after equal seeds mean equal draw counts.
static int fingerprint() { return number(0, INT_MAX); }

static void same_rolls(const std::function<int()> &original, const std::function<int()> &shared,
                       Range bounds) {
    for (uint64_t seed = 1; seed <= 40; ++seed) {
        randomize(seed);
        const int expected = original(), expected_next = fingerprint();
        randomize(seed);
        const int actual = shared(), actual_next = fingerprint();
        assert(actual == expected && actual_next == expected_next);
        assert(bounds.low <= actual && actual <= bounds.high);
    }
}

// Every value from low to high must turn up over enough seeds.
static void reaches(const std::function<int()> &shared, Range bounds) {
    int low = INT_MAX, high = INT_MIN;
    for (uint64_t seed = 1; seed <= 2000; ++seed) {
        randomize(seed);
        const int value = shared();
        low = std::min(low, value);
        high = std::max(high, value);
    }
    assert(low == bounds.low && high == bounds.high);
}

// bash() before its damage moved into bash_damage().
static int old_bash_damage(P_char ch) {
    int dmg = 1 + str_app[STAT_INDEX(GET_C_STR(ch))].todam;
    if (ch->equipment[WEAR_SHIELD]) {
        dmg += number(0, 4) + ch->equipment[WEAR_SHIELD]->weight / 2;
        if (strstr(ch->equipment[WEAR_SHIELD]->name, "spiked"))
            dmg *= 2;
    }
    return MAX(1, dmg);
}

static bool contains(const std::string &text, const char *part) {
    return text.find(part) != std::string::npos;
}

int main() {
    // The live rolls are the real RNG; the bounds follow dice()'s clamping and
    // number()'s reversed bounds without drawing.
    assert(live_rolls.dice == dice && live_rolls.number == number);
    randomize(9);
    const int untouched = fingerprint();
    randomize(9);
    assert(lowest_rolls.dice(0, 0) == 1 && highest_rolls.dice(0, 0) == 1);
    assert(lowest_rolls.dice(-2, 6) == 1 && highest_rolls.dice(-2, 6) == 6);
    assert(lowest_rolls.dice(3, 4) == 3 && highest_rolls.dice(3, 4) == 12);
    assert(lowest_rolls.number(5, 1) == 1 && highest_rolls.number(5, 1) == 5);
    assert(fingerprint() == untouched);
    reaches([] { return dice(2, 3) * 5; }, { lowest_rolls.dice(2, 3) * 5, highest_rolls.dice(2, 3) * 5 });
    reaches([] { return number(5, 1); }, { lowest_rolls.number(5, 1), highest_rolls.number(5, 1) });

    assert(seconds(WAIT_SEC) == "1 second");
    assert(seconds(PULSE_VIOLENCE * 2) == "8 seconds");
    assert(seconds(6) == "1.5 seconds");
    assert(real_time(30 * WAIT_SEC) == "30 seconds" && real_time(60 * WAIT_SEC) == "1 minute");
    assert(real_time(75 * WAIT_SEC) == "1 minute 15 seconds" && real_time(720 * WAIT_SEC) == "12 minutes");
    assert(game_hours(1) == "1-2 game hours (1.25-2.5 minutes)");
    assert(game_hours(24) == "24-25 game hours (30-31.25 minutes)");
    assert(game_hours(0) == "up to 1 game hour (up to 1.25 minutes)");
    assert(game_hours(-1) == "permanent");
    assert(game_hours_range({ 24, 24 }) == game_hours(24));
    assert(game_hours_range({ 2, 5 }) == "2-6 game hours (2.5-7.5 minutes)");
    assert(show_signed({ -10, -5 }) == "-10 to -5" && show_signed({ -3, -3 }) == "-3");
    assert(show_signed({ 2, 5 }) == "2-5");
    assert(show_landing({ 1, 5 }) == "1-5");
    assert(show_landing({ -25, 55 }) == "0-55 (none below 1 lands)");
    assert(show_landing({ -5, -2 }) == "0 (none below 1 lands)");
    assert(game_hours(8001) == "8001-8002 game hours (10001.25-10002.5 minutes)");
    assert(show({ 3, 3 }) == "3" && show({ 3, 9 }) == "3-9");
    // Info pages style facts at render time: cyan labels, bright numbers, dim notes.
    assert(info_field("Type", "Skill") == "  &+cType:&n Skill\n");
    assert(mechanics_section("  Fire damage: 84-504 at your level, 50\n  Armor class: -10\n"
                             "  Your lag: 1.5 seconds\n  Defenses apply after.\n") ==
           "\n&+W  Mechanics&n\n  &+cFire damage:&n &+W84-504&n at your level, &+W50&n\n"
           "  &+cArmor class:&n &+W-10&n\n  &+cYour lag:&n &+W1.5&n seconds\n"
           "&+L  Defenses apply after.&n\n");
    assert(mechanics_section("  Every saving throw: +7\n    (or water: 2 more)\n") ==
           "\n&+W  Mechanics&n\n  &+cEvery saving throw:&n &+W+7&n\n    (or water: &+W2&n more)\n");
    assert(ability_facts(SPELL_FIREBALL) == fireball_facts);
    assert(ability_facts(SKILL_BASH) == bash_facts);
    assert(ability_facts(UNCONVERTED) == nullptr);
    assert(innate_facts(INNATE_REFLECTION) == reflection_innate_facts);
    assert(innate_facts(INNATE_DOORBASH) == nullptr);

    // Fireball rolls exactly as before at every level, and its facts never roll.
    for (int level = 1; level <= 62; ++level)
        same_rolls([=] { return dice(((int)(level / 3) + 5), 6) * 4; },
                   [=] { return fireball_damage(live_rolls, level); },
                   { fireball_damage(lowest_rolls, level), fireball_damage(highest_rolls, level) });
    char_data ch{};
    ch.player.level = 50;
    randomize(9);
    std::string text = fireball_facts(&ch);
    assert(fingerprint() == untouched);
    assert(contains(text, "Fire damage: 84-504 at your level, 50\n"));
    assert(contains(text, "If the target fails its save: 168-1008\n"));
    assert(fireball_failed_save(84) == 168);
    assert(contains(text, "Globe of invulnerability: stops it\n"));
    ch.player.m_class = CLASS_CONJURER;
    ch.player.spec = SPEC_FIRE;
    assert(contains(fireball_facts(&ch), "Globe of invulnerability: stops it\n"));
    ch.player.level = 51;
    assert(contains(fireball_facts(&ch), "Globe of invulnerability: does not stop it\n"));
    ch.specials.act = ACT_ISNPC;
    assert(contains(fireball_facts(&ch), "Globe of invulnerability: stops it\n"));
    ch = char_data{};
    ch.player.level = 50;

    // Bash damage rolls exactly as before with and without shields and strength.
    for (int i = 0; i < 52; ++i)
        str_app[i].todam = static_cast<::byte>(i - 12);
    obj_data shield{}, spiked{};
    shield.weight = 9;
    shield.name = const_cast<char *>("shield kite");
    spiked.weight = 10;
    spiked.name = const_cast<char *>("shield spiked");
    for (int strength : { 0, 5, 30, 80, 100 })
        for (P_obj worn : { (P_obj) nullptr, &shield, &spiked }) {
            ch.curr_stats.Str = strength;
            ch.equipment[WEAR_SHIELD] = worn;
            const Range bounds = { bash_damage(lowest_rolls, &ch), bash_damage(highest_rolls, &ch) };
            same_rolls([&] { return old_bash_damage(&ch); }, [&] { return bash_damage(live_rolls, &ch); },
                       bounds);
            reaches([&] { return bash_damage(live_rolls, &ch); }, bounds);
        }
    ch.curr_stats.Str = 30; // todam -7: a shieldless bash still deals 1
    ch.equipment[WEAR_SHIELD] = nullptr;
    assert(bash_damage(lowest_rolls, &ch) == 1 && bash_damage(highest_rolls, &ch) == 1);
    assert(contains(bash_facts(&ch), "Damage on a hit: 1 with your strength and no shield\n"));
    ch.curr_stats.Str = 100;
    str_app[STAT_INDEX(100)].todam = 1; // base 2, spiked weight 10: (0-4 + 2 + 5) * 2
    ch.equipment[WEAR_SHIELD] = &spiked;
    randomize(9);
    text = bash_facts(&ch);
    assert(fingerprint() == untouched);
    assert(contains(text, "Damage on a hit: 14-22 with your strength and shield\n"));
    assert(contains(text, "Your lag on a hit: 8 seconds\n"));
    assert(contains(text, "Your lag on a miss: 8 seconds, or 12 seconds if you fall prone\n"));
    assert(contains(text, "Your lag if the target is already down: 8 seconds\n"));
    assert(contains(text, "Your lag if the target is asleep: 4 seconds (you attack it instead)\n"));
    assert(contains(text, "Your lag if the target evades: 2 seconds\n"));
    assert(contains(text, "Your lag if the target is 2 or more sizes bigger or smaller: 2 seconds\n"
                          "    (also a centaur or drider at least your size)\n"));
    assert(contains(text, "Your lag if the target foils the takedown: 8 seconds\n    (grapple,"));
    assert(contains(text, "Target's lag: 8 seconds\n"));
    assert(!contains(text, "was already down")); // the unreachable down-target lag is not shown
    for (size_t start = 0, end; start < text.size(); start = end + 1) {
        end = text.find('\n', start);
        assert(end != std::string::npos && end - start <= 79);
    }
    ch.player.race = RACE_QUADRUPED;
    assert(contains(bash_facts(&ch), "    (also any target at least your size)\n"));
    ch.player.race = 0;
    ch.player.m_class = CLASS_WARRIOR;
    ch.player.spec = SPEC_GUARDIAN;
    assert(contains(bash_facts(&ch), "Target's lag: 10 seconds\n"));
    puts("PASS: shared rolls match the old code, ranges are exact, facts never roll");
}
'''


def check_handlers_use_shared_numbers():
    bash = function_bodies(strip_comments(source("actoff.c").read_text()),
                           r"\bvoid\s+bash\s*\(\s*P_char\s+ch")[0]
    for call in ("dmg = bash_damage(live_rolls, ch);", "CharWait(ch, bash_hit_lag());",
                 "CharWait(ch, bash_miss_lag(true));", "CharWait(ch, bash_miss_lag(false));",
                 "CharWait(victim, bash_target_lag(ch, GET_POS(victim) == POS_STANDING));",
                 "CharWait(ch, bash_target_down_lag());", "CharWait(ch, bash_takedown_penalty_lag());",
                 "melee_damage(ch, victim, dmg, PHSDAM_TOUCH, 0)"):
        assert call in bash, call

    # Each lag helper sits in its own branch: from the branch's message to its return.
    def branch(body, marker):
        start = body.index(marker)
        return body[start:body.index("return", start)]
    takedown = function_bodies(strip_comments(source("actoff.c").read_text()),
                               r"\bfloat\s+takedown_check\s*\(")[0]
    for body, marker, call in (
            (bash, "As $N avoids your bash, you topple over", "CharWait(ch, bash_target_down_lag());"),
            (bash, "simply too huge for you to move", "CharWait(ch, bash_size_lag());"),
            (bash, "just too small", "CharWait(ch, bash_size_lag());"),
            (bash, "percent_chance == TAKEDOWN_PENALTY", "CharWait(ch, bash_takedown_penalty_lag());"),
            (takedown, "cannot respond to your attack", "CharWait(ch, takedown_sleeping_target_lag());"),
            (takedown, "TAKEDOWN_EVADE);", "CharWait(ch, takedown_evade_lag());")):
        assert call in branch(body, marker), (marker, call)
    fireball = function_bodies(strip_comments(source("magic.c").read_text()),
                               r"\bvoid\s+spell_fireball\s*\(")[0]
    for call in ("int dam = fireball_damage(live_rolls, level);", "dam = fireball_failed_save(dam);",
                 "if (fireball_passes_globes(ch))"):
        assert call in fireball, call


def main():
    check_handlers_use_shared_numbers()
    functions = [extract_function("utility.c", "int dice(int num, int size)"),
                 extract_function("utility.c", "int STAT_INDEX(int v)"),
                 extract_function("magic.c", "static int fireball_damage("),
                 extract_function("magic.c", "static bool fireball_passes_globes("),
                 extract_function("magic.c", "static int fireball_failed_save("),
                 extract_function("magic.c", "std::string fireball_facts("),
                 extract_function("actoff.c", "static int bash_damage("),
                 extract_function("actoff.c", "static int bash_hit_lag("),
                 extract_function("actoff.c", "static int bash_miss_lag("),
                 extract_function("actoff.c", "static int takedown_sleeping_target_lag("),
                 extract_function("actoff.c", "static int takedown_evade_lag("),
                 extract_function("actoff.c", "static int bash_target_down_lag("),
                 extract_function("actoff.c", "static int bash_size_lag("),
                 extract_function("actoff.c", "static int bash_takedown_penalty_lag("),
                 extract_function("actoff.c", "static int bash_target_lag("),
                 extract_function("actoff.c", "std::string bash_facts(")]
    # abilities.c's table names every facts function; the ones not built here never run.
    declared = re.findall(r"^std::string (\w+_facts)\(char_data \*ch\);", source("abilities.h").read_text(), re.M)
    functions += [f"std::string {name}(char_data *) {{ std::abort(); }}"
                  for name in declared if name not in ("fireball_facts", "bash_facts")]
    # Any spell or skill with no numbers has no facts.
    no_numbers = (ROOT / "tests/fixtures/ability_coverage_no_numbers.txt").read_text().split()
    unconverted = next(name for name in no_numbers if name.startswith(("SPELL_", "SKILL_")))
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ability-framework-", dir=build) as temporary:
        directory = Path(temporary)
        harness = directory / "abilities.cpp"
        harness.write_text(HARNESS.replace("int main() {", "\n".join(functions) + "\nint main() {")
                           .replace("UNCONVERTED", unconverted))
        binary = directory / "abilities"
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
                        "-Isrc", "-I/usr/include/mysql", "-I/usr/include/libxml2",
                        str(harness), "src/abilities/abilities.c", "src/core/random.c",
                        "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], cwd=directory, check=True)


if __name__ == "__main__":
    main()
