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
#include "net/comm.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
static room_data rooms[3]{};
P_room world = rooms;
zone_data zones[1]{};
zone_data *zone_table = zones;
static int healing_done, healing_xp, cured, wait_pulses, dice_total = 300;
static bool entry_allowed = true, hostile, raid_allowed = true;
static P_char pet_fixture, owner_fixture;
static hardcore_config hc{};
void send_to_char(const char *text, P_char) { if (std::strstr(text,"Your vision returns")) ++cured; }
void act(const char *, int, P_char, P_obj, void *, int) {}
int dice(int, int) { return dice_total; }
void update_pos(P_char) {}
P_char get_linked_char(P_char ch, ush_int) { return ch == pet_fixture ? owner_fixture : nullptr; }
P_char get_linking_char(P_char, ush_int) { return nullptr; }
int can_enter_room(P_char, int, int) { return entry_allowed; }
bool racewar(P_char, P_char) { return hostile; }
int is_Raidable(P_char, char *, int) { return raid_allowed; }
int is_introd(P_char, P_char) { return true; }
bool is_linked_to(P_char, P_char, ush_int) { return false; }
int how_close(int, int, int) { return 0; }
bool ac_can_see(P_char, P_char, bool) { return true; }
void CharWait(P_char, int delay) { wait_pulses += delay; }
void char_from_room(P_char ch) { ch->in_room = NOWHERE; }
bool char_to_room(P_char ch, int room, int) { ch->in_room = room; return true; }
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
void affect_from_char(P_char ch, int type) {
    for (auto *af = ch->affected; af;) {
        auto *next = af->next;
        if (af->type == type) affect_remove(ch, af);
        af = next;
    }
}
int number(int low, int) { return low; }
void gmcp_char_vitals(P_char) {}
void update_achievements(P_char, P_char, int amount, int) { healing_done = amount; }
int gain_exp(P_char, P_char, int amount, int) { healing_xp = amount; return 0; }
const hardcore_config *hardcore_config_get() { return &hc; }
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
    ("magic.c", "void spell_cure_blind("),
    ("ethermancer.c", "void spell_ethereal_recharge("),
    ("ethermancer.c", "void spell_greater_ethereal_recharge("),
    ("magic.c", "bool can_relocate_to("),
    ("magic.c", "void spell_dimension_door("),
    ("magic.c", "void spell_relocate("),
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

    // Air Recharge runs through real heal()/vamp(), including all amplification
    // and reduction stages, and credits only the final restored amount.
    char_data air{}, target{};
    init(air, false); init(target, false);
    air.player.m_class = CLASS_CONJURER; air.player.spec = SPEC_AIR;
    affected_type form{}, aura{}, plague{}, blind{};
    form.type = SPELL_AIR_FORM; form.duration = 8;
    aura.type = AURA_HEALING; aura.modifier = 56;
    plague.type = SPELL_PLAGUE; plague.modifier = 10000;
    blind.type = SPELL_BLINDNESS; blind.next = &form;
    for (int hp : {0, 1, 950, 1000, 1050}) {
        for (bool enhanced : {false,true}) {
            for (bool hardcore : {false,true}) {
                for (bool incoming : {false,true}) {
                    for (bool infected : {false,true}) {
                        air.points.max_hit = 1000; air.points.hit = hp;
                        air.affected = &blind; air.specials.affected_by = AFF_BLIND;
                        form.next = incoming ? &aura : (infected ? &plague : nullptr);
                        aura.next = infected ? &plague : nullptr;
                        air.specials.affected_by3 = (enhanced ? AFF3_ENHANCE_HEALING : 0) |
                            (incoming ? AFF3_PALADIN_AURA : 0);
                        air.specials.act2 = hardcore ? PLR2_HARDCORE_CHAR : 0;
                        hc.bonus_healing_multiplier = 2.0;
                        air.specials.fighting = &target;
                        cured = 0; healing_done = healing_xp = -1;
                        spell_ethereal_recharge(56, &air, nullptr, 0, &air, nullptr);
                        int gain = air.points.hit - hp;
                        assert(gain >= 0 && gain <= 100 && air.points.hit <= std::max(hp,1000));
                        assert(cured == 1 && healing_done == gain && healing_xp == gain);
                        assert(!IS_AFFECTED(&air, AFF_BLIND) && !affected_by_spell(&air, SPELL_BLINDNESS));
                        if (!infected) assert(gain == std::max(0,std::min(100,1000-hp)));
                    }
                }
            }
        }
    }
    air.specials.fighting = nullptr;
    air.specials.affected_by3 = air.specials.act2 = 0;
    form.next = nullptr; air.affected = nullptr;
    air.points.hit = 0;
    cured = 0; spell_ethereal_recharge(56, &air, nullptr, 0, &air, nullptr);
    assert(air.points.hit == 0 && cured == 0);
    air.specials.affected_by2 = AFF2_AIR_AURA;
    spell_ethereal_recharge(56, &air, nullptr, 0, &air, nullptr);
    assert(air.points.hit == 0 && cured == 0); // loose aura never grants the exception
    air.affected = &form; air.specials.affected_by2 = 0;
    spell_greater_ethereal_recharge(56, &air, nullptr, 0, &air, nullptr);
    assert(air.points.hit == 0); // No new Greater Recharge self-target exception.
    target.points.hit = 0;
    spell_ethereal_recharge(56, &air, nullptr, 0, &target, nullptr);
    assert(target.points.hit == 0); // another player gains no new target route
    target.specials.affected_by4 = AFF4_PHANTASMAL_FORM;
    spell_ethereal_recharge(56, &air, nullptr, 0, &target, nullptr);
    assert(target.points.hit == 150);
    air.player.spec = SPEC_FIRE; air.points.hit = 0;
    spell_ethereal_recharge(56, &air, nullptr, 0, &air, nullptr);
    assert(air.points.hit == 0);
    // Small roll plus the real plague reduction must remain below the ceiling.
    air.player.spec = SPEC_AIR; form.next = &plague; dice_total = 50;
    spell_ethereal_recharge(56, &air, nullptr, 0, &air, nullptr);
    assert(air.points.hit == 35); form.next = nullptr; dice_total = 300;
    affected_type mantle{}; mantle.type = SPELL_BMANTLE; mantle.modifier = 10000;
    form.next = &mantle; dice_total = 50; air.points.hit = 0;
    spell_ethereal_recharge(56, &air, nullptr, 0, &air, nullptr);
    assert(air.points.hit == 37); form.next = nullptr; dice_total = 300;
    char_data pet{}; pet.specials.act = ACT_ISNPC;
    SET_POS(&pet, STAT_NORMAL + POS_STANDING); pet.points.max_hit = 1000;
    pet_fixture = &pet; owner_fixture = &air;
    for (int race : {RACE_A_ELEMENTAL, RACE_V_ELEMENTAL, RACE_W_ELEMENTAL}) {
        pet.player.race = race; pet.points.hit = 0;
        spell_ethereal_recharge(56, &air, nullptr, 0, &pet, nullptr);
        assert(pet.points.hit == (race == RACE_W_ELEMENTAL ? 0 : 150));
    }
    pet_fixture = owner_fixture = nullptr;

    // Whole travel handlers, retaining actual target/PvP/ocean checks and waits
    // even when a travel attempt is rejected.
    for (int kind : {0,1,2,3}) {
        for (bool npc : {false,true}) {
            init(air, false); init(target, false);
            air.specials.act = npc ? ACT_ISNPC : 0;
            if (kind == 0) { air.player.m_class = CLASS_CONJURER; air.player.spec = SPEC_AIR; }
            if (kind == 1) { air.player.m_class = CLASS_CONJURER; air.player.spec = SPEC_FIRE; }
            if (kind == 2) { air.player.m_class = CLASS_SORCERER; air.player.spec = SPEC_SHADOW; }
            if (kind == 3) { air.player.m_class = CLASS_SORCERER; air.player.spec = 0; }
            for (int failure : {0,1,2,3,4}) {
                rooms[1] = {}; rooms[2] = {};
                if (failure == 1) rooms[2].sector_type = SECT_OCEAN;
                if (failure == 2) rooms[1].room_flags = ROOM_NO_TELEPORT;
                hostile = failure == 3; raid_allowed = failure != 4;
                air.in_room = 1; target.in_room = 2; wait_pulses = 0;
                spell_dimension_door(56, &air, nullptr, 0, &target, nullptr);
                int dd_wait = kind == 2 ? WAIT_SEC : (npc ? WAIT_SEC+1 : WAIT_SEC*(kind==0 ? 3 : 9));
                assert(wait_pulses == dd_wait && air.in_room == (failure ? 1 : 2));
                air.in_room = 1; wait_pulses = 0;
                spell_relocate(56, &air, nullptr, 0, &target, nullptr);
                int relocate_wait = kind == 2 ? 4 : (npc ? 5 : (kind==0 ? WAIT_SEC*5 : 80));
                assert(wait_pulses == relocate_wait && air.in_room == (failure ? 1 : 2));
            }
        }
    }
    puts("Cleric compatibility and Air: real healing modifiers/cap/credit, target controls and travel waits passed");
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
