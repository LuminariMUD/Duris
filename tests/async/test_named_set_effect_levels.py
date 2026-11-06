#!/usr/bin/env python3
"""Run apply_zone_spell's real level selection across small and oversized worn sets."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, HARNESS_STUBS, extract_function

harness = r"""
#include "core/prototypes.h"
#include "core/utils.h"
#include "item/named_set_effects.h"
#include "magic/spells.h"
#include "net/comm.h"
#include <cassert>
#include <cstdio>
#include <cstring>
Skill skills[MAX_AFFECT_TYPES + 1];
static room_data room{};
P_room world = &room;
int get_property(const char *, int fallback) { return fallback; }
int GET_CLASS(P_char ch,uint cls) { return (ch->player.m_class&cls)!=0; }
bool grouped(P_char, P_char) { return false; }
void named_set_grant::release_wearer_output() {}
bool affected_by_skill(P_char, int) { return false; }
struct affected_type *get_spell_from_char(P_char, int, void *, int) { return nullptr; }
struct affected_type *affect_to_char(P_char, struct affected_type *) { return nullptr; }
void spell_fireshield(int, P_char, char *, int, P_char, P_obj) {}
void spell_haste(int, P_char, char *, int, P_char, P_obj) {}
void spell_infernal_fury(int, P_char, char *, int, P_char, P_obj) {}
enum { SETMSG_NONE, SETMSG_PROTECT, SETMSG_STRENGTH };
void bard_dragons(int, P_char, P_char, int) {}
static int cast_level, casts;
static void record_cast(int level, P_char, char *, int, P_char, P_obj) { cast_level = level; ++casts; }
bool named_set_effect_supported(int) { return true; }
bool has_skin_spell(P_char) { return false; }
void spell_stone_skin(int level, P_char ch, char *arg, int type, P_char victim, P_obj obj) {
    record_cast(level, ch, arg, type, victim, obj);
}
""" + extract_function("specs.object.c", "static void grant_dragons_to_group(") + \
    extract_function("specs.object.c", "void apply_zone_spell(") + r"""
int main() {
    for (int spell : {SPELL_CONJURE_ELEMENTAL, SPELL_INVIGORATE, SPELL_ENDURANCE, SPELL_STONE_SKIN}) {
        skills[spell].spell_pointer = record_cast;
        const bool floored = spell != SPELL_STONE_SKIN;
        for (int count : {2, 3, 5, 6, 12, 40}) {
            char_data wearer{};
            wearer.points.vitality = 0;
            wearer.points.max_vitality = 100;
            obj_data item{};
            casts = 0;
            apply_zone_spell(&wearer, count, "Test", 1, &item, spell);
            assert(casts == 1);
            const int raw = floored ? count * 10 : count * 5;
            const int expected = MIN(56, floored ? MAX(30, raw) : raw);
            assert(cast_level == expected);
        }
    }
    std::puts("PASS named set effect levels stay within the shared cap");
}
"""

out = ROOT / "bin/tests"
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="named-set-levels-", dir=out) as temporary:
    cpp, binary = Path(temporary) / "test.cpp", Path(temporary) / "test"
    cpp.write_text(harness)
    subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-D__NO_REDIS__",
                    "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                    "-fno-pie", "-no-pie", "-ffunction-sections", "-fdata-sections",
                    "-Isrc", "-I/usr/include/mysql", str(cpp), str(HARNESS_STUBS),
                    "-Wl,--gc-sections", "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=30)
