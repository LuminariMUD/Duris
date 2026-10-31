#!/usr/bin/env python3
"""Execute quest awards, combat eligibility and kill-bonus XP with production bodies."""

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
#include "cmd/interp.h"
#include "core/utils.h"
#include "core/utility.h"
#include "core/files.h"
#include "magic/spells.h"
#include "persistence/persistence_checkpoint.h"
#include "net/comm.h"
#include "net/gmcp.h"
#include "net/ansi.h"
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
#include "player/player_save_pipeline.h"
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
#include <tuple>

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
bool missing_reward = false;
bool history_allowed = true;
bool defer_history = false;
std::function<void(P_char)> deferred_history;
bool player_save_pipeline_world_quest_pending(int) { return bool(deferred_history); }
int maximum_exp_level = 20, death_cutoff = -1;
double death_penalty = 0.10;
P_char last_recipient = nullptr;
obj_data reward{};
bool conjure_valid = false;
bool recipe_known = false;
bool sql_has_spellbook_mob(int, int) { return recipe_known; }
int conjure_roll = 0, conjure_intelligence = 100;
int last_random_low = 0, last_random_high = 0;
std::vector<P_char> learned_minions, failed_learning;
affected_type containment_affect{};
std::string containment_wear_off_char, containment_wear_off_room;
namespace economic_gameplay_authority {
bool enabled = false;
bool active() { return enabled; }
}

int get_property(const char *key, int fallback) {
    if (!std::strcmp(key, "exp.maxExpLevel")) return maximum_exp_level;
    if (!std::strcmp(key, "exp.goodieDeathExpLossLevelThreshold") && death_cutoff >= 0)
        return death_cutoff;
    return fallback;
}
float get_property(const char *key, double fallback) {
    return !std::strcmp(key, "exp.death.level.loss") ? death_penalty : fallback;
}
int sql_level_cap(int) { return maximum_exp_level; }
int frag_cap_config_hardcore_level_cap(int cap) { return cap; }
const hardcore_config *hardcore_config_get() { static hardcore_config config{}; return &config; }
int IS_MORPH(P_char) { return false; }
int GET_CLASS(P_char ch, unsigned int cls) { return ch->player.m_class & cls; }
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
double check_nexus_bonus_precise(P_char, double xp, int, bool) { return xp * (1 + nexus_percent); }
divine_boon_state divine_state;
bool divine_enabled = false, target_eligible = true;
const divine_boon_state *divine_boon_runtime_state() { return divine_enabled ? &divine_state : nullptr; }
bool divine_boon_reward_zone_eligible(int zone, unsigned side) {
    // Simulate the pulse-validated shared cache at this boundary. The separate
    // selection harness executes the real cache and proves no per-hit graph walk.
    if (!target_eligible || side > 1) return false;
    for (const auto &slot : divine_state.slots)
        if (slot.category == divine_boon_category::experience &&
            divine_boon_active(slot, time(nullptr)) && divine_boon_target_zone(slot) == zone)
            return true;
    return false;
}
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
bool valid_conjure(P_char, P_char) { return conjure_valid; }
void learn_conjure_recipe(P_char ch, P_char) { learned_minions.push_back(ch); }
void affect_to_char_with_messages(P_char, affected_type *af, const char *self, const char *room) {
    containment_affect = *af;
    containment_wear_off_char = self;
    containment_wear_off_room = room;
}
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
void send_to_char(const char *text, P_char ch) {
    output += text;
    last_recipient = ch;
    if (std::strstr(text, "You fail to learn")) failed_learning.push_back(ch);
}
void send_to_char_f(P_char recipient, const char *format, ...) {
    char buffer[1024];
    va_list args;
    va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);
    output += buffer;
    last_recipient = recipient;
}
void act(const char *text, int, P_char ch, P_obj, void *, int target) {
    if (!IS_AWAKE(ch) && std::strstr(text, "You fail to learn")) return;
    if (target == TO_VICT || target == TO_CHAR) output += text;
    if (target == TO_CHAR && std::strstr(text, "You fail to learn"))
        failed_learning.push_back(ch);
}
void mobsay(P_char, const char *) {}
void do_action(P_char, char *, int) {}
char *coin_stringv(int, int) { static char text[] = "coins"; return text; }
int number(int low, int high) {
    last_random_low = low; last_random_high = high;
    if (conjure_roll && low == 1 && high == conjure_intelligence) return conjure_roll;
    return low;
}
void ADD_MONEY(P_char, int) { assert(false); }
P_obj quest_item_reward(P_char) {
    if (missing_reward) return nullptr;
    reward.obj_uid=1000; reward.loc_p=LOC_NOWHERE; reward.next=nullptr; object_list=&reward;
    return &reward;
}
bool item_movement_transaction_player_busy(P_char) { return false; }
void quest_epic_reward(P_char, int, int) { ++epics; }
player_world_quest_reward captured_reward{};
bool sql_world_quest_finish_async(P_char ch, const std::vector<P_obj> &objects, bool, bool,
                                  const player_world_quest_reward &values, int,
                                  std::function<bool(P_char)> committed) {
    captured_reward = values;
    ++finished; if (!history_allowed) return false;
    auto publish = [objects, committed = std::move(committed)](P_char actor) {
        for (auto object : objects)
            if (object) { object->loc_p=LOC_CARRIED; object->loc.carrying=actor; }
        committed(actor);
    };
    if (defer_history) deferred_history=std::move(publish); else publish(ch);
    return true;
}
P_char find_character_by_runtime_id(uint64_t) { return nullptr; }
void extract_obj(P_obj, int) { object_list=nullptr; }
void resetQuest(P_char ch) {
    ch->only.pc->quest_active = 0;
    ch->only.pc->quest_mob_vnum = 0;
}
uint64_t discoveries_at_level_save = 0;
static void notify_level_advancement(P_char, int);
static void advance_level_impl(P_char ch, bool notify_player, bool, std::uint64_t) {
    discoveries_at_level_save = ch->only.pc->learned_flight_stops;
    ++ch->player.level;
    if (notify_player) notify_level_advancement(ch, GET_LEVEL(ch) - 1);
}
static void lose_level_impl(P_char ch, std::uint64_t,
    telemetry_progression_source, telemetry_progression_reason) { --ch->player.level; }
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
        history_allowed = true;
        defer_history = false;
        deferred_history = {};
        pc.divine_experience_pending = 0;
        other_pc.divine_experience_pending = 0;
        pc.quest_active = 1;
        pc.quest_mob_vnum = 55;
        pc.quest_type = FIND_AND_KILL;
        pc.quest_zone_number = zones[0].number = 123;
        zones[1].number = 456;
        rooms[0].zone = 0; rooms[1].zone = 1;
        mob.in_room = 0;
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
    // Copied residents use their original victim-race XP factor, even when
    // server configuration gives their visible race a different modifier.
    for (auto [vnum, original_race, copied_race] : {
        std::tuple{91201, RACE_HUMAN, RACE_ORC},
        {91401, RACE_HALFLING, RACE_GOBLIN}, {91402, RACE_HALFELF, RACE_TIEFLING},
        {91403, RACE_BARBARIAN, RACE_ORC}, {91404, RACE_CENTAUR, RACE_MINOTAUR},
        {91407, RACE_GNOME, RACE_KOBOLD}, {91432, RACE_GREY, RACE_DROW},
        {91441, RACE_MOUNTAIN, RACE_DUERGAR}, {91460, RACE_GITHZERAI, RACE_GITHYANKI},
        {91464, RACE_HUMAN, RACE_TIEFLING}}) {
        racial_exp_mod_victims[original_race] = .7f;
        racial_exp_mod_victims[copied_race] = 1.3f;
        mobs[0].virtual_number = vnum == 91201 ? 22801 : vnum - 62200;
        mob.player.race = original_race;
        const int original = gain_exp_modifiers_race_only(&player, &mob, 100);
        mobs[0].virtual_number = vnum;
        mob.player.race = copied_race;
        assert(tutorial_mobile_mechanics_race(&mob) == original_race);
        assert(IS_GIANT(&mob) == is_giant_race(original_race));
        assert(gain_exp_modifiers_race_only(&player, &mob, 100) == original);
        mobs[0].virtual_number = 55;
        assert(tutorial_mobile_mechanics_race(&mob) == copied_race);
        assert(IS_GIANT(&mob) == is_giant_race(copied_race));
        assert(gain_exp_modifiers_race_only(&player, &mob, 100) != original);
        for (auto &factor : racial_exp_mod_victims) factor = 1.0f;
    }
    mob.player.race = RACE_HUMAN;
    // Universal protection and ordinary penalties execute the real XP dispatcher,
    // including deleveling and the loss returned to corpse/resurrection accounting.
    for (int race : {RACE_HUMAN, RACE_OGRE, RACE_FIRBOLG}) {
        for (int side : {RACEWAR_GOOD, RACEWAR_EVIL, 0, 3}) {
            for (int level : {1, 2, 29, 30, 31}) {
                reset();
                player.player.race = race;
                player.player.racewar = side;
                player.player.level = level;
                death_penalty = 0.15;
                const int loss = gain_exp(&player, nullptr, 0, EXP_DEATH);
                assert(loss == (level < 30 ? 0 : -1500));
                assert(player.player.level == (level < 30 ? level : level - 1));
                assert(player.points.curr_exp == (level < 30 ? 0 : 8500));
                assert(dirty == (level < 30 ? 0 : 1));
                reset();
                player.player.level = level;
                player.points.curr_exp = 5000;
                assert(gain_exp(&player, nullptr, 0, EXP_DEATH) == (level < 30 ? 0 : -1500));
                assert(player.player.level == level);
                assert(player.points.curr_exp == (level < 30 ? 5000 : 3500));
            }
        }
    }
    // The double specialization must multiply at its accumulator precision.
    // Ordinary death dispatch still uses float and keeps its existing rounding.
    for (bool precise : {false, true}) {
        reset();
        player.player.level = 30;
        player.points.curr_exp = 5000000;
        new_exp_table[31] = 16777223; // Not exactly representable as float.
        death_penalty = 0.125; // Exactly representable in either precision.
        const int loss = precise ? gain_exp_amount<double>(&player, nullptr, 0, EXP_DEATH, false) :
                                   gain_exp(&player, nullptr, 0, EXP_DEATH);
        const int expected = precise ? -2097152 : -2097153;
        assert(loss == expected);
        assert(player.points.curr_exp == 5000000 + expected);
        assert(player.player.level == 30);
        assert(dirty == 1);
    }
    new_exp_table[31] = 10000;
    death_penalty = 0.15;
    // Missing-property fallback and a non-default cutoff use the same policy.
    assert(death_exp_loss_level_threshold() == 30);
    death_cutoff = 25;
    for (int level : {24, 25}) {
        reset();
        player.player.level = level;
        player.points.curr_exp = 5000;
        assert(gain_exp(&player, nullptr, 0, EXP_DEATH) == (level == 24 ? 0 : -1500));
    }
    death_cutoff = -1;
    death_penalty = 0.10;
    maximum_exp_level = 56;
    player.player.race = RACE_HUMAN;
    player.player.racewar = RACEWAR_GOOD;
    auto warning = [&](int cutoff) {
        const std::string text = "\r\n&+WWARNING: YOU HAVE REACHED LEVEL " +
            std::to_string(cutoff) + ". DEATH CAN NOW COST YOU EXPERIENCE AND "
            "CAUSE YOU TO LOSE LEVELS!&N\r\n\r\n";
        assert(output.find(text) != std::string::npos);
        assert(output.find("WARNING:", output.find("WARNING:") + 1) == std::string::npos);
        AnsiString rendered(text.c_str());
        char terminal[MAX_STRING_LENGTH], plain[MAX_STRING_LENGTH];
        rendered.term(terminal, TL_BRIGHT_BG);
        assert(std::strstr(terminal, "\x1b[0;1;37mWARNING:") != nullptr);
        rendered.plain(plain);
        assert(std::string(plain) == "\nWARNING: YOU HAVE REACHED LEVEL " +
            std::to_string(cutoff) + ". DEATH CAN NOW COST YOU EXPERIENCE AND "
            "CAUSE YOU TO LOSE LEVELS!\n\n");
    };
    // Ordinary rewards: no warning before/after the crossing, one at the crossing,
    // and one after losing a level and crossing again. Bulk awards may skip 30.
    for (auto [before, after] : {std::pair{28, 29}, {29, 30}, {28, 31}, {30, 31}, {29, 30}}) {
        reset();
        for (auto &xp : new_exp_table) xp = 10000;
        for (int level = before + 2; level <= after; ++level) new_exp_table[level] = 1000;
        player.player.level = before;
        player.points.curr_exp = 9900;
        const int award = 100 + (after - before - 1) * 1000;
        assert(gain_exp(&player, nullptr, award, EXP_QUEST) == award);
        assert(player.player.level == after);
        if (before < 30 && after >= 30) warning(30);
        else assert(output.find("WARNING:") == std::string::npos);
        assert(last_recipient == &player);
    }
    for (auto &xp : new_exp_table) xp = 10000;
    for (bool bulk : {false, true}) {
        reset();
        player.player.level = bulk ? 28 : 29;
        if (bulk) advance_to_level(&player, 31);
        else advance_level(&player);
        warning(30);
    }
    reset();
    player.player.level = 28;
    player.points.curr_exp = 30000;
    maximum_exp_level = 20;
    illithid_advance_level(&player);
    assert(player.player.level == 31);
    warning(30);
    // A high XP reserve must not advance a fragging illithid above the mortal maximum.
    reset();
    maximum_exp_level = 50;
    for (auto &xp : new_exp_table) xp = 40000000;
    player.player.level = 50;
    player.points.curr_exp = 500000000;
    illithid_advance_level(&player);
    assert(player.player.level == MAXLVLMORTAL);
    assert(player.points.curr_exp == 500000000 - 6 * 40000000);
    illithid_advance_level(&player);
    assert(player.player.level == MAXLVLMORTAL);
    assert(player.points.curr_exp == 500000000 - 6 * 40000000);
    for (auto &xp : new_exp_table) xp = 10000;
    maximum_exp_level = 20;
    reset();
    player.player.level = 24;
    death_cutoff = 25;
    player.specials.act |= PLR_MORPH;
    pc.switched = &other;
    advance_level(&player);
    warning(25);
    assert(last_recipient == &other);
    player.specials.act &= ~PLR_MORPH;
    death_cutoff = -1;
    // An award at the cap does not manufacture a threshold crossing.
    reset();
    player.player.level = 29;
    player.points.curr_exp = 10000;
    maximum_exp_level = 29;
    gain_exp(&player, nullptr, 100, EXP_QUEST);
    assert(player.player.level == 29 && output.find("WARNING:") == std::string::npos);
    maximum_exp_level = 20;
    player.player.race = RACE_HUMAN;
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
    for (int scenario = 0; scenario < 10; ++scenario) {
        reset();
        if (scenario == 0) npc.R_num = 1;
        if (scenario == 1) pc.quest_active = 0;
        if (scenario == 2) pc.quest_accomplished = 1;
        if (scenario == 3) player.specials.position = STAT_DEAD;
        if (scenario == 6) pc.quest_type = FIND_AND_ASK;
        if (scenario == 7) mob.in_room = 1;
        if (scenario == 8) mob.in_room = NOWHERE;
        if (scenario == 9) mob.in_room = top_of_world + 1;
        quest_kill(&player, scenario == 4 ? &other : scenario == 5 ? nullptr : &mob);
        assert(player.points.curr_exp == 0 && pc.quest_kill_how_many == 0);
        assert(output.find("Quest EXP:") == std::string::npos);
    }
    // An ASK interaction must match both type and the accepted destination.
    for (int scenario = 0; scenario < 6; ++scenario) {
        reset();
        pc.quest_type = scenario == 0 ? FIND_AND_KILL : FIND_AND_ASK;
        if (scenario == 1) mob.in_room = 1;
        if (scenario == 2) mob.in_room = NOWHERE;
        if (scenario == 3) mob.in_room = top_of_world + 1;
        if (scenario == 4) npc.R_num = 1;
        const auto before = pc;
        quest_ask(&player, scenario == 5 ? nullptr : &mob);
        assert(!memcmp(&before, &pc, sizeof(pc)));
        assert(player.points.curr_exp == 0 && finished == 0 && epics == 0);
    }
    reset(); pc.quest_type = FIND_AND_ASK;
    quest_ask(&player, &mob);
    assert(finished == 1 && epics == 1 && pc.quest_active == 0);
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
    // Zero applied awards: modifiers, integer truncation, global XP limits and safe rooms.
    for (int scenario = 0; scenario < 5; ++scenario) {
        reset();
        if (scenario == 0) earned_multiplier = 0;
        if (scenario == 1) racial_exp_mods[RACE_HUMAN] = 0.001f;
        if (scenario == 2) player.points.curr_exp = global_exp_limit;
        if (scenario == 3) rooms[0].room_flags = ROOM_SAFE;
        if (scenario == 4) new_exp_table[21] = 2;
        const int before = player.points.curr_exp;
        quest_kill(&player, &mob);
        assert(player.points.curr_exp == before);
        assert(output.find("Quest EXP:") == std::string::npos);
    }
    // The old twice-next-level XP gate is gone, but levelling still stops at the frag cap.
    reset();
    player.points.curr_exp = 2 * new_exp_table[21];
    assert(gain_exp(&player, nullptr, 1000, EXP_WORLD_QUEST) == 1000);
    assert(player.points.curr_exp == 21000 && player.player.level == 20);
    assert(dirty == 1);
    quest_line(1000);
    // Bank every otherwise-awarded XP point even if the retired modifier slot is changed.
    reset();
    player.points.curr_exp = new_exp_table[21];
    exp_mods[EXPMOD_OVER_LEVEL_CAP] = 0.7f;
    assert(gain_exp(&player, &mob, 1000, EXP_KILL) == 1000);
    assert(player.points.curr_exp == 11000 && player.player.level == 20);
    assert(output == "&+CEXP:&+G 1000 \r\n");
    exp_mods[EXPMOD_OVER_LEVEL_CAP] = 1.0f;
    // Only the available room under the global limit is credited.
    reset();
    global_exp_limit = 20500;
    player.points.curr_exp = 20400;
    assert(gain_exp(&player, nullptr, 1000, EXP_WORLD_QUEST) == 100);
    assert(player.points.curr_exp == global_exp_limit && dirty == 1);
    quest_line(100);
    output.clear();
    assert(gain_exp(&player, nullptr, 1000, EXP_WORLD_QUEST) == 0);
    assert(output.find("Quest EXP:") == std::string::npos && dirty == 1);
    // A misconfigured global ceiling cannot overflow the signed character XP field.
    reset();
    global_exp_limit = std::numeric_limits<long>::max();
    player.points.curr_exp = INT_MAX - 30;
    assert(gain_exp(&player, nullptr, 1000, EXP_WORLD_QUEST) == 30);
    assert(player.points.curr_exp == INT_MAX);
    quest_line(30);
    output.clear();
    assert(gain_exp(&player, nullptr, 1000, EXP_WORLD_QUEST) == 0);
    assert(player.points.curr_exp == INT_MAX && output.empty());
    reset();
    global_exp_limit = std::numeric_limits<long>::max();
    player.points.curr_exp = INT_MAX - 30;
    assert(gain_exp(&player, nullptr, 1000, EXP_QUEST) == 30);
    assert(player.points.curr_exp == INT_MAX);
    // Banked XP cannot cross the locked cap, then advances normally upon unlock.
    reset();
    player.player.level = 29;
    player.points.curr_exp = 30000;
    maximum_exp_level = 29;
    assert(gain_exp(&player, nullptr, 100, EXP_QUEST) == 100);
    assert(player.player.level == 29 && player.points.curr_exp == 30100);
    maximum_exp_level = 31;
    assert(gain_exp(&player, nullptr, 100, EXP_QUEST) == 100);
    assert(player.player.level == 31 && player.points.curr_exp == 10200);
    maximum_exp_level = 20;
    // Negative awards remain possible at the accumulation ceiling.
    reset();
    player.player.level = 30;
    player.points.curr_exp = global_exp_limit;
    assert(gain_exp(&player, nullptr, 0, EXP_DEATH) == -1000);
    assert(player.points.curr_exp == global_exp_limit - 1000);
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

    // A refused history event cannot silently clear a normal completed task either.
    reset();
    history_allowed = false;
    pc.quest_type = FIND_AND_ASK;
    quest_full_reward(&player, &mob, FIND_AND_ASK);
    assert(finished == 1 && pc.quest_active == 1);

    reset(); missing_reward = true;
    quest_full_reward(&player, &mob, FIND_AND_ASK);
    assert(finished == 0 && pc.quest_active == 1 && player.points.curr_exp == 0);
    reset(); missing_reward = true; pc.quest_kill_how_many = 4;
    quest_kill(&player, &mob);
    assert(finished == 0 && pc.quest_active == 1 &&
           pc.quest_accomplished == PLAYER_WORLD_QUEST_KILL_HISTORY_PENDING &&
           player.points.curr_exp == 260);
    quest_kill(&player, &mob);
    assert(player.points.curr_exp == 260 && finished == 0);
    missing_reward = false;
    quest_full_reward(&player, &mob, FIND_AND_KILL);
    assert(finished == 1 && pc.quest_active == 0 && player.points.curr_exp == 260);
    // A reward that would crumble on publication is refused before history.
    reset(); reward.extra2_flags = ITEM2_CRUMBLELOOT;
    quest_full_reward(&player, &mob, FIND_AND_ASK);
    assert(finished == 0 && pc.quest_active == 1 && object_list == nullptr);
    reward.extra2_flags = 0;

    // Refusing the final KILL history must not award repeatable final-kill XP.
    reset();
    history_allowed = false;
    pc.quest_kill_how_many = 4;
    quest_kill(&player, &mob);
    assert(finished == 1 && pc.quest_active == 1 &&
           pc.quest_accomplished == PLAYER_WORLD_QUEST_KILL_HISTORY_PENDING &&
           player.points.curr_exp == 260);
    quest_kill(&player, &mob);
    assert(player.points.curr_exp == 260 && finished == 1);
    history_allowed = true;
    quest_full_reward(&player, &mob, FIND_AND_KILL);
    assert(finished == 2 && pc.quest_active == 0 && player.points.curr_exp == 260);

    // A final kill crossing level 25 computes the mercenary payout at the new level.
    reset();
    player.player.level = 24;
    player.player.m_class = CLASS_MERCENARY;
    player.points.curr_exp = 9900;
    maximum_exp_level = 25;
    new_exp_table[25] = 10000;
    pc.quest_kill_how_many = 4;
    history_allowed = false;
    quest_kill(&player, &mob);
    assert(player.player.level == 25 && pc.quest_accomplished == PLAYER_WORLD_QUEST_KILL_HISTORY_PENDING);
    assert(captured_reward.money == 25 * 1256 + 1);
    const int already_credited = player.points.curr_exp;
    history_allowed = true;
    defer_history = true;
    quest_full_reward(&player, &mob, FIND_AND_KILL);
    assert(player.points.curr_exp == already_credited && captured_reward.money == 25 * 1256 + 1);
    deferred_history = {};
    player.player.m_class = 0;
    maximum_exp_level = 20;

    // An older unsecured receipt has not yet received final-kill XP.
    reset();
    pc.quest_accomplished = PLAYER_WORLD_QUEST_KILL_REWARD_UNSECURED;
    pc.quest_kill_how_many = 5;
    quest_full_reward(&player, &mob, FIND_AND_KILL);
    assert(player.points.curr_exp == 260 && finished == 1 && pc.quest_active == 0);

    // A committed marker survives loss of the live callback: the item was
    // already saved, and only the captured remaining rewards are applied.
    for (int marker : { PLAYER_WORLD_QUEST_REWARD_PENDING,
                        PLAYER_WORLD_QUEST_KILL_REWARD_PENDING }) {
        reset();
        pc.quest_accomplished = marker;
        pc.quest_receiver = marker == PLAYER_WORLD_QUEST_REWARD_PENDING ? 1300 : 260;
        pc.quest_shares_left = 0; pc.quest_kill_how_many = 0;
        object_list = nullptr;
        quest_full_reward(&player, &mob, FIND_AND_ASK);
        assert(player.points.curr_exp == (marker == PLAYER_WORLD_QUEST_REWARD_PENDING ? 1300 : 260));
        assert(finished == 0 && pc.quest_active == 0 && object_list == nullptr);
    }

    // An acknowledgement delivered after the player's level changes uses the
    // award captured at completion, not the later level's reward formula.
    for (bool final_kill : {false, true}) {
        reset(); defer_history = true;
        // Completion remains prominent even with XP feedback disabled.
        if (final_kill) player.specials.act2 = 0;
        if (final_kill) { pc.quest_kill_how_many = 4; quest_kill(&player, &mob); }
        else { pc.quest_type = FIND_AND_ASK; quest_full_reward(&player, &mob, FIND_AND_ASK); }
        assert(deferred_history && pc.quest_active == 1 &&
               player.points.curr_exp == (final_kill ? 260 : 0));
        assert(output.find("QUEST COMPLETE") == std::string::npos);
        player.player.level = 30;
        auto complete = std::move(deferred_history); deferred_history = {};
        complete(&player);
        assert(player.points.curr_exp == (final_kill ? 260 : 1300) && pc.quest_active == 0);
        if (final_kill) {
            assert(output.find(
                "\r\n&+Y================ QUEST COMPLETE ================&n\r\n"
                "&+WFor completing your quest you receive a reward&+W in your inventory.&n\r\n"
                "&+WCongratulations, you finished your quest!&n\r\n"
                "&+Y================================================&n\r\n\r\n") != std::string::npos);
        }
    }
    // Preserve each original high-level epic roll boundary.
    reset(); player.player.level = 56;
    for (int level = 46; level <= 55; ++level) {
        pc.quest_level = level;
        assert(quest_epic_reward_amount(&player) == level - 45);
        assert(last_random_low == level - 45 &&
               last_random_high == (level == 54 ? 10 : std::min(level - 43, 11)));
    }
    pc.quest_level = 56;
    assert(quest_epic_reward_amount(&player) == 15);
    pc.quest_level = 0;

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
    assert(player.points.curr_exp == global_exp_limit && output.empty());
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
    // Trainer encounters cannot grant any combat XP, with or without Divine
    // bonuses. Ordinary NPCs still award each source through the same dispatcher.
    group_list trainer_group{}, reward_group{};
    trainer_group.ch = &other;
    trainer_group.next = &reward_group;
    reward_group.ch = &player;
    for (auto trainer_flag : {0u, ACT_TEACHER, ACT_SPEC_TEACHER}) {
        for (bool enabled : {false, true}) {
            for (int kind : {EXP_DAMAGE, EXP_TANKING, EXP_MELEE, EXP_KILL, EXP_KILL_BONUS}) {
                reset_divine();
                divine_enabled = enabled;
                mob.specials.act = ACT_ISNPC | trainer_flag;
                player.group = &trainer_group;
                other.in_room = 0;
                boon_events.clear();
                const int xp = gain_exp_combat_share(&player, &mob, 100.5, 100, kind);
                assert(trainer_flag ? xp == 0 : xp > 0);
                assert(player.points.curr_exp == xp);
                if (trainer_flag) {
                    assert(dirty == 0);
                    assert(output.empty());
                    assert(boon_events.empty());
                }
            }
            for (P_char patient : {&player, &other}) {
                reset_divine();
                divine_enabled = enabled;
                in_test_group = true;
                patient->specials.fighting = &mob;
                const int xp = gain_exp(&player, patient, 40, EXP_HEALING);
                assert(trainer_flag ? xp == 0 : xp > 0);
                assert(player.points.curr_exp == xp);
                patient->specials.fighting = nullptr;
            }
            // Healing a trainer also cannot yield XP from its ordinary opponent.
            reset_divine();
            divine_enabled = enabled;
            in_test_group = true;
            mob.specials.fighting = &other;
            const int healing = gain_exp(&player, &mob, 40, EXP_HEALING);
            assert(trainer_flag ? healing == 0 : healing > 0);

            // A rejected damage award must not reach its recursive tank share.
            reset_divine();
            divine_enabled = enabled;
            in_test_group = true;
            other.points.curr_exp = 0;
            other.in_room = 0;
            other.player.race = RACE_HUMAN;
            other.player.racewar = RACEWAR_GOOD;
            other.group = &trainer_group;
            mob.specials.fighting = &other;
            gain_exp(&player, &mob, 100, EXP_DAMAGE);
            assert(trainer_flag ? other.points.curr_exp == 0 : other.points.curr_exp > 0);
            other.group = nullptr;

            // Noncombat rewards and overlapping player flags are unaffected.
            reset_divine();
            divine_enabled = enabled;
            assert(gain_exp(&player, &mob, 100, EXP_QUEST) == 100);
            other.specials.act = trainer_flag;
            player.specials.fighting = &other;
            assert(gain_exp(&player, &player, 40, EXP_HEALING) > 0);
            other.specials.act = 0;
        }
    }
    mob.specials.act = ACT_ISNPC;
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
    player.player.level = 30;
    new_exp_table[31] = 10000;
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
    assert(gain_exp(&player, &mob, 100, EXP_DAMAGE) == 200);
    assert(other.points.curr_exp == 66); // Tank credit stays unboosted; the retired cap slot affects neither actor.
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

    for (int scenario = 0; scenario < 10; ++scenario) {
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
        assert(gain_exp(&player, &mob, 100, EXP_KILL) == 100);
    }
    reset_divine();
    player.player.racewar = RACEWAR_EVIL;
    assert(gain_exp(&player, &mob, 100, EXP_KILL) == 200);
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

    // Feedback uses the credited eligible base on the precise path, not the
    // off/on difference that also includes legacy float rounding. Each source
    // starts with 100 ordinary XP and 100 eligible base after its share math.
    for (int kind : {EXP_KILL, EXP_KILL_BONUS, EXP_DAMAGE, EXP_TANKING,
                     EXP_HEALING, EXP_MELEE}) {
        for (int scenario = 0; scenario < 11; ++scenario) {
            reset_divine();
            player.group = &tank_group;
            other.in_room = player.in_room;
            player.specials.fighting = &mob;
            const bool kill = kind == EXP_KILL || kind == EXP_KILL_BONUS;
            const int value = kind == EXP_TANKING ? 300 :
                              kind == EXP_HEALING ? 40 : kind == EXP_MELEE ? 25 : 100;
            int expected = 200, bonus = 100;
            if (scenario == 1) { divine_enabled = false; expected = 100; bonus = 0; }
            if (scenario == 2) player.specials.act2 = 0;
            if (scenario == 3) { new_exp_table[21] = 300; expected = 100; bonus = 0; }
            if (scenario == 4) { new_exp_table[21] = 450; expected = 150; bonus = 50; }
            if (scenario == 5) { player.points.curr_exp = global_exp_limit - 100; expected = 100; bonus = 0; }
            if (scenario == 6) { player.points.curr_exp = global_exp_limit - 150; expected = 150; bonus = 50; }
            if (scenario == 7) { player.points.curr_exp = global_exp_limit; expected = bonus = 0; }
            if (scenario == 8 || scenario == 9) {
                global_exp_limit = static_cast<long>(INT_MAX) + 1000;
                player.points.curr_exp = INT_MAX - (scenario == 8 ? 100 : 150);
                expected = scenario == 8 ? 100 : 150;
                bonus = scenario == 8 ? 0 : 50;
            }
            if (scenario == 10) { target_eligible = false; expected = 100; bonus = 0; }
            const int before = player.points.curr_exp;
            P_char victim = kind == EXP_HEALING ? &player : &mob;
            assert(gain_exp(&player, victim, value, kind) == expected);
            assert(player.points.curr_exp - before == expected);
            if (scenario == 2) {
                assert(output.empty() && pc.divine_experience_pending == 0);
            } else if (kill) {
                const std::string line = expected ? "&+CEXP:&+G " + std::to_string(expected) +
                    (bonus ? " &+C(Divine Boon +" + std::to_string(bonus) + ")&+G" : "") + " \r\n" : "";
                assert(output == line);
                assert(pc.divine_experience_pending == 0);
            } else {
                assert(output.empty()); // Never emit a fresh line on each hit.
                assert(pc.divine_experience_pending == static_cast<uint64_t>(bonus));
            }
            output.clear();
            display_divine_experience(&player);
            const std::string summary = !kill && bonus && scenario != 2 ?
                "&+CDivine Boon:&+G +" + std::to_string(bonus) + " combat EXP this tick.&n\r\n" : "";
            assert(output == summary);
            assert(pc.divine_experience_pending == 0);
            display_divine_experience(&player);
            assert(output == summary); // A pulse cannot publish the same credit twice.
        }
    }
    reset_divine();
    for (int hit = 0; hit < 100; ++hit)
        assert(gain_exp(&player, &mob, 10, EXP_DAMAGE) == 20);
    assert(output.empty());
    display_divine_experience(&player);
    assert(output == "&+CDivine Boon:&+G +1000 combat EXP this tick.&n\r\n");
    // Opting out before the pulse also discards an already accumulated notice.
    output.clear();
    assert(gain_exp(&player, &mob, 10, EXP_DAMAGE) == 20);
    player.specials.act2 = 0;
    display_divine_experience(&player);
    assert(output.empty() && pc.divine_experience_pending == 0);
    player.specials.act2 = PLR2_EXP;
    display_divine_experience(&player);
    assert(output.empty());

    // The controlled Newhaven configuration from #479: the additional 1 XP in
    // the off/on delta is precision recovery, not an extra unit of Divine base.
    reset_divine();
    new_exp_table[21] = 400000;
    exp_mods[EXPMOD_GLOBAL] = 0.5f;
    racial_exp_mods[RACE_HUMAN] = 1.3f;
    divine_enabled = false;
    assert(gain_exp(&player, &mob, 6000, EXP_KILL) == 3899);
    assert(output == "&+CEXP:&+G 3899 \r\n");
    player.points.curr_exp = 0;
    output.clear();
    divine_enabled = true;
    assert(gain_exp(&player, &mob, 6000, EXP_KILL) == 6900);
    assert(output == "&+CEXP:&+G 6900 &+C(Divine Boon +3000)&+G \r\n");
    // Fractional base may contribute the unit crossing the final integer floor.
    reset_divine();
    racial_exp_mods[RACE_HUMAN] = 0.75f;
    nexus_percent = 0.1;
    assert(gain_exp(&player, &mob, 101, EXP_KILL) == 159);
    assert(output == "&+CEXP:&+G 159 &+C(Divine Boon +76)&+G \r\n");
    reset_divine();
    assert(gain_exp_combat_share(&player, &mob, 0.25, 0, EXP_DAMAGE) == 1);
    display_divine_experience(&player);
    assert(output.empty()); // Positive base that rounds away earns no notice.
    reset_divine();
    player.player.level = MINLVLIMMORTAL;
    assert(gain_exp(&player, &mob, 100, EXP_KILL) == 0);
    assert(output.find("Divine Boon") == std::string::npos);
    assert(pc.divine_experience_pending == 0);
    for (int kind : {EXP_QUEST, EXP_WORLD_QUEST, EXP_RESURRECT}) {
        reset_divine();
        assert(gain_exp(&player, nullptr, 100, kind) == 100);
        display_divine_experience(&player);
        assert(output.find("Divine Boon") == std::string::npos);
    }

    // Exercise learning through both production kill_gain branches. Enumerating
    // every possible roll proves the strict threshold and Charisma cap survive.
    affected_type contained{};
    contained.type = SPELL_CONTAIN_BEING;
    struct learning_case { int charisma, level, intelligence, successes; };
    for (const auto scenario : {learning_case{100, 56, 100, 43},
                               learning_case{100, 61, 100, 38},
                               learning_case{56, 56, 100, 0},
                               learning_case{157, 56, 100, 100},
                               learning_case{500, 56, 200, 173}}) {
        for (bool in_group : {false, true}) {
            int successes = 0;
            for (int roll = 1; roll <= scenario.intelligence; ++roll) {
                reset_divine();
                player.player.level = 56;
                player.player.m_class = CLASS_SUMMONER;
                player.player.spec = SPEC_MENTALIST;
                player.curr_stats.Cha = scenario.charisma;
                player.curr_stats.Luk = 0;
                player.affected = &blood;
                blood.modifier = 0;
                group.ch = &player;
                group.next = nullptr;
                player.group = in_group ? &group : nullptr;
                mob.player.level = scenario.level;
                mob.curr_stats.Int = scenario.intelligence;
                mob.affected = &contained;
                conjure_valid = true;
                conjure_roll = roll;
                conjure_intelligence = scenario.intelligence;
                learned_minions.clear();
                failed_learning.clear();
                kill_gain(&player, &mob);
                const bool success = roll < MIN(scenario.charisma, 230) - scenario.level;
                assert(learned_minions.size() == (success ? 1u : 0u));
                assert(failed_learning.size() == (success ? 0u : 1u));
                if (success) assert(learned_minions.front() == &player);
                else assert(failed_learning.front() == &player);
                successes += success;
            }
            assert(successes == scenario.successes);
        }
    }

    // One group member's failed roll neither reports to nor prevents another
    // member's successful learning attempt.
    reset_divine();
    player.player.level = other.player.level = 56;
    player.player.m_class = other.player.m_class = CLASS_SUMMONER;
    player.player.spec = other.player.spec = SPEC_MENTALIST;
    player.curr_stats.Cha = 100;
    other.curr_stats.Cha = 150;
    player.affected = &blood;
    other.affected = &other_blood;
    blood.modifier = other_blood.modifier = 0;
    player.in_room = other.in_room = 0;
    group_list other_member{};
    group.ch = &player;
    group.next = &other_member;
    other_member.ch = &other;
    player.group = other.group = &group;
    mob.player.level = 56;
    mob.curr_stats.Int = conjure_intelligence = 100;
    mob.affected = &contained;
    conjure_roll = 80;
    learned_minions.clear();
    failed_learning.clear();
    kill_gain(&player, &mob);
    assert(learned_minions.size() == 1 && learned_minions.front() == &other);
    assert(failed_learning.size() == 1 && failed_learning.front() == &player);

    // Failed rolls remain private and reach sleeping/knocked-out group members.
    for (bool knocked_out : {false, true}) {
        player.specials.position = knocked_out ? POS_STANDING | STAT_NORMAL : STAT_SLEEPING;
        if (knocked_out) SET_BIT(player.specials.affected_by, AFF_KNOCKED_OUT);
        assert(!IS_AWAKE(&player));
        learned_minions.clear();
        failed_learning.clear();
        kill_gain(&player, &mob);
        assert(failed_learning.size() == 1 && failed_learning.front() == &player);
        assert(learned_minions.size() == 1 && learned_minions.front() == &other);
        REMOVE_BIT(player.specials.affected_by, AFF_KNOCKED_OUT);
    }
    player.specials.position = POS_STANDING | STAT_NORMAL;

    // Both solo and group failed rolls suppress misleading feedback for known recipes.
    recipe_known = true;
    group.next = nullptr;
    for (bool in_group : {false, true}) {
        player.group = in_group ? &group : nullptr;
        learned_minions.clear();
        failed_learning.clear();
        kill_gain(&player, &mob);
        assert(learned_minions.empty() && failed_learning.empty());
    }
    recipe_known = false;

    // An expired mark makes no learning roll. A rejected target keeps the
    // existing eligibility feedback rather than claiming a failed random roll.
    other.group = nullptr;
    group.next = nullptr;
    player.group = nullptr;
    for (bool marked : {false, true}) {
        mob.affected = marked ? &contained : nullptr;
        conjure_valid = false;
        output.clear();
        learned_minions.clear();
        failed_learning.clear();
        kill_gain(&player, &mob);
        assert(learned_minions.empty() && failed_learning.empty());
        assert((output.find("outside of your area of expertise") != std::string::npos) == marked);
    }

    // Registration keeps the existing 25-second duration and explains expiry
    // to the target and everyone watching the encounter.
    mob.affected = nullptr;
    spell_contain_being(56, &player, nullptr, 0, &mob, nullptr);
    assert(containment_affect.type == SPELL_CONTAIN_BEING);
    assert(containment_affect.flags == AFFTYPE_SHORT);
    assert(containment_affect.duration == 25 * WAIT_SEC);
    assert(containment_wear_off_char.find("containment fades") != std::string::npos);
    assert(containment_wear_off_room.find("containment around $n fades") != std::string::npos);
    assert(containment_wear_off_room.find("can no longer be learned") != std::string::npos);
}
'''


def main() -> None:
    properties = (ROOT / "lib" / "duris.properties").read_text(encoding="utf-8")
    assert "exp.factor.overCap=" not in properties
    assert 'get_property("exp.factor.overCap"' not in source("limits.c").read_text(encoding="utf-8")
    functions = [
        extract_function("limits.c", signature)
        for signature in (
            "static telemetry_progression_source progression_source_for_type(",
            "static telemetry_progression_reason progression_reason_for_type(",
            "int death_exp_loss_level_threshold(",
            "static void notify_level_advancement(",
            "void advance_level(P_char ch)",
            "void advance_to_level(",
            "void illithid_advance_level(",
            "static void display_divine_experience(",
            "void display_gain(",
            "int exp_level_percent_modifier(",
        )
    ]
    functions += [extract_function("limits.c", "static bool divine_experience_active(")]
    functions += [extract_function("specs.ailvio.c", "int tutorial_mobile_mechanics_race(")]
    for signature in ("static void apply_exp_modifier(", "Amount gain_exp_modifiers_race_only(",
                      "Amount gain_exp_modifiers(", "Amount gain_global_exp_modifiers(",
                      "static int gain_exp_amount("):
        parameters = "typename Amount, typename Modifier" if "apply_exp_modifier" in signature else "typename Amount"
        functions += [f"template <{parameters}>\n" + extract_function("limits.c", signature)]
    functions += [extract_function("limits.c", "int gain_exp_combat_share(")]
    functions += [extract_function("limits.c", "int gain_exp(")]
    functions += [extract_function("world_quest.c", signature) for signature in (
        "static int quest_epic_reward_amount(", "int quest_exp_reward(",
        "static player_world_quest_reward world_quest_prepare_reward(",
        "static P_obj world_quest_reward_by_uid(", "static void world_quest_deliver_reward(",
        "static bool world_quest_start_reward(", "void quest_full_reward(",
        "static bool world_quest_matches_target(", "void quest_ask(", "void quest_kill(")]
    functions += [extract_function("achievements.c", "void update_addicted_to_blood(")]
    functions += [extract_function("magic.c", "void spell_contain_being(")]
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
                *flags, str(program), "src/telemetry/telemetry_progression.c", "src/economy/divine_boon.c",
                str(source("ansi.c")), str(source("unicode.c")), "-lcrypto", str(HARNESS_STUBS), "-o", str(binary),
            ], cwd=ROOT, check=True)
            subprocess.run([str(binary)], check=True, timeout=10)
    print("quest XP, trainer combat eligibility and kill-bonus credit passed (mariadb + flatfile)")


if __name__ == "__main__":
    main()
