#!/usr/bin/env python3
"""Real random-NPC creation terminates and selects the requested faction."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, HARNESS_STUBS, extract_function, source

text = source('random.mob.c').read_text()
prefixes = text[text.index('const char *prefix_name_theme'):text.index('#define MAX_ZONES_RANDOM_DATA')]
harness = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/utility.h"
#include "world/db.h"
#include "item/random_equipment.h"
#include <cassert>
#include <cstdlib>
#include <string>
extern const int class_table[LAST_RACE + 1][CLASS_COUNT + 1];
extern const race_names race_names_table[];
extern const class_names class_names_table[];
static zone_data zones[1];
zone_data *zone_table = zones;
static room_data rooms[2];
P_room world = rooms;
static char_data mob;
static npc_only_data npc;
static int template_side, selection, draws, extracted;
struct zone_random_data { int zone; int races[10]; };
static zone_random_data zones_random_data[] = {{1, {RACE_HUMAN, 0}}, {0, {0}}};
P_char read_mobile(int, int) {
    mob = {}; npc = {}; mob.only.npc = &npc;
    mob.specials.act = ACT_ISNPC; mob.player.racewar = template_side;
    return &mob;
}
void extract_char(P_char) { ++extracted; }
int real_zone0(int) { return 0; }
bool char_to_room(P_char ch, int room, int) { ch->in_room = room; return true; }
int number(int low, int high) {
    assert(low <= high && ++draws < 100);
    if (low == 0 && high > 1) return selection % (high + 1);
    return high;
}
int BOUNDED(int low, int value, int high) { return std::max(low, std::min(value, high)); }
int GET_CLASS(P_char ch, uint cls) { return ch->player.m_class & cls; }
void MonkSetSpecialDie(P_char) {}
char *str_dup(const char *text) { return strdup(text); }
std::string strip_ansi(const char *text) { return text; }
int get_name(char *, int, uint64_t) { return false; }
P_obj create_random_eq(P_char, int, int, int, int) { assert(false); return nullptr; }
void obj_to_char(P_obj, P_char) { assert(false); }
void do_wear(P_char, char *, int) { assert(false); }
int find_mob_map_room(P_char) { assert(false); return 0; }
void debug(const char *, ...) {}
''' + prefixes + extract_function('utility.c', 'int flag2idx(') + \
    extract_function('random.mob.c', 'static bool random_mob_class_allowed(') + \
    extract_function('random.mob.c', 'P_char create_random_mob(') + r'''
int main() {
    zones[0].real_bottom = 1;
    zones[0].name = const_cast<char *>("fixture");
    int created[3] = {};
    for (template_side = 0; template_side <= 3; ++template_side)
        for (int theme : {4, 5, 6})
            for (selection = 0; selection < 27; ++selection) {
                draws = extracted = 0;
                P_char made = create_random_mob(theme, 40);
                assert(mob.player.racewar == theme - 3);
                assert(made == &mob || (!made && extracted == 1));
                if (made) ++created[theme - 4];
                int race = mob.player.race;
                assert(race >= 1 && race <= 27);
                assert(theme == 4 ? OLD_RACE_GOOD(race, 1000) :
                       theme == 5 ? OLD_RACE_EVIL(race, -1000) : OLD_RACE_PUNDEAD(race));
                free(mob.player.name); free(mob.player.short_descr); free(mob.player.long_descr);
            }
    for (int count : created) assert(count > 0);
}
'''
build = ROOT / 'bin/tests'
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='random-mob-theme-', dir=build) as directory:
    cpp = Path(directory) / 'test.cpp'
    binary = Path(directory) / 'test'
    cpp.write_text(harness)
    subprocess.run(['g++', '-std=c++20', '-g', '-O1', '-fsanitize=address,undefined',
                    '-fno-pie', '-no-pie', '-ffunction-sections', '-fdata-sections',
                    '-Isrc', '-I/usr/include/mysql', str(cpp), str(HARNESS_STUBS),
                    'src/core/constant.c', 'src/core/common.c', '-Wl,--gc-sections',
                    '-o', str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
print('random mob themes 4/5/6 across template factions: passed')
