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
#include "item/item_value_procs.h"
#include <cassert>
#include <climits>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <utility>
#include <algorithm>
#include <array>
#include <unordered_set>

extern Skill skills[MAX_AFFECT_TYPES + 1];
void initialize_skills();
// Epic skills have no spell-circle registrations; the rest of skills.c runs normally.
void create_epic_skills() {}
int get_mincircle(int spell);
static bool native_owner;
static obj_proc_type previous_proc;
obj_proc_type proclib_chain_incumbent(int) { return previous_proc; }
int proclib_obj_cmd_bridge(P_obj,P_char,int,char*) { assert(false); return 0; }
bool native_artifact_configured_owner(int) { return native_owner; }
static void callable_spell(int,P_char,char*,int,P_char,P_obj) { assert(false); }
static index_data indexes[1]{};
P_index obj_index = indexes;
int top_of_objt = 0;
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
    skills[SPELL_EARTH_FORM].spell_pointer = callable_spell;
    skills[SPELL_EARTHEN_TOMB].spell_pointer = callable_spell;
    assert(skills[SPELL_EARTH_FORM].m_class[flag2idx(CLASS_CONJURER)-1].rlevel[SPEC_EARTH] == 10);
    assert(skills[SPELL_EARTHEN_TOMB].m_class[flag2idx(CLASS_CONJURER)-1].rlevel[SPEC_EARTH] == 12);
    assert(get_mincircle(SPELL_EARTH_FORM) == 10);
    assert(get_mincircle(SPELL_EARTHEN_TOMB) == 12);
    assert(get_mincircle(SPELL_GIRILALS_GRANITE_HAMMER) == 11);
    assert(get_mincircle(SPELL_ILESHS_SMASHING_FURY) == 12);
    auto earth = packed(SPELL_EARTH_FORM);
    assert(itemvalue(&earth) == 60); // Formerly 78 at the fallback circle 13.
    earth.value[5] = SPELL_EARTHEN_TOMB;
    assert(itemvalue(&earth) == 72); // Formerly 78.

    assert(get_mincircle(FIRST_SPELL - 1) == 0);
    assert(get_mincircle(LAST_SPELL + 1) == 0);
    assert(get_mincircle(-1) == 0 && get_mincircle(INT_MAX) == 0);
    for (int spell : {FIRST_SPELL, LAST_SPELL})
    {
        skills[spell] = Skill{};
        assert(get_mincircle(spell) == 13); // Valid, unregistered retains its fallback.
        skills[spell].m_class[0].rlevel[0] = 2;
        assert(get_mincircle(spell) == 2);
        skills[spell] = Skill{};
        skills[spell].m_class[CLASS_COUNT - 1].rlevel[MAX_SPEC] = 3;
        assert(get_mincircle(spell) == 3);
        skills[spell].m_class[CLASS_COUNT - 1].rlevel[MAX_SPEC - 1] = 4;
        assert(get_mincircle(spell) == 3); // A later, worse registration cannot replace the minimum.
        skills[spell].m_class[1].rlevel[0] = 2;
        assert(get_mincircle(spell) == 2);
    }
    for (int i = 0; i < 3; ++i)
    {
        skills[32 + i] = Skill{};
        skills[32 + i].m_class[1].rlevel[0] = i == 2 ? 4 : i + 1;
        skills[32 + i].spell_pointer = callable_spell;
    }
    std::puts("circles: real earth registrations and first/last class/spec boundaries");
}

static void packed_rounding()
{
    auto object = packed(1000000000 + 33032);
    assert(itemvalue(&object) == 9);
    object.value[5] = 1000000000 + 34033032;
    assert(itemvalue(&object) == 14);
    object.value[5] = 33032;
    assert(itemvalue(&object) == 18); // All-spells mode sums circles.
    object = packed(32);
    assert(itemvalue(&object) == 6);
    object.value[5] += 1000000000;
    assert(itemvalue(&object) == 6); // Single integral random-one contribution agrees.
    object = packed(1000000032, 25);
    object.wear_flags |= ITEM_WEAR_EYES;
    assert(itemvalue(&object) == 3); // 2.5 * 1.3 quantizes only after the slot multiplier.
    object = packed(1000000000);
    assert(itemvalue(&object) == 1); // Empty random-one selection retains the floor.
    assert(get_mincircle(851) == 0); // The unavailable choice in authored item #59249.
    object = packed(1000000000 + 33032000 + 851);
    assert(itemvalue(&object) == 6); // Zero credit stays in the three-choice denominator.
    object = packed(32, 19);
    assert(itemvalue(&object) == 1);
    object.value[6] = 20;
    assert(itemvalue(&object) == 2); // Preserve the historical level-20 policy jump.
    // Choosing one of one spell must equal casting that one spell, including fractions.
    for (int level : {1, 19, 20, 25, 60})
    for (int chance : {1, 30, 45, 60})
    for (unsigned int slot : {0u, static_cast<unsigned int>(ITEM_WEAR_EYES)}) {
        object = packed(32, level, chance);
        object.wear_flags |= slot;
        const int all = itemvalue(&object);
        object.value[5] += 1000000000;
        assert(itemvalue(&object) == all);
    }
    std::puts("packed: unequal means, fractional final rounding, all/single spell, levels 19/20");
}

static void applies()
{
    auto object = item();
    object.affected[0] = {APPLY_STR_MAX, 2};
    object.affected[1] = {APPLY_HITROLL, 3};
    assert(itemvalue(&object) == 60);
    std::swap(object.affected[0], object.affected[1]);
    assert(itemvalue(&object) == 60); // Apply additions precede apply factors in both orders.

    object = item();
    object.affected[0] = {APPLY_HIT, 10};
    assert(itemvalue(&object) == 29);
    object.affected[3] = {APPLY_HITROLL, 0};
    assert(itemvalue(&object) == 29);
    object.affected[3] = {APPLY_SPELL_PULSE, 0};
    assert(itemvalue(&object) == 29);
    object.affected[3] = {APPLY_STR_MAX, 0};
    assert(itemvalue(&object) == 29);

    object = item();
    object.affected[3] = {APPLY_STR, 6};
    assert(itemvalue(&object) == 25); // The fourth slot counts in the server.
    object.affected[0] = {APPLY_STR, 3};
    object.affected[3].modifier = 3;
    assert(itemvalue(&object) == 25); // The curve sees the live total once.
    object.affected[0].modifier = object.affected[3].modifier = 100;
    assert(itemvalue(&object) == 39601); // Total 200 must not narrow to a byte.
    object.affected[0].modifier = 6;
    object.affected[3].modifier = -6;
    assert(itemvalue(&object) == 1); // Cancellation is neutral, including its multiplier.

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

static void apply_permutations()
{
    const struct { int location, modifier, score; } singles[] = {
        {APPLY_AC, -10, 15}, {APPLY_STR_MAX, 2, 13}, {APPLY_HITROLL, 3, 37},
        {APPLY_DAMROLL, 3, 37}, {APPLY_COMBAT_PULSE, -1, 150}, {APPLY_SPELL_PULSE, -1, 150}};
    for (const auto &single : singles) for (int slot = 0; slot < MAX_OBJ_AFFECT; ++slot) {
        auto object = item();
        object.affected[slot].location = single.location;
        object.affected[slot].modifier = single.modifier;
        assert(itemvalue(&object) == single.score);
    }
    const item_value_apply choices[] = {{APPLY_AC, -10}, {APPLY_STR_MAX, 2},
        {APPLY_HITROLL, 3}, {APPLY_DAMROLL, 2}, {APPLY_COMBAT_PULSE, -1}, {APPLY_SPELL_PULSE, -1},
        {APPLY_STR_RACE, 1}, {APPLY_AGI_RACE, 1}};
    constexpr int choice_count = std::size(choices);
    int checked = 0;
    for (int a = 0; a < choice_count; ++a)
    for (int b = a + 1; b < choice_count; ++b)
    for (int c = b + 1; c < choice_count; ++c)
    for (int d = c + 1; d < choice_count; ++d)
    for (int type : {ITEM_WORN, ITEM_ARMOR, ITEM_WEAPON})
    for (bool premium : {false, true})
    for (bool twohands : {false, true})
    {
        if ((type != ITEM_WEAPON && twohands) || (type == ITEM_WEAPON && premium)) continue;
        const int selected[] = {a, b, c, d};
        std::array<int, 4> order{0, 1, 2, 3};
        item_value_breakdown expected{};
        bool first = true;
        do {
            auto object = item();
            object.type = type;
            if (premium) object.wear_flags |= ITEM_WEAR_EYES;
            if (twohands) object.extra_flags |= ITEM_TWOHANDS;
            object.value[0] = type == ITEM_WEAPON ? WEAPON_LONGSWORD : 10;
            object.value[1] = 2; object.value[2] = 6;
            if (type == ITEM_WEAPON) object.wear_flags |= ITEM_WIELD;
            for (int slot = 0; slot < MAX_OBJ_AFFECT; ++slot) {
                const auto apply = choices[selected[order[slot]]];
                object.affected[slot].location = apply.location;
                object.affected[slot].modifier = apply.modifier;
            }
            const auto original = object;
            item_value_breakdown detail;
            itemvalue(&object, &detail);
            assert(!std::memcmp(&object, &original, sizeof(object)));
            if (first) { expected = detail; first = false; }
            else assert(detail.score == expected.score && detail.base == expected.base &&
                        detail.multiplier == expected.multiplier && detail.unrounded == expected.unrounded);
            ++checked;
        } while (std::next_permutation(order.begin(), order.end()));
    }
    std::printf("apply permutations: %d mixed AC/max-stat/hit/damage/pulse/racial cases, identical breakdowns and unchanged slots\n", checked);
}

static void zero_insertion()
{
    int checked = 0;
    for (int type : {ITEM_WORN, ITEM_ARMOR, ITEM_WEAPON})
    for (int slot = 0; slot < MAX_OBJ_AFFECT; ++slot)
    for (int location = 0; location <= UCHAR_MAX; ++location) {
        auto object = item();
        object.type = type;
        object.value[0] = type == ITEM_WEAPON ? WEAPON_LONGSWORD : 10;
        object.value[1] = 2; object.value[2] = 6;
        if (type == ITEM_WEAPON) {
            object.wear_flags |= ITEM_WIELD;
            object.extra_flags |= ITEM_TWOHANDS;
        } else object.wear_flags |= ITEM_WEAR_EYES;
        object.affected[(slot + 1) % MAX_OBJ_AFFECT] = {APPLY_HIT, 10};
        item_value_breakdown before, after;
        itemvalue(&object, &before);
        object.affected[slot].location = location;
        object.affected[slot].modifier = 0;
        const auto unchanged = object;
        itemvalue(&object, &after);
        assert(before.score == after.score && before.base == after.base &&
               before.multiplier == after.multiplier && before.unrounded == after.unrounded);
        assert(!std::memcmp(&object, &unchanged, sizeof(object)));
        ++checked;
    }
    std::printf("zero insertion: %d stored-location/slot/type cases retain identical values, breakdowns and inputs\n", checked);
}

static void proc_policy()
{
    assert(item_value_proc(treasure_chest).credit == 200);
    assert(item_value_proc(artifact_monolith).credit == 200);
    assert(item_value_proc(huntsman_ward).credit == 125);
    assert(item_value_proc(ravenloft_bell).credit == 200); // Earlier branches beat the sentinel group.
    assert(item_value_proc(unclassified_proc).credit == 100);
    assert(item_value_proc(teleporting_map_pool).policy == item_value_proc_policy::utility);
    assert(item_value_proc(teleporting_map_pool).credit == 0);
    assert(item_value_proc(unclassified_proc).policy == item_value_proc_policy::unclassified);
    assert(item_value_proc(nullptr).policy == item_value_proc_policy::none);
    std::unordered_set<obj_proc_type> unique;
    for (const auto &entry : item_value_proc_entries())
        assert(unique.insert(entry.callback).second);
    auto object = packed(32);
    obj_index[0].func.obj = unclassified_proc;
    item_value_breakdown routes;
    assert(itemvalue(&object, &routes) == 106);
    assert(routes.native_melee_suppressed && !routes.context_complete); // Unsplit legacy credit is explicit.
    obj_index[0].func.obj = teleporting_map_pool;
    object = item();
    assert(itemvalue(&object) == 1);
    object.type = ITEM_WEAPON;
    object.value[0] = WEAPON_LONGSWORD;
    object.value[1] = object.value[2] = 400;
    item_value_breakdown utility;
    assert(itemvalue(&object, &utility) == 1 && utility.utility_override);
    assert(utility.native_proc_policy == item_value_proc_policy::utility);
    assert(!strcmp(utility.native_proc_name, "teleporting_map_pool"));
    obj_index[0].func.obj = nullptr;
    object = packed(32000);
    object.type = ITEM_ARMOR;
    object.wear_flags = ITEM_TAKE | ITEM_WEAR_HANDS;
    object.extra2_flags = ITEM2_MONK_PROC;
    assert(itemvalue(&object) == 1); // The dispatcher refuses this gap.
    object = packed(32000); // Weapons cast a prefix by count, not every occupied slot.
    assert(itemvalue(&object, &routes) == 1 && routes.packed_cast_mask == 0);
    object = packed(33032);
    skills[33].spell_pointer = nullptr;
    assert(itemvalue(&object, &routes) == 6 && routes.packed_cast_mask == 1);
    object.type = ITEM_WORN; object.wear_flags = ITEM_TAKE | ITEM_WEAR_HANDS;
    object.extra2_flags = ITEM2_MONK_PROC;
    assert(itemvalue(&object, &routes) == 1 && routes.packed_cast_mask == 0);
    skills[33].spell_pointer = callable_spell;
    assert(itemvalue(&object) == 18);
    for (int vnum : {21,22}) {
        indexes[0].virtual_number = vnum;
        obj_index[0].func.obj = artifact_stone;
        object = packed(32);
        native_owner = true;
        assert(itemvalue(&object, &routes) == 125 && routes.packed_credit == 0);
        assert(!routes.native_melee_suppressed && routes.context_complete);
        native_owner = false;
        assert(itemvalue(&object, &routes) == 131 && routes.packed_credit == 6);
        assert(routes.native_melee_suppressed && !routes.context_complete);
    }
    obj_index[0].func.obj = nullptr; indexes[0].virtual_number = 0;
    object=item(); object.affected[0]={APPLY_HIT,10};
    previous_proc=artifact_stone; obj_index[0].func.obj=proclib_obj_cmd_bridge;
    assert(itemvalue(&object)==154); // A sibling's instance library cannot reprice this plain object.
    object.extra_flags |= ITEM_PROCLIB;
    assert(itemvalue(&object,&routes)==129 && !routes.context_complete);
    object.extra_flags &= ~ITEM_PROCLIB; previous_proc=nullptr;
    assert(itemvalue(&object)==29);
    obj_index[0].func.obj=nullptr;

    object = item();
    object.bitvector5 = AFF5_PROT_UNDEAD;
    assert(itemvalue(&object) == 1); // F05: omission, not an approved weight.
    object=packed(32); object.type=ITEM_WEAPON; object.value[0]=WEAPON_LONGSWORD;
    obj_index[0].func.obj=zarthos_vampire_slayer;
    assert(itemvalue(&object,&routes)==6 && routes.native_price_suppressed && routes.native_base==0);
    object.value[0]=WEAPON_DAGGER;
    assert(itemvalue(&object,&routes)==121 && !routes.native_price_suppressed && routes.native_base==115);
    object.type=ITEM_WORN; object.wear_flags=ITEM_TAKE|ITEM_WEAR_HANDS; object.extra2_flags=ITEM2_MONK_PROC;
    object.value[5]=32000;
    assert(itemvalue(&object,&routes)==1 && routes.native_price_suppressed);
    obj_index[0].func.obj=nullptr;
    std::puts("proc policy: real pricing, first-match precedence, fallback, utility override and executable packed routes");
}


static void coverage_cases()
{
    obj_index[0].func.obj = nullptr;
    auto object=item(); object.affected[0]={APPLY_HIT,10};
    item_value_breakdown detail;
    assert(itemvalue(&object,&detail)==29);
    auto reconcile=[&] {
        const double terms=detail.flags_base+detail.applies_base+detail.type_base+detail.packed_credit+detail.native_base;
        assert(std::abs(terms-detail.base)<1e-8);
        assert(std::abs(detail.base*detail.multiplier-detail.unrounded)<1e-8);
    };
    int priced=0;
    for(int bank=0;bank<5;++bank) for(int bit=0;bit<64;++bit) {
        object=item(); object.affected[0]={APPLY_HIT,10};
        const auto flag=1ULL<<bit;
        if(bank<4 && bit>=static_cast<int>(sizeof(object.bitvector)*8)) continue;
        if(bank==0) object.bitvector=flag;
        if(bank==1) object.bitvector2=flag;
        if(bank==2) object.bitvector3=flag;
        if(bank==3) object.bitvector4=flag;
        if(bank==4) object.bitvector5=flag;
        itemvalue(&object,&detail); reconcile();
        if(bank==0 && (flag & (static_cast<unsigned long long>(AFF_SLEEP)|AFF_FEAR|AFF_CHARM))) {
            assert(!detail.unpriced_affects[0] && detail.score==29); continue;
        }
        if(!detail.unpriced_affects[bank]) {
            ++priced; assert(detail.base!=29 || detail.multiplier!=1);
        } else assert(detail.unpriced_affects[bank]==flag && !detail.context_complete);
    }
    assert(priced==67);
    for(int location=1;location<=SCHAR_MAX;++location) {
        object=item(); object.affected[0]={APPLY_HIT,10}; object.affected[1]={static_cast<signed char>(location),1};
        itemvalue(&object,&detail); reconcile();
        if(!detail.unpriced_apply_slots) assert(detail.base!=29 || detail.multiplier!=1);
        else assert(detail.unpriced_apply_slots==2 && !detail.context_complete);
    }
    object=item(); object.affected[0]={APPLY_KARMA_MAX,5};
    itemvalue(&object,&detail); assert(detail.unpriced_apply_slots==1);
    for(int type:{ITEM_SHIELD,ITEM_FIREWEAPON,ITEM_MISSILE}) {
        object=item(); object.type=type;
        itemvalue(&object,&detail); assert(detail.unpriced_type && !detail.context_complete);
    }
    object=item(); obj_affect dynamic{}; object.affects=&dynamic;
    itemvalue(&object,&detail); assert(detail.unpriced_dynamic_effects && !detail.context_complete);
    std::puts("coverage: 67 priced affect bits, five banks, apply families, unpriced types/dynamic effects and reconciled breakdown");
}

static void resolved_racial_context()
{
    auto object = item();
    object.affected[0] = {APPLY_HIT, 10};
    object.affected[3] = {APPLY_STR_RACE, 1};
    item_value_breakdown detail;
    assert(itemvalue(&object, &detail) == 39);
    assert(detail.base == 39 && detail.multiplier == 1 && detail.score == 39);
    object.affected[1] = {APPLY_STR_RACE, 1};
    object.affected[2] = {APPLY_STR_RACE, 2}; // The zero factor is weaker than race 1.
    assert(itemvalue(&object, &detail) == 39);
    std::swap(object.affected[1], object.affected[2]);
    assert(itemvalue(&object, &detail) == 39);
    object.affected[1] = object.affected[2] = {};
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
        item_value_breakdown detail;
        assert(itemvalue(&object, &detail) == 0 && detail.invalid);
        std::puts("boundary score unavailable without undefined arithmetic");
        return 0;
    }
    assert(itemvalue(nullptr) == 0);
    auto unresolved = item();
    item_value_breakdown unavailable;
    unresolved.R_num = -1;
    assert(itemvalue(&unresolved, &unavailable) == 0 && unavailable.invalid);
    unresolved.R_num = top_of_objt + 1;
    assert(itemvalue(&unresolved, &unavailable) == 0 && unavailable.invalid);
    const auto saved_index = obj_index;
    unresolved.R_num = 0;
    obj_index = nullptr;
    assert(itemvalue(&unresolved, &unavailable) == 0 && unavailable.invalid);
    obj_index = saved_index;
    circles(); packed_rounding(); applies(); apply_permutations(); zero_insertion(); proc_policy(); coverage_cases(); resolved_racial_context();
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
#include "item/objmisc.h"
#include <cassert>
#include <cstring>
#include <algorithm>
#include <cstdio>
#include <climits>
#include <cmath>
#include <limits>

static void numeric_bounds()
{
    item_value_input input;
    item_value_context context;
    item_value_breakdown detail;
    input.type = ITEM_WEAPON; input.value[0] = WEAPON_LONGSWORD;
    for (int dice : {1000, 50000, INT_MAX}) {
        input.value[1] = input.value[2] = dice;
        assert(evaluate_item_value(input, context, &detail) == 0 && detail.invalid);
        input.value[0] = WEAPON_DAGGER;
        assert(evaluate_item_value(input, context, &detail) == 0 && detail.invalid);
        input.value[0] = WEAPON_LONGSWORD;
    }
    for (int count : {INT_MIN, INT_MAX})
    for (int sides : {INT_MIN, INT_MAX}) {
        input.value[1] = count; input.value[2] = sides;
        const int score = evaluate_item_value(input, context, &detail);
        assert((score == 0) == detail.invalid);
    }
    input = {};
    context.native_proc_credit = INT_MAX;
    assert(evaluate_item_value(input, context, &detail) == INT_MAX && !detail.invalid);
    input.affected[0] = {APPLY_HIT, 1};
    assert(evaluate_item_value(input, context, &detail) == 0 && detail.invalid);
    input.affected[0] = {APPLY_STR_RACE, 1};
    context.native_proc_credit = INT_MAX - 1;
    context.racial_credits[0] = .75;
    assert(evaluate_item_value(input, context, &detail) == INT_MAX - 1 && !detail.invalid);
    context.racial_credits[0] = 1;
    assert(evaluate_item_value(input, context, &detail) == INT_MAX && !detail.invalid);
    context.racial_credits[0] = 1.25;
    assert(evaluate_item_value(input, context, &detail) == 0 && detail.invalid);

    for (double credit : {std::numeric_limits<double>::quiet_NaN(),
                           std::numeric_limits<double>::infinity(),
                           -std::numeric_limits<double>::infinity()}) {
        context.racial_credits[3] = credit; // Even unused context participates in sorting.
        assert(evaluate_item_value(input, context, &detail) == 0 && detail.invalid);
    }
    context = {}; input = {};
    input.affected[0] = {APPLY_STR_RACE, 1};
    input.affected[1] = {APPLY_DEX_RACE, 1};
    context.racial_credits[0] = context.racial_credits[1] = std::numeric_limits<double>::max();
    assert(evaluate_item_value(input, context, &detail) == 0 && detail.invalid);
    context.racial_credits[0] = context.racial_credits[1] = -std::numeric_limits<double>::max();
    assert(evaluate_item_value(input, context, &detail) == 0 && detail.invalid && detail.floored);

    input = {}; context = {};
    input.wear_flags = ITEM_WIELD;
    input.value[5] = 32032032; input.value[6] = 20; input.value[7] = INT_MAX;
    for (auto &circle : context.spell_circles) circle = INT_MAX;
    const int score = evaluate_item_value(input, context, &detail);
    assert(!detail.invalid && score >= 179 && score <= 180 && std::abs(detail.unrounded - 180) < 1e-10);
    std::puts("numeric bounds: finite context, widened dice/circles and checked output conversion");
}

static void apply_totals()
{
    int checked = 0;
    for (int type : {ITEM_WORN, ITEM_ARMOR, ITEM_WEAPON})
    for (int slot = 0; slot < MAX_OBJ_AFFECT; ++slot)
    for (int kind : {APPLY_STR, APPLY_DEX, APPLY_INT, APPLY_WIS, APPLY_CON, APPLY_AGI,
                     APPLY_POW, APPLY_CHA, APPLY_LUCK, APPLY_HIT, APPLY_MOVE, APPLY_MANA,
                     APPLY_HIT_REG, APPLY_MOVE_REG, APPLY_MANA_REG, APPLY_AC,
                     APPLY_SAVING_PARA, APPLY_SAVING_ROD, APPLY_SAVING_FEAR,
                     APPLY_SAVING_BREATH, APPLY_SAVING_SPELL, APPLY_COMBAT_PULSE,
                     APPLY_SPELL_PULSE, APPLY_STR_MAX, APPLY_DEX_MAX, APPLY_INT_MAX,
                     APPLY_WIS_MAX, APPLY_CON_MAX, APPLY_AGI_MAX, APPLY_POW_MAX,
                     APPLY_CHA_MAX, APPLY_LUCK_MAX})
    for (int left : {-128, -100, -6, -1, 0, 1, 3, 6, 100, 127})
    for (int right : {-128, -100, -6, -1, 0, 1, 3, 6, 100, 127}) {
        item_value_input input;
        item_value_context context;
        input.type = type;
        input.wear_flags = ITEM_TAKE | ITEM_WEAR_EYES;
        input.extra_flags = ITEM_TWOHANDS;
        input.value[0] = 10; input.value[1] = 2; input.value[2] = 6;
        context.native_proc_credit = 29;
        input.affected[slot] = {kind, left};
        input.affected[(slot + 1) % MAX_OBJ_AFFECT] = {kind, right};
        const auto unchanged = input;
        item_value_breakdown split, merged;
        evaluate_item_value(input, context, &split);
        assert(!std::memcmp(&input, &unchanged, sizeof(input)));
        input.affected[slot].modifier = left + right;
        input.affected[(slot + 1) % MAX_OBJ_AFFECT] = {};
        evaluate_item_value(input, context, &merged);
        assert(split.score == merged.score && split.base == merged.base &&
               split.multiplier == merged.multiplier && split.unrounded == merged.unrounded);
        ++checked;
    }
    std::printf("apply totals: %d split/merge, cancellation and widened-total cases\n", checked);

    // MAX also affects the live current stat, so the two locations stay distinct.
    item_value_input input;
    item_value_context context;
    item_value_breakdown current, maximum, together;
    input.affected[0] = {APPLY_STR, 6};
    evaluate_item_value(input, context, &current);
    input.affected[0] = {APPLY_STR_MAX, 2};
    evaluate_item_value(input, context, &maximum);
    input.affected[1] = {APPLY_STR, 6};
    evaluate_item_value(input, context, &together);
    assert(together.base == current.base + maximum.base && together.multiplier == maximum.multiplier);

    for (int kind = APPLY_STR_RACE; kind <= APPLY_LUCK_RACE; ++kind)
    for (int left : {-50, 0, 10, 50, 150})
    for (int right : {-50, 0, 10, 50, 150}) {
        input = {}; context = {};
        context.native_proc_credit = 200;
        input.affected[0] = {kind, 1}; input.affected[1] = {kind, 2};
        context.racial_credits[0] = left; context.racial_credits[1] = right;
        evaluate_item_value(input, context, &together);
        assert(together.base == 200 + std::max(left, right));
        input.affected[2] = {kind, LAST_RACE + 1}; context.racial_credits[2] = 100;
        input.affected[3] = {kind, -1}; context.racial_credits[3] = 100;
        evaluate_item_value(input, context, &together);
        assert(together.base == 400 + std::max(left, right));
        input.affected[2].modifier = input.affected[3].modifier = 0;
        evaluate_item_value(input, context, &together);
        assert(together.base == 200 + std::max(left, right));
    }
}

int main()
{
    numeric_bounds();
    apply_totals();
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
    input.affected[0] = {APPLY_STR_RACE, 1};
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
    proc = (ROOT / "src/item/item_value_procs.c").read_text()
    callbacks = sorted(set(re.findall(
        r'\{\s*(\w+),\s*"\w+",\s*\d+,\s*item_value_proc_policy::(?:priced|utility)', proc)))
    route_source = re.sub(r'//[^\n]*|/\*.*?\*/', '', (ROOT / "src/specs/specs.object.c").read_text(), flags=re.S)
    melee_only = re.findall(r'\{\s*(\w+),\s*"\w+",\s*\d+,\s*item_value_proc_policy::priced,\s*true', proc)
    assert len(melee_only) == 20
    for name in melee_only:
        definition = re.search(r'\bint ' + name + r'\s*\([^;{}]*\)\s*\{', route_source)
        assert definition and re.match(r'\s*P_char\s+(\w+)\s*=\s*melee_proc_target\(obj,\s*ch,\s*cmd,\s*arg\);\s*if\s*\(\s*!\1(?:\s*\|\|[^{};]*)?\)\s*\{\s*return FALSE;\s*\}', route_source[definition.end():]), name
    identities = "\n".join(
        f"int {name}(P_obj, P_char, int, char *) {{ assert(false); return 0; }}"
        for name in callbacks)
    production = "\n".join((
        extract_function("utility.c", "int flag2idx(int flag)\n{"),
        extract_function("tradeskill.c", "int get_mincircle(int spell)\n{")))
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ival-characterization-", dir=build) as tmp:
        source, binary = Path(tmp) / "test.cpp", Path(tmp) / "test"
        source.write_text(HARNESS.replace("// CALLBACKS", identities).replace("// PRODUCTION", production))
        subprocess.run([
            "g++", "-std=c++20", "-g", "-O1", "-D_PFILE_", "-Isrc",
            "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
            "-fsanitize=address,undefined,float-cast-overflow", "-fno-sanitize-recover=all",
            "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
            str(source), rel("skills.c"), str(HARNESS_STUBS), "src/item/item_value.c",
            "src/item/item_value_runtime.c", "src/item/item_value_procs.c", "-o", str(binary),
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
        for value in ("50000", "1000", str(2**31 - 1)):
            result = subprocess.run([str(binary), value], capture_output=True, text=True, env=env)
            assert result.returncode == 0 and "boundary score unavailable" in result.stdout, result.stderr
            print(f"F08 {value}d{value}: unavailable without sanitizer errors", flush=True)


if __name__ == "__main__":
    main()
