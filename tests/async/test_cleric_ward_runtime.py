#!/usr/bin/env python3
"""Exercise Cleric healing exclusions and verify the retired ward cannot regenerate."""
from pathlib import Path
import subprocess

from _paths import ROOT, HARNESS_STUBS, extract_function, source

innates = source("innates.c").read_text()
fight = source("fight.c").read_text()
affects = source("affects.c").read_text()
limits = source("limits.c").read_text()
paladins = source("paladins.c").read_text()
epic = source("epic_skills.c").read_text()
assert "ADD_CLASS_INNATE(INNATE_WARDING_FAITH" not in innates
assert "ADD_CLASS_INNATE(INNATE_AURA_HEALING, CLASS_CLERIC" not in innates
assert "INNATE_AURA_SPELL_PROTECTION, CLASS_CLERIC, 1, SPEC_HEALER" in innates
assert "INNATE_AURA_PROTECTION, CLASS_CLERIC, 1, SPEC_ZEALOT" in innates
assert "ch->points.base_ward = 0;" in affects
assert "BOUNDED(0, GET_MAX_WARD(ch) - t1, GET_MAX_WARD(ch))" in affects
assert "has_innate(ch, INNATE_WARDING_FAITH)" not in limits
assert "GET_WARD(healer) + (hits / 10)" not in fight
assert "notch_skill(ch, SKILL_EPIC_WARDING_FAITH" not in fight
assert "EPIC_REWARD_SKILL, SKILL_EPIC_WARDING_FAITH" not in epic
assert "55168, SKILL_EPIC_WARDING_FAITH" not in epic
assert "SKILL_CREATE(\"epic warding faith\", SKILL_EPIC_WARDING_FAITH" in epic
assert "aura == AURA_HEALING && GET_SPEC(victim, CLASS_CLERIC, SPEC_HEALER)" in paladins
assert "void remove_incoming_healing_aura(P_char victim)" in paladins

PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "classes/paladins.h"
#include "world/hardcore_config.h"
#include "world/achievements.h"
#include "world/events.h"
#include "telemetry/telemetry_runtime.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
static room_data rooms[1]{};
P_room world = rooms;
float get_property(const char *, double fallback) { return fallback; }
int GET_CHAR_SKILL_P(P_char, int) { return 0; }
int GET_CLASS(P_char ch, uint cls) { return bool(ch->player.m_class & cls); }
room_affect *get_spell_from_room(P_room, int) { return nullptr; }
affected_type *get_spell_from_char(P_char ch, int id, void *, int) {
    for (auto *af = ch->affected; af; af = af->next) if (af->type == id) return af;
    return nullptr;
}
bool affected_by_spell(P_char ch, int id) { return get_spell_from_char(ch, id) != nullptr; }
bool affected_by_skill(P_char ch, int id) { return affected_by_spell(ch, id); }
void wear_off_message(P_char, affected_type *) {}
void affect_remove(P_char ch, affected_type *af) {
    auto **p = &ch->affected;
    while (*p && *p != af) p = &(*p)->next;
    assert(*p); *p = af->next;
}
int number(int low, int) { return low; }
void gmcp_char_vitals(P_char) {}
void update_achievements(P_char, P_char, int, int) {}
int gain_exp(P_char, P_char, int, int) { return 0; }
const hardcore_config *hardcore_config_get() { static hardcore_config cfg{}; return &cfg; }
void telemetry_runtime_game_combat_healing(P_char, P_char, std::uint64_t, std::uint64_t, std::uint32_t) noexcept {}
nevent_schedule_result add_event(event_func, int, P_char, P_char, P_obj, int,
                                 const void *, int size) {
    assert(size == sizeof(int)); // Nature's Touch schedules another wave.
    return {};
}
'''
PRODUCTION = "\n".join(extract_function(file, signature) for file, signature in (
    ("paladins.c", "bool has_aura("),
    ("paladins.c", "int aura_mod("),
    ("fight.c", "int vamp("),
    ("fight.c", "void heal("),
    ("magic.c", "void spell_group_heal("),
    ("magic.c", "void event_natures_touch("),
))
DRIVER = r'''
static void init(char_data &ch, bool healer) {
    ch = {};
    ch.specials.position = STAT_NORMAL;
    ch.player.m_class = CLASS_CLERIC;
    ch.player.spec = healer ? SPEC_HEALER : SPEC_HOLYMAN;
    ch.player.level = 56;
    ch.in_room = 0;
    ch.points.max_hit = 10000;
    ch.points.max_ward = 0;
}
int main() {
    char_data healer{}, holyman{}, warrior{}, mates[2]{};
    init(healer, true);
    init(holyman, false);
    init(warrior, false);
    warrior.player.m_class = CLASS_WARRIOR;
    warrior.player.spec = 0;
    affected_type white{};
    white.type = AURA_HEALING;
    white.modifier = 56;
    healer.affected = &white;
    warrior.affected = &white;
    healer.specials.affected_by3 |= AFF3_PALADIN_AURA;
    warrior.specials.affected_by3 |= AFF3_PALADIN_AURA;

    assert(vamp(&healer, 100, 10000) == 100);
    assert(vamp(&warrior, 100, 10000) == 111);
    warrior.points.hit = 0;
    assert(vamp(&warrior, 100, 10000, false) == 100);

    healer.points.hit = 0;
    heal(&healer, &healer, 100, 10000);
    assert(healer.points.hit == 120 && healer.points.ward == 0);
    warrior.points.hit = 0;
    heal(&warrior, &healer, 100, 10000);
    assert(warrior.points.hit == 120 && healer.points.ward == 0);
    warrior.points.hit = 0;
    heal(&warrior, &holyman, 100, 10000);
    assert(warrior.points.hit == 111);
    healer.points.hit = 0;
    heal(&healer, &holyman, 100, 10000);
    assert(healer.points.hit == 100);

    group_list group[2]{};
    for (int i = 0; i < 2; ++i) {
        init(mates[i], false);
        mates[i].player.m_class = CLASS_WARRIOR;
        mates[i].player.spec = 0;
        mates[i].affected = &white;
        mates[i].specials.affected_by3 |= AFF3_PALADIN_AURA;
        group[i] = {&mates[i], i == 0 ? &group[1] : nullptr};
    }
    healer.group = group;
    healer.points.hit = 0;
    spell_group_heal(56, &healer, nullptr, 0, nullptr, nullptr);
    assert(healer.points.hit == 144);
    for (const auto &mate : mates)
        assert(mate.points.hit == 144);
    assert(healer.points.ward == 0);

    int nature_wave = 100;
    warrior.points.hit = 0;
    event_natures_touch(&healer, &warrior, nullptr, &nature_wave);
    assert(warrior.points.hit == 100);
    warrior.points.hit = 0;
    event_natures_touch(&holyman, &warrior, nullptr, &nature_wave);
    assert(warrior.points.hit == 111);

    puts("Healer ward retirement and Paladin aura healing exclusions passed");
}
'''
output = ROOT / "bin/tests/cleric-ward"
output.mkdir(parents=True, exist_ok=True)
cpp, binary = output / "harness.cpp", output / "harness"
cpp.write_text(PRELUDE + "\n" + PRODUCTION + DRIVER)
subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
                "-I" + str(ROOT / "src"), str(cpp), str(HARNESS_STUBS),
                "-o", str(binary)], check=True)
subprocess.run([str(binary)], check=True)
