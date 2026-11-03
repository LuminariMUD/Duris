#!/usr/bin/env python3
"""Execute "innate aura <keyword>" shortcuts through the real do_innate dispatcher."""
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, HARNESS_STUBS, extract_function, source

innates = source('innates.c').read_text()
table = re.search(r'const struct innate_data innates_data\[LAST_INNATE \+ 1\] = .*?\n};', innates, re.S).group()
table = re.sub(r'(\{ "[^"]+", )(\w+)( \})',
               lambda m: m[1] + (m[2] if m[2].startswith('do_aura_') else 'NULL') + m[3], table)
macros = innates[innates.index('#define ADD_RACIAL_INNATE'):innates.index('float regen_factor')]
arrays = innates[innates.index('char racial_innates['):innates.index('extern const struct race_names')]
auras = ['protection', 'spell_protection', 'precision', 'battlelust', 'endurance', 'healing', 'vigor']
prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "cmd/interp.h"
#include "magic/spells.h"
#include "classes/necromancy.h"
#include <cassert>
#include <cstring>
#include <string>
#include <utility>
static std::string used, output;
bool SanityCheck(P_char ch, const char *) { return ch != nullptr; }
int fill_word(char *) { return false; }
int checked_appendf(char *, size_t, const char *, ...) { return 0; }
int GET_CLASS(P_char ch, unsigned int cls) { return (ch->player.m_class & cls) != 0; }
bool epic_summon(P_char, char *) { return false; }
void do_list_innates(P_char, char *) {}
void send_to_char(const char *text, P_char) { output += text; }
int get_property(const char *, int fallback) { return fallback; }
''' + ''.join(f'void do_aura_{a}(P_char, char *, int) {{ used = "{a}"; }}\n' for a in auras)
functions = [
    ('utility.c', 'int flag2idx('),
    ('interp.c', 'void argument_interpreter('), ('interp.c', 'char *one_argument('),
    ('interp.c', 'bool is_abbrev('),
    ('utility.c', 'int strn_cmp('), ('sparser.c', 'char *skip_spaces('),
    ('innates.c', 'void get_property_format('), ('innates.c', 'int get_innate_property('),
    ('innates.c', 'static int innate_char_race('), ('innates.c', 'static int innate_unlock_level('),
    ('affects.c', 'struct affected_type *get_spell_from_char('),
    ('affects.c', 'bool affected_by_spell('),
    ('innates.c', 'bool has_innate('), ('innates.c', 'void assign_innates('),
    ('innates.c', 'bool can_use_innate('), ('innates.c', 'void do_innate(P_char ch,'),
]
production = '\n'.join(extract_function(file, signature) for file, signature in functions)
driver = r'''
static std::string run(P_char ch, const char *text) {
    char args[MAX_STRING_LENGTH];
    strcpy(args, text); used.clear(); output.clear();
    do_innate(ch, args, CMD_INNATE);
    return used.empty() ? output : used;
}
int main() {
    assign_innates();
    char_data pal{}, ap{}, healer{}, cleric{};
    pal.player.m_class = CLASS_PALADIN; pal.player.level = 50;
    ap.player.m_class = CLASS_ANTIPALADIN; ap.player.level = 50;
    healer.player.m_class = CLASS_CLERIC; healer.player.level = 50; healer.player.spec = SPEC_HEALER;
    cleric.player.m_class = CLASS_CLERIC; cleric.player.level = 50;
    const std::string none = "You know no such aura!\n";
    // Every keyword, its shortest unambiguous prefix, and mixed case.
    for (auto [input, aura] : std::initializer_list<std::pair<const char *, const char *>>{
             {"aura protection", "protection"}, {"aura p", "protection"}, {"aura pr", "protection"},
             {"aura precision", "precision"}, {"aura pre", "precision"},
             {"aura battlelust", "battlelust"}, {"aura b", "battlelust"},
             {"aura endurance", "endurance"}, {"aura e", "endurance"},
             {"aura healing", "healing"}, {"aura h", "healing"}, {"aura improved", "healing"},
             {"AURA Heal", "healing"}})
        assert(run(&pal, input) == aura);
    assert(run(&ap, "aura vigor") == "vigor" && run(&ap, "aura v") == "vigor");
    assert(run(&healer, "aura spell") == "spell_protection" && run(&healer, "aura s") == "spell_protection");
    // The syntax the help files have always documented.
    assert(run(&pal, "aura of protection") == "protection");
    assert(run(&pal, "aura of improved healing") == "healing");
    assert(run(&ap, "aura of vigor") == "vigor");
    assert(run(&healer, "aura of spell protection") == "spell_protection");
    // Keywords select only owned auras and never fall back to a different one.
    assert(run(&pal, "aura vigor") == none);
    assert(run(&ap, "aura heal") == none);
    assert(run(&healer, "aura p") == none);
    assert(run(&cleric, "aura spell") == none);
    assert(run(&pal, "aura of") == none && run(&pal, "aura xyz") == none);
    assert(run(&pal, "aura protectionx") == none);
    // Full names and bare "aura" keep their existing behaviour.
    assert(run(&pal, "aura_of_improved_healing") == "healing");
    assert(run(&ap, "aura_of_vigor") == "vigor");
    assert(run(&healer, "aura_of_spell_protection") == "spell_protection");
    assert(run(&pal, "aura") == "protection");
    // Unlock levels still apply.
    pal.player.level = 20;
    assert(run(&pal, "aura heal") == none && run(&pal, "aura end") == "endurance");
    puts("Innate aura keywords: shortcuts, \"of\" syntax, ownership, unlock levels and full names passed.");
}
'''
build = ROOT / 'bin/tests'
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='aura-keywords-', dir=build) as directory:
    cpp, binary = Path(directory) / 'harness.cpp', Path(directory) / 'harness'
    cpp.write_text(prelude + macros + arrays + table + production + driver)
    subprocess.run(['g++', '-std=c++20', '-g', '-ffunction-sections', '-fdata-sections',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie',
                    '-I' + str(ROOT / 'src'), str(cpp), str(HARNESS_STUBS), '-Wl,--gc-sections',
                    '-lbsd', '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
