#!/usr/bin/env python3
"""Training targets must not consume another NPC's conversation via their base prototype."""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function

program = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "cmd/interp.h"
#include "magic/spells.h"
#include "world/buildings.h"
#include <cassert>
room_data rooms[1]{};
P_room world = rooms;
index_data mobs[2]{}, objects[1]{};
P_index mob_index = mobs, obj_index = objects;
int dummy_calls = 0, guide_calls = 0, map_calls = 0;
bool consume_guide = false;
bool affected_by_spell(P_char, int) { return false; }
int real_mobile0(int) { return -1; }
int inherited(P_char, P_char, int, char *) { ++dummy_calls; return true; }
int guide(P_char, P_char, int, char *) { ++guide_calls; return consume_guide; }
int map(P_obj, P_char, int, char *) { ++map_calls; return true; }
'''
program += extract_function('training_dummy.c', 'bool training_dummy_is(')
program += '\n' + extract_function('interp.c', 'bool special(P_char ch, int cmd, char *arg)')
program += r'''
int main() {
    char_data player{}, dummy{}, teacher{};
    npc_only_data dummy_data{}, teacher_data{};
    player.specials.position = dummy.specials.position = teacher.specials.position = STAT_NORMAL + POS_STANDING;
    dummy.specials.act = teacher.specials.act = ACT_ISNPC;
    dummy.only.npc = &dummy_data; teacher.only.npc = &teacher_data;
    dummy_data.training_dummy = true;
    dummy_data.R_num = 0; teacher_data.R_num = 1;
    mobs[0].virtual_number = 1255; mobs[1].virtual_number = 29201;
    mobs[0].func.mob = inherited; mobs[0].qst_func = inherited;
    mobs[1].func.mob = guide;
    obj_data controller{};
    controller.R_num = 0;
    objects[0].func.obj = map;
    rooms[0].contents = &controller;
    char request[] = "burbul map";
    for (bool dummy_first : {false, true}) {
        rooms[0].people = dummy_first ? &dummy : &teacher;
        dummy.next_in_room = dummy_first ? &teacher : &player;
        teacher.next_in_room = dummy_first ? &player : &dummy;
        for (int cmd : {CMD_ASK, CMD_TELL}) {
            dummy_calls = guide_calls = map_calls = 0;
            consume_guide = false;
            assert(special(&player, cmd, request));
            assert(dummy_calls == 0 && guide_calls == 1 && map_calls == 1);
            consume_guide = true;
            dummy_calls = guide_calls = map_calls = 0;
            assert(special(&player, cmd, request));
            assert(dummy_calls == 0 && guide_calls == 1 && map_calls == 0);
        }
    }
}
'''
directory = ROOT / 'bin/tests'
directory.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='dummy-dispatch-', dir=directory) as temporary:
    root = Path(temporary)
    source = root / 'harness.cpp'
    binary = root / 'harness'
    source.write_text(program)
    subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-Isrc',
                    '-fsanitize=address,undefined', '-fno-pie', '-no-pie',
                    str(source), str(HARNESS_STUBS), '-o', str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=10)
print('training dummy procedure isolation and normal NPC/map dispatch passed')
