#!/usr/bin/env python3
"""Execute Calming's common gate, target selection and aggression delays."""
import subprocess
from _paths import ROOT, HARNESS_STUBS, extract_function, source

prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "combat/justice.h"
#include "magic/spells.h"
#include "abilities/abilities.h"
#include "net/comm.h"
#include <cassert>
#include <cstdio>
#define MAX_TARGETS 20
static room_data rooms[1]{};
P_room world = rooms;
static zone_data zones[1]{};
zone_data *zone_table = zones;
hometown_data hometowns[3]{};
static char_data holder{}, guard{};
struct dex_app_type dex_app[36]{};
static index_data indexes[1]{};
P_index mob_index = indexes;
static bool owned = true;
static int attacks, delay;
bool has_innate(P_char ch,int innate) { return ch == &holder && owned && innate == INNATE_CALMING; }
bool SanityCheck(P_char ch,const char *) { return ch != nullptr; }
bool is_aggr_to(P_char,P_char) { return true; }
bool calmcheck(P_char) { return false; }
int CountToughness(P_char,P_char) { return 1; }
bool ac_can_see(P_char,P_char,bool) { return true; }
bool training_dummy_target_allowed(P_char,P_char) { return true; }
affected_type *get_spell_from_char(P_char,int,void *,int) { return nullptr; }
bool affected_by_spell(P_char,int) { return false; }
int number(int low,int) { return low; }
int dice(int n,int) { return n; }
const Rolls live_rolls = {dice,number};
int get_property(const char *,int fallback) { return fallback; }
float get_property(const char *,double fallback) { return fallback; }
int STAT_INDEX(int) { return 0; }
int BOUNDED(int a,int b,int c) { return std::max(a,std::min(b,c)); }
nevent_schedule_result add_event(event_func,int n,P_char,P_char,P_obj,int,const void *,int) { delay = n; ++attacks; return {}; }
void event_agg_attack(P_char,P_char,P_obj,void *) {}
'''
functions = [("handler.c", s) for s in (
    "bool innate_calming_active(", "int calming_delay(", "int calming_level_gap(",
    "int calming_gap_roll(", "int calming_notarget_percent(", "int calming_notarget_roll(",
)] + [("mobact.c", "P_char PickTarget(")]
# Run the actual entry scheduling block without unrelated relocation/proc machinery.
entry = extract_function("handler.c", "bool char_to_room(P_char ch,")
a = entry.index("\tint calming = 0;", entry.index("t_ch = PickTarget(ch);"))
b = entry.index("\n\tfor (t_ch = world",a)
entry = "void entry_delay(P_char ch) { P_char t_ch = &guard;\n" + entry[a:b].replace("return FALSE;","return;") + "}\n"
# The periodic scheduler also runs the same common gate.
periodic = extract_function("mobact.c", "void event_mob_mundane(")
a = periodic.index("\t\tint calming = 0;",periodic.index("PROFILE_START(mundane_picktarget)"))
b = periodic.index("\n\t\tPROFILE_END(mundane_picktarget)",a)
periodic = "void periodic_delay(P_char ch) { P_char tmp_ch = &holder;\n" + periodic[a:b] + "}\n"
# Every gameplay consumer goes through the common gate, including controlled commands.
for file in ("actmove.c","actoff.c","interp.c","mobact.c"):
    assert "INNATE_CALMING" not in source(file).read_text(), file
assert "innate_calming_active(exec_char)" in source("interp.c").read_text()
driver = r'''
int main() {
    hometowns[0].flags = JUSTICE_GOODHOME;
    hometowns[1].flags = JUSTICE_EVILHOME;
    hometowns[2].flags = JUSTICE_NEUTRALHOME;
    SET_POS(&holder,POS_STANDING + STAT_NORMAL);
    SET_POS(&guard,POS_STANDING + STAT_NORMAL);
    guard.specials.act = ACT_ISNPC;
    holder.player.level = guard.player.level = 50;
    rooms[0].people = &holder;
    for (int side : {RACEWAR_GOOD,RACEWAR_EVIL,RACEWAR_NEUTRAL,RACEWAR_UNDEAD})
        for (int town : {0,1,2,3}) for (bool enabled : {false,true}) {
            holder.player.racewar = side; zones[0].hometown = town; owned = enabled;
            bool enemy = (side == RACEWAR_GOOD && town == 2) || (side == RACEWAR_EVIL && town == 1);
            bool active = enabled && !enemy;
            assert(innate_calming_active(&holder) == active);
            assert(PickTarget(&guard) == (active ? nullptr : &holder));
            attacks = delay = 0;
            entry_delay(&holder);
            assert(attacks == 1 && delay == (active ? 10 : 0));
            periodic_delay(&guard);
            assert(attacks == 2 && delay == 1 + (active ? 10 : 0));
        }
    holder.in_room = NOWHERE;
    assert(!innate_calming_active(&holder));
    puts("Calming: townless/own/enemy/neutral homes, all sides, target selection and entry/periodic delays passed.");
}
'''
build = ROOT/"bin/tests/calming-hometowns"
build.mkdir(parents=True,exist_ok=True)
cpp,binary = build/"harness.cpp",build/"harness"
cpp.write_text(prelude + "\n".join(extract_function(f,s) for f,s in functions) + entry + periodic + driver)
subprocess.run(["g++","-std=c++20","-g","-fsanitize=address,undefined","-I"+str(ROOT/"src"),
                str(cpp),str(HARNESS_STUBS),"-o",str(binary)],check=True)
subprocess.run([str(binary)],check=True)
