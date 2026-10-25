#!/usr/bin/env python3
"""Execute innate registration and both production affinity aggression paths."""
import re
import subprocess
from pathlib import Path

from _paths import ROOT, HARNESS_STUBS, extract_function, source

innates = source('innates.c').read_text()
table = re.search(r'const struct innate_data innates_data\[LAST_INNATE \+ 1\] = .*?\n};', innates, re.S).group()
table = re.sub(r'(\{ "[^"]+", )\w+( \})', r'\1NULL\2', table)
macros = innates[innates.index('#define ADD_RACIAL_INNATE'):innates.index('float regen_factor')]
arrays = innates[innates.index('char racial_innates['):innates.index('extern const struct race_names')]

prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "world/map.h"
#include "world/weather.h"
#include "classes/necromancy.h"
#include "combat/justice.h"
#include "guild/assocs.h"
#include "guild/guildhall.h"
#include "world/buildings.h"
#include "item/objmisc.h"
#include "net/comm.h"
#include "magic/spells.h"
#include <cassert>
#include <cstring>
#include <cstdlib>
#include <string>
room_data rooms[2]{};
P_room world = rooms;
const int top_of_world = 1;
index_data indexes[1]{};
P_index mob_index = indexes;
zone_data zones[1]{};
zone_data *zone_table = zones;
hometown_data hometowns[1]{};
time_info_data time_info{};
Skill skills[MAX_SKILLS];
static int attacks;
int GET_CLASS(P_char ch, unsigned int cls) { return (ch->player.m_class & cls) != 0; }
bool affected_by_spell(P_char, int) { return false; }
affected_type *get_spell_from_char(P_char, int, void *, int) { return nullptr; }
P_char get_linked_char(P_char, int) { return nullptr; }
bool AdjacentInRoom(P_char, P_char) { return true; }
bool aggressive_to_race(P_char, P_char) { return false; }
bool aggressive_to_class(P_char, P_char) { return false; }
int number(int from, int) { return from; }
int IS_MORPH(P_char) { return false; }
int BOUNDED(int low, int value, int high) { return std::max(low, std::min(value, high)); }
int real_room(int) { return 0; }
bool is_aggr_to(P_char, P_char) { assert(false); return false; }
int IS_THIEF(P_char) { return false; }
int IS_WARRIOR(P_char) { return false; }
int GET_ALT_SIZE(P_char) { return 2; }
int get_takedown_size(P_char) { return 2; }
int GET_CHAR_SKILL_P(P_char, int) { assert(false); return 0; }
bool isBashable(P_char, P_char, bool) { assert(false); return false; }
void *__malloc(size_t size, const char *, const char *, int) { return std::calloc(1, size); }
void __free(void *pointer, const char *, int) { std::free(pointer); }
void send_to_char(const char *, P_char) {}
void act(const char *, int, P_char, P_obj, void *, int) {}
bool training_dummy_is(const P_char) { return false; }
bool training_dummy_target_allowed(P_char, P_char) { return true; }
void training_dummy_retarget_nonpet(P_char, P_char) {}
bool collector_presence_is_npc(P_char) { return false; }
void MobRetaliateRange(P_char, P_char) { assert(false); }
void stop_riding(P_char) { assert(false); }
bool DragonCombat(P_char, int) { assert(false); return false; }
void set_fighting(P_char, P_char) { assert(false); }
bool backstab(P_char, P_char) { assert(false); return false; }
void bodyslam(P_char, P_char) { assert(false); }
void bash(P_char, P_char, bool) { assert(false); }
void attack(P_char, P_char) { ++attacks; }
'''

functions = [
    ('utility.c', 'int flag2idx('),
    ('innates.c', 'static int innate_char_race('),
    ('innates.c', 'static int innate_unlock_level('),
    ('innates.c', 'bool has_innate('),
    ('innates.c', 'void assign_innates('),
    ('innates.c', 'string list_innates('),
    ('mobact.c', 'void remember(P_char ch, P_char victim, bool check_group_remember)'),
    ('mobact.c', 'void clearMemory(P_char ch)'),
    ('mobact.c', 'int CheckFor_remember(P_char ch, P_char victim)\n{'),
    ('utility.c', 'bool has_native_planar_affinity('),
    ('utility.c', 'bool aggressive_to('),
    ('mobact.c', 'void MobStartFight('),
]

driver = r'''
int main() {
    assign_innates();
    char_data player{}, mob{}, pet{}, groupmate{};
    pc_only_data pc{};
    npc_only_data npc{}, pet_npc{};
    player.only.pc = &pc;
    mob.only.npc = &npc; mob.specials.act = ACT_ISNPC | ACT_MEMORY;
    pet.only.npc = &pet_npc; pet.specials.act = ACT_ISNPC;
    SET_POS(&player, STAT_NORMAL + POS_STANDING);
    SET_POS(&mob, STAT_NORMAL + POS_STANDING);
    player.player.race = RACE_HUMAN;
    pc.pid = 215;
    Memory memory{};
    memory.pcID = pc.pid;
    mob.player.race = RACE_HUMAN;
    mob.in_room = player.in_room = 0;
    npc.aggro_flags = AGGR_ALL;
    struct Grant { int cls, spec, innate, first, last; const char *name; };
    Grant grants[] = {
        {CLASS_CONJURER, SPEC_AIR, INNATE_AIR_AFFINITY, AIRSTART, AIREND, "air affinity"},
        {CLASS_CONJURER, SPEC_WATER, INNATE_WATER_AFFINITY, WATERSTART, WATEREND, "water affinity"},
        {CLASS_CONJURER, SPEC_FIRE, INNATE_FIRE_AFFINITY, FIRESTART, FIREEND, "fire affinity"},
        {CLASS_CONJURER, SPEC_EARTH, INNATE_EARTH_AFFINITY, EARTHSTART, EARTHEND, "earth affinity"},
        {CLASS_PSIONICIST, SPEC_PSYCHEPORTER, INNATE_ASTRAL_NATIVE, ASTRALSTART, ASTRALEND, "astral affinity"},
    };
    assert(INNATE_REFLECTION == 179 && INNATE_AIR_AFFINITY == 180 && LAST_INNATE == 183);
    for (const auto &g : grants) {
        player.player.m_class = g.cls; player.player.spec = g.spec;
        auto listing = list_innates(0, flag2idx(g.cls), g.spec);
        assert(listing.find(std::string(g.name) + " &n(obtained at level &+c51") != std::string::npos);
        assert(!strcmp(innates_data[g.innate].name, g.name));
        assert(!innates_data[g.innate].func);
        for (int level : {30, 41, 46, 50, 51, 56}) {
            player.player.level = level;
            assert(has_innate(&player, g.innate) == (level >= 51));
            for (int room : {g.first - 1, g.first, g.last, g.last + 1, 1}) {
                rooms[0].number = room;
                const bool protected_here = level >= 51 && room >= g.first && room <= g.last;
                assert(has_native_planar_affinity(&player) == protected_here);
                for (int mob_level : {1, 56, 100}) {
                    mob.player.level = mob_level;
                    npc.memory = nullptr;
                    assert(aggressive_to(&mob, &player) == !protected_here);
                    // Provoke, flee/re-enter: memory overrides affinity at any mob level.
                    npc.memory = &memory;
                    assert(aggressive_to(&mob, &player));
                }
                for (int boss : {19840, 19870, 1}) {
                    indexes[0].virtual_number = boss;
                    attacks = 0; npc.memory = nullptr;
                    MobStartFight(&mob, &player);
                    assert(attacks == ((boss != 1 && protected_here) ? 0 : 1));
                    attacks = 0; npc.memory = &memory;
                    MobStartFight(&mob, &player);
                    assert(attacks == 1);
                }
            }
        }
        rooms[0].number = g.first; player.player.level = 51;
        for (int room : {NOWHERE, top_of_world + 1}) {
            player.in_room = room; assert(!has_native_planar_affinity(&player));
        }
        player.in_room = 0;
        pet.player = player.player; pet.in_room = 0; pet.following = &player;
        assert(!has_native_planar_affinity(&pet));
        groupmate.in_room = 0; groupmate.player.level = 56;
        assert(!has_native_planar_affinity(&groupmate));
        npc.memory = nullptr;
        assert(aggressive_to(&mob, &pet));
        assert(aggressive_to(&mob, &groupmate));
        // Losing specialization cannot retain the grant.
        player.player.spec = 0;
        assert(!has_innate(&player, g.innate));
        assert(!has_native_planar_affinity(&player));
    }
    assert(!has_native_planar_affinity(nullptr));
    // Actual group-memory propagation revokes otherwise valid native protection.
    pc_only_data group_pc{};
    groupmate.only.pc = &group_pc; group_pc.pid = 216;
    SET_POS(&groupmate, STAT_NORMAL + POS_STANDING);
    groupmate.player = player.player;
    player.player.m_class = groupmate.player.m_class = CLASS_CONJURER;
    player.player.spec = groupmate.player.spec = SPEC_WATER;
    player.player.level = groupmate.player.level = 51;
    rooms[0].number = WATERSTART;
    group_list group[2]{};
    group[0].ch = &player; group[0].next = &group[1]; group[1].ch = &groupmate;
    player.group = group;
    mob.specials.act2 = ACT2_REMEMBERS_GROUP;
    indexes[0].virtual_number = 1;
    assert(!aggressive_to(&mob, &player) && !aggressive_to(&mob, &groupmate));
    remember(&mob, &player, true);
    assert(CheckFor_remember(&mob, &player) && CheckFor_remember(&mob, &groupmate));
    assert(aggressive_to(&mob, &player) && aggressive_to(&mob, &groupmate));
    clearMemory(&mob);
    assert(!aggressive_to(&mob, &player) && !aggressive_to(&mob, &groupmate));
    // Memoryless mobs resume their usual native-plane behavior after combat.
    REMOVE_BIT(mob.specials.act, ACT_MEMORY);
    remember(&mob, &player, true);
    assert(!npc.memory && !aggressive_to(&mob, &player));
    puts("Planar affinity: registration, names, 50/51 gates, exact boundaries, aggro, both bosses and memory passed.");
}
'''

build = ROOT / 'bin/tests/planar-affinity'
build.mkdir(parents=True, exist_ok=True)
cpp, binary = build / 'harness.cpp', build / 'harness'
cpp.write_text(prelude + macros + arrays + table + '\n'.join(
    extract_function(file, signature) for file, signature in functions) + driver)
subprocess.run(['g++', '-std=c++20', '-g', '-ffunction-sections', '-fdata-sections',
                '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie',
                '-I' + str(ROOT / 'src'), str(cpp), str(HARNESS_STUBS), '-Wl,--gc-sections',
                '-lbsd', '-o', str(binary)], check=True)
subprocess.run([str(binary)], check=True)
