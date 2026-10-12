#!/usr/bin/env python3
"""ASan/UBSan: public removal and replacement of equipment that crumbles on transfer."""
import os
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, SRC, HARNESS_STUBS, extract_function

actobj = (SRC / 'actobj.c').read_text()
production = '\n'.join([
    extract_function('handler.c', 'void obj_to_char('),
    extract_function('actobj.c', 'int wearing_invis('),
    actobj[actobj.index('#define REMOVE_SUCCESS'):actobj.index('int remove_item(')],
    extract_function('actobj.c', 'int remove_item('),
    extract_function('actobj.c', 'int remove_and_wear('),
    extract_function('actobj.c', 'void do_remove('),
])
harness = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "magic/spells.h"
#include "item/encumbrance_policy.h"
#include <cassert>
#include <cstring>
#include <set>
#include <string>

static index_data indexes[1]{};
P_index obj_index = indexes;
P_index mob_index = indexes;
static room_data rooms[1]{};
P_room world = rooms;
static std::set<P_obj> live;
static std::set<int> effects;
static std::string output;
static int extracted;
void send_to_char(const char *text, P_char) { output += text; }
void send_to_room(const char *text, int) { output += text; }
void act(const char *text, int, P_char, P_obj obj, void *, int) {
    if (obj) { assert(live.count(obj)); output += obj->short_description; }
    output += text;
}
void extract_obj(P_obj obj, int) {
    assert(live.erase(obj) == 1 && OBJ_NOWHERE(obj));
    ++extracted;
    delete obj;
}
bool training_dummy_is(P_char) { return false; }
void obj_to_room(P_obj, int) { assert(false); }
void artifact_update_location_sql(P_obj) {}
void mark_char_or_owner_dirty(P_char) {}
int char_light(P_char) { return 0; }
int room_light(int, int) { return 0; }
void balance_affects(P_char) {}
void strip_holy_sword(P_char) {}
void CharWait(P_char, int) {}
int STAT_INDEX(int) { return 30; }
char *one_argument(const char *arg, char *word) { strcpy(word, arg); return const_cast<char *>(arg + strlen(arg)); }
bool affected_by_spell(P_char, int spell) { return effects.count(spell); }
void affect_from_char(P_char, int spell) { effects.erase(spell); }
affected_type *affect_to_char(P_char, affected_type *af) { effects.insert(af->type); return nullptr; }
obj_affect *get_obj_affect(P_obj obj, int type) { return obj->affects && obj->affects->type == type ? obj->affects : nullptr; }
void obj_affect_remove(P_obj obj, obj_affect *) { obj->affects = nullptr; }
P_obj unequip_char(P_char ch, int slot, bool) {
    P_obj obj = ch->equipment[slot]; ch->equipment[slot] = nullptr;
    obj->loc_p = LOC_NOWHERE; return obj;
}
P_obj get_object_in_equip(P_char ch, char *, int *slot) { *slot = WEAR_BODY; return ch->equipment[*slot]; }
void execute_wear(P_char ch, P_obj obj, int slot, int, bool) {
    assert(live.count(obj) && !ch->equipment[slot]);
    ch->equipment[slot] = obj; obj->loc_p = LOC_WORN; obj->loc.wearing = ch;
}
// PRODUCTION
int main() {
    for (int mode = 0; mode < 3; ++mode) {
        for (bool crumble : {false, true}) {
            for (bool trusted : {false, true}) {
                pc_only_data pc{}; char_data ch{}; ch.only.pc = &pc;
                ch.player.level = trusted ? 62 : 1;
                ch.in_room = 1;
                P_obj obj = new obj_data{}; live.insert(obj);
                obj->R_num = 0; indexes[0].virtual_number = 400218;
                obj->short_description = const_cast<char *>("test robe");
                obj->extra2_flags = crumble ? ITEM2_CRUMBLELOOT : 0;
                obj->bitvector = AFF_INVISIBLE;
                obj_affect enchant{}; enchant.type = SKILL_ENCHANT; enchant.data = SPELL_ARMOR;
                obj->affects = &enchant;
                effects = {TAG_PERMINVIS, SPELL_ARMOR, SPELL_BATTLEMAGE};
                execute_wear(&ch, obj, WEAR_BODY, 0, false);
                output.clear(); extracted = 0;
                P_obj replacement = nullptr;
                if (mode == 2) {
                    replacement = new obj_data{}; live.insert(replacement);
                    assert(remove_and_wear(&ch, replacement, WEAR_BODY, 0, true));
                    assert(ch.equipment[WEAR_BODY] == replacement);
                } else {
                    char arg[8]; strcpy(arg, mode == 0 ? "robe" : "all");
                    do_remove(&ch, arg, 0);
                    assert(!ch.equipment[WEAR_BODY]);
                }
                assert(!effects.count(TAG_PERMINVIS) && !effects.count(SPELL_ARMOR));
                if (mode != 2) assert(!effects.count(SPELL_BATTLEMAGE));
                if (crumble && !trusted) {
                    assert(extracted == 1 && ch.carrying == nullptr);
                    assert(output.find("crumble to dust") != std::string::npos);
                    assert(output.find("You are quite naked") == std::string::npos);
                } else {
                    assert(extracted == 0 && ch.carrying == obj && obj->affects == nullptr);
                    assert(output.find("You stop using") != std::string::npos);
                    live.erase(obj); delete obj;
                }
                if (replacement) { live.erase(replacement); delete replacement; }
                assert(live.empty());
            }
        }
    }
    puts("crumbleloot single/all removal and replacement passed");
}
'''
build = ROOT / 'bin/tests'
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='remove-crumbleloot-', dir=build) as td:
    source, binary = Path(td) / 'test.cpp', Path(td) / 'test'
    source.write_text(harness.replace('// PRODUCTION', production))
    subprocess.run(['g++', '-std=c++20', '-g', '-fsanitize=address,undefined',
                    '-fno-omit-frame-pointer', '-fno-pie', '-no-pie', '-I' + str(SRC),
                    str(source), str(HARNESS_STUBS), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True,
                   env={**os.environ, 'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1'})
