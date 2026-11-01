#!/usr/bin/env python3
"""Regression coverage for bash knockdown Char.Vitals freshness and group observation (issue 504).

When a character is knocked down by bash:
1. Damage is evaluated against the original posture, then knockdown publishes the final posture.
2. The GMCP Char.Vitals message dispatched from combat or knockdown reflects "position": "sitting"
   immediately, rather than leaving the client showing the pre-knockdown posture.
3. Permitted group observers are flagged for an update and observe "position": "sitting" in Group.Status.
4. When bash damage is completely absorbed by a ward (0 damage dealt), Char.Vitals and Group.Status
   still dispatch promptly reflecting the knockdown posture.
5. When an attacker fails bash and topples over, the attacker's Char.Vitals reflects their fallen posture.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, HARNESS_STUBS, extract_function

def test_native_bash_vitals_runtime() -> None:
    """Execute production bash with real GMCP serializers and verify packet freshness."""
    prelude = r'''
#define TAKEDOWN_DEFAULT 0
#define TAKEDOWN_AIR_ELEMENTAL BIT_1
#define TAKEDOWN_FIRE_ELEMENTAL BIT_2
#define TAKEDOWN_EARTH_ELEMENTAL BIT_3
#define TAKEDOWN_WATER_ELEMENTAL BIT_4
#define TAKEDOWN_GHOST BIT_5
#define TAKEDOWN_AIR_AURA BIT_6
#define TAKEDOWN_VICTIM_BACK_RANK BIT_7
#define TAKEDOWN_CHAR_BACK_RANK BIT_8
#define TAKEDOWN_AGI_CHECK BIT_9
#define TAKEDOWN_DRAGON BIT_10
#define TAKEDOWN_NO_BASH BIT_11
#define TAKEDOWN_FOOTING BIT_12
#define TAKEDOWN_HARPY BIT_13
#define TAKEDOWN_GRAPPLE BIT_14
#define TAKEDOWN_EVADE BIT_15
#define TAKEDOWN_LUK_CHECK BIT_16
#define TAKEDOWN_ELEMENTALS \
    TAKEDOWN_AIR_ELEMENTAL | TAKEDOWN_FIRE_ELEMENTAL | TAKEDOWN_EARTH_ELEMENTAL | \
    TAKEDOWN_WATER_ELEMENTAL
#define TAKEDOWN_ALL 65535U
#define TAKEDOWN_CANCELLED -1
#define TAKEDOWN_PENALTY -2

#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "item/objmisc.h"
#include "classes/paladins.h"
#include "combat/damage.h"
#include "combat/forced_movement.h"
#include "magic/spells.h"
#include "net/comm.h"
#include "net/gmcp.h"
#include "core/json_utils.h"

#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <map>

// Global game world stubs
static room_data rooms[2]{};
P_room world = rooms;
const int top_of_world = 1;
P_desc descriptor_list = nullptr;
struct str_app_type str_app[36]{};
struct dex_app_type dex_app[36]{};
long new_exp_table[100]{};

const struct class_names class_names_table[64] = {
    { const_cast<char*>("none"), const_cast<char*>("none"), const_cast<char*>("no"), 'N' },
    { const_cast<char*>("warrior"), const_cast<char*>("warrior"), const_cast<char*>("wa"), 'W' }
};

const struct race_names race_names_table[100] = {
    { const_cast<char*>("human"), const_cast<char*>("human"), const_cast<char*>("hu"), const_cast<char*>("human") }
};

// GMCP delivery interception
static std::map<P_desc, std::vector<std::pair<std::string, std::string>>> gmcp_deliveries;

void gmcp_send(struct descriptor_data *desc, const char *pkg, const char *data)
{
    if (desc && pkg && data)
    {
        gmcp_deliveries[desc].emplace_back(pkg, data);
    }
}

// Harness state controls
static bool force_bash_hit = true;
static bool zero_damage_ward = false;
static int melee_damage_calls = 0;
static int damage_entry_position = -1;
static P_char tackle_target = nullptr;

int number(int low, int high)
{
    if (!force_bash_hit)
        return high; // trigger miss
    return low;      // trigger hit
}

int dice(int num, int size) { return num * size; }

int CanDoFightMove(P_char, P_char) { return 1; }
void appear(P_char, bool) {}
P_char guard_check(P_char, P_char victim) { return victim; }
int get_takedown_size(P_char) { return 0; }
bool has_innate(P_char, int) { return false; }
int on_front_line(P_char) { return 1; }
bool notch_skill(P_char, int, float) { return false; }
float get_property(const char *, double fallback, bool) { return fallback; }
float get_property(const char *, double fallback) { return fallback; }
int get_property(const char *, int fallback) { return fallback; }
bool good_for_skewering(P_obj) { return false; }
float takedown_check(P_char, P_char, float chance, int, ulong) { return chance; }
int CountNumGreaterElementalFollowersInSameRoom(P_char) { return 0; }
void engage(P_char, P_char) {}
void CharWait(P_char ch, int) { SET_BIT(ch->specials.act2, PLR2_WAIT); }
P_char ParseTarget(P_char, char *) { return tackle_target; }
void set_fighting(P_char ch, P_char victim) { ch->specials.fighting = victim; }
void unlink_char(P_char, P_char, ush_int) {}
using forced_departure_message = std::pair<uint64_t, std::string>;
static std::vector<forced_departure_message> snapshot_forced_departure(P_char, P_char, int, bool, bool)
{ assert(false); return {}; }
static void deliver_forced_departure(const std::vector<forced_departure_message> &, P_char, P_char, int, bool)
{ assert(false); }
static void forced_rebound_messages(P_char, P_char, forced_block, bool) { assert(false); }
forced_move_result move_forced_pair(P_char, P_char, int, const std::function<void()> &)
{ assert(false); return {forced_move_status::interrupted}; }
affected_type *affect_to_char(P_char, affected_type *) { return nullptr; }
void set_short_affected_by(P_char, int, int) {}
bool affected_by_spell(P_char, int) { return false; }
int GET_CHAR_SKILL_P(P_char, int) { return 90; }
P_char get_linked_char(P_char, int) { return nullptr; }
void send_to_char(const char *, P_char) {}
void act(const char *, int, P_char, P_obj, void *, int) {}
void debug(const char *, ...) {}
void logit(int, const char *, ...) {}

int flag2idx(int) { return 1; }
int BOUNDED(int a, int b, int c) { return b < a ? a : b > c ? c : b; }
int STAT_INDEX(int s) { return s; }
int GET_CLASS(P_char, unsigned int) { return 0; }
int GET_PRIME_CLASS(P_char ch, uint m_class) { return (ch && (ch->player.m_class & m_class)); }
int GET_SECONDARY_CLASS(P_char, uint) { return 0; }
void stop_fighting(P_char) {}
void stop_riding(P_char) {}
void Stun(P_char, P_char, int, bool) {}
int NumAttackers(P_char) { return 0; }
void affect_from_char(P_char, int) {}
void do_wake(P_char, char *, int) {}
void do_stand(P_char, char *, int) {}
void do_alert(P_char, char *, int) {}
void StopAllAttackers(P_char) {}
void StopMercifulAttackers(P_char) {}
void clear_links(P_char, unsigned short) {}

unsigned int calculate_ch_state(P_char ch)
{
    if (ch)
    {
        if (GET_HIT(ch) < -10)
            return STAT_DEAD;
        else if (GET_HIT(ch) <= -6)
            return STAT_DYING;
        else if (GET_HIT(ch) <= -3)
            return STAT_INCAP;
        return STAT_NORMAL;
    }
    return STAT_DEAD;
}

int melee_damage(P_char ch, P_char victim, double dam, int, struct damage_messages *, int *)
{
    (void)ch;
    ++melee_damage_calls;
    damage_entry_position = GET_POS(victim);
    if (zero_damage_ward)
    {
        // 0 damage dealt: returns DAM_NONEDEAD without calling gmcp_char_vitals
        return DAM_NONEDEAD;
    }
    GET_HIT(victim) -= static_cast<int>(dam);
    gmcp_char_vitals(victim);
    return DAM_NONEDEAD;
}
'''

    driver = r'''
int main()
{
    // Initialize str_app
    for (int i = 0; i < 36; ++i)
        str_app[i].todam = 2;

    // Descriptors
    descriptor_data desc_victim{};
    desc_victim.connected = CON_PLAYING;
    desc_victim.gmcp_enabled = 1;

    descriptor_data desc_observer{};
    desc_observer.connected = CON_PLAYING;
    desc_observer.gmcp_enabled = 1;

    descriptor_data desc_attacker{};
    desc_attacker.connected = CON_PLAYING;
    desc_attacker.gmcp_enabled = 1;

    // Characters
    pc_only_data attacker_pc{};
    pc_only_data victim_pc{};
    char_data attacker{};
    attacker.only.pc = &attacker_pc;
    attacker.desc = &desc_attacker;
    attacker.player.name = const_cast<char*>("Attacker");
    SET_POS(&attacker, POS_STANDING + STAT_NORMAL);

    char_data victim{};
    victim.only.pc = &victim_pc;
    victim.desc = &desc_victim;
    victim.player.name = const_cast<char*>("Victim");
    victim.points.hit = 100;
    victim.points.max_hit = 100;
    victim.points.vitality = 100;
    victim.points.max_vitality = 100;
    victim.points.mana = 100;
    victim.points.max_mana = 100;
    SET_POS(&victim, POS_STANDING + STAT_NORMAL);

    char_data observer{};
    observer.desc = &desc_observer;
    observer.player.name = const_cast<char*>("Observer");
    SET_POS(&observer, POS_STANDING + STAT_NORMAL);

    // Form group with victim and observer
    group_list g_observer{};
    g_observer.ch = &observer;
    group_list g_victim{};
    g_victim.ch = &victim;
    g_victim.next = &g_observer;

    victim.group = &g_victim;
    observer.group = &g_victim;

    // --- TEST 1: Standard successful bash knockdown ---
    force_bash_hit = true;
    zero_damage_ward = false;
    gmcp_deliveries.clear();
    desc_observer.last_group_update = 0;

    bash(&attacker, &victim, false);

    assert(GET_POS(&victim) == POS_SITTING);
    assert(melee_damage_calls == 1);
    assert(damage_entry_position == POS_STANDING);
    assert(!gmcp_deliveries[&desc_victim].empty());

    // Damage may publish the original posture; the final packet must contain knockdown.
    std::string last_vitals;
    for (const auto &[pkg, data] : gmcp_deliveries[&desc_victim])
        if (pkg == GMCP_PKG_CHAR_VITALS)
            last_vitals = data;
    assert(last_vitals.find("\"position\":\"sitting\"") != std::string::npos);

    // Group observer must have last_group_update flagged
    assert(desc_observer.last_group_update == 1);

    // Sending group status must reflect sitting position
    gmcp_deliveries.clear();
    gmcp_send_group_status(&observer);
    assert(!gmcp_deliveries[&desc_observer].empty());
    bool found_group_status = false;
    for (const auto &[pkg, data] : gmcp_deliveries[&desc_observer])
    {
        if (pkg == GMCP_PKG_GROUP_STATUS)
        {
            found_group_status = true;
            assert(data.find("\"name\":\"Victim\"") != std::string::npos);
            assert(data.find("\"position\":\"sitting\"") != std::string::npos);
        }
    }
    assert(found_group_status);

    // --- TEST 2: Bash with damage ward absorbing all damage (0 damage) ---
    SET_POS(&victim, POS_STANDING + STAT_NORMAL);
    zero_damage_ward = true;
    gmcp_deliveries.clear();
    desc_observer.last_group_update = 0;

    bash(&attacker, &victim, false);

    assert(GET_POS(&victim) == POS_SITTING);
    assert(damage_entry_position == POS_STANDING);
    bool found_vitals = false;
    for (const auto &[pkg, data] : gmcp_deliveries[&desc_victim])
    {
        if (pkg == GMCP_PKG_CHAR_VITALS)
        {
            found_vitals = true;
            assert(data.find("\"position\":\"sitting\"") != std::string::npos);
        }
    }
    assert(found_vitals);
    assert(desc_observer.last_group_update == 1);

    // --- TEST 3: Attacker fails bash and topples over ---
    SET_POS(&attacker, POS_STANDING + STAT_NORMAL);
    SET_POS(&victim, POS_STANDING + STAT_NORMAL);
    force_bash_hit = false;
    zero_damage_ward = false;
    gmcp_deliveries.clear();

    bash(&attacker, &victim, false);

    assert(GET_POS(&attacker) != POS_STANDING);
    bool found_attacker_vitals = false;
    for (const auto &[pkg, data] : gmcp_deliveries[&desc_attacker])
    {
        if (pkg == GMCP_PKG_CHAR_VITALS)
        {
            found_attacker_vitals = true;
            assert(data.find("\"position\":\"standing\"") == std::string::npos);
        }
    }
    assert(found_attacker_vitals);

    // An idle NPC with a standing default must stay down when it topples.
    npc_only_data npc_data{};
    npc_data.default_pos = POS_STANDING + STAT_NORMAL;
    char_data npc{};
    npc.specials.act = ACT_ISNPC;
    npc.only.npc = &npc_data;
    npc.points.hit = npc.points.max_hit = 100;
    SET_POS(&npc, POS_STANDING + STAT_NORMAL);
    SET_POS(&victim, POS_SITTING + STAT_NORMAL);
    const int calls_before = melee_damage_calls;
    bash(&npc, &victim, false);
    assert(GET_POS(&npc) == POS_SITTING);
    assert(!CAN_ACT((&npc)));
    assert(melee_damage_calls == calls_before);

    // Tackle starts against an idle NPC, before combat or wait can prevent
    // update_pos from restoring its default stance. Avoid movement via the
    // existing guild-room rule; this case exercises the command itself.
    rooms[0].room_flags = ROOM_GUILD;
    npc.specials.act2 = 0;
    npc.specials.fighting = nullptr;
    SET_POS(&npc, POS_STANDING + STAT_NORMAL);
    SET_POS(&attacker, POS_STANDING + STAT_NORMAL);
    attacker.specials.fighting = nullptr;
    tackle_target = &npc;
    force_bash_hit = true;
    char target[] = "npc";
    do_tackle(&attacker, target, 0);
    assert(GET_POS(&npc) == POS_SITTING);
    assert(!CAN_ACT((&npc)));
    assert(IS_FIGHTING(&attacker));

    std::printf("Bash/tackle vitals knockdown native runtime tests passed\n");
    return 0;
}
'''

    tackle_fn = extract_function("actoff.c", "void do_tackle(")
    bash_fn = extract_function("actoff.c", "void bash(P_char ch, P_char victim, bool _debug)")
    update_pos_fn = extract_function("combat/fight.c", "void update_pos(P_char ch)")
    json_build_char_vitals_fn = extract_function("core/json_utils.c", "char *json_build_char_vitals(struct char_data *ch)")
    gmcp_char_vitals_fn = extract_function("net/gmcp.c", "void gmcp_char_vitals(struct char_data *ch)")
    gmcp_send_group_status_fn = extract_function("net/gmcp.c", "void gmcp_send_group_status(struct char_data *ch)")
    update_groupies_fn = extract_function("guild/group.c", "void update_groupies(P_char ch, bool only_in_room)")

    build_root = Path(os.environ.get("BIN_ROOT", ROOT / "bin")) / "tests"
    build_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bash-vitals-", dir=build_root) as directory:
        harness = Path(directory) / "harness.cpp"
        binary = Path(directory) / "harness"
        harness.write_text(
            "\n".join((
                prelude,
                json_build_char_vitals_fn,
                update_groupies_fn,
                gmcp_char_vitals_fn,
                gmcp_send_group_status_fn,
                update_pos_fn,
                bash_fn,
                tackle_fn,
                driver,
            )),
            encoding="utf-8",
        )
        subprocess.run(
            [
                "g++",
                "-std=c++20",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-Wno-unused-parameter",
                "-Wno-unused-variable",
                *(["-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie"]
                  if os.environ.get("SANITIZE") == "1" else []),
                f"-I{ROOT / 'src'}",
                str(harness),
                str(HARNESS_STUBS),
                "-lcjson",
                "-o",
                str(binary),
            ],
            cwd=ROOT,
            check=True,
        )
        subprocess.run([str(binary)], cwd=ROOT, check=True)


if __name__ == "__main__":
    test_native_bash_vitals_runtime()
    print("All bash vitals knockdown tests passed")
