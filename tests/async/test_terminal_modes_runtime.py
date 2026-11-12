#!/usr/bin/env python3
"""Exercise terminal selection, menu preservation, maps, and group presentation.

Uses production types and function bodies. World lookup, output transport and
GMCP delivery are captured boundaries; group display, pending group updates,
the hardcore death menu transition, progression and equipment mutations are
extracted with controlled stat derivation. No account/player files or running server are used.
"""
import subprocess
import tempfile
from pathlib import Path
from _paths import ROOT, HARNESS_STUBS, extract_function, source
from _innate_numbers import with_innate_numbers


PRELUDE = r'''
#include "core/prototypes.h"
#include "abilities/abilities.h"
#include "core/utils.h"
#include "core/utility.h"
#include "net/comm.h"
#include "net/gmcp.h"
#include "account/account.h"
#include "account/pwipe_launch.h"
#include "world/map.h"
#include "world/events.h"
#include "magic/spells.h"
#include "ships/ships.h"
#include "item/item_actions.h"
#include "item/encumbrance_policy.h"
#include "guild/assocs.h"
#include "telemetry/telemetry_runtime.h"
#include "world/hardcore_config.h"
#include "classes/reavers.h"
#include "economy/boon.h"
#include "economy/nexus_stones.h"
#include <cassert>
#include <cmath>
#include <cctype>
#include <cstring>
#include <vector>
static std::string output, map_data;
static int group_updates, map_updates;
static int self_vitals;
static bool closed;
static bool member_visible = true;
static P_char hidden_member;
static room_data rooms[2]{};
P_room world = rooms;
extern const int top_of_world = 1;
static zone_data zones[1]{};
zone_data *zone_table = zones;
const race_names race_names_table[LAST_RACE]{{"Human", "Human", "Human", "PH"}};
const class_names class_names_table[CLASS_COUNT + 1]{
    {"None", "None", "---", '-'}, {"Warrior", "Warrior", "War", 'w'}};
const char *greetings = "generic greeting\n";
static char ansi_greeting[] = "ansi greeting\n";
char *greetinga = ansi_greeting;
const char *greetinga1 = greetinga, *greetinga2 = greetinga;
const char *greetinga3 = greetinga, *greetinga4 = greetinga;
const char *valid_term_list = "terminal help\n";
void write_to_q(const char *text, txt_q *, int) { output += text; }
void send_to_char(const char *text, P_char) { output += text; }
void send_to_char(const char *text, P_char, int) { output += text; }
void send_to_char_f(P_char, const char *, ...) {}
void send_account_name_prompt(P_desc) { output += "Account name: "; }
void display_account_menu(P_desc, char *) { output += "Account menu"; }
bool pwipe_launch_closed_at(time_t) { return closed; }
std::string pwipe_launch_screen(bool color) { return color ? "color launch" : "plain launch"; }
int number(int a, int) { return a; }
int flag2idx(int) { return 1; }
int IS_MORPH(P_char) { return false; }
bool ac_can_see(P_char, P_char target, bool) { return member_visible || target != hidden_member; }
static int row_visits;
bool racewar(P_char, P_char) { ++row_visits; return false; }
bool has_innate(P_char, int) { return false; }
int get_real_race(P_char) { return 0; }
const char *get_class_name(P_char, P_char) { return "Warrior"; }
std::string pad_ansi(const char *text, int, bool) { return text; }
int get_property(const char *, int fallback) { return fallback; }
float get_property(const char *, double fallback) { return fallback; }
void gmcp_send_group_status(P_char) { ++group_updates; }
void gmcp_send(P_desc, const char *package, const char *) {
    if (!strcmp(package, GMCP_PKG_CHAR_VITALS)) ++self_vitals;
}
char *json_build_char_vitals(P_char) { return strdup("{}"); }
char *str_dup(const char *text) { return strdup(text); }
void __free(void *pointer, const char *, int) { assert(pointer); free(pointer); }
void gmcp_send_room_map(P_char, const char *text) { ++map_updates; map_data = text; }
void gmcp_send_quest_map(P_char ch, const char *text) { gmcp_send_room_map(ch, text); }
P_ship get_ship_from_char(P_char) { return nullptr; }
int map_view_distance(P_char, int) { return 3; }
unsigned int calculate_relative_room(unsigned int, int, int) { return 1; }
int whats_in_maproom(P_char, int, int, int) { return 0; }
float combat_by_race[LAST_RACE + 1][3]{};
float combat_by_class[CLASS_COUNT + 1][2]{};
float pulse_all = 0;
static P_char pending_balance;
static int mana_bonus;
void all_affects(P_char ch, int mode) {
    const int missing_hit = GET_MAX_HIT(ch) - GET_HIT(ch);
    const int missing_vitality = GET_MAX_VITALITY(ch) - GET_VITALITY(ch);
    P_obj body = mode ? ch->equipment[WEAR_BODY] : nullptr;
    GET_MAX_HIT(ch) = ch->points.base_hit + (body ? body->affected[0].modifier : 0);
    GET_HIT(ch) = GET_MAX_HIT(ch) - missing_hit;
    GET_MAX_VITALITY(ch) = ch->points.base_vitality;
    GET_VITALITY(ch) = GET_MAX_VITALITY(ch) - missing_vitality;
    GET_MAX_MANA(ch) = 100 + (mode ? mana_bonus : 0);
    GET_MANA(ch) = GET_MAX_MANA(ch);
}
void balance_affects(P_char ch) { pending_balance = ch; }
void item_actions_source_leaving(P_obj) {}
void clear_links(P_char, P_obj, int) {}
int char_light(P_char) { return 0; }
int room_light(int, int) { return 0; }
void gmcp_items_changed(P_char) {}
void mark_char_or_owner_dirty(P_char) {}
void statuslog(int, const char *, ...) {}
void logit(const char *, const char *, ...) {}
void die(P_char, P_char) { assert(false); }
int real_room0(int) { return 0; }
int GET_CLASS(P_char ch, uint cls) { return (ch->player.m_class & cls) != 0; }
int GET_PRIME_CLASS(P_char ch, uint cls) { return GET_CLASS(ch, cls); }
int GET_SECONDARY_CLASS(P_char ch, uint cls) { return (ch->player.secondary_class & cls) != 0; }
int GET_CHAR_SKILL_P(P_char, int) { return 0; }
bool innate_two_daggers(P_char) { return false; }
void apply_reaver_mods(P_char) { assert(false); }
void StartRegen(P_char, regen_resource) { assert(false && "full resources must not mask notifications"); }
void sql_update_level(P_char) {}
const char *PLAYERLOG = "player";
void sql_log(P_char, const char *, const char *, ...) {}
bool Guild::save() { assert(false); return false; }
void update_skills(P_char) {}
void update_pos(P_char) {}
void check_boon_completion(P_char, P_char, double, int) {}
void githyanki_weapon(P_char) { assert(false); }
void gmcp_char_status(P_char) {}
void persistence_schedule_level_checkpoint(P_char, int, int, const char *) {}
int forget_spells(P_char, int) { return 0; }
bool hardcore_config_level_loss_allowed(int) { return true; }
int check_nexus_bonus(P_char, int amount, int) { return amount; }
telemetry_capture_result telemetry_runtime_game_progression(P_char, P_desc,
                                                            telemetry_progression_observation) { return {}; }
'''

DERIVED_CASES = r'''
void check_derived_vitals() {
    descriptor_data da{}, db{}; char_data a{}, b{}; pc_only_data pa{}, pb{};
    a.desc = &da; b.desc = &db; da.character = &a; db.character = &b;
    a.only.pc = &pa; b.only.pc = &pb;
    a.player.name = (char *)"Leader"; b.player.name = (char *)"Member";
    a.player.level = b.player.level = 5;
    a.player.m_class = b.player.m_class = CLASS_WARRIOR;
    a.in_room = b.in_room = 1;
    SET_POS((&a), STAT_NORMAL + POS_STANDING); SET_POS((&b), STAT_NORMAL + POS_STANDING);
    group_list tail{&b, nullptr}, head{&a, &tail}; a.group = b.group = &head;
    for (P_char ch : {&a, &b}) {
        ch->points.base_hit = 60; ch->points.base_vitality = 100;
        all_affects(ch, TRUE);
        GET_HIT(ch) = GET_MAX_HIT(ch); GET_VITALITY(ch) = GET_MAX_VITALITY(ch);
    }
    da.term_type = db.term_type = TERM_MSP;
    obj_data armor{}; armor.type = ITEM_ARMOR; armor.affected[0].modifier = 40;
    b.equipment[WEAR_BODY] = &armor; all_affects(&b, TRUE); GET_HIT((&b)) = GET_MAX_HIT((&b));
    send_msp_group(&a, true); output.clear(); self_vitals = 0;
    assert(unequip_char(&b, WEAR_BODY, false) == &armor);
    assert(GET_HIT((&b)) == 60 && GET_MAX_HIT((&b)) == 60);
    assert(da.last_group_update == GROUP_UPDATE_ALL);
    pending_group_update(&a);
    assert(output.find("60h") != std::string::npos);
    // A temporary save unequip cannot publish the stripped intermediate stats.
    b.equipment[WEAR_BODY] = &armor; all_affects(&b, TRUE);
    da.last_group_update = db.last_group_update = 0;
    unequip_char(&b, WEAR_BODY, true);
    assert(!da.last_group_update && !db.last_group_update);
    // Deferred gear/stat changes notify only after recalculation.
    b.equipment[WEAR_BODY] = &armor; pending_balance = nullptr;
    balance_affects(&b);
    assert(!da.last_group_update && pending_balance == &b);
    event_balance_affects(pending_balance, nullptr, nullptr, nullptr);
    assert(da.last_group_update == GROUP_UPDATE_ALL);
    pending_group_update(&a);
    assert(output.find("100H") != std::string::npos);
    da.last_group_update = db.last_group_update = 0;
    self_vitals = row_visits = 0; mana_bonus = 20;
    event_balance_affects(&b, nullptr, nullptr, nullptr);
    assert(!da.last_group_update && !db.last_group_update && !self_vitals && !row_visits);
    mana_bonus = 0;
    // Remote structured observers need level metadata even if visible HP is unchanged.
    a.in_room = 0; da.gmcp_enabled = true; group_updates = 0;
    advance_level_impl(&b, false, false, 0);
    assert(GET_LEVEL((&b)) == 6 && da.last_group_update);
    pending_group_update(&a);
    assert(group_updates == 1);
    lose_level_impl(&b, 0, telemetry_progression_source::system,
                    telemetry_progression_reason::system_adjustment);
    assert(GET_LEVEL((&b)) == 5 && da.last_group_update && pending_balance == &b);
    pending_group_update(&a);
    assert(group_updates == 2);
    event_balance_affects(&b, nullptr, nullptr, nullptr);
    assert(da.last_group_update && GET_HIT((&b)) == GET_MAX_HIT((&b)));
    pending_group_update(&a);
    // Quiet mode still gets current self vitals without automatic group frames.
    db.msp_group_manual = true; db.prompt_mode = false; db.last_group_update = 0;
    ++b.points.base_hit;
    event_balance_affects(&b, nullptr, nullptr, nullptr);
    assert(db.prompt_mode && !db.last_group_update);
    FREE(da.msp_group_output);
    puts("PASS: production progression, permanent/temporary unequip and deferred derived-vitals notifications");
}
'''

CASES = r'''
int main()
{
    check_derived_vitals();
    descriptor_data d{};
    for (const auto &[input, terminal] : std::vector<std::pair<const char *, int>>{
        {"", TERM_ANSI}, {"  ", TERM_ANSI}, {"1", TERM_GENERIC}, {"01", TERM_GENERIC},
        {"2", TERM_ANSI}, {"02", TERM_ANSI}, {"3", TERM_MSP}, {"03", TERM_MSP},
        {"9", TERM_ANSI}, {"09", TERM_ANSI}, {" 3 Legacy Client", TERM_MSP}})
    {
        d.connected = CON_GET_TERM; output.clear();
        select_terminal(&d, input);
        assert(d.connected == CON_GET_ACCT_NAME && d.term_type == terminal);
        assert(output.find("Account name:") != std::string::npos);
        if (std::string(input).find("Legacy") != std::string::npos)
            assert(std::string(d.client_str) == "Legacy Client");
        if (std::string(input) == "9" || std::string(input) == "09")
            assert(output == "Account name: ");
    }
    for (const char *input : {"3junk", "0x3", "invalid", "0", "4"})
    {
        d.connected = CON_GET_TERM; d.term_type = TERM_GENERIC; output.clear();
        select_terminal(&d, input);
        assert(d.connected == CON_GET_TERM && d.term_type == TERM_GENERIC);
        assert(output.find("Unknown terminal type") != std::string::npos);
    }
    output.clear(); select_terminal(&d, "?");
    assert(d.connected == CON_GET_TERM && output.find("terminal help") != std::string::npos);
    closed = true;
    for (int terminal : {TERM_GENERIC, TERM_ANSI, TERM_MSP})
    {
        output.clear(); select_terminal(&d, std::to_string(terminal).c_str());
        assert(output.find(terminal == TERM_GENERIC ? "plain launch" : "color launch") !=
               std::string::npos);
    }
    acct_entry account{};
    acct_chars entry{};
    char fixture_name[] = "Fixture";
    entry.charname = fixture_name;
    d.account = &account;
    for (int terminal : {TERM_GENERIC, TERM_ANSI, TERM_MSP})
    for (bool populated : {false, true})
    {
        d.term_type = terminal; output.clear();
        account.acct_character_list = populated ? &entry : nullptr;
        display_delete_character_list(&d);
        assert(d.term_type == terminal);
        assert(output.find(populated ? "Fixture" : "don't have any characters") != std::string::npos);
    }
    char_data actor{}, member{};
    pc_only_data pc{}, member_pc{};
    actor.only.pc = &pc; member.only.pc = &member_pc;
    actor.desc = &d; d.character = &actor;
    actor.in_room = member.in_room = 1;
    actor.specials.position = member.specials.position = STAT_NORMAL | POS_STANDING;
    char leader_name[] = "Leader", member_name[] = "Member";
    actor.player.name = leader_name; member.player.name = member_name;
    actor.points.hit = actor.points.max_hit = member.points.hit = member.points.max_hit = 100;
    actor.points.vitality = actor.points.max_vitality = 100;
    member.points.vitality = member.points.max_vitality = 100;
    for (int terminal : {TERM_GENERIC, TERM_ANSI, TERM_MSP})
    {
        d.term_type = terminal; d.character = &actor; d.connected = CON_PLAYING;
        output.clear();
        death_return_menu(&d);
        assert(d.term_type == terminal && !d.character && d.connected == CON_DISPLAY_ACCT_MENU);
        assert(output.find("Account menu") != std::string::npos);
    }
    d.character = &actor; d.connected = CON_PLAYING;
    for (auto &symbol : sector_symbol) symbol.set("&+g.");
    for (int terminal : {TERM_GENERIC, TERM_ANSI, TERM_MSP})
    for (bool gmcp : {false, true})
    for (bool map_on : {false, true})
    for (int mode : {MAP_IGNORE_TOGGLE, MAP_USE_TOGGLE, MAP_AUTOMAP})
    {
        d.term_type = terminal; d.gmcp_enabled = gmcp;
        actor.specials.act = map_on ? PLR_MAP : 0;
        output.clear(); map_data.clear(); map_updates = 0;
        display_map_room(&actor, 1, 3, mode, 0);
        bool shown = !gmcp || ((map_on || mode == MAP_IGNORE_TOGGLE) &&
                                  (mode != MAP_AUTOMAP || terminal == TERM_MSP));
        assert(output.empty() == !shown);
        assert(map_updates == int(gmcp) && map_data.empty() == !gmcp);
        if (shown && terminal == TERM_MSP) {
            const char *tag = mode == MAP_AUTOMAP ? "automap" : "map";
            assert(output.find(std::string("<") + tag + ">") != std::string::npos);
            assert(output.find(std::string("</") + tag + ">") != std::string::npos);
        }
    }
    d.term_type = TERM_MSP; d.gmcp_enabled = false;
    actor.specials.act = PLR_MAP;
    d.last_map_update = 1; output.clear();
    map_look_room(&actor, actor.in_room, MAP_USE_TOGGLE);
    assert(!d.last_map_update && output.find("<map>") != std::string::npos);
    d.last_map_update = 1;
    map_look_room(&actor, 0, MAP_IGNORE_TOGGLE); // A remote map is not our refresh.
    assert(d.last_map_update);
    actor.specials.act = 0; output.clear();
    map_look_room(&actor, actor.in_room, MAP_AUTOMAP);
    assert(d.last_map_update && output.empty());
    group_list tail{&member, nullptr}, head{&actor, &tail};
    for (int terminal : {TERM_GENERIC, TERM_ANSI, TERM_MSP})
    for (bool gmcp : {false, true})
    for (bool websocket : {false, true})
    for (bool grouped : {false, true})
    {
        if (d.msp_group_output) FREE(d.msp_group_output);
        d.term_type = terminal; d.gmcp_enabled = gmcp; d.websocket = websocket;
        d.last_group_update = 1; actor.group = grouped ? &head : nullptr;
        output.clear(); group_updates = 0;
        pending_group_update(&actor);
        assert(!d.last_group_update && group_updates == int(gmcp));
        assert((output.find("<group>") != std::string::npos) == (terminal == TERM_MSP));
        assert((output.find("</group>") != std::string::npos) == (terminal == TERM_MSP));
        if (terminal == TERM_MSP && grouped)
            assert(output.find("Leader") != std::string::npos &&
                   output.find("Member") != std::string::npos);
    }
    for (bool gmcp : {false, true})
    for (bool websocket : {false, true})
    {
        if (d.msp_group_output) FREE(d.msp_group_output);
        d.term_type = TERM_MSP; d.gmcp_enabled = gmcp; d.websocket = websocket;
        actor.group = member.group = &head;
        actor.in_room = member.in_room = 1;
        member.points.hit = member.points.vitality = 100;
        member.specials.act2 = 0;
        member.player.name = member_name;
        hidden_member = &member;
        member_visible = true;
        auto automatic = [&](bool group_changed = true, bool structure = false) {
            output.clear(); group_updates = 0;
            if (structure) update_groupies(&member);
            else if (group_changed) update_group_vitals(&member);
            gmcp_char_vitals(&member);
            assert(bool(d.last_group_update) == (group_changed &&
                   (gmcp || structure || (!d.msp_group_manual && member.in_room == actor.in_room))));
            pending_group_update(&actor);
            assert(!d.last_group_update && group_updates == int(gmcp && group_changed));
            return output;
        };
        const std::string initial = automatic();
        assert(initial == "<group>\n( Head) Leader\n <&+G100h&n/&+G100H&n> <&+G100m&n/&+G100M&n>"
                          "\n(Front)  Member\n <&+G100h&n/&+G100H&n> <&+G100m&n/&+G100M&n>\n</group>\n");
        assert(automatic().empty());
        ++member.points.mana;
        assert(automatic(false).empty()); // Mana is not in the MSP group display.
        --member.points.hit;
        assert(automatic().find("99h") != std::string::npos);
        assert(automatic().empty());
        --member.points.vitality;
        assert(automatic().find("99m") != std::string::npos);
        SET_BIT(member.specials.act2, PLR2_BACK_RANK);
        assert(automatic(true, true).find("Back") != std::string::npos);
        member_visible = false;
        assert(automatic(true, true).find("Someone") != std::string::npos);
        member_visible = true;
        assert(automatic(true, true).find("Member") != std::string::npos);
        member.in_room = 0;
        assert(!automatic(true, true).empty());
        --member.points.hit;
        assert(automatic().empty()); // Remote HP is not displayed to this observer.
        member.in_room = 1;
        assert(automatic(true, true).find("98h") != std::string::npos);
        std::string manual;
        for (int repeat = 0; repeat < 2; ++repeat) {
            output.clear(); group_updates = 0;
            do_group(&actor, writable_arg(""), 0);
            assert(!output.empty() && group_updates == int(gmcp));
            if (repeat) assert(output == manual);
            manual = output;
        }
        assert(automatic().empty());
        // One connection's unchanged display cannot suppress another connection's first frame.
        descriptor_data other{};
        other.character = &actor; other.term_type = TERM_MSP;
        actor.desc = &other; output.clear();
        send_msp_group(&actor, false);
        assert(output == manual);
        FREE(other.msp_group_output);
        actor.desc = &d;
        actor.group = member.group = nullptr;
        output.clear(); d.last_group_update = 1;
        pending_group_update(&actor);
        assert(output == "<group>\n</group>\n");
        output.clear(); d.last_group_update = 1;
        pending_group_update(&actor);
        assert(output.empty());
        for (int repeat = 0; repeat < 2; ++repeat) {
            output.clear(); do_group(&actor, writable_arg(""), 0);
            assert(output == "<group>\n</group>\n");
        }
        actor.group = member.group = &head;
        assert(!automatic(true, true).empty());
        assert(automatic().empty());
    }
    d.term_type = TERM_MSP; d.last_group_update = 0;
    reset_msp_entry(&d);
    assert(!d.msp_group_output && d.last_group_update == GROUP_UPDATE_ALL);
    // Quiet MSP has no automatic group frames, including on real HP changes.
    d.gmcp_enabled = false; d.msp_group_manual = true;
    actor.group = member.group = &head; actor.in_room = member.in_room = 1;
    output.clear(); d.last_group_update = 0;
    --member.points.hit;
    update_group_vitals(&member);
    assert(!d.last_group_update);
    d.prompt_mode = false;
    update_group_vitals(&actor);
    assert(d.prompt_mode && !d.last_group_update);
    update_groupies(&member);
    assert(!d.last_group_update);
    send_msp_group(&actor, false);
    assert(output.empty());
    do_group(&actor, writable_arg(""), 0);
    assert(output.find("<group>") != std::string::npos);
    d.msp_group_manual = false;
    d.prompt_mode = false;
    update_group_vitals(&actor);
    assert(!d.prompt_mode); // Ordinary MSP retains its existing prompt policy.
    d.last_group_update = 0;
    row_visits = 0;
    for (int tick = 0; tick < 8; ++tick) {
        ++member.points.mana;
        ++member.points.ward;
        gmcp_char_vitals(&member); // A transport send owns no group invalidation.
        pending_group_update(&actor);
    }
    assert(!d.last_group_update && row_visits == 0);
    member.in_room = 0;
    --member.points.hit;
    update_group_vitals(&member);
    pending_group_update(&actor);
    assert(!d.last_group_update && row_visits == 0);
    FREE(d.msp_group_output);
    puts("PASS: terminal modes, unchanged automatic MSP groups, explicit groups, and leaving/rejoining");
}
'''


def main():
    entry = extract_function("nanny.c", "void enter_game(")
    reset_start = entry.index("\tif (d->msp_group_output)")
    reset_end = entry.index("\n\tP_desc i;", reset_start)
    entry_reset = "void reset_msp_entry(P_desc d) {\n" + entry[reset_start:reset_end] + "\n}\n"
    group = extract_function("group.c", "void do_group(")
    member_line = (extract_function("group.c", "static char group_vital_ansi(") +
                   extract_function("group.c", "static void show_group_member("))
    display = group[group.index("\tif (!*name)"):group.index("\n\tif (ch->group)\n")]
    group_wrapper = r'''
void do_group(P_char ch, char *, int) {
    const char *name = "";
    char Gbuf1[MAX_STRING_LENGTH];
    group_list *gl;
    int maxsize, counter;
''' + display + "\n}\n"
    comm = source("comm.c").read_text()
    start = comm.index("\t\t\tif (t_ch->desc && t_ch->desc->last_group_update)")
    end = comm.index("\n\t\t\tif (t_ch->points.delay_move", start)
    pending = "void pending_group_update(P_char t_ch) {\n" + comm[start:end] + "\n}\n"
    death = extract_function("fight.c", "void die(")
    start = death.index("\t\t\t\t\t// Return to account menu")
    end = death.index("\n\t\t\t\t\treturn;", start) + len("\n\t\t\t\t\treturn;")
    death_menu = "void death_return_menu(P_desc d) {\n" + death[start:end] + "\n}\n"
    map_source = source("map.c").read_text()
    start = map_source.index("enum\n{")
    glyph_enum = map_source[start:map_source.index("};", start) + 2]
    bodies = [PRELUDE, entry_reset, glyph_enum, "AnsiString sector_symbol[CONTAINS_MAX];",
              extract_function("map.c", "template <size_t N> static inline void append_cstr("),
              extract_function("utility.c", "int BOUNDED(int a, int b, int c)"),
              extract_function("nanny.c", "void select_terminal("),
              extract_function("account.c", "void display_delete_character_list("),
              extract_function("group.c", "void displayH("),
              extract_function("group.c", "void displayM("),
              extract_function("group.c", "void send_msp_group("),
              extract_function("group.c", "void update_groupies("),
              extract_function("group.c", "void update_group_vitals("),
              extract_function("gmcp.c", "void gmcp_char_vitals("),
              member_line, group_wrapper, pending, death_menu,
              extract_function("limits.c", "int death_exp_loss_level_threshold("),
              extract_function("limits.c", "static void notify_level_advancement("),
              extract_function("limits.c", "static void advance_level_impl(P_char ch, bool notify_player, bool process_boons,\n\t\t\t       std::uint64_t threshold_xp)\n{"),
              extract_function("limits.c", "static void lose_level_impl(P_char ch, std::uint64_t threshold_xp,\n\t\t\t    telemetry_progression_source source,\n\t\t\t    telemetry_progression_reason reason)\n{"),
              extract_function("affects.c", "float player_racial_damage_multiplier("),
              extract_function("affects.c", "char affect_total("),
              extract_function("affects.c", "void event_balance_affects("),
              extract_function("handler.c", "P_obj unequip_char("), DERIVED_CASES,
              extract_function("map.c", "void display_map_room("),
              extract_function("map.c", "void map_look_room("), CASES]
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="terminal-modes-", dir=build) as directory:
        cpp, binary = Path(directory) / "harness.cpp", Path(directory) / "harness"
        cpp.write_text(with_innate_numbers("\n".join(bodies)))
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Og", "-g",
                        "-fsanitize=address,undefined", "-fno-pie", "-no-pie", "-Isrc",
                        str(cpp), "src/net/ansi.c", "src/net/unicode.c", "src/core/safe_format.c",
                        "src/telemetry/telemetry_progression.c",
                        str(HARNESS_STUBS), "-o", str(binary)], cwd=ROOT, check=True, timeout=120)
        subprocess.run([str(binary)], check=True, timeout=30)


if __name__ == "__main__":
    main()
