#!/usr/bin/env python3
"""Native ival baselines for the staged repairs in ival-system-review-plan.md.

LEGACY assertions deliberately pin reproduced defects, not desired behavior.
Update each with its corresponding repair and score-delta evidence. Circle
registrations come from the real skills.c _PFILE_ path; native proc pricing is
the real function with inert, distinct callback identities (never executed).
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function, rel


HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "item/objmisc.h"
#include "magic/spells.h"
#include "item/item_value.h"
#include <cassert>
#include <climits>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <utility>

extern Skill skills[MAX_AFFECT_TYPES + 1];
void initialize_skills();
// Epic skills have no spell-circle registrations; the rest of skills.c runs normally.
void create_epic_skills() {}
int get_mincircle(int spell);
int get_ival_from_proc(obj_proc_type proc);
static index_data indexes[1]{};
P_index obj_index = indexes;
extern const stat_data stat_factor[LAST_RACE + 1] = {{}, {80,100,120,130,150,90,110,170,105,100}};

// A valuation must not draw from the game RNG or invoke a native callback.
int number(int, int) { assert(false); return 0; }
// CALLBACKS
int unclassified_proc(P_obj, P_char, int, char *) { assert(false); return 0; }
// PRODUCTION

static obj_data item()
{
    obj_data object{};
    object.type = ITEM_WORN;
    object.wear_flags = ITEM_TAKE;
    return object;
}

static obj_data packed(int spells, int level = 60, int denominator = 30)
{
    auto object = item();
    object.wear_flags |= ITEM_WIELD;
    object.value[5] = spells;
    object.value[6] = level;
    object.value[7] = denominator;
    return object;
}

static void circles()
{
    initialize_skills();
    assert(skills[SPELL_EARTH_FORM].m_class[flag2idx(CLASS_CONJURER)-1].rlevel[SPEC_EARTH] == 10);
    assert(skills[SPELL_EARTHEN_TOMB].m_class[flag2idx(CLASS_CONJURER)-1].rlevel[SPEC_EARTH] == 12);
    assert(get_mincircle(SPELL_EARTH_FORM) == 13); // LEGACY F01: should be 10.
    assert(get_mincircle(SPELL_EARTHEN_TOMB) == 13); // LEGACY F01: should be 12.

    assert(get_mincircle(FIRST_SPELL - 1) == 0);
    assert(get_mincircle(LAST_SPELL + 1) == 0);
    for (int spell : {FIRST_SPELL, LAST_SPELL})
    {
        skills[spell] = Skill{};
        assert(get_mincircle(spell) == 13); // Valid, unregistered retains its fallback.
        skills[spell].m_class[0].rlevel[0] = 2;
        assert(get_mincircle(spell) == 13); // LEGACY F01: first class is skipped.
        skills[spell] = Skill{};
        skills[spell].m_class[CLASS_COUNT - 1].rlevel[MAX_SPEC] = 3;
        assert(get_mincircle(spell) == 13); // LEGACY F01: last specialization is skipped.
        skills[spell].m_class[CLASS_COUNT - 1].rlevel[MAX_SPEC - 1] = 4;
        assert(get_mincircle(spell) == 4);
        skills[spell].m_class[1].rlevel[0] = 2;
        assert(get_mincircle(spell) == 2);
    }
    for (int i = 0; i < 3; ++i)
    {
        skills[32 + i] = Skill{};
        skills[32 + i].m_class[1].rlevel[0] = i == 2 ? 4 : i + 1;
    }
    std::puts("circles: real earth registrations and first/last class/spec boundaries");
}

static void packed_rounding()
{
    auto object = packed(1000000000 + 33032);
    assert(itemvalue(&object) == 6); // LEGACY F02: arithmetic mean would give 9.
    object.value[5] = 1000000000 + 34033032;
    assert(itemvalue(&object) == 12); // LEGACY F02: mean 7/3 would give 14.
    object.value[5] = 33032;
    assert(itemvalue(&object) == 18); // All-spells mode sums circles.
    object = packed(32);
    assert(itemvalue(&object) == 6);
    object.value[5] += 1000000000;
    assert(itemvalue(&object) == 6); // Single integral random-one contribution agrees.
    object = packed(1000000032, 25);
    object.wear_flags |= ITEM_WEAR_EYES;
    assert(itemvalue(&object) == 2); // LEGACY F02: 2.5 * 1.3 should quantize to 3.
    object = packed(32, 19);
    assert(itemvalue(&object) == 1);
    object.value[6] = 20;
    assert(itemvalue(&object) == 2); // Preserve the historical level-20 policy jump.
    std::puts("packed: unequal means, fractional final rounding, all/single spell, levels 19/20");
}

static void applies()
{
    auto object = item();
    object.affected[0] = {APPLY_STR_MAX, 2};
    object.affected[1] = {APPLY_HITROLL, 3};
    assert(itemvalue(&object) == 60);
    std::swap(object.affected[0], object.affected[1]);
    assert(itemvalue(&object) == 58); // LEGACY F03: same stats, different slot order.

    object = item();
    object.affected[0] = {APPLY_HIT, 10};
    assert(itemvalue(&object) == 29);
    object.affected[3] = {APPLY_HITROLL, 0};
    assert(itemvalue(&object) == 35); // LEGACY F04: zero should be neutral.
    object.affected[3] = {APPLY_SPELL_PULSE, 0};
    assert(itemvalue(&object) == 58); // LEGACY F04.
    object.affected[3] = {APPLY_STR_MAX, 0};
    assert(itemvalue(&object) == 33); // LEGACY F04.

    object = item();
    object.affected[3] = {APPLY_STR, 6};
    assert(itemvalue(&object) == 25); // The fourth slot counts in the server.
    object.affected[0] = {APPLY_STR, 3};
    object.affected[3].modifier = 3;
    assert(itemvalue(&object) == 12); // LEGACY F04: split total differs from merged.
    object.affected[0].modifier = object.affected[3].modifier = 100;
    assert(itemvalue(&object) == 19602); // Widened semantic total must not narrow to a byte.
    object.affected[0].modifier = 6;
    object.affected[3].modifier = -6;
    assert(itemvalue(&object) == 13); // LEGACY F04: cancellation differs from no stat.

    for (int modifier : {SCHAR_MIN, SCHAR_MAX})
        for (int apply : {APPLY_HITROLL, APPLY_STR, APPLY_HIT, APPLY_MANA,
                          APPLY_HIT_REG, APPLY_AC, APPLY_SAVING_SPELL,
                          APPLY_COMBAT_PULSE, APPLY_STR_MAX})
        {
            object = item();
            object.affected[3].location = apply;
            object.affected[3].modifier = modifier;
            assert(itemvalue(&object) >= 1);
        }
    std::puts("applies: order, zero, fourth slot, duplicate/cancelled stats and byte extremes");
}

static void proc_policy()
{
    assert(get_ival_from_proc(treasure_chest) == 200);
    assert(get_ival_from_proc(artifact_monolith) == 200);
    assert(get_ival_from_proc(huntsman_ward) == 125);
    assert(get_ival_from_proc(ravenloft_bell) == 200); // Earlier branches beat the sentinel group.
    assert(get_ival_from_proc(unclassified_proc) == 100);
    assert(get_ival_from_proc(teleporting_map_pool) == -100000); // LEGACY F09.
    auto object = packed(32);
    obj_index[0].func.obj = unclassified_proc;
    assert(itemvalue(&object) == 106); // LEGACY F09: credits both native and packed routes.
    obj_index[0].func.obj = teleporting_map_pool;
    object = item();
    assert(itemvalue(&object) == 1);
    object.type = ITEM_WEAPON;
    object.value[0] = WEAPON_LONGSWORD;
    object.value[1] = object.value[2] = 400;
    assert(itemvalue(&object) == 48060000); // LEGACY F09: sentinel is not a utility override.
    obj_index[0].func.obj = nullptr;
    object = packed(32000);
    object.type = ITEM_ARMOR;
    object.wear_flags = ITEM_TAKE | ITEM_WEAR_HANDS;
    object.extra2_flags = ITEM2_MONK_PROC;
    assert(itemvalue(&object) == 6); // LEGACY F09: the dispatcher refuses this gap.
    object = item();
    object.bitvector5 = AFF5_PROT_UNDEAD;
    assert(itemvalue(&object) == 1); // F05: omission, not an approved weight.
    std::puts("proc policy: real pricing, first-match precedence, fallback, sentinel and routing gap");
}

static void resolved_racial_context()
{
    auto object = item();
    object.affected[0] = {APPLY_HIT, 10};
    object.affected[3] = {APPLY_STR_RACE, 1};
    item_value_breakdown detail;
    assert(itemvalue(&object, &detail) == 39);
    assert(detail.base == 39 && detail.multiplier == 1 && detail.score == 39);
    object.affected[3].location = APPLY_AGI_RACE;
    assert(itemvalue(&object, &detail) == 119);
    object.affected[3].modifier = -128;
    assert(itemvalue(&object, &detail) == 129); // Preserve invalid-race diagnostic/credit policy.
    assert(itemvalue(nullptr, &detail) == 0 && detail.score == 0);
}

int main(int argc, char **argv)
{
    if (argc == 2)
    {
        auto object = item();
        object.type = ITEM_WEAPON;
        object.value[0] = WEAPON_LONGSWORD;
        object.value[1] = object.value[2] = std::atoi(argv[1]);
        std::printf("boundary score: %d\n", itemvalue(&object));
        return 0;
    }
    assert(itemvalue(nullptr) == 0);
    circles(); packed_rounding(); applies(); proc_policy(); resolved_racial_context();
    auto object = packed(32);
    const auto original = object;
    const auto index = indexes[0];
    for (int i = 0; i < 100; ++i) assert(itemvalue(&object) == 6);
    assert(std::memcmp(&object, &original, sizeof(object)) == 0);
    assert(std::memcmp(&indexes[0], &index, sizeof(index)) == 0);
    std::puts("repeated evaluation leaves object/index inputs unchanged and draws no RNG");
}
'''

PURE = r'''
#include "item/item_value.h"
#include <cassert>
#include <cstring>

int main()
{
    item_value_input input;
    item_value_context context;
    item_value_breakdown detail;
    input.type = ITEM_WORN;
    input.wear_flags = ITEM_TAKE;
    input.affected[3] = {APPLY_HIT, 10};
    assert(evaluate_item_value(input, context, &detail) == 29);
    assert(detail.base == 29 && detail.multiplier == 1 && detail.unrounded == 29);
    assert(!detail.floored && !detail.utility_override && detail.score == 29);
    context.native_proc_credit = 7;
    context.racial_credits[0] = 50;
    assert(evaluate_item_value(input, context, &detail) == 86);
    assert(detail.unrounded == detail.base * detail.multiplier && detail.base == 86);
    input.extra_flags = ITEM_TWOHANDS;
    assert(evaluate_item_value(input, context, &detail) == 68);
    assert(detail.multiplier == .8 && detail.score == static_cast<int>(detail.unrounded));
    input.type = ITEM_KEY;
    assert(evaluate_item_value(input, context, &detail) == 1 && detail.utility_override);
    input = {}; context = {};
    assert(evaluate_item_value(input, context, &detail) == 1 && detail.floored);
    assert(detail.unrounded == 0 && detail.base == 0);
    input.type = ITEM_WORN; input.wear_flags = ITEM_TAKE | ITEM_WIELD;
    input.value[5] = 33032; input.value[6] = 60; input.value[7] = 30;
    assert(item_value_has_packed_proc(input));
    // There are deliberately no engine globals in this executable. All external
    // context is explicit, and changing it changes exactly the resolved credits.
    assert(evaluate_item_value(input, context, &detail) == 1);
    context.spell_circles[0] = 1; context.spell_circles[1] = 2;
    assert(evaluate_item_value(input, context, &detail) == 18);
    const auto original_input = input;
    const auto original_context = context;
    for (int i = 0; i < 100; ++i)
        assert(evaluate_item_value(input, context) == detail.score);
    assert(std::memcmp(&input, &original_input, sizeof(input)) == 0);
    assert(std::memcmp(&context, &original_context, sizeof(context)) == 0);
}
'''


def main():
    proc = extract_function("tradeskill.c", "int get_ival_from_proc(obj_proc_type proc)\n{")
    callbacks = sorted(set(re.findall(r"\bproc == (\w+)", proc)))
    identities = "\n".join(
        f"int {name}(P_obj, P_char, int, char *) {{ assert(false); return 0; }}"
        for name in callbacks)
    production = "\n".join((
        extract_function("utility.c", "int flag2idx(int flag)\n{"),
        extract_function("tradeskill.c", "int get_mincircle(int spell)\n{"),
        proc))
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ival-characterization-", dir=build) as tmp:
        source, binary = Path(tmp) / "test.cpp", Path(tmp) / "test"
        source.write_text(HARNESS.replace("// CALLBACKS", identities).replace("// PRODUCTION", production))
        subprocess.run([
            "g++", "-std=c++20", "-g", "-O1", "-D_PFILE_", "-Isrc",
            "-fsanitize=address,undefined,float-cast-overflow", "-fno-sanitize-recover=all",
            "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
            str(source), rel("skills.c"), str(HARNESS_STUBS), "src/item/item_value.c",
            "src/item/item_value_runtime.c", "-o", str(binary),
        ], cwd=ROOT, check=True)
        env = {**os.environ, "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1",
               "UBSAN_OPTIONS": "halt_on_error=1"}
        subprocess.run([str(binary)], check=True, env=env)
        pure_source = Path(tmp) / "pure.cpp"
        pure_source.write_text(PURE)
        # Both consumers link the numeric module without any engine service or
        # harness stubs. The editor's _DE_ build must stay usable too.
        for mode, defines in (("server", []), ("editor", ["-D_DE_", "-D__UNIX__"])):
            pure_binary = Path(tmp) / f"pure-{mode}"
            subprocess.run([
                "g++", "-std=c++20", "-g", "-O1", "-Isrc", *defines,
                "-fsanitize=address,undefined,float-cast-overflow", "-fno-sanitize-recover=all",
                "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
                str(pure_source), "src/item/item_value.c", "-o", str(pure_binary),
            ], cwd=ROOT, check=True)
            subprocess.run([str(pure_binary)], check=True, env=env)
        print("shared numeric module: isolated server/editor builds, explicit context and breakdown passed")
        # LEGACY F08: expected sanitizer failures are pinned explicitly. Replace
        # these expectations with safe-result/admission checks with the repair.
        for value, diagnostic in (("50000", "signed integer overflow"),
                                  ("1000", "outside the range of representable values of type 'int'")):
            result = subprocess.run([str(binary), value], capture_output=True, text=True, env=env)
            assert result.returncode != 0 and diagnostic in result.stderr, result.stderr
            print(f"LEGACY F08 {value}d{value}: reproduced {diagnostic}", flush=True)


if __name__ == "__main__":
    main()
