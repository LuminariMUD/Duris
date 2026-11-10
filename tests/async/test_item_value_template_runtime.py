#!/usr/bin/env python3
"""Compare read-only valuation with the real engine constructor and callbacks.

Uses the existing server objects, renaming only its main entry point. UID and
RNG endpoints are controlled; valuation, decoders, native handlers, object
construction, conversion, and cleanup are production code. Metadata uses native
loaders; no game loop, reset execution, listening socket, or database is started.
"""
from pathlib import Path
import os
import shlex
import shutil
import csv
import hashlib
import subprocess
import tempfile
import argparse
import json
import re

from _paths import ROOT, extract_function


HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "item/item_value.h"
#include "item/item_value_procs.h"
#include "item/objmisc.h"
#include "world/object_template.h"
#include "specs/object_bindings.h"
#include "world/db.h"
#include "core/mm.h"
#include "magic/spells.h"
#include "core/proc-libs.h"
#include "combat/ctf.h"
#include "economy/nexus_stones.h"
#include "economy/mining.h"
#include "kingdom/kingdom.h"
#include "world/vnum.obj.h"
#include "mob/studioproc.h"
#include "item/random_equipment.h"
#include "item/random_equipment_config.h"
#include "economy/crafting.h"
#include "item/enhance.h"
#include "world/world_quest_policy_math.h"
#include <algorithm>
#include <array>
#include <chrono>
#include <map>
#include <vector>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <set>
#include <string>

extern P_index obj_index;
extern P_obj object_list;
extern int top_of_objt;
extern long ne_event_counter;
extern mm_ds *dead_obj_pool;
extern struct race_names race_names_table[];
void update_stat_data();
void ne_init_event_pool();
static unsigned long long identities = 1000000;
static unsigned long rolls;
static bool seeded_rng;
static bool corpus;
static int compared;
static FILE *reference_scores;
extern "C" unsigned long long __wrap__Z25persistence_next_item_uidv() { return ++identities; }
extern "C" int __real__Z6numberii(int, int);
extern "C" int __wrap__Z6numberii(int low, int high) {
    ++rolls; return seeded_rng ? __real__Z6numberii(low, high) : low;
}

// SOURCE_REWARD_POLICY
// CONSUMER_BASELINE

#if VALUE_BASELINE
extern Skill skills[];
int get_mincircle(int);
static bool before_context;
#if CIRCLE_BASELINE
// BASELINE_CIRCLE
extern "C" int __real__Z13get_mincirclei(int);
extern "C" int __wrap__Z13get_mincirclei(int spell) {
    return before_context ? get_mincircle_before(spell) : __real__Z13get_mincirclei(spell);
}
#else
static int get_mincircle_before(int spell) { return get_mincircle(spell); }
#endif
#if NUMERIC_BASELINE
static unsigned long before_evaluations, after_evaluations;
int itemvalue_before(P_obj);
extern "C" int __real__Z9itemvalueP8obj_data(P_obj);
extern "C" int __wrap__Z9itemvalueP8obj_data(P_obj object) {
    if (before_context) {
        ++before_evaluations;
        return itemvalue_before(object);
    }
    ++after_evaluations;
    return __real__Z9itemvalueP8obj_data(object);
}
#endif
static FILE *deltas;
extern P_room world;
extern int top_of_world, top_of_zone_table;
extern zone_data *zone_table;
extern int enhance_level_gate_multiplier, enhance_stat_platinum_base, enhance_stat_platinum_per_ival;

struct zone_interval { int bottom = 0, top = 0, zone = -1; };
static std::vector<zone_interval> quest_intervals;
// QUEST_POLICIES
// BAG_POLICY

static int replacement_cost(int sval) {
    int cost;
    // REPLACEMENT_PRICE
    return cost;
}
static int64_t nominal_superior_cost(int source_value) {
    // SUPERIOR_PRICE
    return cost;
}
struct consumer_snapshot {
    int value, replacement_cost;
    int64_t craft_min_level, enhance_min_level, donor_min, craft_xp, superior_cost;
    crafting_plan materials{};
    bool craft_plan, recipe_available;
};
static consumer_snapshot consumer_values(P_obj object, bool before) {
#if NUMERIC_BASELINE
    const auto calls = before ? before_evaluations : after_evaluations;
#endif
    before_context = before;
    consumer_snapshot result{};
    result.value = itemvalue(object);
#if NUMERIC_BASELINE
    assert((before ? before_evaluations : after_evaluations) > calls);
#endif
    result.craft_plan = crafting_build_plan(object, &result.materials);
    result.recipe_available = crafting_recipe_target_is_available(object);
    before_context = false;
    const int64_t gate = crafting_level_gate_multiplier();
    assert(gate > 0 && enhance_level_gate_multiplier > 0);
    result.craft_min_level = (result.value + gate - 1) / gate;
    result.enhance_min_level = (static_cast<int64_t>(result.value) + enhance_level_gate_multiplier - 1) / enhance_level_gate_multiplier;
    result.donor_min = static_cast<int64_t>(result.value) - enhance_material_ival_delta +
        ((object->wear_flags & ITEM_GUILD_INSIGNIA) ? enhance_guild_insignia_ival_bonus : 0);
    result.craft_xp = static_cast<int64_t>(result.value) * crafting_experience_per_ival();
    if (result.craft_plan) assert(result.materials.experience == result.craft_xp);
    if (result.craft_xp > INT_MAX) assert(!result.craft_plan && !result.recipe_available);
    result.replacement_cost = replacement_cost(result.value);
    result.superior_cost = nominal_superior_cost(result.value);
    return result;
}
struct quest_weight_delta { int before_count = 0, after_count = 0; int64_t before_sum = 0, after_sum = 0; };
static std::map<std::pair<int, int>, quest_weight_delta> quest_weights;
static void write_quest_weights() {
    FILE *file = std::fopen("quest-weight-deltas.csv", "w"); assert(file);
    std::fputs("zone,quest_level,before_count,after_count,before_sum,after_sum,before_weight_unit_fit,after_weight_unit_fit\n", file);
    for (const auto &[key, delta] : quest_weights) {
        if (delta.before_count == delta.after_count && delta.before_sum == delta.after_sum) continue;
        const auto [zone, level] = key;
        const double old_average = delta.before_count ? double(delta.before_sum) / delta.before_count : 0;
        const double new_average = delta.after_count ? double(delta.after_sum) / delta.after_count : 0;
        std::fprintf(file, "%d,%d,%d,%d,%lld,%lld,%.12g,%.12g\n", zone_table[zone].number, level,
                     delta.before_count, delta.after_count, (long long)delta.before_sum, (long long)delta.after_sum,
                     world_quest_zone_raw_score(level, level, old_average, delta.before_count),
                     world_quest_zone_raw_score(level, level, new_average, delta.after_count));
    }
    assert(!std::fclose(file));
}
static void value_delta(const char *cohort, int id, P_obj object) {
    const auto random = rolls;
    const auto ids = identities;
    const auto old = consumer_values(object, true);
    const auto updated = consumer_values(object, false);
    assert(rolls == random && identities == ids);
    const int vnum = obj_index[object->R_num].virtual_number;
    std::set<int> apply_kinds;
    int apply_stages = 0;
    for (const auto &apply : object->affected) {
        if (apply.location != APPLY_NONE) apply_kinds.insert(apply.location);
        switch (apply.location) {
        case APPLY_AC: if (apply.modifier) apply_stages |= 1; break;
        case APPLY_STR_MAX: case APPLY_DEX_MAX: case APPLY_INT_MAX: case APPLY_WIS_MAX:
        case APPLY_CON_MAX: case APPLY_CHA_MAX: case APPLY_AGI_MAX: case APPLY_POW_MAX: case APPLY_LUCK_MAX:
            apply_stages |= 1; break;
        case APPLY_HITROLL: case APPLY_DAMROLL: case APPLY_COMBAT_PULSE: case APPLY_SPELL_PULSE:
            apply_stages |= 2; break;
        }
    }
    P_obj obj = object;
    // PACKED_DECLARATIONS
    unsigned int callbacks = 0;
    bool dense = true;
    for (int slot = 0; slot < 3; ++slot) {
        if (slot < count && !spells[slot]) dense = false;
        if (spells[slot] > 0 && spells[slot] < MAX_SKILLS && skills[spells[slot]].spell_pointer)
            callbacks |= 1u << slot;
    }
    const bool candidate = vnum >= enhance_search_vnum_min && vnum <= enhance_search_vnum_max && is_enhance_pool_candidate(object);
    std::fprintf(deltas, "%s,%d,%d,%d,%d,%d,%d,%d,%d,%llu,", cohort, id, old.value, updated.value, object->value[5],
                 object->type, is_salvageable(object), !is_enhance_banned(object), candidate,
                 static_cast<unsigned long long>(object->bitvector5));
    std::fprintf(deltas, "%d,%d,%d,%d,%d,%d,", old.craft_plan, updated.craft_plan,
                 old.materials.high_material_count, updated.materials.high_material_count,
                 old.materials.low_material_count, updated.materials.low_material_count);
    std::fprintf(deltas, "%lld,%lld,%lld,%lld,%d,%d,", (long long)old.craft_xp, (long long)updated.craft_xp,
                 (long long)old.craft_min_level, (long long)updated.craft_min_level, old.recipe_available, updated.recipe_available);
    std::fprintf(deltas, "%lld,%lld,%lld,%lld,%d,%d,%lld,%lld,", (long long)old.enhance_min_level,
                 (long long)updated.enhance_min_level, (long long)old.donor_min, (long long)updated.donor_min,
                 old.replacement_cost, updated.replacement_cost, (long long)old.superior_cost, (long long)updated.superior_cost);
    const int zone = source_eligible_reward(object) ? zone_for_vnum(vnum) : -1;
    int floor_lost = 0, floor_gained = 0;
    if (!std::strcmp(cohort, "template") && zone >= 0) {
        for (int level = 1; level < TOTALLVLS; ++level) {
            auto &delta = quest_weights[{zone, level}];
            const bool old_floor = world_quest_item_passes_floor(level, old.value);
            const bool new_floor = world_quest_item_passes_floor(level, updated.value);
            if (old_floor) { ++delta.before_count; delta.before_sum += old.value; }
            if (new_floor) { ++delta.after_count; delta.after_sum += updated.value; }
            floor_lost += old_floor && !new_floor;
            floor_gained += new_floor && !old_floor;
        }
    }
    item_value_breakdown resolved; itemvalue(object, &resolved);
    std::fprintf(deltas, "%d,%d,%d,%d,%d,%d,%d,%d,%u,%d,%d,%zu,%d", static_cast<int>(resolved.native_base),
                 source_eligible_reward(object), vnum, zone >= 0 ? zone_table[zone].number : -1, floor_lost, floor_gained,
                 count, dense, callbacks, object->value[6], object->value[7], apply_kinds.size(), apply_stages);
    for (const auto &apply : object->affected)
        std::fprintf(deltas, ",%d,%d", apply.location, apply.modifier);
    std::fprintf(deltas, ",%d,%d,%d\n", qualification_bag_candidate(object),
                 object->type == ITEM_WEAPON ? object->value[1] : 0,
                 object->type == ITEM_WEAPON ? object->value[2] : 0);
}

static void generated_deltas() {
    boot_random_equipment_config();
    FILE *pool = std::fopen("generator-circles.csv", "w"); assert(pool);
    std::fputs("spell,self_only,before,after\n", pool);
    for (const auto &entry : spells_data)
        std::fprintf(pool, "%d,%d,%d,%d\n", entry.spell, entry.self_only,
                     get_mincircle_before(entry.spell), get_mincircle(entry.spell));
    assert(!std::fclose(pool));
    char_data finder{};
    pc_only_data pc{};
    finder.only.pc = &pc;
    finder.player.name = const_cast<char *>("ValuationFixture");
    finder.player.level = 56;
    finder.curr_stats.Luk = 160;
    extern P_room world;
    extern int top_of_world;
    extern zone_data *zone_table;
    for (int room = 0; room <= top_of_world; ++room)
        if (!zone_table[world[room].zone].hometown &&
            strip_ansi(zone_table[world[room].zone].name) != zone_table[world[room].zone].name) {
            finder.in_room = room;
            break;
        }
    seeded_rng = true;
    int count = 0;
    for (int seed = 1; seed <= 16; ++seed)
    for (int level : {1, 20, 40, 60, 62})
    for (int slot = 0; slot < MAX_SLOT; ++slot) {
        randomize(seed * 100000 + level * 1000 + slot);
        P_obj object = create_random_eq(&finder, 56, level, slot, -1);
        assert(object);
        value_delta("generated", ++count, object);
        extract_obj(object);
    }
    std::printf("seeded native generator comparisons: %d samples\n", count);
}
#endif

static void fixture_files()
{
    std::filesystem::create_directories("areas");
    std::filesystem::create_directories("lib");
    std::set<int> numbers;
    for (auto stage : {object_proc_binding_stage::objects, object_proc_binding_stage::rooms})
        for (const auto &binding : object_proc_bindings(stage)) numbers.insert(binding.vnum);
    for (int i = 0; i < 12; ++i) numbers.insert(9000000 + i);
    for (int vnum : {193, 394, 395, 434, 477, 478, 479, 480, 481, 482, 483, 484,
                     485, 486, 790, 48111}) numbers.insert(vnum);
    FILE *objects = std::fopen("areas/world.obj", "w"); assert(objects);
    for (int vnum : numbers)
        std::fprintf(objects, "#%d\nfixture~\na fixture~\nA fixture is here.~\n~\n"
                     "11 1 0 0 7 0 0 1 0 0 0\n0 0 0 0 0 0 0 0\n1 0 100 0 0 0 0\n", vnum);
    std::fputs("$~\n", objects); assert(!std::fclose(objects));
    FILE *properties = std::fopen("lib/duris.properties", "w"); assert(properties);
    std::fprintf(properties, "stats.str.%s=140\n", race_names_table[RACE_HUMAN].no_spaces);
    assert(!std::fclose(properties));
    FILE *config = std::fopen("lib/kingdom.cfg", "w"); assert(config);
    std::fputs("kingdom.enabled=1\n", config); assert(!std::fclose(config));
    FILE *triggers = std::fopen("areas/world.trg", "w"); assert(triggers);
    // Non-object targets must be skipped before looking up unloaded mobiles/rooms.
    std::fputs("#9000009 M\nT REPOP\necho unused\n~\nS\n"
               "#9000009 R\nT ENTER\necho unused\n~\nS\n"
               "#9000009 O\nT SEARCH\nmload 87\ntransfer 22800\n~\nS\n#~\n", triggers);
    assert(!std::fclose(triggers));
}

static object_template base(int vnum = 9000000)
{
    assert(cache_object_template(vnum));
    object_template object = *find_object_template(vnum);
    object.affected[0] = {APPLY_HIT, 10};
    return object;
}

static void unavailable_salvage()
{
    auto prototype = *find_object_template(9000000);
    prototype.type = ITEM_WEAPON;
    prototype.wear_flags = ITEM_TAKE | ITEM_WIELD;
    prototype.extra_flags = prototype.extra2_flags = 0;
    prototype.material = MAT_CLOTH;
    prototype.value[0] = WEAPON_LONGSWORD;
    prototype.value[1] = prototype.value[2] = 50000;
    P_obj item = instantiate_object_template(prototype);
    assert(item && itemvalue(item) == 0 && is_salvageable(item));
    assert(get_matstart(item) > 0);
    crafting_plan plan{};
    assert(!crafting_build_plan(item, &plan));
    char_data player{};
    pc_only_data pc{};
    player.only.pc = &pc;
    player.player.name = const_cast<char *>("ValuationFixture");
    player.player.level = 56;
    player.specials.position = POS_STANDING | STAT_NORMAL;
    pc.skills[SKILL_SALVAGE].learned = 100;
    player.carrying = item;
    item->loc_p = LOC_CARRIED;
    item->loc.carrying = &player;
    assert(GET_CHAR_SKILL(&player, SKILL_SALVAGE) >= 1);
    assert(get_obj_in_list_vis(&player, "fixture", item) == item);
    const auto original = *item;
    const auto random = rolls;
    const auto ids = identities;
    char command[] = "fixture";
    do_salvage(&player, command, 0);
    assert(player.carrying == item && !std::memcmp(item, &original, sizeof(*item)));
    assert(rolls == random && identities == ids);
    player.carrying = nullptr;
    item->loc_p = LOC_NOWHERE;
    item->loc.carrying = nullptr;
    extract_obj(item);
    std::puts("native salvage command: unavailable score preserves item before rolls/grants");
}


static void qualify_consumer_index() {
    load_enhance_config();
    long long old_us=0, old_ids=0; int old_stats=0;
#if CONSUMER_BASELINE
    std::array<std::vector<int>,ENHANCE_IVAL_TABLE_SIZE> expected;
    const auto old_start=std::chrono::steady_clock::now(); const auto before_ids=identities;
    load_enhance_index_before();
    old_us=std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now()-old_start).count();
    old_ids=identities-before_ids;
    for(int bucket=0;bucket<ENHANCE_IVAL_TABLE_SIZE;++bucket)
        for(auto *entry=enhance_ival_table[bucket];entry;entry=entry->next) expected[bucket].push_back(entry->vnum);
    for(auto *entry:enhance_stat_table) for(;entry;entry=entry->next) ++old_stats;
    for(auto &head:enhance_ival_table) while(head){auto *next=head->next;free(head);head=next;}
    for(auto &head:enhance_stat_table) while(head){auto *next=head->next;free(head);head=next;}
#endif
    const auto ids=identities; const auto random=rolls; const auto events=ne_event_counter; const auto objects=object_list;
    const auto start=std::chrono::steady_clock::now(); assert(load_enhance_index());
    const auto elapsed=std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now()-start).count();
    assert(identities==ids && rolls==random && ne_event_counter==events && object_list==objects);
    int count=0, stats=0;
    for(int bucket=0;bucket<ENHANCE_IVAL_TABLE_SIZE;++bucket) {
        std::vector<int> actual;
        for(auto *entry=enhance_ival_table[bucket];entry;entry=entry->next) {
            actual.push_back(entry->vnum); ++count;
            const auto *prototype=find_object_template(entry->vnum); assert(prototype && entry->ival==itemvalue(*prototype));
        }
#if CONSUMER_BASELINE
        assert(actual==expected[bucket]); // Includes collisions and the incumbent same-score tie order.
#endif
    }
    for(auto *entry:enhance_stat_table) for(;entry;entry=entry->next) ++stats;
    FILE *metrics=std::fopen("consumer-metrics.json","w"); assert(metrics);
    std::fprintf(metrics,"{\"templates\":%d,\"index_templates\":%d,\"legacy_index_us\":%lld,\"template_index_us\":%lld,\"legacy_transient_identities\":%lld,\"template_transient_identities\":0,\"template_rng_draws\":0,\"legacy_stat_entries\":%d,\"deduplicated_stat_entries\":%d}\n",top_of_objt+1,count,old_us,(long long)elapsed,old_ids,old_stats,stats);
    assert(!std::fclose(metrics));
    std::printf("native consumer index: %d templates, %d stat entries; legacy/new transient identities %lld/0; legacy/new time %lld/%lld us\n",count,stats,old_ids,old_us,(long long)elapsed);
}

static void parity(object_template &prototype, const char *label)
{
    std::fprintf(stderr, "checking real engine template parity %s vnum=%d\n", label,
                 obj_index[prototype.R_num].virtual_number);
    const auto ids = identities;
    const auto random = rolls;
    const auto events = ne_event_counter;
    const auto objects = object_list;
    const auto count = obj_index[prototype.R_num].number;
    const auto proc = obj_index[prototype.R_num].func.obj;
    const auto values = prototype;
    item_value_breakdown detail;
    const int from_template = itemvalue(prototype, &detail);
    assert(from_template == detail.score && detail.unrounded == detail.base * detail.multiplier);
    assert(identities == ids && rolls == random && ne_event_counter == events);
    assert(object_list == objects && obj_index[prototype.R_num].number == count);
    assert(obj_index[prototype.R_num].func.obj == proc);
    assert(!std::memcmp(prototype.value, values.value, sizeof(prototype.value)));
    assert(!std::memcmp(prototype.affected, values.affected, sizeof(prototype.affected)));
    assert(prototype.bitvector == values.bitvector && prototype.extra_flags == values.extra_flags);
    assert(prototype.descriptions.size() == values.descriptions.size());
    for (size_t i = 0; i < prototype.descriptions.size(); ++i)
        assert(prototype.descriptions[i].keyword == values.descriptions[i].keyword &&
               prototype.descriptions[i].description == values.descriptions[i].description);
    auto view=inspect_object_template(prototype);
    assert(!view.obj_uid && !view.nevents && !view.next_content);
    P_obj instance = instantiate_object_template(prototype);
    assert(is_enhance_pool_candidate(&view)==is_enhance_pool_candidate(instance));
    assert(source_eligible_reward(&view)==source_eligible_reward(instance));
    assert(view.type==instance->type && view.wear_flags==instance->wear_flags && view.material==instance->material);
    // Only inspectable power fields are compared: money/state callbacks may
    // initialize unrelated value slots that these consumers never read.
    if (is_enhance_pool_candidate(&view))
        assert(!std::memcmp(view.affected,instance->affected,sizeof(view.affected)));

    assert(instance && identities == ids + 1);
    const int runtime = itemvalue(instance);
    if (runtime != from_template) {
        std::fprintf(stderr, "%s: template=%d runtime=%d\n", label, from_template, runtime);
        std::abort();
    }
#if VALUE_BASELINE
    if (corpus) value_delta("template", obj_index[prototype.R_num].virtual_number, instance);
#endif
    extract_obj(instance);
    assert(object_list == objects && obj_index[prototype.R_num].number == count);
    if (ne_event_counter != events) {
        std::fprintf(stderr, "%s: reference extraction events before=%ld after=%ld\n", label, events, ne_event_counter);
        std::abort();
    }
    ++compared;
    if (corpus) std::fprintf(reference_scores, "%d,%d\n",
                             obj_index[prototype.R_num].virtual_number, runtime);
    if (!corpus) std::printf("real engine template parity %s: %d\n", label, runtime);
}

int main(int argc, char **)
{
    std::setvbuf(stdout, nullptr, _IONBF, 0);
    corpus = argc > 1;
    if (!corpus) fixture_files();
    assert(boot_material_rarity_objects(0));
    assert(identities == 1000000 && rolls == 0 && !object_list && ne_event_counter == 0);
    dead_obj_pool = mm_create("OBJS", sizeof(obj_data), offsetof(obj_data, next), 4);
    ne_init_event_pool();
    if (corpus) {
#if VALUE_BASELINE
        boot_crafting_system();
        load_enhance_config();
        build_intervals();
        deltas = std::fopen("value-deltas.csv", "w"); assert(deltas);
        std::fputs("cohort,id,before,after,packed_spells,type,salvageable,enhance_allowed,enhance_index_candidate,unpriced_bank5,"
                   "craft_plan_before,craft_plan_after,high_units_before,high_units_after,low_units_before,low_units_after,"
                   "craft_xp_before,craft_xp_after,craft_min_level_before,craft_min_level_after,recipe_before,recipe_after,"
                   "enhance_min_level_before,enhance_min_level_after,donor_min_before,donor_min_after,"
                   "replacement_cost_copper_before,replacement_cost_copper_after,nominal_superior_cost_copper_before,nominal_superior_cost_copper_after,"
                   "native_proc_credit,quest_source_eligible,template_vnum,quest_zone,quest_floor_lost,quest_floor_gained,"
                   "packed_slot_count,packed_dense,packed_callback_mask,proc_level,proc_denominator,apply_kind_count,apply_stage_mask,"
                   "apply0,modifier0,apply1,modifier1,apply2,modifier2,apply3,modifier3,faerie_candidate,weapon_dice_count,weapon_dice_sides\n", deltas);
        FILE *settings = std::fopen("consumer-settings.json", "w"); assert(settings);
        std::fprintf(settings, "{\"max_mortal_level\":%d,\"craft_level_gate\":%d,\"craft_xp_per_ival\":%d,\"enhance_level_gate\":%d,"
                     "\"enhance_donor_delta\":%d,\"enhance_insignia_bonus\":%d,"
                     "\"enhance_low_threshold\":%d,\"enhance_low_cost_copper\":%d,\"enhance_high_cost_copper\":%d,"
                     "\"superior_base_copper\":%d,\"superior_per_ival_copper\":%d}\n",
                     MAXLVLMORTAL, crafting_level_gate_multiplier(), crafting_experience_per_ival(), enhance_level_gate_multiplier,
                     enhance_material_ival_delta, enhance_guild_insignia_ival_bonus,
                     enhance_cost_low_ival_threshold, enhance_cost_low_amount, enhance_cost_high_amount,
                     enhance_stat_platinum_base, enhance_stat_platinum_per_ival);
        assert(!std::fclose(settings));
        FILE *circles = std::fopen("changed-circles.csv", "w"); assert(circles);
        std::fputs("spell,before,after\n", circles);
        for (int spell = FIRST_SPELL; spell <= LAST_SPELL; ++spell) {
            const int old_circle = get_mincircle_before(spell);
            const int new_circle = get_mincircle(spell);
            if (old_circle != new_circle)
                std::fprintf(circles, "%d,%d,%d\n", spell, old_circle, new_circle);
        }
        assert(!std::fclose(circles));
#endif
        reference_scores = std::fopen("reference-scores.csv", "w"); assert(reference_scores);
        for (int rnum = 0; rnum <= top_of_objt; ++rnum) {
            assert(cache_object_template(obj_index[rnum].virtual_number));
            auto object = *find_object_template(obj_index[rnum].virtual_number);
            parity(object, "effective-world");
        }
        qualify_consumer_index();
        std::printf("effective-world native constructor/template parity: %d templates\n", compared);
        assert(!std::fclose(reference_scores));
#if VALUE_BASELINE
        generated_deltas();
        write_quest_weights();
        assert(!std::fclose(deltas));
#endif
        return 0;
    }
    assert(kingdom_enabled());
    for (int vnum : {477, 478, 479, 480, 481, 482, 483, 484, 485, 486, 48111})
        assert(obj_index[real_object(vnum)].func.obj);
    assert(obj_index[real_object(193)].func.obj == mine);
    assert(obj_index[real_object(434)].func.obj == mine);
    assert(obj_index[real_object(394)].func.obj == nexus_stone);
    assert(obj_index[real_object(395)].func.obj == nexus_guardian_pwn_mace);
    assert(obj_index[real_object(9000009)].func.obj == studioproc_obj);
    const auto first_proc = obj_index[0].func.obj;
    assign_ctf_object_procs(); // Missing flags must not index -1 or overwrite slot 0.
    assert(obj_index[real_object(790)].func.obj == ctf_flag_proc);
    assert(obj_index[0].func.obj == first_proc && !object_list && ne_event_counter == 0);
    auto object = base(); parity(object, "stat-only");
    object = base(23808); parity(object, "native-stoneskin");
    object = base(1372); object.type = ITEM_WEAPON; object.wear_flags |= ITEM_WIELD;
    object.value[0] = WEAPON_LONGSWORD; object.value[1] = 2; object.value[2] = 6;
    parity(object, "native-weapon");
    object = base(9000001); object.type = ITEM_WEAPON; object.wear_flags |= ITEM_WIELD;
    object.value[0] = WEAPON_LONGSWORD; object.value[1] = 2; object.value[2] = 6;
    object.value[5] = 32; object.value[6] = 60; object.value[7] = 30;
    parity(object, "packed");
    object = base(9000002); object.affected[3] = {APPLY_STR_RACE, RACE_HUMAN};
    assert(itemvalue(object) == 159); parity(object, "configured-racial");
    object = base(9000003); object.type = ITEM_ARMOR; object.value[0] = 10;
    parity(object, "armor");
    object = base(9000004); object.type = ITEM_SHIELD; object.value[3] = 10;
    parity(object, "shield-legacy");
    object = base(9000005); object.type = ITEM_WEAPON; object.value[0] = WEAPON_DAGGER;
    object.value[1] = 0; object.value[2] = -1;
    object.bitvector = AFF_SLEEP | AFF_FEAR | AFF_CHARM | AFF_HASTE;
    parity(object, "normalization");
    object.extra_flags |= ITEM_IGNORE; parity(object, "ignored-normalization");
    object = base(9000006); object.descriptions.push_back({"_proclib_hummer1", ""});
    parity(object, "proclib-hummer");
    object = base(9000007); object.descriptions.push_back({"_PROCLIB_TRANSPORTER1", "portal 101"});
    parity(object, "proclib-uppercase-transporter");
    object = base(9000008); object.descriptions.push_back({"_proclib_transporter1", "not-valid"});
    parity(object, "invalid-proclib");
    object = base(1372); object.descriptions.push_back({"_proclib_sayresponse1", "'hello' 'a reply'"});
    parity(object, "native-plus-proclib");
    for (const char *name : {"actroom1", "actworn1", "hummer1", "sayresponse1", "transporter1"})
        assert(!valid_object_proclib(name, std::string(MAX_STRING_LENGTH, 'x').c_str()));
    object.R_num = -1; assert(itemvalue(object) == 0);
    assert(!object_list && ne_event_counter == 0);
    unavailable_salvage();
    assert(!object_list && ne_event_counter == 0);
    std::puts("real engine: template evaluation creates no identities/objects/events, consumes no RNG, and leaves inputs/bindings unchanged");
}
'''


def consumer_effects(rows, settings, quest_rows):
    """Summarize native values/plans and policy boundaries; never calculate iVal."""
    result = {}
    maximum = settings["max_mortal_level"]
    for cohort in ("template", "generated"):
        changed = [{key: (value if key == "cohort" else int(value)) for key, value in row.items()}
                   for row in rows if row["cohort"] == cohort and row["before"] != row["after"]]
        recipes = [row for row in changed if row["recipe_before"] or row["recipe_after"]]
        # Both command modes reject non-salvageable sources before their score/price gates.
        sources = [row for row in changed if row["salvageable"] and row["enhance_allowed"]]
        mortal_sources = [row for row in sources if min(row["enhance_min_level_before"], row["enhance_min_level_after"]) <= maximum]
        effects = {
            "changed_scores": len(changed),
            "score_delta_range": [min((r["after"] - r["before"] for r in changed), default=0),
                                  max((r["after"] - r["before"] for r in changed), default=0)],
            "salvage_quality_crossings": {str(limit): sum(bool(r["salvageable"]) and
                ((r["before"] <= limit) != (r["after"] <= limit)) for r in changed) for limit in (5, 10, 15, 20)},
            "salvage_recipe_roll_100_crossings": sum(bool(r["salvageable"]) and
                ((r["before"] >= 100) != (r["after"] >= 100)) for r in changed),
            "faerie_bag_crossings": {str(limit): sum(bool(r["faerie_candidate"]) and (
                ((r["before"] <= limit) != (r["after"] <= limit)) if limit == 125 else
                ((r["before"] >= limit) != (r["after"] >= limit))) for r in changed) for limit in (25, 50, 125)},
            "faerie_bag_high_value_log_crossings": sum(bool(r["faerie_candidate"]) and
                ((r["before"] > 100) != (r["after"] > 100)) for r in changed),
            "raw_score_25_50_125_crossings": {str(limit): sum(
                ((r["before"] <= limit) != (r["after"] <= limit)) if limit == 125 else
                ((r["before"] >= limit) != (r["after"] >= limit)) for r in changed) for limit in (25, 50, 125)},
            "recipe_admission_changes": sum(r["recipe_before"] != r["recipe_after"] for r in changed),
            "craft_mortal_level_requirement_changes": sum(
                min(maximum + 1, r["craft_min_level_before"]) != min(maximum + 1, r["craft_min_level_after"]) for r in recipes),
            "recipe_material_plan_changes": sum(r["high_units_before"] != r["high_units_after"] or
                r["low_units_before"] != r["low_units_after"] for r in recipes),
            "recipe_high_units_delta_one_craft_each": sum(r["high_units_after"] - r["high_units_before"] for r in recipes),
            "recipe_low_units_delta_one_craft_each": sum(r["low_units_after"] - r["low_units_before"] for r in recipes),
            "nominal_recipe_xp_delta_one_craft_each": sum(r["craft_xp_after"] - r["craft_xp_before"] for r in recipes),
            "enhance_source_mortal_level_requirement_changes": sum(
                min(maximum + 1, r["enhance_min_level_before"]) != min(maximum + 1, r["enhance_min_level_after"]) for r in mortal_sources),
            "enhance_mortal_source_donor_floor_shifts": {str(r["id"]):
                [r["donor_min_before"], r["donor_min_after"]] for r in mortal_sources if r["donor_min_before"] != r["donor_min_after"]},
            "replacement_fee_changes": sum(r["replacement_cost_copper_before"] != r["replacement_cost_copper_after"] for r in sources),
            "nominal_superior_cost_delta_mortal_sources_copper": sum(
                r["nominal_superior_cost_copper_after"] - r["nominal_superior_cost_copper_before"] for r in mortal_sources),
            "enhancement_index_score_bucket_changes": sum(r["enhance_index_candidate"] for r in changed),
            "quest_reward_floor_losses": sum(r["quest_floor_lost"] for r in changed),
            "quest_reward_floor_gains": sum(r["quest_floor_gained"] for r in changed),
            "changed_rows_with_unpriced_bank5": sum(bool(r["unpriced_bank5"]) for r in changed),
            "changed_native_proc_credits": sorted(set(r["native_proc_credit"] for r in changed)),
            "changed_dense_callable_packed_rows": sum(r["packed_slot_count"] > 0 and r["packed_dense"] and
                r["packed_callback_mask"] == (1 << r["packed_slot_count"]) - 1 and r["proc_level"] > 0 and
                r["proc_denominator"] > 0 and r["template_vnum"] not in (21, 22) for r in changed),
            "changed_partially_callable_packed_ids": [r["id"] for r in changed if r["packed_dense"] and
                0 < r["packed_callback_mask"] < (1 << r["packed_slot_count"]) - 1],
            "changed_single_apply_kind_ids": [r["id"] for r in changed if r["apply_kind_count"] == 1],
            "changed_without_mixed_apply_stages_ids": [r["id"] for r in changed if r["apply_stage_mask"] != 3],
        }
        result[cohort] = effects
    zones = {}
    for row in quest_rows:
        old, new = int(row["before_sum"]), int(row["after_sum"])
        zone = zones.setdefault(row["zone"], {"changed_level_rows": 0, "count_changes": 0, "ratio_min": None, "ratio_max": None})
        zone["changed_level_rows"] += 1
        zone["count_changes"] += row["before_count"] != row["after_count"]
        if old:
            ratio = new / old
            zone["ratio_min"] = ratio if zone["ratio_min"] is None else min(zone["ratio_min"], ratio)
            zone["ratio_max"] = ratio if zone["ratio_max"] is None else max(zone["ratio_max"], ratio)
    result["quest_zone_reward_weight_ratios"] = zones
    result["interpretation"] = [
        "Scores, crafting plans, recipe admission and enhancement candidate eligibility come from native code.",
        "Enhancement source/price effects require both native salvageability and enhancement admission; random equipment VNUMs fail this command gate.",
        "XP and superior prices are nominal if the action is otherwise eligible; currency units are copper.",
        "Before/after projections hold current consumer rules/configuration fixed; direct rule/configuration changes require separate checks.",
        "A source minimum rising from L to H removes levels L..H-1; a donor floor rising from A to B removes donor values A..B-1 if donor scores are fixed.",
        "Quest weight ratios assume unchanged mob level fit; the CSV uses unit fit. Geographic and zone eligibility remain separate gates.",
        "Index tie/selection behavior and complete command/persistence journeys remain F13/F16; legacy mechanical coverage remains F05/F09.",
    ]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    baseline = parser.add_mutually_exclusive_group()
    baseline.add_argument("--circle-baseline", help="Git revision providing the pre-fix circle lookup")
    baseline.add_argument("--consumer-baseline", help="Git revision with the transient-object index for native catalog/timing comparison")
    baseline.add_argument("--numeric-baseline", help="Git revision providing the pre-fix numeric evaluator")
    parser.add_argument("--delta-output", type=Path, help="Directory for circle-fix qualification evidence")
    args = parser.parse_args()
    revision = args.circle_baseline or args.numeric_baseline
    assert bool(revision or args.consumer_baseline) == bool(args.delta_output), "provide baseline and delta-output together"
    configuration = ["make", "-s", "--no-print-directory", "-C", "src",
                     "--eval=.PHONY: ivalue-objects ivalue-libs",
                     "--eval=ivalue-objects:;@echo $(DMS_OBJS)",
                     "--eval=ivalue-libs:;@echo $(LIBS)"]
    objects = shlex.split(subprocess.check_output(configuration + ["ivalue-objects"], cwd=ROOT, text=True))
    libraries = shlex.split(subprocess.check_output(configuration + ["ivalue-libs"], cwd=ROOT, text=True))
    assert objects and all(Path(path).is_file() for path in objects), "build the server with make -C src first"
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="item-value-engine-", dir=build) as tmp:
        path = Path(tmp)
        source, binary = path / "test.cpp", path / "test"
        code = HARNESS.replace("// SOURCE_REWARD_POLICY", extract_function("world_quest_policy.c", "bool source_eligible_reward("))
        baseline_flags = []
        if args.consumer_baseline:
            old_enhance = path / "enhance-before.c"
            old_enhance.write_text(subprocess.check_output(["git", "show", f"{args.consumer_baseline}:src/item/enhance.c"], cwd=ROOT, text=True))
            legacy = "\n".join(extract_function(old_enhance, signature) for signature in
                ("static int enhance_hash(int key)\n{", "static int enhance_stat_hash(int key)\n{", "void load_enhance_index(void)\n{"))
            code = code.replace("// CONSUMER_BASELINE", legacy.replace("void load_enhance_index(", "void load_enhance_index_before(", 1))
            baseline_flags += ["-DCONSUMER_BASELINE=1"]
        if revision:
            policies = (ROOT / "src/world/world_quest_policy.c").read_text()
            native_queries = next(line for line in policies.splitlines() if line.startswith("constexpr int WORLD_QUEST_MAX_ZONE_NUMBER"))
            for signature in ("bool normal_zone(", "bool valid_room_interval(", "int zone_for_vnum(",
                              "void build_intervals()"):
                native_queries += "\n" + extract_function("world_quest_policy.c", signature)
            code = code.replace("// QUEST_POLICIES", native_queries)
            field_filter = extract_function("actmove.c", "static bool faerie_reward_candidate(")
            code = code.replace("// BAG_POLICY", field_filter + "\nstatic bool qualification_bag_candidate(P_obj object) {\n"
                "const int vnum=OBJ_VNUM(object); return vnum>=1300 && vnum<=134000 && faerie_reward_candidate(object) && itemvalue(object)>0;\n}")
            enhance = (ROOT / "src/item/enhance.c").read_text()
            fight = (ROOT / "src/combat/fight.c").read_text()
            start = fight.index("\tconst int spells[3] = { obj->value[5] % 1000")
            end = fight.index("\n\tconst auto continuation", start)
            code = code.replace("// PACKED_DECLARATIONS", fight[start:end])
            start = enhance.index("\tif (sval <= enhance_cost_low_ival_threshold)")
            end = enhance.index("\n\tif (enhancement_wallet_balance(ch) < cost)", start)
            code = code.replace("// REPLACEMENT_PRICE", enhance[start:end])
            start = enhance.index("\tconst int64_t cost = enhance_stat_platinum_base +")
            end = enhance.index(";", start) + 1
            code = code.replace("// SUPERIOR_PRICE", enhance[start:end])
            for file in (["src/item/item_value.c", "src/item/item_value_runtime.c"] if args.circle_baseline else []):
                old = subprocess.check_output(["git", "show", f"{revision}:{file}"],
                                              cwd=ROOT, text=True)
                assert old == (ROOT / file).read_text(), "comparison requires unchanged context and, for circle mode, numeric adapters"
            old = path / "tradeskill-before.c"
            old.write_text(subprocess.check_output([
                "git", "show", f"{revision}:src/economy/tradeskill.c"], cwd=ROOT, text=True))
            function = extract_function(old, "int get_mincircle(int spell)\n{")
            baseline_flags = ["-DVALUE_BASELINE=1"]
            if args.circle_baseline:
                code = code.replace("// BASELINE_CIRCLE", function.replace("get_mincircle(", "get_mincircle_before(", 1))
                baseline_flags += ["-DCIRCLE_BASELINE=1", "-Wl,--wrap=_Z13get_mincirclei"]
            else:
                assert function == extract_function("tradeskill.c", "int get_mincircle(int spell)\n{"), "numeric comparison requires unchanged circle context"
                signature = "int get_ival_from_proc(obj_proc_type proc)\n{"
                old_runtime_flags = []
                if signature in old.read_text():
                    # Price policy moved out of tradeskill.c. Execute the exact
                    # old chain for the old adapter, including its utility sentinel.
                    declarations = (ROOT / "src/item/item_value_procs.c").read_text().split(
                        "static const item_value_proc_entry entries[]", 1)[0]
                    code += "\n" + declarations + "\n" + extract_function(old, signature).replace(
                        "get_ival_from_proc(", "get_ival_from_proc_before(", 1)
                    old_runtime_flags += ["-Dget_ival_from_proc=get_ival_from_proc_before"]
                else:
                    old_procs = path / "item_value_procs_before.c"
                    old_procs.write_text(subprocess.check_output(
                        ["git", "show", f"{revision}:src/item/item_value_procs.c"], cwd=ROOT, text=True))
                    old_procs_object = path / "item_value_procs_before.o"
                    subprocess.run(["g++", "-std=c++20", "-g", "-Isrc",
                        "-Ditem_value_proc=item_value_proc_before",
                        "-Ditem_value_proc_entries=item_value_proc_entries_before", "-c", str(old_procs),
                        "-o", str(old_procs_object)], cwd=ROOT, check=True)
                    objects.append(str(old_procs_object))
                    old_runtime_flags += ["-Ditem_value_proc=item_value_proc_before"]
                old_header = subprocess.check_output(["git", "show", f"{revision}:src/item/item_value.h"], cwd=ROOT, text=True)
                current_header = (ROOT / "src/item/item_value.h").read_text()
                fields = lambda text, name: re.search(r"struct " + name + r"\n\{(.*?)\n\};", text, re.S).group(1)
                for name in ("item_value_apply", "item_value_input"):
                    assert fields(old_header, name) == fields(current_header, name), "comparison requires unchanged stored inputs"
                # Old sources compile against the current header. Existing context
                # fields keep their meaning; appended policy fields default safely.
                assert fields(current_header, "item_value_context").startswith(fields(old_header, "item_value_context")), "comparison requires unchanged baseline context fields"
                old_header_path = path / "item_value_before.h"
                old_header_path.write_text(old_header)
                signature = "template <typename Object> void normalize_item_value_fields("
                assert extract_function(old_header_path, signature) == extract_function(ROOT / "src/item/item_value.h", signature), "comparison requires unchanged constructor normalization"
                old_numeric = path / "item_value_before.c"
                old_numeric.write_text(subprocess.check_output(["git", "show", f"{revision}:src/item/item_value.c"], cwd=ROOT, text=True))
                signature = "bool item_value_has_packed_proc("
                old_object = path / "item_value_before.o"
                subprocess.run(["g++", "-std=c++20", "-g", "-Isrc", "-Devaluate_item_value=evaluate_item_value_before",
                                "-Ditem_value_has_packed_proc=item_value_has_packed_proc_before",
                                "-Ditem_value_material_quantities=item_value_material_quantities_before",
                                "-Ditem_value_packed_cast_mask=item_value_packed_cast_mask_before",
                                "-Ditem_value_proc_policy_name=item_value_proc_policy_name_before", "-c", str(old_numeric),
                                "-o", str(old_object)], cwd=ROOT, check=True)
                objects.append(str(old_object))
                old_runtime = path / "item_value_runtime_before.c"
                old_runtime.write_text(subprocess.check_output(["git", "show", f"{revision}:src/item/item_value_runtime.c"], cwd=ROOT, text=True))
                old_runtime_object = path / "item_value_runtime_before.o"
                subprocess.run(["g++", "-std=c++20", "-g", "-Isrc", "-Ditemvalue=itemvalue_before",
                                "-Devaluate_item_value=evaluate_item_value_before",
                                "-Ditem_value_has_packed_proc=item_value_has_packed_proc_before",
                                "-Ditem_value_packed_cast_mask=item_value_packed_cast_mask_before",
                                *old_runtime_flags, "-c", str(old_runtime),
                                "-o", str(old_runtime_object)], cwd=ROOT, check=True)
                objects.append(str(old_runtime_object))
                baseline_flags += ["-DNUMERIC_BASELINE=1", "-Wl,--wrap=_Z9itemvalueP8obj_data"]
        source.write_text(code)
        comm = next(item for item in objects if item.endswith("/net/comm.o"))
        renamed = path / "comm.o"
        subprocess.run(["objcopy", "--redefine-sym", "main=duris_server_main", comm, str(renamed)], check=True)
        objects = [str(renamed) if item == comm else item for item in objects]
        subprocess.run([
            "g++", "-std=c++20", "-g", "-DTEST_MUD", "-Isrc", "-I/usr/include/mysql",
            "-I/usr/include/libxml2", str(source), *objects, "-rdynamic",
            "-Wl,--wrap=_Z25persistence_next_item_uidv", "-Wl,--wrap=_Z6numberii",
            *baseline_flags, *libraries, "-o", str(binary),
        ], cwd=ROOT, check=True)
        world = path / "world"
        (world / "areas").mkdir(parents=True)
        (world / "lib").mkdir()
        for name in ("duris.properties", "kingdom.cfg", "item_abilities.json", "random_equipment.cfg", "crafting.cfg", "enhance.cfg"):
            shutil.copyfile(ROOT / "lib" / name, world / "lib" / name)
        shutil.copyfile(ROOT / "areas/AREA", world / "areas/AREA")
        for name in ("obj", "trg", "mob", "wld", "zon"):
            (world / "areas" / name).symlink_to(ROOT / "areas" / name, target_is_directory=True)
            subprocess.run(["make", "-s", "-C", f"areas/src/{name}"], cwd=ROOT, check=True)
            built = subprocess.run([str(ROOT / f"bin/areas/tools/make_{name}")],
                                   cwd=world / "areas", capture_output=True, text=True)
            assert built.returncode == 0, built.stderr
            (world / "areas" / f"tworld.{name}").rename(world / "areas" / f"world.{name}")
        (path / "areas").mkdir()
        for name in ("mob", "wld", "zon"):
            (path / "areas" / f"world.{name}").symlink_to(world / "areas" / f"world.{name}")
        result = subprocess.run([str(binary)], cwd=path, capture_output=True, text=True,
                                timeout=60, env=os.environ)
        print(result.stdout, end="")
        if result.returncode:
            print(result.stderr, end="")
        assert result.returncode == 0, result.returncode

        result = subprocess.run([str(binary), "corpus"], cwd=world, capture_output=True,
                                text=True, timeout=120, env=os.environ)
        print(result.stdout, end="")
        if result.returncode:
            print(result.stderr[-4000:], end="")
        assert result.returncode == 0, result.returncode

        server = ROOT / "bin/server/dms_new"
        output = world / "report"
        command = [str(server), "--material-rarity-report", str(output)]
        result = subprocess.run(command, cwd=world, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr[-5000:]
        expected = {int(vnum): int(score) for vnum, score in
                    csv.reader((world / "reference-scores.csv").open())}
        reported = {}
        with (output / "material-rarity-summary.csv").open() as file:
            headings = next(csv.reader(file))
            assert "total_material_units" in headings and "share_percent" in headings
        exclusion_reasons = set()
        for name in ("recipes", "exclusions"):
            with (output / f"material-rarity-{name}.csv").open() as file:
                for row in csv.DictReader(file):
                    vnum, score = int(row["template_vnum"]), int(row["itemvalue"])
                    assert score == expected[vnum], (vnum, score, expected[vnum])
                    reported[vnum] = score
                    if name == "exclusions":
                        exclusion_reasons.add(row["reason"])
        assert "unmapped-material-family" in exclusion_reasons
        assert reported == expected
        with (output / "item-values.csv").open() as file:
            valuations = list(csv.DictReader(file))
        assert {int(row["template_vnum"]): int(row["itemvalue"]) for row in valuations} == expected
        for row in valuations:
            base = sum(float(row[name]) for name in ("flags_base", "applies_base", "type_base", "packed_base", "native_base"))
            assert abs(base - float(row["base"])) < 1e-6
            assert abs(float(row["base"]) * float(row["multiplier"]) - float(row["unrounded"])) < 1e-6
            assert row["proc_policy"] in ("none", "priced", "utility", "unclassified")
            assert 0 <= int(row["packed_cast_mask"]) <= 7
        provenance = dict(line.split("=", 1) for line in
                          (output / "material-rarity-README.txt").read_text().splitlines()
                          if "=" in line)
        for label, file in (("binary", server), ("objects", world / "areas/world.obj"),
                            ("properties", world / "lib/duris.properties"),
                            ("studio", world / "areas/world.trg"),
                            ("mobiles", world / "areas/world.mob"),
                            ("rooms", world / "areas/world.wld"),
                            ("zones", world / "areas/world.zon"),
                            ("kingdom_config", world / "lib/kingdom.cfg"),
                            ("item_abilities", world / "lib/item_abilities.json")):
            assert provenance[label + "_sha256"] == hashlib.sha256(file.read_bytes()).hexdigest()
        assert provenance["formula_revision"] == "ival-v8-proc-semantics"
        assert provenance["context"] == "configured-healthy-boot"
        assert provenance["mini_mode"] == "0" and provenance["no_specials"] == "0"
        if args.consumer_baseline:
            args.delta_output.mkdir(parents=True, exist_ok=True)
            metrics = json.loads((world / "consumer-metrics.json").read_text())
            metrics.update(baseline_revision=args.consumer_baseline, formula_revision=provenance["formula_revision"],
                           cache_state="prewarmed by constructor/template parity", provenance=provenance)
            (args.delta_output / "consumer-metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
        elif args.delta_output:
            args.delta_output.mkdir(parents=True, exist_ok=True)
            with (world / "value-deltas.csv").open() as file:
                reader = csv.DictReader(file)
                columns = reader.fieldnames
                rows = list(reader)
            assert all(None not in row and all(value is not None for value in row.values()) for row in rows)
            changed = [row for row in rows if row["before"] != row["after"]]
            with (args.delta_output / "changed-values.csv").open("w", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=columns)
                writer.writeheader()
                writer.writerows(changed)
            shutil.copyfile(world / "changed-circles.csv", args.delta_output / "changed-circles.csv")
            shutil.copyfile(world / "generator-circles.csv", args.delta_output / "generator-circles.csv")
            shutil.copyfile(world / "quest-weight-deltas.csv", args.delta_output / "quest-weight-deltas.csv")
            settings = json.loads((world / "consumer-settings.json").read_text())
            with (world / "quest-weight-deltas.csv").open() as file:
                quest_rows = list(csv.DictReader(file))
            effects = consumer_effects(rows, settings, quest_rows)
            (args.delta_output / "consumer-effects.json").write_text(json.dumps(effects, indent=2) + "\n")
            summary = {
                "baseline_revision": revision,
                "circle_functions_sha256": {
                    "before": hashlib.sha256(function.encode()).hexdigest(),
                    "after": hashlib.sha256(extract_function(
                        "tradeskill.c", "int get_mincircle(int spell)\n{").encode()).hexdigest(),
                },
                "formula_revision": provenance["formula_revision"],
                "comparison": "circle context" if args.circle_baseline else "numeric evaluator and runtime adapter",
                "consumer_settings": settings,
                "consumer_config_sha256": {name: hashlib.sha256((world / "lib" / name).read_bytes()).hexdigest()
                                           for name in ("crafting.cfg", "enhance.cfg", "random_equipment.cfg")},
                "provenance": provenance,
                "compared": {kind: sum(row["cohort"] == kind for row in rows)
                             for kind in ("template", "generated")},
                "changed": {kind: sum(row["cohort"] == kind for row in changed)
                            for kind in ("template", "generated")},
                "generated_seeds": "seed=1..16; source_level=1,20,40,60,62; every native slot; finder_level=56/luck=160",
                "observed_ranges": {kind: {
                    "score": [min(int(r["after"]) for r in rows if r["cohort"] == kind),
                              max(int(r["after"]) for r in rows if r["cohort"] == kind)],
                    "unavailable_scores": sum(int(r["after"]) < 1 for r in rows if r["cohort"] == kind),
                    "unrepresentable_craft_xp": sum(int(r["craft_xp_after"]) > 2**31 - 1 for r in rows if r["cohort"] == kind),
                    "craft_xp_overflow_within_mortal_level_gate": sum(int(r["craft_xp_after"]) > 2**31 - 1 and
                        int(r["craft_min_level_after"]) <= settings["max_mortal_level"] for r in rows if r["cohort"] == kind),
                    "max_weapon_dice_count": max(int(r["weapon_dice_count"]) for r in rows if r["cohort"] == kind),
                    "max_weapon_dice_sides": max(int(r["weapon_dice_sides"]) for r in rows if r["cohort"] == kind),
                    "apply_modifier": [min(int(r[f"modifier{i}"]) for r in rows if r["cohort"] == kind for i in range(4)),
                                       max(int(r[f"modifier{i}"]) for r in rows if r["cohort"] == kind for i in range(4))],
                } for kind in ("template", "generated")},
                "score_derived_consumer_effects": {
                    "status": "none in measured cohorts" if not changed else "direct effects recorded in consumer-effects.json",
                    "families": ["salvage quality/breakage", "craft/forge level/recipe/material/XP",
                                 "enhancement source/donor/result/price", "quest floors/zone weights",
                                 "faerie bag 25/50/125"],
                    "basis": "Under fixed current consumer rules/configuration, equal scores imply no score-derived threshold, material, XP or currency delta"
                             if not changed else "Native consumer plans/filters plus their configured score boundaries; see explicit qualification limits",
                },
            }
            if args.numeric_baseline:
                summary["runtime_adapter_sha256"] = {
                    "before": hashlib.sha256(old_runtime.read_bytes()).hexdigest(),
                    "after": hashlib.sha256((ROOT / "src/item/item_value_runtime.c").read_bytes()).hexdigest(),
                }
                summary["evaluator_functions_sha256"] = {
                    "before": hashlib.sha256(extract_function(old_numeric, "int evaluate_item_value(").encode()).hexdigest(),
                    "after": hashlib.sha256(extract_function("item_value.c", "int evaluate_item_value(").encode()).hexdigest(),
                }
            (args.delta_output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
            print("native value deltas:", summary["compared"], summary["changed"], flush=True)
        (world / "areas_mini").symlink_to(ROOT / "areas_mini", target_is_directory=True)
        for flag, mode, specials in (("-s", "0", "1"), ("--minimal", "1", "0")):
            target = world / ("report" + flag)
            result = subprocess.run([str(server), flag, "--material-rarity-report", str(target)],
                                    cwd=world, capture_output=True, text=True, timeout=60)
            assert result.returncode == 0, result.stderr[-5000:]
            metadata = (target / "material-rarity-README.txt").read_text()
            assert f"mini_mode={mode}\n" in metadata and f"no_specials={specials}\n" in metadata
        properties = world / "lib/duris.properties"
        valid_properties = properties.read_bytes()
        report_hashes = {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in output.iterdir()}
        for invalid in ("32768", "nan", "100junk"):
            properties.write_text(f"stats.str.Human={invalid}\n")
            result = subprocess.run(command, cwd=world, capture_output=True, text=True, timeout=60)
            assert result.returncode == 1 and "valuation properties could not be loaded" in result.stderr
            assert report_hashes == {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in output.iterdir()}
        properties.write_bytes(valid_properties)
        properties.unlink()
        result = subprocess.run(command, cwd=world, capture_output=True, text=True, timeout=60)
        assert result.returncode == 1 and "valuation properties could not be loaded" in result.stderr
        print("offline CLI: all effective-world scores match real constructors; provenance and missing-context failure passed")


if __name__ == "__main__":
    main()
