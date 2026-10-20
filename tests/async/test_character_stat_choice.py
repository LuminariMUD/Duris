#!/usr/bin/env python3
"""Execute the production roller and Telnet bonus handler with controlled dice."""
import subprocess
from _paths import ROOT, HARNESS_STUBS, extract_function

PRELUDE = r"""
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "world/db.h"
#include <cassert>
#include <cstring>
#include <string>
struct index_data *mob_index = nullptr;
static int expected_rolls, expected_faces, calls;
static bool maximum;
static std::string output;
char *bonus = nullptr;
void write_to_q(const char *text, txt_q *, const int) { if (text) output += text; }
void display_stats(P_desc) {}
void display_characteristics(P_desc) {}
int dice(int rolls, int faces) {
    assert(rolls == expected_rolls && faces == expected_faces);
    ++calls;
    return maximum ? rolls * faces : rolls;
}
"""
PRODUCTION = "\n".join(extract_function(file, sig) for file, sig in (
    ("utility.c", "int BOUNDED("),
    ("actwiz.c", "void roll_basic_attributes("),
    ("nanny.c", "void add_stat_bonus("),
    ("nanny.c", "void select_bonus("),
))
DRIVER = r"""
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
    puts("PASS production formulas/extrema/all ten assignments/mob floors and four capped Telnet bonuses");
}
"""
output = ROOT / "bin/tests/stat-choice"
output.mkdir(parents=True, exist_ok=True)
cpp, binary = output / "harness.cpp", output / "harness"
cpp.write_text(PRELUDE + PRODUCTION + DRIVER)
subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined",
                "-fno-pie", "-no-pie", "-I" + str(ROOT / "src"), str(cpp), str(HARNESS_STUBS),
                "-o", str(binary)], check=True)
subprocess.run([str(binary)], check=True)
