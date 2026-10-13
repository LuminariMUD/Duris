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
#include "player/character_mechanics.h"
#include <cassert>
#include <cstring>
#include <string>
Skill skills[MAX_SKILLS];
index_data indexes[1]{};
P_index mob_index = indexes;
static int casts, lag, timer_seconds = 300;
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
    return strcmp(key, "innate.timer.secs.reflection") == 0 ? timer_seconds : fallback;
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
    ('utility.c', 'int flag2idx('),
    ('interp.c', 'void argument_interpreter('), ('interp.c', 'bool is_abbrev('),
    ('affects.c', 'struct affected_type *get_spell_from_char('),
    ('affects.c', 'bool affected_by_spell('),
    ('innates.c', 'void get_property_format('), ('innates.c', 'int get_innate_property('),
    ('innates.c', 'static int innate_char_race('), ('innates.c', 'static int innate_unlock_level('),
    ('innates.c', 'bool has_innate('), ('innates.c', 'void assign_innates('),
    ('innates.c', 'bool can_use_innate('), ('innates.c', 'bool check_innate_time('),
    ('innates.c', 'void do_innate_reflection(P_char ch'), ('innates.c', 'void do_innate(P_char ch,'),
]
production = '\n'.join(extract_function(file, signature) for file, signature in functions)
driver = r'''
static void reflect(P_char ch) { char args[] = "reflection someone_else"; do_innate(ch, args, CMD_INNATE); }
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
