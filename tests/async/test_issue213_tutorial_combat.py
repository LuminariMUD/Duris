#!/usr/bin/env python3
"""Execute production racial combat effects with original/copied NPC identities.

The damage/counting functions and runtime dispatch blocks are real production
code. Spell/event callbacks are controlled boundaries; loaded NPC profiles and
full authored gameplay have separate journey coverage.
"""
from pathlib import Path
import re
import subprocess
import tempfile
from _paths import ROOT, source, extract_function

fight = source('fight.c').read_text()
magic = source('magic.c').read_text()
parser = source('sparser.c').read_text()
mods = source('dam_mods.c').read_text()

def block(text, start):
    begin = text.index(start)
    opening = text.index('{', begin)
    depth = 0
    for end in range(opening, len(text)):
        depth += (text[end] == '{') - (text[end] == '}')
        if not depth:
            return text[begin:end + 1]
    raise AssertionError(start)

low_health = block(fight, '\t\tif (tutorial_mobile_mechanics_race(victim) == RACE_MINOTAUR')
hit = re.search(r'\tif \([^\n]*RACE_MINOTAUR\)\n\t\tminotaur_race_proc\(ch, victim\);', fight)[0]
horde_call = fight.index('dam = orc_horde_dam_modifier(ch, dam, TRUE);')
horde_start = fight.rfind('\tif (', 0, horde_call)
horde_dispatch = fight[horde_start:fight.index('\n\tif (weapon && IS_SLAYING', horde_start)]
dodge_start = fight.index('\tif (tutorial_mobile_mechanics_race(char_dodger) == RACE_DROW')
dodge = fight[dodge_start:fight.index('\n\t// Dodge success.', dodge_start)]
cold = block(mods, 'if (tutorial_mobile_mechanics_race(victim) == RACE_BARBARIAN)')
gith = re.findall(r'dam\s*=\s*[^;]*RACE_GITH(?:ZERAI|YANKI)[^;]*;', magic)
assert len(gith) == 3
cast_start = parser.rfind('\tif (', 0, parser.index('!= RACE_MINOTAUR'))
cast = block(parser[cast_start:], '\tif (').replace('return;', 'return false;')

prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "net/comm.h"
#include "combat/dam_mods.h"
#include <cassert>
#include <cmath>
#include <cstdlib>
#include <cstring>
room_data rooms[3]{}; P_room world = rooms;
index_data profiles[16]{}; P_index mob_index = profiles;
char_data actors[16]{}; npc_only_data npcs[16]{};
int berserks = 0, procs = 0; bool active_berserk = false;
[[noreturn]] int panic_corruption_int(const char *, const char *, ...) { std::abort(); }
float get_property(const char *, double fallback) { return fallback; }
int number(int low, int high) { return low == 0 ? 0 : high; }
bool affected_by_spell(P_char, int spell) { return active_berserk && spell == SKILL_BERSERK; }
void berserk(P_char, int duration) { assert(duration == 6 * PULSE_VIOLENCE); ++berserks; }
bool minotaur_race_proc(P_char, P_char victim) { ++procs; GET_HIT(victim) -= 7; return false; }
int load_modifier(P_char) { return 75; }
bool is_dragoon_mounted(P_char) { return false; }
bool is_ally(P_char, P_char) { return true; }
int IS_MORPH(P_char) { return false; }
void act(const char *, int, P_char, P_obj, void *, int) { assert(false); }
void debug(const char *, ...) {}
void send_to_char(const char *, P_char) {}
void npc(int slot, int vnum, int race) {
    actors[slot] = {}; npcs[slot] = {};
    actors[slot].only.npc = &npcs[slot]; npcs[slot].R_num = slot;
    actors[slot].specials.act = ACT_ISNPC;
    actors[slot].player.race = race; actors[slot].player.level = 20;
    actors[slot].in_room = 1;
    actors[slot].points.hit = 1; actors[slot].points.max_hit = 100;
    SET_POS(&actors[slot], POS_STANDING + STAT_NORMAL);
    profiles[slot].virtual_number = vnum;
}
'''
functions = extract_function('specs.ailvio.c', 'int tutorial_mobile_mechanics_race(')
functions += extract_function('fight.c', 'double orc_horde_dam_modifier(')
functions += extract_function('sparser.c', 'int get_weight_allies_in_room(')
functions += '\nvoid low_health(P_char victim) {\n' + low_health + '\n}\n'
functions += '\nvoid racial_hit(P_char ch, P_char victim) {\n' + hit + '\n}\n'
functions += '\ndouble racial_damage(P_char ch, P_char victim, double dam) {\n' + horde_dispatch + '\nreturn dam; }\n'
functions += '\nint racial_dodge(P_char char_dodger) { int percent=0; bool dragoon_dodge=false;\n' + dodge + '\nreturn dragoon_dodge ? 2 : 1; }\n'
functions += '\ndouble cold_resistance(P_char victim) { damage_mod value{dam_mod_type::None, 0}; auto *dam_mod=&value;\n' + cold + '\nreturn value.mod; }\n'
for index, line in enumerate(gith):
    functions += f'\nint gith_word_{index}(P_char victim, int dam) {{ {line} return dam; }}\n'
functions += '\nbool can_cast_berserk(P_char ch) {\n' + cast + '\nreturn true; }\n'

cases = r'''
int main() {
    npc(1, 29204, RACE_CENTAUR); npc(2, 91404, RACE_MINOTAUR);
    npc(3, 29206, RACE_HUMAN); npc(4, 91406, RACE_ORC);
    npc(5, 1001, RACE_ORC); npc(6, 1002, RACE_ORC);
    npc(7, 29232, RACE_GREY); npc(8, 91432, RACE_DROW); npc(9, 1003, RACE_DROW);
    npc(10, 29203, RACE_BARBARIAN); npc(11, 91403, RACE_ORC);
    npc(12, 29260, RACE_GITHZERAI); npc(13, 91460, RACE_GITHYANKI);
    npc(14, 1004, RACE_MINOTAUR);
    low_health(&actors[1]); low_health(&actors[2]); assert(berserks == 0);
    low_health(&actors[14]); assert(berserks == 1);
    actors[0].points.hit = 100;
    racial_hit(&actors[1], &actors[0]); racial_hit(&actors[2], &actors[0]);
    assert(procs == 0 && actors[0].points.hit == 100);
    racial_hit(&actors[14], &actors[0]); assert(procs == 1 && actors[0].points.hit == 93);
    actors[5].next_in_room=&actors[3]; actors[3].next_in_room=&actors[6];
    world[1].people=&actors[5];
    const double before = orc_horde_dam_modifier(&actors[5], 100, true);
    assert(std::abs(before - 101.5) < .00001);
    actors[5].next_in_room=&actors[4]; actors[4].next_in_room=&actors[6];
    assert(orc_horde_dam_modifier(&actors[5], 100, true) == before);
    assert(racial_damage(&actors[3], &actors[7], 100) == 100);
    assert(racial_damage(&actors[4], &actors[7], 100) == 100);
    assert(racial_damage(&actors[7], &actors[4], 100) == 100);
    assert(racial_dodge(&actors[7]) == 0 && racial_dodge(&actors[8]) == 0);
    assert(racial_dodge(&actors[9]) == 1);
    assert(cold_resistance(&actors[10]) == -.4 && cold_resistance(&actors[11]) == -.4);
    assert(cold_resistance(&actors[5]) == 0);
    assert(gith_word_0(&actors[12], 200) == 300 && gith_word_0(&actors[13], 200) == 300);
    assert(gith_word_1(&actors[12], 200) == 200 && gith_word_1(&actors[13], 200) == 200);
    assert(gith_word_2(&actors[12], 200) == 200 && gith_word_2(&actors[13], 200) == 200);
    actors[3].next_in_room=nullptr; world[1].people=&actors[3];
    const int weight=get_weight_allies_in_room(&actors[0], 1);
    actors[4].next_in_room=nullptr; world[1].people=&actors[4];
    assert(weight == 5 && get_weight_allies_in_room(&actors[0], 1) == weight);
    active_berserk=true;
    assert(!can_cast_berserk(&actors[1]) && !can_cast_berserk(&actors[2]));
    assert(can_cast_berserk(&actors[14]));
    // Ordinary players retain their actual racial combat benefits.
    active_berserk=false;
    actors[14].specials.act=0; low_health(&actors[14]); assert(berserks == 2);
    active_berserk=true;
    assert(can_cast_berserk(&actors[14]));
}
'''
with tempfile.TemporaryDirectory(prefix='duris-tutorial-combat-') as temporary:
    path = Path(temporary)
    cpp, binary = path / 'combat.cpp', path / 'combat'
    cpp.write_text(prelude + functions + cases)
    subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-Isrc',
                    '-fsanitize=address,undefined', '-fno-pie', '-no-pie', str(cpp), '-o', str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
print('runtime tutorial parity: minotaur procs/berserk, orc damage/counting, dodge, cold/word damage, ally weight and cast restriction')
