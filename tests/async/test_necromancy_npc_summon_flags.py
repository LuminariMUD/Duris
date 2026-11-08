#!/usr/bin/env python3
"""Execute the four corpse summons' initialization blocks with real types/macros.

This checks flag/stat preservation and the caster gate, not full spell dispatch,
earlier pet restrictions, corpse consumption or live hunting.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function


harness = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <initializer_list>

static P_char pet_caster, pet_owner;
P_char get_linked_char(P_char ch, ush_int type) {
    assert(type == LNK_PET);
    return ch == pet_caster ? pet_owner : nullptr;
}
'''

for name in ("call_titan", "create_dracolich", "call_avatar", "create_greater_dracolich"):
    spell = extract_function("necromancy.c", f"void spell_{name}(")
    # Include the real unconditional aggression assignment and the following
    # outer branch. Nested closing braces have more than one tab of indentation.
    start = spell.index("\n\tSET_BIT(mob->only.npc->aggro_flags, AGGR_ALL);")
    branch = spell.index("\n\tif (", start)
    end = spell.index("\n\t}", branch) + len("\n\t}")
    harness += f"\nstatic void {name}(P_char ch, P_char mob) {{\n{spell[start:end]}\n}}\n"

harness += r'''
int main() {
    using Handler = void (*)(P_char, P_char);
    const Handler handlers[] = {call_titan, create_dracolich, call_avatar,
                                create_greater_dracolich};
    const unsigned flags = ACT_HUNTER | ACT_GUILD_GOLEM | ACT_SENTINEL;
    unsigned cases = 0;
    for (unsigned handler = 0; handler < 4; ++handler)
    for (unsigned bits = 0; bits < 8; ++bits)
    for (unsigned other : {0U, ~flags})
    for (unsigned long aggro : {0UL, static_cast<unsigned long>(AGGR_ALL),
                               ~static_cast<unsigned long>(AGGR_ALL), ~0UL})
    for (unsigned caster_kind = 0; caster_kind < 4; ++caster_kind)
    for (int level : {49, 50, 53, 54, 56})
    for (int dice : {7, 12, 18}) {
        char_data caster{}, owner{}, mob{};
        npc_only_data npc{};
        caster.specials.act = caster_kind == 0 ? 0U : ACT_ISNPC;
        caster.player.level = level;
        owner.specials.act = caster_kind == 3 ? ACT_ISNPC : 0U;
        pet_caster = &caster;
        pet_owner = caster_kind >= 2 ? &owner : nullptr;
        const bool qualifies = caster_kind == 1 || caster_kind == 3;
        const unsigned initial = ACT_ISNPC | other |
            (bits & 1 ? ACT_HUNTER : 0U) |
            (bits & 2 ? ACT_GUILD_GOLEM : 0U) |
            (bits & 4 ? ACT_SENTINEL : 0U);
        mob.only.npc = &npc;
        mob.specials.act = initial;
        npc.aggro_flags = aggro;
        mob.points.damnodice = dice;
        mob.points.base_hitroll = 2;
        mob.points.hitroll = 3;

        unsigned expected_flags = initial;
        int expected_dice = dice, expected_base_hitroll = 2, expected_hitroll = 3;
        if (qualifies) {
            expected_flags = (initial | ACT_HUNTER) & ~ACT_GUILD_GOLEM;
            if (handler < 2) expected_flags &= ~ACT_SENTINEL;
            if (level >= (handler == 1 ? 50 : 54)) {
                const int summon_dice = (handler == 0 || handler == 3) ? 10 : 15;
                expected_dice = handler < 2 ? summon_dice : std::max(dice, summon_dice);
                expected_base_hitroll = expected_hitroll = level;
            }
        }
        // Repeating the block must be idempotent; real casts create a new mob.
        for (int application = 0; application < 2; ++application) {
            handlers[handler](&caster, &mob);
            assert(mob.specials.act == expected_flags);
            assert(npc.aggro_flags == (aggro | AGGR_ALL));
            assert(mob.points.damnodice == expected_dice);
            assert(mob.points.base_hitroll == expected_base_hitroll);
            assert(mob.points.hitroll == expected_hitroll);
        }
        ++cases;
    }
    std::printf("PASS: %u corpse-summon initialization cases, each applied twice\n", cases);
}
'''

build_root = ROOT / "bin/tests"
build_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="necromancy-npc-flags-", dir=build_root) as directory:
    work = Path(directory)
    source, binary = work / "test.cpp", work / "test"
    source.write_text(harness)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-no-pie",
                    "-Isrc", str(source), "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=work, check=True)
