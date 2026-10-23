#!/usr/bin/env python3
"""Execute trapdamage: unsupported types keep charges; supported types still fire."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, SRC, HARNESS_STUBS, extract_function

source = (SRC / 'trap.c').read_text()
defines = source[source.index('#define TRAP_DAM_SLEEP'):source.index('void do_trapremove')]
harness = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/utility.h"
#include "net/comm.h"
#include "combat/damage.h"
#include "magic/spells.h"
#include <cassert>
#include <cstdarg>
#include <string>
static room_data rooms[1];
P_room world = rooms;
static index_data indexes[1];
P_index obj_index = indexes;
static int reports, effects;
static std::string audit;
void logit(const char *, const char *format, ...) {
    char buf[1024]; va_list args; va_start(args, format);
    vsnprintf(buf, sizeof(buf), format, args); va_end(args);
    audit += buf; ++reports;
}
int dice(int, int) { return 10; }
int number(int low, int) { return low; }
void act(const char *, int, P_char, P_obj, void *, int) {}
void send_to_char(const char *, P_char) {}
void send_to_room(const char *, int) {}
affected_type *affect_to_char(P_char, affected_type *affect) { ++effects; return affect; }
void stop_fighting(P_char) {}
void spell_teleport(int, P_char, char *, int, P_char, P_obj) { ++effects; }
int spell_damage(P_char, P_char, double, int, uint, damage_messages *, int *) { ++effects; return 0; }
bool damage(P_char, P_char, double, int) { ++effects; return true; }
''' + defines + extract_function('trap.c', 'void trapdamage(') + r'''
int main() {
    char_data actor = {};
    pc_only_data pc = {};
    actor.only.pc = &pc;
    indexes[0].virtual_number = 131200;
    obj_data item = {};
    for (int type = -1; type <= 16; ++type) {
        item.trap_dam = type; item.trap_charge = 2;
        effects = reports = 0; audit.clear();
        trapdamage(&actor, &item);
        if (type < 0 || type > 8) {
            assert(item.trap_charge == 2 && reports == 1 && effects == 0);
            assert(audit.find("131200") != std::string::npos);
            item.trap_charge = -1;
            trapdamage(&actor, &item);
            assert(item.trap_charge == -1 && reports == 2 && effects == 0);
        } else assert(item.trap_charge == 1 && reports == 0 && effects == 1);
    }
}
'''
build = ROOT / 'bin/tests'
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='unsupported-trap-', dir=build) as directory:
    cpp = Path(directory) / 'test.cpp'
    binary = Path(directory) / 'test'
    cpp.write_text(harness)
    subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-pie', '-no-pie',
                    '-Isrc', '-I/usr/include/mysql', str(cpp), str(HARNESS_STUBS),
                    '-o', str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
print('trap damage types: passed')
