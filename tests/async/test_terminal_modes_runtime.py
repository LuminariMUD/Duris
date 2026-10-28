#!/usr/bin/env python3
"""Exercise terminal selection, menu preservation, maps, and group presentation.

Uses production types and function bodies. World lookup, output transport and
GMCP delivery are captured boundaries; group display, pending group updates,
and the hardcore death menu transition are extracted without unrelated combat
and mutation paths. No account/player files or running server are used.
"""
import subprocess
import tempfile
from pathlib import Path
from _paths import ROOT, HARNESS_STUBS, extract_function, source


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/utility.h"
#include "net/comm.h"
#include "net/gmcp.h"
#include "account/account.h"
#include "account/pwipe_launch.h"
#include "world/map.h"
#include "ships/ships.h"
#include <cassert>
#include <cmath>
#include <cctype>
#include <cstring>
#include <vector>
static std::string output, map_data;
static int group_updates, map_updates;
static bool closed;
static bool member_visible = true;
static P_char hidden_member;
static room_data rooms[2]{};
P_room world = rooms;
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
void send_account_name_prompt(P_desc) { output += "Account name: "; }
void display_account_menu(P_desc, char *) { output += "Account menu"; }
bool pwipe_launch_closed_at(time_t) { return closed; }
std::string pwipe_launch_screen(bool color) { return color ? "color launch" : "plain launch"; }
int number(int a, int) { return a; }
int flag2idx(int) { return 1; }
int IS_MORPH(P_char) { return false; }
bool ac_can_see(P_char, P_char target, bool) { return member_visible || target != hidden_member; }
bool racewar(P_char, P_char) { return false; }
bool has_innate(P_char, int) { return false; }
int get_real_race(P_char) { return 0; }
const char *get_class_name(P_char, P_char) { return "Warrior"; }
std::string pad_ansi(const char *text, int, bool) { return text; }
int get_property(const char *, int fallback) { return fallback; }
float get_property(const char *, double fallback) { return fallback; }
void gmcp_send_group_status(P_char) { ++group_updates; }
void gmcp_send(P_desc, const char *, const char *) {}
char *json_build_char_vitals(P_char) { return strdup("{}"); }
char *str_dup(const char *text) { return strdup(text); }
void __free(void *pointer, const char *, int) { assert(pointer); free(pointer); }
void gmcp_send_room_map(P_char, const char *text) { ++map_updates; map_data = text; }
void gmcp_send_quest_map(P_char ch, const char *text) { gmcp_send_room_map(ch, text); }
P_ship get_ship_from_char(P_char) { return nullptr; }
unsigned int calculate_relative_room(unsigned int, int, int) { return 1; }
int whats_in_maproom(P_char, int, int, int) { return 0; }
'''

CASES = r'''
int main()
{
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
        auto automatic = [&]() {
            output.clear(); group_updates = 0;
            gmcp_char_vitals(&member); // Actual producer, including non-GMCP members.
            assert(d.last_group_update);
            pending_group_update(&actor);
            assert(!d.last_group_update && group_updates == int(gmcp));
            return output;
        };
        const std::string initial = automatic();
        assert(initial == "<group>\n( Head) Leader\n <&+G100h&n/&+G100H&n> <&+G100m&n/&+G100M&n>"
                          "\n(Front)  Member\n <&+G100h&n/&+G100H&n> <&+G100m&n/&+G100M&n>\n</group>\n");
        assert(automatic().empty());
        ++member.points.mana;
        assert(automatic().empty()); // Mana is not in the MSP group display.
        --member.points.hit;
        assert(automatic().find("99h") != std::string::npos);
        assert(automatic().empty());
        --member.points.vitality;
        assert(automatic().find("99m") != std::string::npos);
        SET_BIT(member.specials.act2, PLR2_BACK_RANK);
        assert(automatic().find("Back") != std::string::npos);
        member_visible = false;
        assert(automatic().find("Someone") != std::string::npos);
        member_visible = true;
        assert(automatic().find("Member") != std::string::npos);
        member.in_room = 0;
        assert(!automatic().empty());
        --member.points.hit;
        assert(automatic().empty()); // Remote HP is not displayed to this observer.
        member.in_room = 1;
        assert(automatic().find("98h") != std::string::npos);
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
        assert(!automatic().empty());
        assert(automatic().empty());
    }
    FREE(d.msp_group_output);
    puts("PASS: terminal modes, unchanged automatic MSP groups, explicit groups, and leaving/rejoining");
}
'''


def main():
    group = extract_function("group.c", "void do_group(")
    display = group[group.index("\tif (!*name)"):group.index("\n\tif (ch->group)\n")]
    group_wrapper = r'''
void do_group(P_char ch, char *, int) {
    const char *name = "";
    char Gbuf1[MAX_STRING_LENGTH], Gbuf2[MAX_STRING_LENGTH], Gbuf3[MAX_STRING_LENGTH];
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
    bodies = [PRELUDE, glyph_enum, "AnsiString sector_symbol[CONTAINS_MAX];",
              extract_function("map.c", "template <size_t N> static inline void append_cstr("),
              extract_function("utility.c", "int BOUNDED(int a, int b, int c)"),
              extract_function("nanny.c", "void select_terminal("),
              extract_function("account.c", "void display_delete_character_list("),
              extract_function("group.c", "void displayH("),
              extract_function("group.c", "void displayM("),
              extract_function("group.c", "void send_msp_group("),
              extract_function("group.c", "void update_groupies("),
              extract_function("gmcp.c", "void gmcp_char_vitals("),
              group_wrapper, pending, death_menu,
              extract_function("map.c", "void display_map_room("), CASES]
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="terminal-modes-", dir=build) as directory:
        cpp, binary = Path(directory) / "harness.cpp", Path(directory) / "harness"
        cpp.write_text("\n".join(bodies))
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Og", "-g",
                        "-fsanitize=address,undefined", "-fno-pie", "-no-pie", "-Isrc",
                        str(cpp), "src/net/ansi.c", "src/net/unicode.c", "src/core/safe_format.c",
                        str(HARNESS_STUBS), "-o", str(binary)], cwd=ROOT, check=True, timeout=120)
        subprocess.run([str(binary)], check=True, timeout=30)


if __name__ == "__main__":
    main()
