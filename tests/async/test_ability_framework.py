#!/usr/bin/env python3
"""Shared ability numbers: rolls match the old handler code, ranges are exact, facts never roll.

Builds src/abilities/abilities.c and the real RNG with the converted abilities' shared
functions extracted from their handler files, under sanitizers. The pre-conversion
expressions are kept below as the oracle.
"""
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
#include <cstring>
#include <functional>
#include <string>

void randomize(uint64_t seed);
std::string reflection_innate_facts(P_char) { return ""; }
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
    assert(game_hours(1) == "1 game hour (about 1.25 minutes)");
    assert(game_hours(24) == "24 game hours (about 30 minutes)");
    assert(show({ 3, 3 }) == "3" && show({ 3, 9 }) == "3-9");
    assert(ability_facts(SPELL_FIREBALL) == fireball_facts);
    assert(ability_facts(SKILL_BASH) == bash_facts);
    assert(ability_facts(SPELL_HEAL) == nullptr);
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
    assert(contains(text, "Target's lag: 8 seconds, or 4 seconds if the target was already down\n"));
    ch.player.m_class = CLASS_WARRIOR;
    ch.player.spec = SPEC_GUARDIAN;
    assert(contains(bash_facts(&ch), "Target's lag: 10 seconds, or 4 seconds"));
    puts("PASS: shared rolls match the old code, ranges are exact, facts never roll");
}
'''


def check_handlers_use_shared_numbers():
    bash = function_bodies(strip_comments(source("actoff.c").read_text()),
                           r"\bvoid\s+bash\s*\(\s*P_char\s+ch")[0]
    for call in ("dmg = bash_damage(live_rolls, ch);", "CharWait(ch, bash_hit_lag());",
                 "CharWait(ch, bash_miss_lag(true));", "CharWait(ch, bash_miss_lag(false));",
                 "CharWait(victim, bash_target_lag(ch, GET_POS(victim) == POS_STANDING));",
                 "melee_damage(ch, victim, dmg, PHSDAM_TOUCH, 0)"):
        assert call in bash, call
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
                 extract_function("actoff.c", "static int bash_target_lag("),
                 extract_function("actoff.c", "std::string bash_facts(")]
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ability-framework-", dir=build) as temporary:
        directory = Path(temporary)
        harness = directory / "abilities.cpp"
        harness.write_text(HARNESS.replace("int main() {", "\n".join(functions) + "\nint main() {"))
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
