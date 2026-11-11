#!/usr/bin/env python3
"""Check active prototypes and execute the summoned book/totem constructors."""
import re
import subprocess

from _paths import ROOT, extract_function

VNUMS = {31, 98, 417, 2679, 26209, 29201, 120016}
NORENT = 8388608
found = {}
for line in (ROOT / 'areas/AREA').read_text().splitlines():
    if not line.strip() or line.startswith('*'):
        continue
    path = ROOT / 'areas/obj' / (line.split()[0] + '.obj')
    if not path.exists():
        continue
    for match in re.finditer(r'^#(\d+)\n(.*?)(?=^#|\Z)', path.read_text(), re.M | re.S):
        vnum = int(match[1])
        if vnum not in VNUMS:
            continue
        assert vnum not in found, f'duplicate active prototype {vnum}'
        flags = int(match[2].split('~', 4)[4].splitlines()[1].split()[6])
        assert not flags & NORENT, f'{path}: {vnum} still has NORENT'
        found[vnum] = flags
assert set(found) == VNUMS

functions = '\n'.join(extract_function('classes/new_skills.c', signature) for signature in (
    'void event_summon_book(', 'static int summon_totem_hit_points(',
    'static int summon_totem_pulse(', 'void event_summon_totem('))
harness = r'''
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
struct character { struct { const char *name; } player; int level; };
struct affect { int location, modifier; };
struct object {
    unsigned extra_flags, str_mask, bitvector, bitvector2;
    char *name, *short_description;
    affect affected[3];
};
using P_char = character *;
using P_obj = object *;
enum class summoned_replacement_kind { book, totem };
constexpr int VIRTUAL=0, STRUNG_DESC2=1, STRUNG_KEYS=2;
constexpr int APPLY_SPELL_PULSE=1, APPLY_HIT=2;
constexpr unsigned AFF2_SOULSHIELD=1, AFF_SENSE_LIFE=2, AFF_FARSEE=4;
constexpr unsigned ITEM_NORENT=8388608;
#define SET_BIT(value, flag) ((value) |= (flag))
#define GET_LEVEL(ch) ((ch)->level)
#define checked_snprintf snprintf
#define str_dup strdup
static object item{};
static bool submitted;
static unsigned prototype_flags;
P_obj read_object(int vnum, int) {
    assert(vnum == 31 || vnum == 417);
    item = {}; item.extra_flags = prototype_flags;
    return &item;
}
void submit_summoned_replacement(P_char, P_obj obj, summoned_replacement_kind) {
    assert(obj == &item);
    assert(!(obj->extra_flags & ITEM_NORENT));
    assert(obj->extra_flags == prototype_flags);
    submitted = true;
}
'''
harness += functions
harness += r'''
int main() {
    character ch{{"Renttest"}, 60};
    for (int level : {1, 60}) {
        ch.level = level;
        for (int vnum : {31, 417}) {
            prototype_flags = vnum == 31 ? BOOK_FLAGS : TOTEM_FLAGS;
            submitted = false;
            if (vnum == 31) event_summon_book(&ch, nullptr, nullptr, nullptr);
            else event_summon_totem(&ch, nullptr, nullptr, nullptr);
            assert(submitted);
            assert(item.name && item.short_description);
            free(item.name); free(item.short_description);
        }
    }
}
'''.replace('BOOK_FLAGS', str(found[31])).replace('TOTEM_FLAGS', str(found[417]))
harness = '#include <initializer_list>\n' + harness
build = ROOT / 'bin/tests/reported_items_rentable'
build.mkdir(parents=True, exist_ok=True)
cpp = build / 'summoned_rentable.cpp'
cpp.write_text(harness)
binary = build / 'summoned_rentable'
subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', str(cpp), '-o', str(binary)], check=True)
subprocess.run([str(binary)], check=True)
print('PASS: seven active prototypes and summoned book/totem grants are rentable.')
