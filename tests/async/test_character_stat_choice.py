#!/usr/bin/env python3
"""Execute the production roller and Telnet bonus handler with controlled dice."""
import subprocess
from _paths import ROOT, HARNESS_STUBS, extract_function, source

PRELUDE = r"""
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "world/db.h"
#include "account/account.h"
#include "net/ws_handlers.h"
#include "net/websocket.h"
#include <cassert>
#include <cstring>
#include <string>
struct index_data *mob_index = nullptr;
static int expected_rolls, expected_faces, calls;
static bool maximum;
static std::string output;
char *bonus = nullptr;
void write_to_q(const char *text, txt_q *, const int) { if (text) output += text; }
int websocket_send_text(P_desc, const char *text) { output = text; return 1; }
static int ws_is_playable_race(int race) { return race == RACE_HUMAN || race == RACE_MOUNTAIN; }
void display_stats(P_desc) {}
void display_characteristics(P_desc) {}
int dice(int rolls, int faces) {
    assert(rolls == expected_rolls && faces == expected_faces);
    ++calls;
    return maximum ? rolls * faces : rolls;
}
"""
labels = source("actinf.c").read_text()
start = labels.index("const char *stat_names2[18]")
PRELUDE += labels[start:labels.index("};", start) + 2]
PRODUCTION = "\n".join(extract_function(file, sig) for file, sig in (
    ("utility.c", "int BOUNDED("),
    ("actwiz.c", "void roll_basic_attributes("),
    ("nanny.c", "void add_stat_bonus("),
    ("nanny.c", "void select_bonus("),
    ("utility.c", "int STAT_INDEX(int v)\n{\n\t"),
    ("actinf.c", "const char *stat_to_string2("),
    ("ws_handlers.c", "void ws_send_system("),
    ("ws_handlers.c", "static void ws_reset_chargen("),
    ("ws_handlers.c", "static cJSON *build_chargen_stats_json("),
    ("ws_handlers.c", "static sh_int *get_chargen_stat_ptr("),
    ("ws_handlers.c", "static bool ws_chargen_allowed("),
    ("ws_handlers.c", "static void add_chargen_state("),
    ("ws_handlers.c", "static void ws_send_chargen_stats("),
    ("ws_handlers.c", "void ws_cmd_roll_stats("),
    ("ws_handlers.c", "void ws_cmd_accept_stats("),
    ("ws_handlers.c", "void ws_cmd_reset_chargen("),
    ("ws_handlers.c", "void ws_cmd_add_bonus("),
    ("ws_handlers.c", "void ws_cmd_swap_stats("),
))
DRIVER = r"""
static void command(P_desc d, ws_cmd_handler handler, const char *json) {
    cJSON *data = cJSON_Parse(json); assert(data); output.clear();
    handler(d, data); cJSON_Delete(data);
}
static void rejected(P_desc d, ws_cmd_handler handler, const char *json) {
    stat_data stats = d->chargen_stats;
    int race = d->chargen_race, method = d->chargen_method, count = d->chargen_bonus_remaining;
    auto phase = d->chargen_phase;
    command(d, handler, json);
    assert(output.find("error") != std::string::npos);
    assert(std::memcmp(&stats, &d->chargen_stats, sizeof stats) == 0);
    assert(race == d->chargen_race && method == d->chargen_method);
    assert(count == d->chargen_bonus_remaining && phase == d->chargen_phase);
}
int main() {
    struct Case { int type, rolls, faces, low, high; };
    Case cases[] = {{ROLL_NORMAL,1,4,87,90}, {ROLL_ADVANCED,3,6,80,95},
                    {ROLL_BAD,4,10,44,80}, {ROLL_MOB_NORMAL,3,11,68,98},
                    {ROLL_MOB_GOOD,3,7,80,98}, {ROLL_MOB_ELITE,3,4,91,100}};
    char_data ch{};
    for (const auto &test : cases) for (bool high : {false,true}) {
        expected_rolls = test.rolls; expected_faces = test.faces;
        calls = 0; maximum = high;
        for (int i=0; i<MAX_ATTRIBUTES; ++i) ch.base_stats[i] = ch.curr_stats[i] = 0;
        roll_basic_attributes(&ch, test.type);
        assert(calls == MAX_ATTRIBUTES);
        for (int i=0; i<MAX_ATTRIBUTES; ++i) {
            assert(ch.base_stats[i] == (high ? test.high : test.low));
            assert(ch.curr_stats[i] == ch.base_stats[i]);
        }
        if (test.type >= ROLL_MOB_NORMAL && test.type <= ROLL_MOB_ELITE) {
            for (int i=0; i<MAX_ATTRIBUTES; ++i) ch.base_stats[i] = ch.curr_stats[i] = 110;
            roll_basic_attributes(&ch, test.type);
            for (int i=0; i<MAX_ATTRIBUTES; ++i) assert(ch.base_stats[i] == 110 && ch.curr_stats[i] == 110);
        }
    }
    descriptor_data d{}; d.character = &ch; d.connected = CON_BONUS1;
    for (int i=0; i<MAX_ATTRIBUTES; ++i) ch.base_stats[i] = ch.curr_stats[i] = 90;
    ch.base_stats.Str = ch.curr_stats.Str = 98;
    char strength[]="s", luck[]="l", karma[]="k";
    select_bonus(&d, strength);
    assert(ch.base_stats.Str == 100 && ch.curr_stats.Str == 100 && d.connected == CON_BONUS2);
    output.clear(); select_bonus(&d, strength);
    assert(d.connected == CON_BONUS2 && output.find("No bonus was used") != std::string::npos);
    select_bonus(&d, karma);
    assert(ch.base_stats.Kar == 90 && d.connected == CON_BONUS2);
    select_bonus(&d, luck);
    assert(ch.base_stats.Luk == 95 && ch.curr_stats.Luk == 95 && d.connected == CON_BONUS3);
    select_bonus(&d, luck);
    assert(ch.base_stats.Luk == 100 && d.connected == CON_BONUS5);
    select_bonus(&d, luck);
    assert(d.connected == CON_BONUS5);
    char dex[]="d"; select_bonus(&d, dex);
    assert(ch.base_stats.Dex == 95 && d.connected == CON_SWAPSTATYN);
    acct_entry account{};
    descriptor_data web{}; web.account = &account; web.connected = CON_ACCT_SELECT_CHAR;
    rejected(&web, ws_cmd_add_bonus, R"({"stat":"str"})");
    rejected(&web, ws_cmd_swap_stats, R"({"stat1":"str","stat2":"luk"})");
    for (const char *bad : {R"({"race":1,"method":"unknown"})", R"({"race":1,"method":false})",
                            R"({"race":1,"method":null})", R"({"race":1.5})"})
        rejected(&web, ws_cmd_roll_stats, bad);
    expected_rolls=1; expected_faces=4; maximum=false;
    command(&web, ws_cmd_roll_stats, R"({"race":1})");
    assert(web.chargen_phase == CHARGEN_BONUSES && web.chargen_bonus_remaining == 4);
    for (int i=0; i<MAX_ATTRIBUTES; ++i) assert(web.chargen_stats[i] == 87);
    rejected(&web, ws_cmd_roll_stats, R"({"race":1})");
    rejected(&web, ws_cmd_roll_stats, R"({"race":5,"method":"advanced"})");
    rejected(&web, ws_cmd_swap_stats, R"({"stat1":"str","stat2":"luk"})");
    command(&web, ws_cmd_reset_chargen, "{}");
    assert(web.chargen_phase == CHARGEN_UNSTARTED && web.chargen_bonus_remaining == 0);
    for (int i=0; i<MAX_ATTRIBUTES; ++i) assert(web.chargen_stats[i] == 0);
    expected_rolls=3; expected_faces=6;
    command(&web, ws_cmd_roll_stats, R"({"race":1,"method":"advanced"})");
    for (int i=0; i<MAX_ATTRIBUTES; ++i) assert(web.chargen_stats[i] == 80);
    rejected(&web, ws_cmd_add_bonus, R"({"stat":"str"})");
    rejected(&web, ws_cmd_roll_stats, R"({"race":5,"method":"advanced"})");
    maximum=true;
    command(&web, ws_cmd_roll_stats, R"({"race":1,"method":"advanced"})");
    for (int i=0; i<MAX_ATTRIBUTES; ++i) assert(web.chargen_stats[i] == 95);
    command(&web, ws_cmd_accept_stats, "{}");
    rejected(&web, ws_cmd_roll_stats, R"({"race":1,"method":"advanced"})");
    rejected(&web, ws_cmd_add_bonus, R"({"stat":"kar"})");
    command(&web, ws_cmd_add_bonus, R"({"stat":"str"})");
    assert(web.chargen_stats.Str == 100 && web.chargen_bonus_remaining == 3);
    rejected(&web, ws_cmd_add_bonus, R"({"stat":"str"})");
    command(&web, ws_cmd_accept_stats, "{}");
    assert(web.chargen_bonus_remaining == 3 && web.chargen_stats.Str == 100);
    for (const char *json : {R"({"stat":"dex"})", R"({"stat":"agi"})", R"({"stat":"luk"})"})
        command(&web, ws_cmd_add_bonus, json);
    assert(web.chargen_bonus_remaining == 0 && web.chargen_phase == CHARGEN_READY);
    rejected(&web, ws_cmd_add_bonus, R"({"stat":"con"})");
    rejected(&web, ws_cmd_swap_stats, R"({"stat1":"str","stat2":"kar"})");
    command(&web, ws_cmd_swap_stats, R"({"stat1":"luk","stat2":"con"})");
    assert(web.chargen_stats.Luk == 95 && web.chargen_stats.Con == 100 && web.chargen_stats.Kar == 95);
    command(&web, ws_cmd_accept_stats, "{}");
    assert(web.chargen_phase == CHARGEN_READY && web.chargen_bonus_remaining == 0);
    web.connected=CON_PLAYING; web.character=&ch;
    rejected(&web, ws_cmd_reset_chargen, "{}");
    rejected(&web, ws_cmd_roll_stats, R"({"race":1})");
    web.character=nullptr; web.connected=CON_NAME;
    rejected(&web, ws_cmd_reset_chargen, "{}");
    web.connected=CON_ACCT_SELECT_CHAR; web.account=nullptr;
    rejected(&web, ws_cmd_roll_stats, R"({"race":1})");
    web.account=&account;
    command(&web, ws_cmd_reset_chargen, "{}");
    assert(web.chargen_phase == CHARGEN_UNSTARTED);
    web.connected=CON_DISPLAY_ACCT_MENU;
    expected_rolls=1; expected_faces=4;
    command(&web, ws_cmd_roll_stats, R"({"race":1})");
    assert(web.chargen_bonus_remaining == 4 && web.chargen_phase == CHARGEN_BONUSES);
    puts("PASS WebSocket numeric state, reroll replacement, reset, phase gates, duplicates, caps and session guards");
    puts("PASS production formulas/extrema/all ten assignments/mob floors and four capped Telnet bonuses");
}
"""
output = ROOT / "bin/tests/stat-choice"
output.mkdir(parents=True, exist_ok=True)
cpp, binary = output / "harness.cpp", output / "harness"
cpp.write_text(PRELUDE + PRODUCTION + DRIVER)
subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined",
                "-fno-pie", "-no-pie", "-I" + str(ROOT / "src"), str(cpp), str(HARNESS_STUBS),
                "-lcjson", "-o", str(binary)], check=True)
subprocess.run([str(binary)], check=True)
