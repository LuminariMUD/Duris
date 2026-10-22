#!/usr/bin/env python3
"""Execute quest awards and kill-bonus XP with production function bodies."""

from pathlib import Path
import os
import re
import shlex
import subprocess
import tempfile

from _paths import ROOT, source
from _source_contract import function_body, strip_comments
from _paths import HARNESS_STUBS


def extract_function(name: str, signature: str) -> str:
    text = source(name).read_text(encoding="utf-8")
    body = function_body(text, re.escape(signature))
    assert body, signature
    start = strip_comments(text).index(signature)
    opening = text.index("{", start)
    return text[start:opening + len(body)]


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/utility.h"
#include "core/files.h"
#include "magic/spells.h"
#include "persistence/persistence_checkpoint.h"
#include "net/comm.h"
#include "net/gmcp.h"
#include "world/difficulty.h"
#include "world/hardcore_config.h"
#include "world/epic_bonus.h"
#include "combat/justice.h"
#include "combat/frag_cap_config.h"
#include "economy/boon.h"
#include "economy/divine_boon_runtime.h"
#include "economy/divine_boon_math.h"
#include "world/db.h"
#include "economy/nexus_stones.h"
#include "world/achievements.h"
#include "world/epic.h"
#include "world/experience_share.h"
#include "item/trophy.h"
#include "item/item_movement_transaction.h"
#include "sql/sql.h"
#include "telemetry/telemetry_runtime.h"
#include <cassert>
#include <algorithm>
#include <climits>
#include <cmath>
#include <limits>
#include <ctime>
#include <type_traits>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

room_data rooms[2]{};
P_room world = rooms;
extern const int top_of_world = 1;
zone_data zones[2]{};
zone_data *zone_table = zones;
index_data mobs[2]{};
P_index mob_index = mobs;
P_obj object_list = nullptr;
long new_exp_table[TOTALLVLS]{};
long global_exp_limit = 100000;
float exp_mods[EXPMOD_MAX + 1]{};
float racial_exp_mods[LAST_RACE + 1]{};
float racial_exp_mod_victims[LAST_RACE + 1]{};
std::string output;
double earned_multiplier = 1.0;
int rested_tag = 0, dirty = 0, epics = 0, finished = 0;
P_char rested_only = nullptr;
bool in_test_group = false;
double epic_percent = 0;
bool grant_allowed = true;
obj_data reward{};
namespace economic_gameplay_authority {
bool enabled = false;
bool active() { return enabled; }
}

int get_property(const char *key, int fallback) {
    if (!std::strcmp(key, "exp.maxExpLevel")) return 20;
    return fallback;
}
float get_property(const char *, double fallback) { return fallback; }
int sql_level_cap(int) { return 20; }
int frag_cap_config_hardcore_level_cap(int cap) { return cap; }
const hardcore_config *hardcore_config_get() { static hardcore_config config{}; return &config; }
int IS_MORPH(P_char) { return false; }
int GET_CLASS(P_char, unsigned int) { return 0; }
int flag2idx(int) { return 1; }
int BOUNDED(int low, int value, int high) { return MAX(low, MIN(value, high)); }
int shop_keeper(P_char, P_char, int, char *) { return 0; }
bool affected_by_spell(P_char ch, int tag) {
    for (auto *af = ch->affected; af; af = af->next)
        if (af->type == tag) return true;
    return tag == rested_tag && (!rested_only || ch == rested_only);
}
bool opposite_racewar(P_char, P_char) { return false; }
bool grouped(P_char, P_char) { return in_test_group; }
double difficulty_multiplier(difficulty_dial dial) {
    return dial == DIFFICULTY_EXP_EARNED ? earned_multiplier : 1.0;
}
int check_nexus_bonus(P_char, int xp, int) { return xp; }
double nexus_percent = 0;
double check_nexus_bonus_precise(P_char, double xp, int) { return xp * (1 + nexus_percent); }
divine_boon_state divine_state;
bool divine_enabled = false, target_eligible = true;
const divine_boon_state *divine_boon_runtime_state() { return divine_enabled ? &divine_state : nullptr; }
bool divine_boon_zone_eligible(int, unsigned) { return target_eligible; }
bool aggressive_to_basic(P_char, P_char) { return false; }
float get_epic_bonus(P_char, int) { return epic_percent; }
double get_epic_bonus_precise(P_char, int) { return epic_percent; }
std::vector<int> boon_events;
void check_boon_completion(P_char, P_char, double, int option) {
    boon_events.push_back(option);
}
void update_achievements(P_char, P_char, int, int) {}
void add_bloodlust(P_char, P_char) {}
void change_alignment(P_char, P_char) {}
bool valid_conjure(P_char, P_char) { return false; }
void learn_conjure_recipe(P_char, P_char) {}
bool gain_epic(P_char, int, int, int) { assert(false); return false; }
affected_type *affect_to_char(P_char, affected_type *) { assert(false); return nullptr; }
bool record_zone_trophy_award(P_char, P_char, int, int) { return false; }
void mark_player_dirty_components(int, player_component_mask_t) { ++dirty; }
telemetry_capture_result telemetry_runtime_game_progression(
    P_char, P_desc, telemetry_progression_observation) { return {}; }
void gmcp_char_vitals(P_char) {}
void gmcp_quest_status(P_char) {}
std::string exp_log;
void logexp(const char *format, ...) {
    char buffer[1024];
    va_list args;
    va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);
    exp_log += buffer;
}
void send_to_char(const char *text, P_char) { output += text; }
void send_to_char_f(P_char, const char *format, ...) {
    char buffer[1024];
    va_list args;
    va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);
    output += buffer;
}
void act(const char *text, int, P_char, P_obj, void *, int target) {
    if (target == TO_VICT || target == TO_CHAR) output += text;
}
void mobsay(P_char, const char *) {}
char *coin_stringv(int, int) { static char text[] = "coins"; return text; }
int number(int low, int) { return low; }
void ADD_MONEY(P_char, int) { assert(false); }
P_obj quest_item_reward(P_char) { return &reward; }
static bool grant_world_quest_reward(P_char, P_obj, int = 0, bool = false) {
    return grant_allowed;
}
bool item_movement_transaction_player_busy(P_char) { return false; }
void quest_epic_reward(P_char, int) { ++epics; }
void sql_world_quest_finished(P_char, P_obj) { ++finished; }
void resetQuest(P_char ch) {
    ch->only.pc->quest_active = 0;
    ch->only.pc->quest_mob_vnum = 0;
}
uint64_t discoveries_at_level_save = 0;
static void advance_level_impl(P_char ch, bool, bool, std::uint64_t) {
    discoveries_at_level_save = ch->only.pc->learned_flight_stops;
    ++ch->player.level;
}
static void lose_level_impl(P_char, std::uint64_t,
    telemetry_progression_source, telemetry_progression_reason) { assert(false); }
static void notify_level_advancement(P_char, int) {}
'''

CASES = r'''
int main() {
    char_data player{}, mob{}, other{};
    pc_only_data pc{}, other_pc{};
    npc_only_data npc{};
    player.only.pc = &pc;
    other.only.pc = &other_pc;
    player.player.name = const_cast<char *>("Tester");
    player.player.level = 20;
    player.player.race = RACE_HUMAN;
    player.specials.position = STAT_NORMAL;
    player.specials.act2 = PLR2_EXP;
    pc.pid = 42;
    mob.only.npc = &npc;
    mob.specials.act = ACT_ISNPC;
    mob.player.name = const_cast<char *>("target");
    mob.player.short_descr = const_cast<char *>("a target");
    mob.player.level = 20;
    mob.player.race = RACE_HUMAN;
    mobs[0].virtual_number = 55;
    mobs[1].virtual_number = 56;
    reward.short_description = const_cast<char *>("a reward");
    for (auto &xp : new_exp_table) xp = 10000;
    for (auto &mod : exp_mods) mod = 1.0f;
    for (auto &mod : racial_exp_mods) mod = 1.0f;
    for (auto &mod : racial_exp_mod_victims) mod = 1.0f;
    auto reset = [&] {
        output.clear();
        exp_log.clear();
        dirty = epics = finished = 0;
        pc.quest_active = 1;
        pc.quest_mob_vnum = 55;
        pc.quest_type = FIND_AND_KILL;
        pc.quest_accomplished = 0;
        pc.quest_kill_original = 5;
        pc.quest_kill_how_many = 0;
        player.points.curr_exp = 0;
        player.player.level = 20;
        player.specials.position = STAT_NORMAL;
        player.specials.act2 = PLR2_EXP;
        npc.R_num = 0;
        rooms[0].room_flags = 0;
        global_exp_limit = 100000;
        new_exp_table[21] = 10000;
        racial_exp_mods[RACE_HUMAN] = 1.0f;
        earned_multiplier = 1.0;
        rested_tag = 0;
    };
    auto quest_line = [&](int amount) {
        const std::string line = "&+CQuest EXP:&+G " + std::to_string(amount) + " \r\n";
        assert(output.find(line) != std::string::npos);
        assert(output.find("Quest EXP:", output.find("Quest EXP:") + 1) == std::string::npos);
        assert(output.find("&+CEXP:") == std::string::npos);
    };
    reset();
    quest_kill(&player, &mob);
    assert(player.points.curr_exp == 260 && pc.quest_kill_how_many == 1);
    quest_line(260);
    assert(output.find("you're not done yet") != std::string::npos);
    output.clear();
    pc.quest_kill_how_many = 4;
    quest_kill(&player, &mob);
    assert(player.points.curr_exp == 520 && finished == 1 && epics == 1);
    quest_line(260);
    assert(output.find("you finished your quest!") != std::string::npos);
    assert(output.find("For completing your quest you receive") != std::string::npos);
    assert(pc.quest_active == 0);

    // Qualification failures must neither award XP nor advance the kill count.
    for (int scenario = 0; scenario < 6; ++scenario) {
        reset();
        if (scenario == 0) npc.R_num = 1;
        if (scenario == 1) pc.quest_active = 0;
        if (scenario == 2) pc.quest_accomplished = 1;
        if (scenario == 3) player.specials.position = STAT_DEAD;
        quest_kill(&player, scenario == 4 ? &other : scenario == 5 ? nullptr : &mob);
        assert(player.points.curr_exp == 0 && pc.quest_kill_how_many == 0);
        assert(output.find("Quest EXP:") == std::string::npos);
    }
    // Report the modified, truncated, per-award capped amount, never the request.
    reset();
    rested_tag = TAG_RESTED;
    racial_exp_mods[RACE_HUMAN] = 0.75f;
    earned_multiplier = 0.5;
    quest_kill(&player, &mob);
    assert(player.points.curr_exp == 146);
    quest_line(146);
    reset();
    assert(gain_exp(&player, nullptr, 100000, EXP_WORLD_QUEST) == 3333);
    assert(player.points.curr_exp == 3333);
    quest_line(3333);
    // Zero applied awards: modifiers, integer truncation, XP caps and safe rooms.
    for (int scenario = 0; scenario < 6; ++scenario) {
        reset();
        if (scenario == 0) earned_multiplier = 0;
        if (scenario == 1) racial_exp_mods[RACE_HUMAN] = 0.001f;
        if (scenario == 2) player.points.curr_exp = global_exp_limit;
        if (scenario == 3) player.points.curr_exp = 2 * new_exp_table[21];
        if (scenario == 4) rooms[0].room_flags = ROOM_SAFE;
        if (scenario == 5) new_exp_table[21] = 2;
        const int before = player.points.curr_exp;
        quest_kill(&player, &mob);
        assert(player.points.curr_exp == before);
        assert(output.find("Quest EXP:") == std::string::npos);
    }
    reset();
    player.specials.act2 = 0;
    quest_kill(&player, &mob);
    assert(player.points.curr_exp == 260 && output.find("Quest EXP:") == std::string::npos);
    reset();
    player.player.level = MINLVLIMMORTAL;
    gain_exp(&player, nullptr, 123, EXP_WORLD_QUEST);
    assert(player.points.curr_exp == 0 && output.empty());
    // Nothing is credited to an immortal, so the staff log keeps the award it would have had.
    assert(exp_log.find("Tester would have gained 123 (") != std::string::npos);
    reset();
    display_gain(&player, 0, EXP_WORLD_QUEST);
    display_gain(&player, -10, EXP_WORLD_QUEST);
    assert(output.empty());

    // Turn-ins retain their existing text and emit exactly one numeric XP line.
    reset();
    quest_full_reward(&player, &mob, FIND_AND_ASK);
    assert(player.points.curr_exp == 1300 && finished == 1 && epics == 1);
    quest_line(1300);
    assert(output.find("You gain some experience.") != std::string::npos);

    reset();
    assert(gain_exp(&player, &mob, 100, EXP_KILL) == 100);
    assert(player.points.curr_exp == 100 && output == "&+CEXP:&+G 100 \r\n");
    output.clear();
    quest_kill(&player, &mob);
    assert(player.points.curr_exp == 360);
    quest_line(260);
    reset();
    player.specials.act2 = 0;
    gain_exp(&player, &mob, 100, EXP_KILL);
    assert(player.points.curr_exp == 100 && output.empty());
    reset();
    player.points.curr_exp = global_exp_limit;
    gain_exp(&player, &mob, 100, EXP_KILL);
    assert(player.points.curr_exp == global_exp_limit && output == "&+CEXP:&+G 100 \r\n");
    reset();
    gain_exp(&player, nullptr, 100, EXP_QUEST);
    assert(player.points.curr_exp == 100 && output.empty());

#ifdef QUEST_ITEM_COMPLETION
    // Accounting defers the last kill and turn-in awards until item settlement.
    economic_gameplay_authority::enabled = true;
    reward.obj_uid = 1000;
    reward.loc_p = LOC_CARRIED;
    reward.loc.carrying = &player;
    object_list = &reward;
    for (int scenario = 0; scenario < 4; ++scenario) {
        reset();
        pc.quest_started = 100;
        pc.quest_kill_how_many = 4;
        if (scenario == 1) global_exp_limit = 0;
        if (scenario == 2) player.specials.act2 = 0;
        quest_kill(&player, &mob);
        assert(player.points.curr_exp == 0 && output.empty());
        const world_quest_reward_context context = {
            world_quest_reward_source_id(&player), 1000, 42, 55, FIND_AND_KILL, false
        };
        item_transfer_result result{};
        result.root_item_uid = 1000;
        result.item_count = 1;
        world_quest_reward_completed(&player, scenario != 3, result, 0,
            reinterpret_cast<const uint8_t *>(&context), sizeof(context));
        if (scenario == 1 || scenario == 3) assert(player.points.curr_exp == 0);
        else assert(player.points.curr_exp == 260);
        if (scenario == 1 || scenario == 2 || scenario == 3)
            assert(output.find("Quest EXP:") == std::string::npos);
        else quest_line(260);
        if (scenario == 3) {
            assert(pc.quest_active == 1 && pc.quest_kill_how_many == 4 && finished == 0);
        } else {
            assert(output.find("you finished your quest!") != std::string::npos);
            assert(finished == 1 && epics == 1 && pc.quest_active == 0);
            const std::string published = output;
            world_quest_reward_completed(&player, true, result, 0,
                reinterpret_cast<const uint8_t *>(&context), sizeof(context));
            assert(output == published && finished == 1);
        }
    }
    reset();
    pc.quest_started = 101;
    quest_full_reward(&player, &mob, FIND_AND_ASK);
    assert(player.points.curr_exp == 0 && output.empty());
    const world_quest_reward_context context = {
        world_quest_reward_source_id(&player), 1000, 42, 55, FIND_AND_ASK, true
    };
    item_transfer_result result{};
    result.root_item_uid = 1000;
    result.item_count = 1;
    world_quest_reward_completed(&player, true, result, 0,
        reinterpret_cast<const uint8_t *>(&context), sizeof(context));
    assert(player.points.curr_exp == 1300 && finished == 1 && epics == 1);
    quest_line(1300);
    assert(output.find("You gain some experience.") != std::string::npos);
#endif
    // Flight discovery uses EXP_QUEST and needs the credited amount even across a level-up.
    reset();
    pc.learned_flight_stops = 2;
    assert(gain_exp(&player, nullptr, 100, EXP_QUEST) == 100);
    reset();
    rested_tag = TAG_RESTED;
    assert(gain_exp(&player, nullptr, 100, EXP_QUEST) == 150);
    reset();
    rested_tag = TAG_WELLRESTED;
    assert(gain_exp(&player, nullptr, 100, EXP_QUEST) == 200);
    reset();
    player.points.curr_exp = global_exp_limit;
    assert(gain_exp(&player, nullptr, 100, EXP_QUEST) == 0);
    reset();
    player.player.level = MINLVLIMMORTAL;
    assert(gain_exp(&player, nullptr, 100, EXP_QUEST) == 0);
    reset();
    player.player.level = 19;
    player.points.curr_exp = 9900;
    assert(gain_exp(&player, nullptr, 1000, EXP_QUEST) == 1000);
    assert(player.player.level == 20 && player.points.curr_exp == 900);
    assert(discoveries_at_level_save == 2);

    // Kill bonuses retain all XP treatment, but one slain victim advances each
    // mob/race boon only once. Exercise both branches of the real kill path.
    affected_type blood{};
    blood.type = TAG_ADDICTED_BLOOD;
    group_list group{};
    group.ch = &player;
    for (bool in_group : {false, true}) {
        for (int streak : {6, 7, 45}) {
            for (int rested : {0, TAG_RESTED, TAG_WELLRESTED}) {
                reset();
                for (auto &xp : new_exp_table) xp = 1000000;
                player.group = in_group ? &group : nullptr;
                player.affected = &blood;
                player.specials.act2 |= PLR2_BOON;
                blood.modifier = streak;
                rested_tag = rested;
                mob.points.curr_exp = 1000;
                rooms[0].people = &player;
                boon_events.clear();
                kill_gain(&player, &mob);
                const int bonus = MAX(0, (streak - 5) / 2);
                const double rest = rested == TAG_WELLRESTED ? 2.0 :
                                    rested == TAG_RESTED ? 1.5 : 1.0;
                assert(player.points.curr_exp == static_cast<int>((1000 + 10 * bonus) * rest));
                assert(std::count(boon_events.begin(), boon_events.end(), BOPT_MOB) == 1);
                assert(std::count(boon_events.begin(), boon_events.end(), BOPT_RACE) == 1);
                assert(std::count(boon_events.begin(), boon_events.end(), BOPT_NONE) ==
                       (bonus > 0 ? 2 : 1));
                assert(blood.modifier == MIN(streak + 1, 45));
                const auto line = output.find("&+CEXP:");
                assert(line != std::string::npos);
                const auto second = output.find("&+CEXP:", line + 1);
                assert((second != std::string::npos) == (bonus > 0));
                if (second != std::string::npos)
                    assert(output.find("&+CEXP:", second + 1) == std::string::npos);
            }
        }
    }
    // Run the real dispatcher, qualification and modifiers for Divine NPC XP.
    auto reset_divine = [&] {
        reset();
        for (auto &mod : exp_mods) mod = 1.0f;
        for (auto &mod : racial_exp_mods) mod = 1.0f;
        for (auto &mod : racial_exp_mod_victims) mod = 1.0f;
        player.player.racewar = RACEWAR_GOOD;
        player.affected = nullptr;
        player.group = nullptr;
        player.in_room = mob.in_room = 0;
        player.specials.fighting = mob.specials.fighting = nullptr;
        mob.player.level = 20;
        other.player.level = 20;
        mob.points.max_hit = 70;
        mob.points.curr_exp = 100;
        zones[0].number = 18;
        zones[0].flags = zones[0].hometown = 0;
        rooms[0].zone = 0;
        rooms[1].zone = 1;
        divine_enabled = target_eligible = true;
        rested_only = nullptr;
        in_test_group = false;
        nexus_percent = epic_percent = 0;
        divine_state = {};
        divine_state.mode = divine_boon_mode::divine;
        auto &slot = divine_state.slots[0];
        slot.id = 1;
        slot.category = divine_boon_category::experience;
        slot.starts_at = time(nullptr) - 10;
        slot.expires_at = time(nullptr) + 7200;
        slot.zones[0] = 18;
    };
    for (int kind : {EXP_DAMAGE, EXP_KILL, EXP_KILL_BONUS}) {
        reset_divine();
        assert(gain_exp(&player, &mob, 100, kind) == 200);
        assert(player.points.curr_exp == 200);
    }
    reset_divine();
    exp_mods[EXPMOD_GLOBAL] = 1.2f;
    assert(gain_exp(&player, &mob, 100, EXP_KILL) == 220);
    reset_divine();
    exp_mods[EXPMOD_GLOBAL] = 0.5f;
    assert(gain_exp(&player, &mob, 100, EXP_KILL) == 100);
    reset_divine();
    exp_mods[EXPMOD_GLOBAL] = 0.9f;
    assert(gain_exp(&player, &mob, 100, EXP_KILL) == 180);
    reset_divine();
    racial_exp_mods[RACE_HUMAN] = 1.2f;
    assert(gain_exp(&player, &mob, 100, EXP_KILL) == 220);
    reset_divine();
    nexus_percent = 0.2;
    assert(gain_exp(&player, &mob, 100, EXP_KILL) == 220);
    reset_divine();
    epic_percent = 0.2f;
    assert(gain_exp(&player, &mob, 100, EXP_DAMAGE) == 220);
    reset_divine();
    epic_percent = 0.01999999999;
    assert(gain_exp(&player, &mob, 100, EXP_DAMAGE) == 201); // Do not round a computed bonus upward.
    reset_divine();
    rested_tag = TAG_RESTED;
    assert(gain_exp(&player, &mob, 100, EXP_KILL) == 250);
    reset_divine();
    rested_tag = TAG_WELLRESTED;
    assert(gain_exp(&player, &mob, 100, EXP_KILL) == 300);
    reset_divine();
    earned_multiplier = 2;
    assert(gain_exp(&player, &mob, 100, EXP_KILL) == 300);
    reset_divine();
    earned_multiplier = 0.5;
    assert(gain_exp(&player, &mob, 100, EXP_KILL) == 100);
    reset_divine();
    racial_exp_mods[RACE_HUMAN] = 0.75f;
    nexus_percent = 0.1;
    assert(gain_exp(&player, &mob, 101, EXP_KILL) == 159); // One final floor.
    reset_divine();
    assert(gain_exp(&player, &mob, 10000, EXP_KILL) == 3333); // Existing cap.
    reset_divine();
    player.points.curr_exp = global_exp_limit;
    gain_exp(&player, &mob, 100, EXP_KILL);
    assert(player.points.curr_exp == global_exp_limit);
    reset_divine();
    for (int kind : {EXP_QUEST, EXP_WORLD_QUEST, EXP_RESURRECT}) {
        player.points.curr_exp = 0;
        assert(gain_exp(&player, nullptr, 100, kind) == 100);
    }
    reset_divine();
    player.points.curr_exp = 1000;
    assert(gain_exp(&player, nullptr, 0, EXP_DEATH) == -1000);
    assert(player.points.curr_exp == 0);
    reset_divine();
    player.specials.fighting = &mob;
    assert(gain_exp(&player, &player, 40, EXP_HEALING) == 200);
    reset_divine();
    other.player.level = 21;
    other.specials.fighting = &mob;
    in_test_group = true;
    assert(gain_exp(&player, &other, 2, EXP_HEALING) == 98); // Keep the half-level until final floor.
    reset_divine();
    player.specials.fighting = &other; // A player opponent cannot supply an NPC boon.
    assert(gain_exp(&player, &player, 40, EXP_HEALING) == 100);
    reset_divine();
    assert(gain_exp(&player, &mob, 25, EXP_MELEE) == 200);

    // Each tank receives its own precise unboosted share. The attacker's rest
    // and Divine increase must not feed back into that recursive calculation.
    reset_divine();
    group_list tank_group{}, attacker_group{};
    tank_group.ch = &other;
    tank_group.next = &attacker_group;
    attacker_group.ch = &player;
    player.group = other.group = &tank_group;
    other.player.level = 20;
    other.player.race = RACE_HUMAN;
    other.player.racewar = RACEWAR_GOOD;
    other.points.curr_exp = 0;
    other.in_room = 0;
    other_pc.pid = 43;
    mob.specials.fighting = &other;
    in_test_group = true;
    rested_tag = TAG_WELLRESTED;
    rested_only = &player;
    assert(gain_exp(&player, &mob, 101, EXP_DAMAGE) == 303);
    assert(other.points.curr_exp == 67); // floor(101/3 + 101/3), not 66 or 134.
    other.group = nullptr;
    reset_divine();
    player.group = other.group = &tank_group;
    other.points.curr_exp = 0;
    mob.specials.fighting = &other;
    in_test_group = true;
    player.points.curr_exp = 10000;
    exp_mods[EXPMOD_OVER_LEVEL_CAP] = 0.5f;
    assert(gain_exp(&player, &mob, 100, EXP_DAMAGE) == 100);
    assert(other.points.curr_exp == 66); // Do not inherit the attacker's level-cap reduction.
    other.group = nullptr;
    reset_divine();
    affected_type other_blood{};
    other_blood.type = TAG_ADDICTED_BLOOD;
    for (bool enabled : {false, true}) {
        reset_divine();
        divine_enabled = enabled;
        player.group = other.group = &tank_group;
        player.affected = &blood;
        other.affected = &other_blood;
        blood.modifier = other_blood.modifier = 6; // No streak award in this case.
        other.points.curr_exp = 0;
        mob.points.curr_exp = 101;
        rooms[0].people = &player;
        kill_gain(&player, &mob);
        assert(player.points.curr_exp == (enabled ? 161 : 80));
        assert(other.points.curr_exp == (enabled ? 161 : 80));
        other.group = nullptr;
    }
    for (bool enabled : {false, true}) {
        reset_divine();
        divine_enabled = enabled;
        player.affected = &blood;
        blood.modifier = 7;
        mob.points.curr_exp = 199;
        rooms[0].people = &player;
        update_addicted_to_blood(&player, &mob);
        assert(player.points.curr_exp == (enabled ? 3 : 1)); // Retain the 1.99 share.
    }

    for (int scenario = 0; scenario < 11; ++scenario) {
        reset_divine();
        if (scenario == 0) divine_enabled = false;
        if (scenario == 1) target_eligible = false;
        if (scenario == 2) divine_state.mode = divine_boon_mode::draining;
        if (scenario == 3) divine_state.slots[0].expires_at = time(nullptr);
        if (scenario == 4) divine_state.slots[0].starts_at = time(nullptr) + 60;
        if (scenario == 5) player.player.racewar = RACEWAR_UNDEAD;
        if (scenario == 6) divine_state.slots[0].zones[0] = 20;
        if (scenario == 7) divine_state.slots[0].category = divine_boon_category::epic;
        if (scenario == 8) mob.in_room = 1;
        if (scenario == 9) zones[0].flags = ZONE_TOWN; // Hometown remains zero.
        if (scenario == 10) player.player.racewar = RACEWAR_EVIL;
        assert(gain_exp(&player, &mob, 100, EXP_KILL) == 100);
    }
    reset_divine();
    rooms[0].room_flags = ROOM_SAFE;
    assert(gain_exp(&player, &mob, 100, EXP_KILL) == 0);
    reset_divine();
    earned_multiplier = std::numeric_limits<double>::infinity();
    assert(gain_exp(&player, &mob, 100, EXP_KILL) == 0);
    assert(player.points.curr_exp == 0);
    reset_divine();
    earned_multiplier = 1e100;
    assert(gain_exp(&player, &mob, 100, EXP_KILL) == 0);
    assert(player.points.curr_exp == 0);
    reset_divine();
    exp_mods[EXPMOD_GLOBAL] = 1e30f; // Overflow before the old kill log's cast.
    assert(gain_exp(&player, &mob, 100, EXP_KILL) == 0);
    assert(player.points.curr_exp == 0);
}
'''


def main() -> None:
    functions = [
        extract_function("limits.c", signature)
        for signature in (
            "static telemetry_progression_source progression_source_for_type(",
            "static telemetry_progression_reason progression_reason_for_type(",
            "void display_gain(",
            "int exp_level_percent_modifier(",
        )
    ]
    functions += [extract_function("limits.c", "static bool divine_experience_active(")]
    for signature in ("static void apply_exp_modifier(", "Amount gain_exp_modifiers_race_only(",
                      "Amount gain_exp_modifiers(", "Amount gain_global_exp_modifiers(",
                      "static int gain_exp_amount("):
        parameters = "typename Amount, typename Modifier" if "apply_exp_modifier" in signature else "typename Amount"
        functions += [f"template <{parameters}>\n" + extract_function("limits.c", signature)]
    functions += [extract_function("limits.c", "int gain_exp_combat_share(")]
    functions += [extract_function("limits.c", "int gain_exp(")]
    functions += [extract_function("world_quest.c", signature) for signature in (
        "int quest_exp_reward(", "void quest_full_reward(", "void quest_kill(")]
    functions += [extract_function("achievements.c", "void update_addicted_to_blood(")]
    functions += [extract_function("fight.c", "void kill_gain(P_char ch, P_char victim)\n")]
    quest = source("world_quest.c").read_text(encoding="utf-8")
    if "static void world_quest_reward_completed(" in quest:
        start = quest.index("struct world_quest_reward_context\n{")
        context = quest[start:quest.index("};", start) + 2]
        functions += ["#define QUEST_ITEM_COMPLETION", context]
        functions += [extract_function("world_quest.c", signature) for signature in (
            "static uint64_t world_quest_reward_source_id(",
            "static void world_quest_reward_completed(",
        )]
    directory = ROOT / "bin" / "tests"
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="quest-xp-", dir=directory) as temporary:
        program = Path(temporary) / "harness.cpp"
        program.write_text(PRELUDE + "\n" + "\n".join(functions) + CASES, encoding="utf-8")
        for backend in ("mariadb", "flatfile"):
            binary = Path(temporary) / backend
            flags = (["-D__NO_MYSQL__", "-Isrc/no_mysql"] if backend == "flatfile" else
                     shlex.split(subprocess.check_output(["mysql_config", "--cflags"], text=True)))
            subprocess.run(shlex.split(os.environ.get("CXX", "g++")) + [
                "-std=c++20", "-fsanitize=address,undefined,float-cast-overflow", "-fno-omit-frame-pointer",
                "-fno-pie", "-no-pie", "-Wall", "-Wextra", "-Wpedantic", "-Werror", "-Isrc",
                *flags, str(program), "src/telemetry/telemetry_progression.c", "src/economy/divine_boon.c", "-lcrypto", str(HARNESS_STUBS), "-o", str(binary),
            ], cwd=ROOT, check=True)
            subprocess.run([str(binary)], check=True, timeout=10)
    print("quest XP and solo/group kill-bonus boon credit passed (mariadb + flatfile)")


if __name__ == "__main__":
    main()
