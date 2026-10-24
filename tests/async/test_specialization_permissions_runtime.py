#!/usr/bin/env python3
"""Unmatched specialization permissions and the player list command stay in bounds."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, HARNESS_STUBS

harness = r'''
#include "classes/specializations.c"
#include <cassert>
#include <cstdarg>
static std::string output;
P_room world = nullptr;
bool creation_all_classes_enabled() { return false; }
void send_to_char(const char *text, P_char) { output += text; }
int checked_snprintf_at(const char *, int, char *buffer, size_t size, const char *format, ...) {
    va_list args; va_start(args, format);
    int result = vsnprintf(buffer, size, format, args); va_end(args);
    assert(result >= 0 && static_cast<size_t>(result) < size); return result;
}
// The list command must return before any teacher/specialization mutation.
int flag2idx(int) { abort(); }
int GET_CLASS(P_char, uint) { abort(); }
bool is_linked_to(P_char, P_char, ush_int) { abort(); }
void mobsay(P_char, const char *) { abort(); }
std::string strip_ansi(const char *) { abort(); }
bool is_abbrev(const char *, const char *) { abort(); }
void update_skills(P_char) { abort(); }
void remove_incoming_healing_aura(P_char) { abort(); }
int main() {
    assert(!is_allowed_race_spec(-1, CLASS_MONK, 999));
    for (int race : {RACE_GITHYANKI, RACE_GITHZERAI})
        for (int spec : {SPEC_WAYOFDRAGON, SPEC_WAYOFSNAKE})
            assert(is_allowed_race_spec(race, CLASS_MONK, spec));
    char_data actor = {};
    char command[] = "list";
    do_specialize(&actor, command, 0);
    assert(output.find("Current list of specializations") != std::string::npos);
    assert(output.find("Gith") != std::string::npos);
}
'''
build = ROOT / 'bin/tests'
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='specialization-permissions-', dir=build) as directory:
    cpp = Path(directory) / 'test.cpp'
    binary = Path(directory) / 'test'
    cpp.write_text(harness)
    subprocess.run(['g++', '-std=c++20', '-g', '-O1', '-fsanitize=address,undefined',
                    '-fno-pie', '-no-pie', '-ffunction-sections', '-fdata-sections',
                    '-Isrc', '-I/usr/include/mysql', str(cpp), str(HARNESS_STUBS),
                    'src/core/common.c', '-Wl,--gc-sections', '-o', str(binary)],
                   cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
print('specialization permission bounds and list command: passed')
