#!/usr/bin/env python3
"""Measure production ward rate/events and effective-healing refill in isolation."""
from pathlib import Path
import subprocess

from _paths import ROOT, HARNESS_STUBS, extract_function, source

properties = dict(line.split("=", 1) for line in (ROOT / "lib/duris.properties").read_text().splitlines()
                  if "=" in line and not line.startswith("#"))
assert float(properties["innate.wardingFaith.rechargeTime"]) == 240
affects = source("affects.c").read_text()
capacity = affects[affects.index("\tif (has_innate(ch, INNATE_WARDING_FAITH))"):]
capacity = capacity[:capacity.index("\n\t// sure best")]
assert "ward_reg" not in capacity, "Innate recovery must not be truncated into the integer rate"
events = source("events.c").read_text()
delays = "\n".join(line for line in events.splitlines()
                   if line.startswith("#define MOB_") and "_REGEN_DELAY" in line)

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
#include <vector>
struct regen_event_state { float accumulated; unsigned long long last_tick; };
unsigned long long ne_event_tick = 0;
static room_data rooms[1]{};
P_room world = rooms;
static int epic = 0;
static bool faith = true;
float get_property(const char *, double fallback) { return fallback; }
bool has_innate(P_char, int id) { return faith && id == INNATE_WARDING_FAITH; }
int GET_CHAR_SKILL_P(P_char, int id) { return id == SKILL_EPIC_WARDING_FAITH ? epic : 0; }
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
int move_regen(P_char, bool) { return 0; }
int hit_regen(P_char, bool) { return 0; }
int mana_regen(P_char, bool) { return 0; }
void event_move_regen(P_char, P_char, P_obj, void *) { assert(false); }
void event_hit_regen(P_char, P_char, P_obj, void *) { assert(false); }
void event_mana_regen(P_char, P_char, P_obj, void *) { assert(false); }
struct pending { P_char ch; event_func callback; unsigned long long due; regen_event_state state; };
static std::vector<pending> queue;
P_nevent get_scheduled(P_char ch, event_func callback) {
    for (const auto &e : queue) if (e.ch == ch && e.callback == callback) return reinterpret_cast<P_nevent>(1);
    return nullptr;
}
nevent_schedule_result add_event(event_func callback, int delay, P_char ch, P_char, P_obj, int,
                                 const void *data, int size) {
    assert(size == sizeof(regen_event_state));
    queue.push_back({ch, callback, ne_event_tick + delay, *static_cast<const regen_event_state *>(data)});
    return {};
}
static void advance(int pulses) {
    for (int i = 0; i < pulses; ++i) {
        ++ne_event_tick;
        for (size_t j = 0; j < queue.size();) {
            if (queue[j].due > ne_event_tick) { ++j; continue; }
            auto e = queue[j]; queue.erase(queue.begin() + j);
            e.callback(e.ch, nullptr, nullptr, &e.state);
        }
    }
}
'''
PRODUCTION = "\n".join(extract_function(file, signature) for file, signature in (
    ("utility.c", "int BOUNDED("),
    ("paladins.c", "bool has_aura("),
    ("paladins.c", "int aura_mod("),
    ("fight.c", "int vamp("),
    ("fight.c", "void heal("),
    ("magic.c", "void spell_group_heal("),
    ("limits.c", "float ward_regen("),
    ("events.c", "static struct regen_event_state regen_state_from_data("),
    ("events.c", "static unsigned long long regen_elapsed_ticks("),
    ("events.c", "void event_ward_regen("),
    ("events.c", "void StartRegen("),
))
DRIVER = r'''
static void init(char_data &ch) {
    ch = {};
    ch.specials.position = STAT_NORMAL;
    ch.player.m_class = CLASS_CLERIC;
    ch.player.spec = SPEC_HEALER;
    ch.player.level = 56;
    ch.in_room = 0;
    ch.points.max_hit = 10000;
    ch.points.max_ward = 1000;
}
int main() {
    char_data ch{}, enemy{}, mates[6]{};
    init(ch); init(enemy);
    for (int level : {30,36,46,51,56}) for (int skill : {0,32,33,65,66,98,99,100}) {
        epic = skill;
        ch.player.level = level;
        capacity(&ch);
        assert(ch.points.base_ward == level * (3 + skill / 33));
        ch.points.max_ward = ch.points.base_ward;
        ch.points.ward = 0;
        assert(std::abs(ward_regen(&ch, true) - ch.points.base_ward * 300.0 / 960.0) < .001);
        StartRegen(&ch, regen_resource::ward);
        assert(queue.size() == 1);
        StartRegen(&ch, regen_resource::ward);
        assert(queue.size() == 1);
        advance(959);
        assert(GET_WARD(&ch) < GET_MAX_WARD(&ch));
        advance(2);
        assert(GET_WARD(&ch) == GET_MAX_WARD(&ch) && queue.empty());
    }
    ch.points.ward = 0;
    ch.specials.fighting = &enemy;
    StartRegen(&ch, regen_resource::ward);
    assert(ward_regen(&ch, false) == 0 && queue.empty());
    ch.specials.fighting = nullptr;
    rooms[0].room_flags = ROOM_NO_HEAL;
    assert(ward_regen(&ch, false) == 0);
    rooms[0].room_flags = ROOM_HEAL;
    assert(ward_regen(&ch, false) > ch.points.base_ward * 300.0 / 960.0);
    rooms[0].room_flags = 0;
    ch.points.ward = ch.points.max_ward;
    ch.points.ward_reg = -1000;
    assert(ward_regen(&ch, false) < 0); // combined rate precedes full-ward early exit
    ch.points.ward_reg = 0;
    // Combat cancels the active chain; restart measures a fresh recovery span.
    ch.points.ward = 0;
    StartRegen(&ch, regen_resource::ward);
    advance(200);
    ch.specials.fighting = &enemy;
    const int before = ch.points.ward;
    advance(1);
    assert(queue.empty() && ch.points.ward == before);
    ch.specials.fighting = nullptr;
    ch.points.ward = 0;
    StartRegen(&ch, regen_resource::ward);
    advance(961);
    assert(ch.points.ward == ch.points.max_ward && queue.empty());
    // NPC capacity keeps its existing doubled multiplier.
    ch.specials.act |= ACT_ISNPC;
    capacity(&ch);
    assert(ch.points.base_ward == 56 * (3 + epic / 33) * 2);
    ch.specials.act &= ~ACT_ISNPC;
    init(ch);
    for (bool combat : {false,true}) for (int effective : {0,1,9,10,19,20,200}) {
        ch.points.ward = 0;
        ch.points.hit = ch.points.max_hit - effective;
        ch.specials.fighting = combat ? &enemy : nullptr;
        heal(&ch, &ch, 1000, ch.points.max_hit);
        assert(ch.points.ward == effective / 10);
        heal(&ch, &ch, 1000, ch.points.max_hit); // overheal is zero
        assert(ch.points.ward == effective / 10);
    }
    ch.specials.fighting = nullptr;
    // Reduced effective healing is applied before refill. A direct vamp
    // (Intercession) never refills ward.
    affected_type plague{};
    plague.type = SPELL_PLAGUE; plague.modifier = 10000;
    ch.affected = &plague;
    ch.points.ward = 0; ch.points.hit = 0;
    heal(&ch, &ch, 100, ch.points.max_hit);
    assert(ch.points.hit == 84 && ch.points.ward == 8);
    ch.affected = nullptr;
    ch.points.ward = 0;
    assert(vamp(&ch, 100, ch.points.max_hit) == 100 && ch.points.ward == 0);
    // Real Group Heal applies outgoing 1.2 and incoming white aura once, then
    // rounds each recipient's effective HP independently for ward refill.
    group_list group[6]{};
    affected_type aura{}; aura.type = AURA_HEALING; aura.modifier = 56;
    for (int size : {1,3,6}) {
        init(ch); ch.group = group;
        int expected = 14; // self: 120 * 1.2 = 144 effective, floor(/10)
        for (int i = 0; i < size - 1; ++i) {
            init(mates[i]);
            mates[i].affected = &aura;
            mates[i].specials.affected_by3 |= AFF3_PALADIN_AURA;
            group[i] = {&mates[i], i + 1 < size - 1 ? &group[i+1] : nullptr};
            expected += 16; // 144 + floor(144 * .112) = 160
        }
        if (size == 1) ch.group = nullptr;
        spell_group_heal(56, &ch, nullptr, 0, nullptr, nullptr);
        assert(ch.points.ward == expected);
        printf("Group Heal size=%d ward_refill=%d\n", size, expected);
    }
    init(ch);
    affected_type white{}; white.type = AURA_HEALING; white.modifier = 56;
    affected_type excluded{}; excluded.next = &white;
    ch.specials.affected_by3 |= AFF3_PALADIN_AURA;
    for (int type : {0, SPELL_ACCEL_HEALING, SKILL_REGENERATE}) {
        ch.points.hit = ch.points.ward = 0;
        excluded.type = type;
        ch.affected = type ? &excluded : &white;
        ch.specials.affected_by4 = type ? 0 : AFF4_REGENERATION;
        heal(&ch, &ch, 100, ch.points.max_hit);
        assert(ch.points.hit == 120 && ch.points.ward == 12);
    }
    ch.specials.affected_by4 = 0;
    ch.affected = &white;
    ch.points.hit = ch.points.ward = 0;
    heal(&ch, &ch, 100, ch.points.max_hit);
    assert(ch.points.hit == 133 && ch.points.ward == 13);
    ch.affected = nullptr;
    ch.specials.affected_by3 = 0;
    ch.points.ward = 995;
    ch.points.hit = 0;
    heal(&ch, &ch, 1000, ch.points.max_hit);
    assert(ch.points.ward == 1000);
    puts("Cleric capacity/rate/event recovery: 40 level/epic cases full within 960 +/- 1 pulses; effective heal/refill passed");
}
'''
output = ROOT / "bin/tests/cleric-ward"
output.mkdir(parents=True, exist_ok=True)
cpp, binary = output / "harness.cpp", output / "harness"
cpp.write_text(PRELUDE + delays + "\nvoid capacity(P_char ch) {\n" + capacity + "\n}\n" + PRODUCTION + DRIVER)
subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined",
                "-fno-pie", "-no-pie", "-I" + str(ROOT / "src"), str(cpp), str(HARNESS_STUBS),
                "-o", str(binary)], check=True)
subprocess.run([str(binary)], check=True)
