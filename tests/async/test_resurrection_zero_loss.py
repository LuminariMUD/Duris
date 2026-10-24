#!/usr/bin/env python3
"""Execute the real resurrection refund block for zero and nonzero corpses."""
from pathlib import Path
import subprocess
import tempfile

from _paths import source

function = source('magic.c').read_text().split('void spell_resurrect(', 1)[1]
start = function.index('\t/*\n\t * restore lost exp from death')
block = function[start:function.index('\n\tGET_HIT(t_ch)', start)]
prelude = r'''
#include <algorithm>
#include <cassert>
struct Character { bool pc = true, trusted = false, evil = false; int level = 29; long xp = 12345; };
struct Object { long value[8]{}; };
#define IS_PC(ch) ((ch)->pc)
#define IS_TRUSTED(ch) ((ch)->trusted)
#define EVIL_RACE(ch) ((ch)->evil)
#define GET_LEVEL(ch) ((ch)->level)
#define GET_NAME(ch) "ResurrectionFixture"
#define GET_EXP(ch) ((ch)->xp)
constexpr int LOG_EXP = 0, EXP_RESURRECT = 1, EXPMOD_RES_EVIL = 0, EXPMOD_RES_NORMAL = 1;
double exp_mods[] = {.7, .8};
int calls = 0, alerts = 0;
long restored = -1;
void logit(int, const char*, ...) {}
void debug(const char*, ...) {}
void wizlog(int, const char*, ...) { ++alerts; }
void gain_exp(Character *ch, void*, long amount, int type) {
    assert(type == EXP_RESURRECT);
    ++calls; restored = amount;
    // The real dispatcher floors this gain at one; the caller must avoid it
    // when a death lost nothing rather than inventing refundable XP.
    ch->xp += std::max(1L, amount);
}
void refund(Character *t_ch, Character *ch, Object *obj) {
    long resu_exp;
'''
cases = r'''
}
int main() {
    for (int level : {1, 29, 30, 56})
        for (bool evil : {false, true})
            for (bool trusted_caster : {false, true}) {
                Character player, caster;
                Object corpse;
                player.level = level; player.evil = evil; caster.trusted = trusted_caster;
                calls = alerts = 0;
                refund(&player, &caster, &corpse);
                assert(player.xp == 12345 && calls == 0 && alerts == 0);
                corpse.value[4] = 100;
                refund(&player, &caster, &corpse);
                const long expected = trusted_caster ? 100 : level >= 56 ? 50 : evil ? 70 : 80;
                assert(calls == 1 && restored == expected && player.xp == 12345 + expected);
                assert(alerts == 0);
            }
    // Preserve the existing nonzero-corpse rounding/minimum-XP behavior.
    Character player, caster;
    Object corpse; corpse.value[4] = 1;
    calls = 0; refund(&player, &caster, &corpse);
    assert(calls == 1 && restored == 0 && player.xp == 12346);
}
'''
with tempfile.TemporaryDirectory(prefix='duris-resurrection-zero-') as temporary:
    root = Path(temporary)
    source, binary = root / 'refund.cpp', root / 'refund'
    source.write_text(prelude + block + cases)
    subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie',
                    str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('zero-loss resurrection does not fabricate XP or warnings; nonzero refunds unchanged')
