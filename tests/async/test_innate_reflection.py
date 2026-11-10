#!/usr/bin/env python3
"""Execute Reflection dispatch, eligibility and cooldown, including rejected titan casts."""
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, HARNESS_STUBS, extract_function, source

innates = source('innates.c').read_text()
table = re.search(r'const struct innate_data innates_data\[LAST_INNATE \+ 1\] = .*?\n};', innates, re.S).group()
table = re.sub(r'(\{ "[^"]+", )(\w+)( \})',
               lambda m: m[1] + (m[2] if m[2] == 'do_innate_reflection' else 'NULL') + m[3], table)
macros = innates[innates.index('#define ADD_RACIAL_INNATE'):innates.index('float regen_factor')]
arrays = innates[innates.index('char racial_innates['):innates.index('extern const struct race_names')]
prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "cmd/interp.h"
#include "magic/spells.h"
#include "classes/necromancy.h"
#include "abilities/abilities.h"
#include "world/events.h"
#include <cassert>
#include <cstring>
#include <regex>
#include <string>
Skill skills[MAX_SKILLS];
index_data indexes[1]{};
P_index mob_index = indexes;
static int casts, lag, timer_seconds = 300, uses = 1, rest_left = 0;
static std::string output;
bool SanityCheck(P_char ch, const char *) { return ch != nullptr; }
int fill_word(char *) { return false; }
int checked_appendf(char *, size_t, const char *, ...) { return 0; }
int GET_CLASS(P_char ch, unsigned int cls) { return (ch->player.m_class & cls) != 0; }
bool epic_summon(P_char, char *) { return false; }
void do_list_innates(P_char, char *) {}
void do_innate_reflection(P_char, char *, int);
void send_to_char(const char *text, P_char) { output += text; }
void CharWait(P_char, int pulses) { lag += pulses; }
int get_property(const char *key, int fallback) {
    if (strcmp(key, "innate.uses.reflection") == 0) return uses;
    return strcmp(key, "innate.timer.secs.reflection") == 0 ? timer_seconds : fallback;
}
int ne_event_time(P_nevent) { return rest_left; }
static std::string reflection_spell_facts(P_char) { return "  Spell line\n"; }
AbilityFacts ability_facts(int skill) { return skill == SPELL_REFLECTION ? reflection_spell_facts : nullptr; }
std::string reflection_innate_facts(P_char);
std::string monkey_grip_innate_facts(P_char);
AbilityFacts innate_facts(int innate) {
    if (innate == INNATE_MONKEY_GRIP) return monkey_grip_innate_facts;
    return innate == INNATE_REFLECTION ? reflection_innate_facts : nullptr;
}
affected_type *affect_to_char(P_char ch, affected_type *af) {
    auto *copy = new affected_type(*af);
    copy->next = ch->affected; ch->affected = copy; return copy;
}
void spell_reflection(int level, P_char ch, char *, int, P_char victim, P_obj) {
    assert(ch == victim && level == GET_LEVEL(ch));
    // A titan would reject the real spell. The innate must never spend its timer here.
    for (auto *link = ch->linked; link; link = link->next_linked)
        assert(link->type != LNK_PET || !IS_NPC(link->linking) || GET_VNUM(link->linking) != 650);
    ++casts;
}
static void clear(P_char ch) {
    while (ch->affected) { auto *af = ch->affected; ch->affected = af->next; delete af; }
    casts = lag = 0; output.clear();
}
'''
functions = [
    ('nanny.c', 'void set_char_size('),
    ('innates.c', 'std::string monkey_grip_innate_facts('),
    ('utility.c', 'int flag2idx('), ('utility.c', 'string strip_ansi('),
    ('interp.c', 'void argument_interpreter('), ('interp.c', 'char *one_argument('),
    ('interp.c', 'bool is_abbrev('),
    ('utility.c', 'int strn_cmp('), ('sparser.c', 'char *skip_spaces('),
    ('affects.c', 'struct affected_type *get_spell_from_char('),
    ('affects.c', 'bool affected_by_spell('),
    ('innates.c', 'void get_property_format('), ('innates.c', 'int get_innate_property('),
    ('innates.c', 'static int innate_char_race('), ('innates.c', 'static int innate_unlock_level('),
    ('innates.c', 'bool has_innate('), ('innates.c', 'void assign_innates('),
    ('innates.c', 'static struct affected_type *find_innate_timer('), ('innates.c', 'static int innate_rest_seconds('), ('innates.c', 'static int innate_uses('), 
    ('innates.c', 'bool can_use_innate('), ('innates.c', 'bool check_innate_time('),
    ('innates.c', 'static int reflection_innate_lag('), ('innates.c', 'void do_innate_reflection(P_char ch'), ('innates.c', 'void do_innate(P_char ch,'),
    ('abilities.c', 'std::string fact('), ('abilities.c', 'std::string seconds('),
    ('abilities.c', 'std::string real_time('), ('abilities.c', 'std::string info_field('),
    ('abilities.c', 'static std::string bright_numbers('), ('abilities.c', 'std::string mechanics_section('),
    ('innates.c', 'std::string innate_rest_facts('), ('innates.c', 'static std::string innate_status('),
    ('innates.c', 'void innate_info(P_char ch'), ('innates.c', 'std::string reflection_innate_facts('),
]
production = '\n'.join(extract_function(file, signature) for file, signature in functions)
driver = r'''
static void reflect(P_char ch) { char args[] = "reflection someone_else"; do_innate(ch, args, CMD_INNATE); }
static std::string info(P_char ch, const char *name) {
    output.clear();
    std::string args = std::string("info ") + name;
    do_innate(ch, args.data(), CMD_INNATE);
    return strip_ansi(output.c_str());
}
static bool has(const std::string &text, const char *part) { return text.find(part) != std::string::npos; }
static std::string innate_list(P_char ch) {
    output.clear();
    char args[] = "";
    do_innate(ch, args, CMD_INNATE);
    return strip_ansi(output.c_str());
}
int main() {
    assign_innates();
    assert(INNATE_WEB_SPRAY == 178 && INNATE_REFLECTION == 179);
    assert(!strcmp(innates_data[INNATE_WEB_SPRAY].name, "web_spray"));
    assert(!strcmp(innates_data[INNATE_REFLECTION].name, "reflection"));
    char_data ch{}, titan{};
    SET_POS(&ch, STAT_NORMAL + POS_STANDING);
    ch.player.level = 31;
    for (int race = 0; race <= LAST_RACE; ++race) {
        ch.player.race = race;
        assert(has_innate(&ch, INNATE_REFLECTION) == (race == RACE_GNOME || race == RACE_KOBOLD));
    }
    for (int race : {RACE_GNOME, RACE_KOBOLD}) {
        ch.player.race = race; ch.player.level = 30;
        reflect(&ch); assert(casts == 0 && !ch.affected && lag == 0);
        ch.player.level = 31;
        reflect(&ch); assert(casts == 1 && lag == PULSE_VIOLENCE);
        assert(ch.affected && ch.affected->location == INNATE_REFLECTION);
        assert(ch.affected->duration == 300 * WAIT_SEC);
        reflect(&ch); assert(casts == 1 && lag == PULSE_VIOLENCE);
        assert(output.find("too tired") != std::string::npos);
        clear(&ch);
    }
    npc_only_data npc{}; titan.only.npc = &npc;
    titan.specials.act = ACT_ISNPC; npc.R_num = 0; indexes[0].virtual_number = 650;
    char_link_data link{}; link.type = LNK_PET; link.linking = &titan; ch.linked = &link;
    reflect(&ch); assert(!ch.affected && casts == 0 && lag == 0);
    assert(output.find("cant support") != std::string::npos);
    ch.linked = nullptr;
    reflect(&ch); assert(casts == 1 && lag == PULSE_VIOLENCE); clear(&ch);
    // Same prototype without a pet link, and ordinary pets, must not block it.
    ch.linked = &link; link.type = LNK_RIDING;
    reflect(&ch); assert(casts == 1); clear(&ch);
    link.type = LNK_PET; indexes[0].virtual_number = IMAGE_REFLECTION_VNUM;
    timer_seconds = 17; reflect(&ch);
    assert(casts == 1 && ch.affected->duration == 17 * WAIT_SEC); clear(&ch);
    // innate info: access, a read-only status, and the shared mechanics.
    clear(&ch); ch.linked = nullptr; ch.player.race = RACE_GNOME; ch.player.level = 30;
    timer_seconds = 300;
    std::string page = info(&ch, "refl");
    assert(has(page, "reflection : INNATE INFO") && has(page, "Type: Active"));
    assert(has(page, "Unlocks for you at level 31.") && !has(page, "Status:"));
    assert(has(page, "  Effect: casts your reflection spell on you at your level\n  Spell line\n"));
    assert(has(page, "  Uses: 1 before it rests\n"));
    assert(has(page, "  Rest: all uses return 5 minutes after the first\n"));
    assert(has(page, "  Your lag: 4 seconds\n"));
    ch.player.level = 31;
    assert(has(info(&ch, "reflection"), "You have it (from level 31).\n  Status: ready\n"));
    reflect(&ch);
    nevent_data rest{}; event_short_affect_data rest_data{};
    rest.func = event_short_affect; rest_data.af = ch.affected; rest.data = &rest_data;
    ch.nevents = &rest; rest_left = 75 * WAIT_SEC;
    const affected_type before = *ch.affected;
    assert(has(info(&ch, "reflection"), "Status: resting; ready in 1 minute 15 seconds\n"));
    assert(ch.affected->modifier == before.modifier && ch.affected->duration == before.duration);
    clear(&ch); ch.nevents = nullptr; uses = 3; reflect(&ch); ch.nevents = &rest;
    rest_data.af = ch.affected; rest_left = 30 * WAIT_SEC;
    page = info(&ch, "reflection");
    assert(has(page, "Status: 2 uses left; all uses return in 30 seconds\n"));
    assert(has(page, "  Uses: 3 before it rests\n"));
    clear(&ch); ch.nevents = nullptr; uses = 1;
    ch.player.race = RACE_HUMAN;
    assert(has(info(&ch, "reflection"), "Not available to your race, class or specialization."));
    assert(has(info(&ch, "nothing such"), "Provide a known innate name"));
    // The plain list ends with its subcommands, their descriptions in one column.
    assert(has(innate_list(&ch), "\n  Use:  innate <name> [arguments]\n"
                                 "  Info: innate info <name>        access, status and mechanics\n"
                                 "  List: innate list [all|player]  every innate and who gets it\n"));
    // Names that share a first word resolve by the whole name.
    assert(has(info(&ch, "protection from cold"), "protection from cold : INNATE INFO"));
    assert(has(info(&ch, "summon warg  "), "summon warg : INNATE INFO"));
    // The harness table keeps only Reflection's handler; the others read as always active.
    page = info(&ch, "infravision");
    assert(has(page, "infravision : INNATE INFO") && has(page, "Type: Always active") && !has(page, "Mechanics"));
    // Monkey Grip is the physical Huge-player hand discount, registered as a passive.
    assert(INNATE_MONKEY_GRIP == 184 && LAST_INNATE == INNATE_MONKEY_GRIP);
    assert(!strcmp(innates_data[INNATE_MONKEY_GRIP].name, "monkey grip"));
    assert(innates_data[INNATE_MONKEY_GRIP].func == nullptr);
    ch = {}; SET_POS(&ch, STAT_NORMAL + POS_STANDING); ch.player.level = 1;
    int huge_races = 0;
    for (int race = 1; race <= RACE_PLAYER_MAX; ++race) {
        ch.player.race = race; set_char_size(&ch);
        const bool huge = GET_SIZE(&ch) >= SIZE_HUGE;
        assert((racial_innates[INNATE_MONKEY_GRIP][race] == 1) == huge);
        assert(has_innate(&ch, INNATE_MONKEY_GRIP) == huge);
        assert(has(innate_list(&ch), "*monkey grip\n") == huge);
        page = info(&ch, "monkey grip");
        assert(has(page, "monkey grip : INNATE INFO") && has(page, "Type: Always active"));
        assert(has(page, "You have it (from level 1).") == huge);
        assert(has(page, "Not available to your race, class or specialization.") == !huge);
        assert(has(page, "two-handed weapons cost 1 hand instead of 2"));
        assert(has(page, "normal two-handed weapon damage is retained"));
        assert(has(page, "Enlarge, Reduce and Titan Form do not change eligibility."));
        assert(has(page, "Two-handed nonweapon items still require 2 hands."));
        assert(!has(page, "Status:"));
        ch.specials.affected_by3 = AFF3_ENLARGE;
        assert(has_innate(&ch, INNATE_MONKEY_GRIP) == huge);
        ch.specials.affected_by3 = AFF3_REDUCE;
        ch.specials.affected_by5 = AFF5_TITAN_FORM;
        assert(has_innate(&ch, INNATE_MONKEY_GRIP) == huge);
        ch.specials.affected_by3 = ch.specials.affected_by5 = 0;
        ch.specials.act = ACT_ISNPC;
        assert(!has_innate(&ch, INNATE_MONKEY_GRIP));
        ch.specials.act = 0;
        huge_races += huge;
    }
    assert(huge_races == 5);
    // Access follows actual stored size, including race disguises with a different body.
    ch.player.race = RACE_OGRE; GET_SIZE(&ch) = SIZE_MEDIUM;
    assert(!has_innate(&ch, INNATE_MONKEY_GRIP));
    ch.player.race = RACE_HUMAN; GET_SIZE(&ch) = SIZE_HUGE;
    assert(has_innate(&ch, INNATE_MONKEY_GRIP));
    puts("Monkey Grip: all 37 player races, Huge grants, personal list/info, base-size access, temporary size effects and NPC isolation passed.");
    puts("Reflection: real dispatch, race/level grants, self targeting, configurable cooldown and titan rejection passed.");
}
'''
build = ROOT / 'bin/tests'
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='reflection-', dir=build) as directory:
    cpp, binary = Path(directory) / 'harness.cpp', Path(directory) / 'harness'
    cpp.write_text(prelude + macros + arrays + table + production + driver)
    subprocess.run(['g++', '-std=c++20', '-g', '-ffunction-sections', '-fdata-sections',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie',
                    '-I' + str(ROOT / 'src'), str(cpp), str(HARNESS_STUBS), '-Wl,--gc-sections',
                    '-lbsd', '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
