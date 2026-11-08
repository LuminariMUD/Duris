#!/usr/bin/env python3
"""Exercise rejected innate uses, real cooldown state, Leap catalog and mounts."""
import re
import subprocess
from _paths import ROOT, HARNESS_STUBS, extract_function, source

innates = source("innates.c").read_text()
table = re.search(r'const struct innate_data innates_data\[LAST_INNATE \+ 1\] = .*?\n};', innates, re.S)[0]
table = re.sub(r'(\{ "[^"]+", )(\w+)( \})', lambda m: m[1] + "NULL" + m[3], table)
macros = innates[innates.index("#define ADD_RACIAL_INNATE"):innates.index("float regen_factor")]
arrays = innates[innates.index("char racial_innates["):innates.index("extern const struct race_names")]
prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "classes/necromancy.h"
#include "abilities/abilities.h"
#include "net/comm.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>
static room_data rooms[2]{};
P_room world = rooms;
static bool prime = true;
static int scheduled, rolls, lag;
static char_data mount{};
static std::string output;
int GET_CLASS(P_char ch, uint cls) { return (ch->player.m_class & cls) != 0; }
int get_property(const char *key, int fallback) {
    return std::strncmp(key, "innate.uses.", 12) == 0 ? 3 : fallback;
}
float get_property(const char *key, double fallback) { return std::strncmp(key, "innate.uses.", 12) == 0 ? 3 : fallback; }
bool SanityCheck(P_char ch, const char *) { return ch != nullptr; }
int is_prime_plane(int) { return prime; }
void send_to_char(const char *s, P_char) { output += s; }
void act(const char *s, int, P_char, P_obj, void *, int) { output += s; }
void CharWait(P_char, int n) { lag += n; }
int number(int low, int) { ++rolls; return low; }
int dice(int n, int) { return n; }
const Rolls live_rolls = {dice,number};
affected_type *affect_to_char(P_char ch, affected_type *af) {
    auto *p = new affected_type(*af); p->next = ch->affected; ch->affected = p; return p;
}
nevent_schedule_result add_event(event_func, int, P_char, P_char, P_obj, int, const void *, int) { ++scheduled; return {}; }
void event_throw_lightning(P_char, P_char, P_obj, void *) {}
void orc_summoning_thing(P_char, P_char, P_obj, void *) {}
int load_modifier(P_char) { return 0; }
int BOUNDED(int a, int b, int c) { return std::max(a,std::min(b,c)); }
P_char read_mobile(int, int) { mount = {}; return &mount; }
bool char_to_room(P_char, int, int) { return true; }
int setup_pet(P_char, P_char, int, int) { return 0; }
void add_follower(P_char, P_char) {}
char_link_data *link_char(P_char, P_char, ush_int) { return nullptr; }
void MonkSetSpecialDie(P_char) {}
void clearMemory(P_char) {}
'''
functions = [("affects.c", "struct affected_type *get_spell_from_char("), ("affects.c", "bool affected_by_spell(")] + [("utility.c", "int flag2idx(")]
functions += [("innates.c", s) for s in (
    "void get_property_format(", "int get_innate_property(", "static int innate_char_race(",
    "static int innate_unlock_level(", "bool has_innate(", "void assign_innates(",
    "static struct affected_type *find_innate_timer(", "static int innate_rest_seconds(",
    "static int innate_uses(", "bool check_innate_time(",
    "static int throw_lightning_delay(", "static int throw_lightning_lag(",
    "void do_throw_lightning(P_char ch,", "static int strength_innate_duration(",
    "static int strength_innate_bonus(", "static int strength_innate_lag(",
    "void do_strength(P_char ch,", "static int enlarge_innate_duration(",
    "static int enlarge_innate_lag(", "void do_enlarge(P_char ch,",
    "static int ud_invisibility_innate_duration(", "void do_ud_invisibility(P_char ch,",
)]
functions += [("new_skills.c", s) for s in (
    "static int summon_horde_delay(", "void do_summon_orc(P_char ch,",
    "static int summoned_mount_factor(", "static int summoned_mount_level(",
    "static int summoned_mount_hit_points(", "static int summoned_mount_skeleton_vitality(",
    "void mount_summoning_thing(P_char ch,",
)]
functions += [("fight.c", s) for s in (
    "static int leap_chance_floor(", "static int leap_chance_top(",
    "static int leap_chance(", "int leapSucceed(",
)]
driver = r'''
static void clear(P_char ch) {
    while (ch->affected) { auto *p = ch->affected; ch->affected = p->next; delete p; }
}
static void fresh(char_data &ch) {
    clear(&ch); ch = {}; SET_POS(&ch, POS_STANDING + STAT_NORMAL);
    ch.player.level = 50; ch.player.m_class = CLASS_WARRIOR;
    ch.player.race = RACE_ORC;
    prime = true; rooms[0].sector_type = SECT_FIELD; scheduled = lag = 0; output.clear();
}
int main() {
    assign_innates(); char_data ch{}, target{};
    for (auto action : {do_throw_lightning,do_strength,do_enlarge,do_ud_invisibility,do_summon_orc}) {
        fresh(ch);
        int innate = action == do_throw_lightning ? INNATE_THROW_LIGHTNING :
            action == do_strength ? INNATE_STRENGTH : action == do_enlarge ? INNATE_ENLARGE :
            action == do_ud_invisibility ? INNATE_UD_INVISIBILITY : INNATE_SUMMON_HORDE;
        if (action == do_strength) { affected_type af{}; af.type = SPELL_STRENGTH; affect_to_char(&ch,&af); }
        if (action == do_enlarge) SET_BIT(ch.specials.affected_by3, AFF3_ENLARGE);
        if (action == do_summon_orc) prime = false;
        auto *before = ch.affected;
        action(&ch,nullptr,0);
        assert(ch.affected == before && !find_innate_timer(&ch,innate));
        assert(!output.empty() && !scheduled);
        // An existing multi-use timer must retain every remaining use, too.
        affected_type timer{}; timer.type = TAG_INNATE_TIMER; timer.location = innate; timer.modifier = 3;
        auto *existing = affect_to_char(&ch,&timer);
        action(&ch,nullptr,0); assert(existing->modifier == 3);
        clear(&ch); ch.specials.affected_by3 = 0; ch.specials.fighting = &target;
        prime = true; output.clear();
        if (action == do_ud_invisibility) rooms[0].sector_type = SECT_UNDRWLD_INSIDE;
        action(&ch,nullptr,0);
        auto *used = find_innate_timer(&ch,innate);
        assert(used && used->modifier == 3 && used->duration > 0);
        if (action == do_throw_lightning || action == do_summon_orc) {
            action(&ch,nullptr,0); assert(used->modifier == 2 && scheduled == 2);
        }
        clear(&ch);
    }
    // Titan form and an existing enlarge affect also reject without a charge.
    for (bool titan : {false,true}) {
        fresh(ch);
        if (titan) SET_BIT(ch.specials.affected_by5,AFF5_TITAN_FORM);
        else { affected_type af{}; af.type = SPELL_ENLARGE; affect_to_char(&ch,&af); }
        do_enlarge(&ch,nullptr,0); assert(!find_innate_timer(&ch,INNATE_ENLARGE));
    }
    fresh(ch); rooms[0].sector_type = SECT_OCEAN;
    do_summon_orc(&ch,nullptr,0); assert(!find_innate_timer(&ch,INNATE_SUMMON_HORDE));
    rooms[0].sector_type = SECT_FIELD;
    for (int race : {RACE_THRIKREEN,RACE_HARPY,RACE_HUMAN}) for (int level : {1,20,21,56}) {
        fresh(ch); ch.player.race = race; ch.player.level = level; ch.curr_stats.Agi = 140;
        rolls = 0;
        bool eligible = race == RACE_HARPY || (race == RACE_THRIKREEN && level >= 21);
        assert(has_innate(&ch,INNATE_LEAP) == eligible);
        assert(bool(leapSucceed(&ch,&target)) == eligible);
        assert(rolls == (eligible ? 1 : 0));
    }
    for (int race : {RACE_SKELETON,RACE_ORC}) for (int level : {1,30,56}) {
        fresh(ch); ch.player.race = race; ch.player.level = level;
        mount_summoning_thing(&ch,nullptr,nullptr,nullptr);
        int factor = std::max(1, int(level * .75 + (level < 6 ? 1 : -5)));
        int hp = factor * (race == RACE_SKELETON ? 15 : 50);
        assert(GET_HIT(&mount) == hp && GET_MAX_HIT(&mount) == hp && mount.points.base_hit == hp);
    }
    clear(&ch);
    puts("Innate actions: rejected uses, remaining charges, valid costs, Leap levels and consistent mount HP passed.");
}
'''
build = ROOT / "bin/tests/innate-action-dispositions"
build.mkdir(parents=True, exist_ok=True)
cpp, binary = build / "harness.cpp", build / "harness"
cpp.write_text(prelude + table + "\n" + macros + arrays + "\n".join(extract_function(f,s) for f,s in functions) + driver)
subprocess.run(["g++", "-std=c++20", "-g", "-fsanitize=address,undefined", "-I"+str(ROOT/"src"),
                str(cpp), str(HARNESS_STUBS), "-o", str(binary)], check=True)
subprocess.run([str(binary)], check=True)
