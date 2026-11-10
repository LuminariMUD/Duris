#!/usr/bin/env python3
"""Run the native enhancement paths with controlled inventory, loads and RNG."""

import subprocess
import tempfile
import shutil
from pathlib import Path

from _paths import HARNESS_STUBS, ROOT, source, extract_function


HARNESS = r"""
#include <cassert>
#include <map>
#include <string>
#include <unordered_set>
#include <vector>
#include <limits>
#include <cstdarg>
#include <cstdio>
#include <fstream>
#include <filesystem>

#include "core/utility.h"
#include "item/enhance.c"
#include "item/item_value_procs.h"

static index_data indices[12]{};
index_data *obj_index = indices;
index_data *mob_index = indices;
int top_of_objt = static_cast<int>(std::size(indices)) - 1;
P_room world = nullptr;
struct zone_data *zone_table = nullptr;
int top_of_zone_table = -1;

static obj_data prototypes[12]{};
static object_template metadata[12];
static int missing_template_vnum;
static bool fail_next_allocation;
extern "C" void *__real__Znwm(size_t);
extern "C" void *__wrap__Znwm(size_t size) {
    if(fail_next_allocation) { fail_next_allocation=false; throw std::bad_alloc(); }
    return __real__Znwm(size);
}
const object_template *find_object_template(int vnum) {
    if(vnum<=0 || vnum==missing_template_vnum) return nullptr;
    for(size_t slot=0;slot<std::size(prototypes);++slot) if(indices[slot].virtual_number==vnum) {
        const auto &object=prototypes[slot]; auto &result=metadata[slot];
        result.R_num=object.R_num;
        result.type=object.type;
        result.material=object.material;
        result.craftsmanship=object.craftsmanship;
        result.extra_flags=object.extra_flags;
        result.wear_flags=object.wear_flags;
        result.extra2_flags=object.extra2_flags;
        result.anti_flags=object.anti_flags;
        result.anti2_flags=object.anti2_flags;
        result.weight=object.weight;
        result.cost=object.cost;
        result.condition=object.condition;
        result.bitvector=object.bitvector;
        result.bitvector2=object.bitvector2;
        result.bitvector3=object.bitvector3;
        result.bitvector4=object.bitvector4;
        result.bitvector5=object.bitvector5;
        std::copy(std::begin(object.value),std::end(object.value),std::begin(result.value));
        std::copy(std::begin(object.affected),std::end(object.affected),std::begin(result.affected));
        result.name=object.name; result.short_description=object.short_description;
        return &result;
    }
    return nullptr;
}
bool cache_object_template(int vnum) { return !vnum || find_object_template(vnum); }
int strn_cmp(const char *,const char *,unsigned int) { assert(false); return 0; }
bool valid_object_proclib(const char *,const char *) { assert(false); return false; }
int item_switch(P_obj,P_char,int,char *) { assert(false); return 0; }

static std::unordered_set<P_obj> temporary;
static std::vector<int> loads;
static std::vector<int> extracted;
static P_obj result;
static P_obj active_pouch;
static bool lucky;
static bool refuse_delivery;
static bool refuse_wallet_submit;
static bool refuse_wallet_commit;
static bool refuse_pouch_write;
static int unavailable_vnum;
static int charges;
static int rolls;
static std::vector<std::string> config_logs;
static std::string output;
static std::string keywords;
static std::string description;
static std::map<int, int> materials;
static int pouch_usage;

static std::vector<std::string> removal_causes;
item_removal_location capture_item_removal(P_obj obj)
{
    return {.vnum = OBJ_VNUM(obj)};
}

void audit_item_removal(const char *cause, const item_removal_location &,
                        const item_removal_location &, int)
{
    removal_causes.emplace_back(cause);
}

extern const struct stat_data stat_factor[LAST_RACE + 1] = {};
int get_mincircle(int spell) {
    if (!spell) return 0;
    assert(spell == 32 || spell == 33);
    return spell == 32 ? 1 : 2;
}
static obj_proc_type previous_proc;
obj_proc_type proclib_chain_incumbent(int) { return previous_proc; }
int proclib_obj_cmd_bridge(P_obj,P_char,int,char*) { assert(false); return 0; }
bool native_artifact_configured_owner(int) { return false; }
Skill skills[MAX_AFFECT_TYPES + 1];
static void fixture_spell(int,P_char,char*,int,P_char,P_obj) { assert(false); }
static const bool prepared_spells = [] { for (int id : {32,33,37}) skills[id].spell_pointer=fixture_spell; return true; }();
item_value_proc_entry item_value_proc(obj_proc_type proc) { assert(!proc); return {nullptr, "none", 0, item_value_proc_policy::none}; }
int number(int low, int high) { ++rolls; return lucky ? low : high; }
void logit(const char *, const char *format, ...) {
    char buffer[2048]; va_list args; va_start(args, format);
    std::vsnprintf(buffer, sizeof(buffer), format, args); va_end(args);
    config_logs.emplace_back(buffer);
}
bool chaos_starter_materials_enabled() { return true; }
P_obj chaos_material_pouch_find(P_char) { return active_pouch; }
void set_obj_extra_flags(P_obj obj, unsigned flags) { obj->extra_flags = flags; }

bool currency_transaction_submit(P_char ch, const currency_vector &wallet, const currency_vector &,
                                 currency_reason_type reason, int64_t, critical_source_site,
                                 critical_deadline_class, currency_completion_fn complete,
                                 const void *context, size_t context_size)
{
    if (refuse_wallet_submit)
        return false;
    if (!refuse_wallet_commit)
    {
        for (size_t i = 0; i < wallet.amount.size(); ++i)
        {
            const int64_t amount = ch->points.cash[i] + wallet.amount[i];
            assert(amount >= 0 && amount <= INT_MAX);
            ch->points.cash[i] = static_cast<int>(amount);
        }
        if (reason == currency_reason_type::wallet_spend)
            ++charges;
    }
    complete(ch, !refuse_wallet_commit, {}, 0, static_cast<const uint8_t *>(context), context_size);
    return true;
}

P_obj read_object(int vnum, int mode)
{
    assert(mode == VIRTUAL);
    loads.push_back(vnum);
    if (!vnum || vnum == unavailable_vnum)
        return nullptr;
    for (size_t slot = 0; slot < std::size(prototypes); ++slot)
        if (indices[slot].virtual_number == vnum)
        {
            auto obj = new obj_data(prototypes[slot]);
            temporary.insert(obj);
            return obj;
        }
    return nullptr;
}

void obj_from_char(P_obj obj)
{
    assert(obj->loc_p == LOC_CARRIED);
    obj->loc_p = LOC_NOWHERE;
}

void extract_obj(P_obj obj, int)
{
    extracted.push_back(OBJ_VNUM(obj));
    if (result == obj)
        result = nullptr;
    if (temporary.erase(obj))
        delete obj;
}

bool obj_to_char(P_obj obj, P_char)
{
    if (refuse_delivery)
    {
        extract_obj(obj);
        return false;
    }
    result = obj;
    return true;
}

void send_to_char(const char *message, P_char) { output += message; }
bool isname(const char *name, const char *keywords) { return !strcmp(name, keywords); }

P_obj get_obj_in_list_vis(P_char, const char *name, P_obj list, bool)
{
    for (auto obj = list; obj; obj = obj->next_content)
        if (isname(name, obj->name))
            return obj;
    return nullptr;
}

void half_chop(char *input, char *word, char *rest)
{
    while (*input == ' ')
        ++input;
    while (*input && *input != ' ')
        *word++ = *input++;
    *word = '\0';
    while (*input == ' ')
        ++input;
    memmove(rest, input, strlen(input) + 1);
}

void set_keywords(P_obj obj, const char *name)
{
    keywords = name;
    obj->name = keywords.data();
}

void set_short_description(P_obj obj, const char *text)
{
    description = text;
    obj->short_description = description.data();
}

void describe_encrusted_enhanced(P_obj) { std::abort(); }

int vnum_in_inv(P_char, int vnum)
{
    const auto entry = materials.find(vnum);
    return entry == materials.end() ? 0 : entry->second;
}

void vnum_from_inv(P_char, int vnum, int count)
{
    assert(materials[vnum] >= count);
    materials[vnum] -= count;
}

bool chaos_material_pouch_can_record_generated(P_char, const chaos_material_pouch_usage *, size_t)
{
    return true;
}

bool chaos_material_pouch_record_generated(P_char, const chaos_material_pouch_usage *usage,
                                           size_t count)
{
    if (refuse_pouch_write)
        return false;
    for (size_t i = 0; i < count; ++i)
        pouch_usage += usage[i].count;
    return true;
}

void chaos_material_pouch_report_generated_failure(P_char, const char *)
{
    output += "ledger write failed";
}

static obj_data &fixture(int slot, int vnum, int ac = 0)
{
    auto &obj = prototypes[slot];
    obj = {};
    obj.R_num = slot;
    indices[slot].virtual_number = vnum;
    obj.wear_flags = ITEM_TAKE | ITEM_HOLD | ITEM_WEAR_ARMS;
    obj.type = ac ? ITEM_ARMOR : ITEM_WORN;
    static char fixture_name[] = "fixture";
    static char fixture_description[] = "a fixture";
    obj.name = fixture_name;
    obj.short_description = fixture_description;
    obj.value[0] = ac;
    obj.loc_p = LOC_CARRIED;
    return obj;
}

static void index_entry(enhance_index_entry &entry, int vnum, int value)
{
    auto &bucket = enhance_ival_table[enhance_hash(value)];
    entry.vnum = vnum;
    entry.ival = value;
    entry.wear_flags = ITEM_WEAR_ARMS;
    entry.next = bucket;
    bucket = &entry;
}

static void clear_attempt()
{
    if (result)
        extract_obj(result);
    assert(temporary.empty());
    result = nullptr;
    removal_causes.clear();
    loads.clear();
    extracted.clear();
    charges = 0;
    output.clear();
}

static void test_minimal_world_essence_command()
{
    assert(!enhancement_system_is_ready()); // Optional index was never booted.
    char_data ch{};
    ch.in_room = NOWHERE;
    GET_PLATINUM(&ch) = 10;
    auto &source = fixture(0, 90010);
    source.name = const_cast<char *>("target");
    source.affected[0] = {APPLY_MANA, 25};
    auto &essence = fixture(1, 400254);
    essence.name = const_cast<char *>("essence");
    source.next_content = &essence;
    ch.carrying = &source;
    char command[] = "target essence";
    do_enhance(&ch, command, 0);
    assert(source.affected[2].location == APPLY_HIT && source.affected[2].modifier == 3);
    assert(essence.loc_p == LOC_NOWHERE && charges == 1 && GET_MONEY(&ch) == 9000);
    assert(loads.empty());
    clear_attempt();
}

static void test_donor_floor()
{
    for (bool insignia : {false, true}) for (int offset : {-1, 0}) {
        for (auto &bucket : enhance_ival_table) bucket = nullptr;
        char_data ch{};
        ch.player.level = 60;
        ch.curr_stats.Luk = 10;
        ch.in_room = NOWHERE;
        GET_PLATINUM(&ch) = 20;
        auto &source = fixture(0, 90010);
        source.affected[0] = {APPLY_MANA, 20};
        if (insignia) source.wear_flags |= ITEM_GUILD_INSIGNIA;
        const int source_value = insignia ? 30 : 20;
        assert(itemvalue(&source) == source_value);
        const int floor = source_value - enhance_material_ival_delta +
            (insignia ? enhance_guild_insignia_ival_bonus : 0);
        auto &donor = fixture(1, 90011);
        const int donor_value = floor + offset;
        donor.affected[0] = {APPLY_MANA, static_cast<signed char>(donor_value / 2)};
        donor.affected[1] = {APPLY_MOVE, static_cast<signed char>(donor_value - donor_value / 2)};
        assert(itemvalue(&donor) == donor_value);
        auto &target = fixture(2, 90012);
        target.affected[0] = {APPLY_MANA, static_cast<signed char>((source_value + 1) / 2)};
        target.affected[1] = {APPLY_MOVE, static_cast<signed char>(source_value + 1 - (source_value + 1) / 2)};
        assert(itemvalue(&target) == source_value + 1);
        enhance_index_entry entry{};
        index_entry(entry, OBJ_VNUM(&target), source_value + 1);
        const auto original_source = source, original_donor = donor;
        const int before_rolls = rolls;
        enhance(&ch, &source, &donor);
        if (offset < 0) {
            assert(output.find("requires an item") != std::string::npos);
            assert(!std::memcmp(&source, &original_source, sizeof(source)));
            assert(!std::memcmp(&donor, &original_donor, sizeof(donor)));
            assert(!result && charges == 0 && GET_MONEY(&ch) == 20000);
            assert(rolls == before_rolls && loads.empty() && extracted.empty());
        } else {
            assert(result && itemvalue(result) == source_value + 1);
            assert(charges == 1 && GET_MONEY(&ch) ==
                20000 - (source_value <= enhance_cost_low_ival_threshold ?
                    enhance_cost_low_amount : enhance_cost_high_amount));
            assert((extracted == std::vector<int>{90010, 90011}));
        }
        clear_attempt();
    }
    for (auto &bucket : enhance_ival_table) bucket = nullptr;
}

static void test_replacement()
{
    // Normalized records from tezcat.obj (98963) and alatorin.obj (83277, 83202).
    auto &source = fixture(0, 98963, 8);
    source.extra_flags = 8192;
    source.extra2_flags = 16641;
    source.affected[0] = {APPLY_SAVING_SPELL, -3};
    source.affected[1] = {APPLY_MANA, 33};
    auto &lower = fixture(1, 83277, 10);
    lower.extra2_flags = 257;
    lower.affected[0] = {APPLY_DAMROLL, 4};
    lower.affected[1] = {APPLY_MOVE_REG, 3};
    auto &higher = fixture(2, 83202, 25);
    higher.extra_flags = 512;
    higher.extra2_flags = 257;
    higher.affected[0] = {APPLY_SAVING_SPELL, -4};
    higher.affected[1] = {APPLY_SAVING_PARA, -3};
    auto &equal = fixture(3, 90000);
    equal = source;
    equal.R_num = 3;
    auto &donor = fixture(4, 90001);
    donor = lower;
    donor.R_num = 4;
    auto &wrong_slot = fixture(5, 90002);
    wrong_slot = higher;
    wrong_slot.R_num = 5;
    wrong_slot.wear_flags = ITEM_TAKE | ITEM_HOLD | ITEM_WEAR_LEGS;

    auto &over_cap = fixture(7, 90004, 80);
    assert(itemvalue(&over_cap) > 88 + enhance_ival_gain_extreme); // Above the source's gain limit.
    assert(itemvalue(&source) == 88);
    assert(itemvalue(&lower) == 87);
    assert(itemvalue(&higher) == 91);
    assert(itemvalue(&equal) == 88);
    char_data ch{};
    ch.player.level = 60;
    ch.curr_stats.Luk = 10;
    ch.in_room = NOWHERE;

    enhance_index_entry low_entry{}, equal_entry{}, high_entry{};
    index_entry(low_entry, 83277, 87);
    index_entry(equal_entry, 90000, 88);
    index_entry(high_entry, 83202, 91);
    const int threshold = enhance_cost_low_ival_threshold;
    const int low_cost = enhance_cost_low_amount, high_cost = enhance_cost_high_amount;
    for (bool cheap : {true, false}) {
        const int fee = cheap ? 123 : 1123;
        enhance_cost_low_ival_threshold = cheap ? 88 : threshold;
        enhance_cost_low_amount = enhance_cost_high_amount = fee;
        GET_PLATINUM(&ch) = GET_GOLD(&ch) = GET_SILVER(&ch) = GET_COPPER(&ch) = 0;
        source.loc_p = donor.loc_p = LOC_CARRIED;
        const int before_rolls = rolls;
        enhance(&ch, &source, &donor);
        const char *coins = cheap ? "1 &+Ygold&N, 2 silver, and 3 &+ycopper&N" :
            "1 &+Wplatinum&N, 1 &+Ygold&N, 2 silver, and 3 &+ycopper&N";
        assert(output.find(coins) != std::string::npos);
        assert(charges == 0 && GET_MONEY(&ch) == 0 && rolls == before_rolls);
        assert(loads.empty() && extracted.empty() && !result);
        assert(source.loc_p == LOC_CARRIED && donor.loc_p == LOC_CARRIED);
        clear_attempt();
        GET_PLATINUM(&ch) = 20;
        enhance(&ch, &source, &donor);
        assert(result && OBJ_VNUM(result) == 83202);
        assert(charges == 1 && GET_MONEY(&ch) == 20000 - fee);
        clear_attempt();
    }
    enhance_cost_low_ival_threshold = threshold;
    enhance_cost_low_amount = low_cost;
    enhance_cost_high_amount = high_cost;
    GET_GOLD(&ch) = GET_SILVER(&ch) = GET_COPPER(&ch) = 0;
    for (bool down_first : {true, false})
        for (bool force_luck : {false, true})
        {
            enhance_original_cascade_down_first = down_first;
            lucky = force_luck;
            GET_PLATINUM(&ch) = 20;
            source.loc_p = donor.loc_p = LOC_CARRIED;
            enhance(&ch, &source, &donor);
            assert(result && OBJ_VNUM(result) == 83202 && itemvalue(result) == 91);
            assert((loads == std::vector<int>{83202}));
            assert((extracted == std::vector<int>{98963, 90001}));
            assert(charges == 1 && GET_PLATINUM(&ch) == 10);
            clear_attempt();
        }
    lucky = false;
    enhance_original_cascade_down_first = true;

    // Failed loads, changed wear and stale high-valued index entries in one bucket.
    enhance_index_entry stale_lower{}, stale_equal{}, stale_wear{}, stale_cap{}, missing{};
    enhance_index_entry same_bucket{};
    index_entry(same_bucket, 83202, 89);
    index_entry(stale_lower, 83277, 89);
    index_entry(stale_equal, 90000, 89);
    index_entry(stale_wear, 90002, 89);
    index_entry(stale_cap, 90004, 89);
    index_entry(missing, 90003, 89);
    GET_PLATINUM(&ch) = 20;
    source.loc_p = donor.loc_p = LOC_CARRIED;
    enhance(&ch, &source, &donor);
    assert((removal_causes == std::vector<std::string>{"enhance_replacement", "enhance_donor"}));
    assert(result && OBJ_VNUM(result) == 83202);
    assert((loads == std::vector<int>{83202}));
    assert((extracted == std::vector<int>{98963, 90001}));
    assert(charges == 1 && GET_PLATINUM(&ch) == 10);
    clear_attempt();

    enhance_ival_table[enhance_hash(89)] = nullptr;
    GET_PLATINUM(&ch) = 20;
    source.loc_p = donor.loc_p = LOC_CARRIED;
    refuse_delivery = true;
    enhance(&ch, &source, &donor);
    assert(!result && charges == 0 && GET_PLATINUM(&ch) == 20);
    assert((extracted == std::vector<int>{83202}));
    assert(source.loc_p == LOC_CARRIED && donor.loc_p == LOC_CARRIED);
    clear_attempt();
    refuse_delivery = false;

    for (bool *refusal : {&refuse_wallet_submit, &refuse_wallet_commit})
    {
        *refusal = true;
        enhance(&ch, &source, &donor);
        assert(!result && charges == 0 && GET_MONEY(&ch) == 20000);
        assert(removal_causes.empty());
        assert((extracted == std::vector<int>{83202}));
        assert(source.loc_p == LOC_CARRIED && donor.loc_p == LOC_CARRIED);
        clear_attempt();
        *refusal = false;
    }

    // No upgrade with a physical donor, then with an empty pool and a Chaos pouch.
    enhance_ival_table[enhance_hash(91)] = nullptr;
    enhance(&ch, &source, &donor);
    assert(!result && loads.empty() && extracted.empty());
    assert(charges == 0 && GET_PLATINUM(&ch) == 20);
    assert(source.loc_p == LOC_CARRIED && donor.loc_p == LOC_CARRIED);
    enhance_ival_table[enhance_hash(87)] = nullptr;
    enhance_ival_table[enhance_hash(88)] = nullptr;
    auto &pouch = fixture(6, VOBJ_CHAOS_CRAFT_POUCH);
    active_pouch = &pouch;
    enhance(&ch, &source, &pouch);
    assert(!result && loads.empty() && extracted.empty());
    assert(charges == 0 && GET_PLATINUM(&ch) == 20);
    assert(source.loc_p == LOC_CARRIED && donor.loc_p == LOC_CARRIED);
    clear_attempt();
    active_pouch = nullptr;
}

static obj_data &valued(int slot, int vnum, int target)
{
    auto &obj = fixture(slot, vnum);
    for (int hit = 0; hit <= 200; ++hit)
        for (int move = 0; move <= 40; ++move)
        {
            obj.affected[0] = {APPLY_HIT, static_cast<sbyte>(hit)};
            obj.affected[1] = {APPLY_MOVE, static_cast<sbyte>(move)};
            if (itemvalue(&obj) == target)
                return obj;
        }
    assert(!"no fixture reaches the requested item value");
    return obj;
}

// The level gate is the only ceiling: a source at 99 upgrades, by at most the largest luck gain.
static void test_level_gate_is_the_ceiling()
{
    for (auto &bucket : enhance_ival_table) bucket = nullptr;
    auto &source = valued(0, 91000, 99);
    auto &donor = valued(1, 91001, 94);
    valued(2, 91002, 102);
    valued(3, 91003, 104);
    enhance_index_entry within{}, beyond{};
    index_entry(beyond, 91003, 104);
    char_data ch{};
    ch.player.level = 33;
    ch.curr_stats.Luk = 10;
    ch.in_room = NOWHERE;
    source.name = const_cast<char *>("upgrade");
    donor.name = const_cast<char *>("donor");
    source.next_content = &donor;
    ch.carrying = &source;
    for (bool force_luck : {false, true})
    {
        lucky = force_luck;
        GET_PLATINUM(&ch) = 20;
        source.loc_p = donor.loc_p = LOC_CARRIED;
        enhance(&ch, &source, &donor);
        assert(!result && loads.empty() && extracted.empty() && charges == 0);
        clear_attempt();
    }
    index_entry(within, 91002, 102);
    for (bool force_luck : {false, true})
    {
        lucky = force_luck;
        GET_PLATINUM(&ch) = 20;
        source.loc_p = donor.loc_p = LOC_CARRIED;
        char command[] = "upgrade donor";
        do_enhance(&ch, command, 0);
        assert(result && OBJ_VNUM(result) == 91002 && itemvalue(result) == 102);
        assert((extracted == std::vector<int>{91000, 91001}) && charges == 1);
        clear_attempt();
    }
    lucky = false;
    ch.player.level = 32;
    GET_PLATINUM(&ch) = 20;
    source.loc_p = donor.loc_p = LOC_CARRIED;
    enhance(&ch, &source, &donor);
    assert(!result && loads.empty() && charges == 0);
    assert(output.find("up to ival 96") != std::string::npos);
    clear_attempt();
    for (auto &bucket : enhance_ival_table) bucket = nullptr;

    // Above 99, the same bound follows configured gains and the pouch exception.
    const int previous_gain = enhance_ival_gain_normal;
    for (int gain : {4, 9}) {
        enhance_ival_gain_normal = gain;
        valued(0, 91000, 120);
        valued(1, 91001, 115);
        valued(2, 91002, 120 + gain);
        valued(3, 91003, 121 + gain);
        enhance_index_entry valid{}, excessive{};
        index_entry(excessive, 91003, 121 + gain);
        ch.player.level = 40;
        GET_PLATINUM(&ch) = 20;
        enhance(&ch, &source, &donor);
        assert(!result && loads.empty() && extracted.empty() && charges == 0);
        assert(GET_MONEY(&ch) == 20000 && source.loc_p == LOC_CARRIED && donor.loc_p == LOC_CARRIED);
        clear_attempt();
        index_entry(valid, 91002, 120 + gain);
        for (bool pouch : {false, true}) {
            source.loc_p = donor.loc_p = LOC_CARRIED;
            GET_PLATINUM(&ch) = 20;
            active_pouch = pouch ? &fixture(6, VOBJ_CHAOS_CRAFT_POUCH) : nullptr;
            enhance(&ch, &source, pouch ? active_pouch : &donor);
            assert(result && itemvalue(result) == 120 + gain);
            assert(charges == 1 && GET_MONEY(&ch) == 10000);
            assert(extracted == (pouch ? std::vector<int>{91000} : std::vector<int>{91000, 91001}));
            clear_attempt();
            active_pouch = nullptr;
        }
        for (auto &bucket : enhance_ival_table) bucket = nullptr;
    }
    enhance_ival_gain_normal = previous_gain;
}

static void test_essence()
{
    char_data ch{};
    ch.in_room = NOWHERE;
    GET_PLATINUM(&ch) = 10;
    auto &base = fixture(0, 90010);
    auto source = base;
    auto &health = fixture(1, 400254);
    auto &endurance = fixture(2, 400258);
    source.affected[0] = {APPLY_STR, 1};
    source.affected[2] = {APPLY_DAMROLL, 3};
    assert(itemvalue(&source) == 40);
    modenhance(&ch, &source, &health);
    assert(source.affected[2].location == APPLY_DAMROLL && source.affected[2].modifier == 3);
    assert(source.extra2_flags == 0 && source.name == base.name);
    assert(health.loc_p == LOC_CARRIED && loads.empty() && extracted.empty());
    assert(charges == 0 && GET_MONEY(&ch) == 10000);

    source = base;
    source.affected[2] = {APPLY_INT, 1};
    auto overwritten = source;
    overwritten.affected[2] = {APPLY_HIT, 3};
    assert(itemvalue(&overwritten) > itemvalue(&source));
    modenhance(&ch, &source, &health);
    assert(source.affected[2].location == APPLY_INT && source.affected[2].modifier == 1);
    assert(output.find("no free slot") != std::string::npos);
    assert(source.extra2_flags == 0 && health.loc_p == LOC_CARRIED);
    assert(charges == 0 && GET_MONEY(&ch) == 10000);

    // Raw valuation increases from 5 * .8032 to 6 * .8032; both truncate to 4.
    source = base;
    source.extra_flags = ITEM_TWOHANDS;
    source.affected[0] = {APPLY_AC, -2};
    source.affected[2] = {APPLY_HIT_REG, 2};
    source.extra2_flags = ITEM2_ENHANCED;
    assert(itemvalue(&source) == 4);
    modenhance(&ch, &source, &endurance);
    assert(source.affected[2].location == APPLY_HIT_REG && source.affected[2].modifier == 2);
    assert(endurance.loc_p == LOC_CARRIED && loads.empty() && extracted.empty());
    assert(charges == 0 && GET_MONEY(&ch) == 10000);

    source = base;
    missing_template_vnum = OBJ_VNUM(&source);
    modenhance(&ch, &source, &health);
    assert(source.affected[2].location == APPLY_NONE && source.extra2_flags == 0);
    assert(source.name == base.name && extracted.empty());
    assert(health.loc_p == LOC_CARRIED && charges == 0 && GET_MONEY(&ch) == 10000);
    missing_template_vnum = 0;
    clear_attempt();

    // An essence below the arbitrary-donor floor still upgrades valuable gear.
    source.affected[0] = {APPLY_MANA, 25};
    assert(itemvalue(&source) == 25 &&
        itemvalue(&health) < itemvalue(&source) - enhance_material_ival_delta);
    refuse_wallet_commit = true;
    modenhance(&ch, &source, &health);
    assert(source.affected[2].location == APPLY_NONE && source.extra2_flags == 0);
    assert(source.name == base.name && health.loc_p == LOC_CARRIED);
    assert(charges == 0 && GET_MONEY(&ch) == 10000);
    assert(extracted.empty());
    clear_attempt();
    refuse_wallet_commit = false;

    modenhance(&ch, &source, &health);
    assert(source.affected[2].location == APPLY_HIT && source.affected[2].modifier == 3);
    assert(IS_OBJ_STAT2(&source, ITEM2_ENHANCED) && strstr(source.name, "enhanced"));
    assert(health.loc_p == LOC_NOWHERE && charges == 1 && GET_MONEY(&ch) == 9000);
    assert((extracted == std::vector<int>{400254}));
    clear_attempt();

    health.loc_p = LOC_CARRIED;
    source.affected[2].modifier = 9;
    modenhance(&ch, &source, &health);
    assert(source.affected[2].modifier == 9 && health.loc_p == LOC_CARRIED && charges == 0);

    enhance_mod_max_steps = 100;
    source.affected[2].modifier = 126;
    modenhance(&ch, &source, &health);
    assert(source.affected[2].modifier == 126 && health.loc_p == LOC_CARRIED && charges == 0);
    assert(GET_MONEY(&ch) == 9000 && loads.empty() && extracted.empty());
    source.affected[2].modifier = 124;
    modenhance(&ch, &source, &health);
    assert(source.affected[2].modifier == SCHAR_MAX && health.loc_p == LOC_NOWHERE);
    assert(charges == 1 && GET_MONEY(&ch) == 8000);
    clear_attempt();
}

enum class superior_case { ordinary, packed, mixed_applies, zero_modifier, duplicate_applies };
static void test_superior(superior_case probe = superior_case::ordinary)
{
    const bool packed_case = probe == superior_case::packed;
    const bool mixed_case = probe == superior_case::mixed_applies;
    const bool zero_case = probe == superior_case::zero_modifier;
    const bool duplicate_case = probe == superior_case::duplicate_applies;
    pouch_usage = 0;
    char_data ch{};
    ch.player.level = 60;
    ch.in_room = NOWHERE;
    GET_PLATINUM(&ch) = 20;
    char command[] = "fixture";
    char preview[] = "fixture missing";

    // Holy cloth from breale.obj. A WIS tier exists, but -4 DAMROLL keeps iVal at 1.
    auto &base = fixture(0, 2623, 3);
    base.material = MAT_CLOTH;
    base.wear_flags = ITEM_TAKE | ITEM_HOLD | ITEM_WEAR_BODY;
    base.affected[0] = {APPLY_WIS, 2};
    base.affected[1] = {APPLY_DAMROLL, -4};
    auto item = base;
    ch.carrying = &item;
    auto &target = fixture(1, 90020);
    target.material = MAT_CLOTH;
    target.wear_flags = base.wear_flags;
    target.affected[0] = {APPLY_WIS, 3};
    target.affected[1] = {APPLY_STR, 3};
    enhance_index_entry wis{}, str{};
    wis.vnum = OBJ_VNUM(&target);
    wis.ival = itemvalue(&target);
    wis.wear_flags = target.wear_flags;
    wis.apply_loc[0] = APPLY_WIS;
    wis.apply_mod[0] = 3;
    str = wis;
    str.apply_loc[0] = APPLY_STR;
    auto &wrong_slot = fixture(2, 90019);
    wrong_slot.wear_flags = ITEM_TAKE | ITEM_HOLD | ITEM_WEAR_LEGS;
    auto hold_only_match = wis;
    hold_only_match.vnum = OBJ_VNUM(&wrong_slot);
    hold_only_match.wear_flags = wrong_slot.wear_flags;
    hold_only_match.next = &wis;
    enhance_stat_table[enhance_stat_hash(APPLY_WIS)] = &hold_only_match;
    assert(find_stat_enhance_target(&item, APPLY_WIS, 3) == &wis);
    item.wear_flags = ITEM_TAKE | ITEM_HOLD;
    assert(find_stat_enhance_target(&item, APPLY_WIS, 3) == nullptr);
    item.wear_flags = ITEM_TAKE | ITEM_WEAR_BACK;
    assert(find_stat_enhance_target(&item, APPLY_WIS, 3) == nullptr);
    item.wear_flags = base.wear_flags;
    enhance_stat_table[enhance_stat_hash(APPLY_STR)] = &str;

    const int low = get_matstart(&target);
    const int high = low + 4;
    materials = {{low, 20}, {high, 20}};
    const auto initial_materials = materials;
    assert(itemvalue(&item) == 1);
    do_enhance(&ch, preview, 0);
    assert(output.find("No superior enhancement") != std::string::npos);
    clear_attempt();
    active_pouch = &fixture(6, VOBJ_CHAOS_CRAFT_POUCH);
    do_enhance(&ch, command, 0);
    assert(output.find("No superior enhancement") != std::string::npos);
    assert(item.affected[0].modifier == 2 && item.name == base.name);
    assert(item.short_description == base.short_description && pouch_usage == 0);
    assert(charges == 0 && GET_MONEY(&ch) == 20000 && materials == initial_materials);
    active_pouch = nullptr;
    clear_attempt();

    base.affected[1] = {APPLY_STR, 2};
    if (packed_case) {
        base.type = ITEM_WEAPON;
        base.wear_flags |= ITEM_WIELD;
        base.value[0] = WEAPON_LONGSWORD;
        base.value[1] = 2;
        base.value[2] = 2;
        base.value[5] = 1000033032;
        base.value[6] = 60;
        base.value[7] = 30;
    }
    if (mixed_case) {
        base.value[0] = 2;
        base.affected[2] = {APPLY_HITROLL, 3};
        base.affected[3] = {APPLY_STR_MAX, 2};
    }
    if (zero_case) base.affected[2] = {APPLY_HITROLL, 0};
    if (duplicate_case) {
        base.affected[0].location = APPLY_STR;
        target.affected[0]={APPLY_STR,3}; target.affected[1]={APPLY_STR,3};
        str.apply_mod[0]=6; str.ival=wis.ival=itemvalue(&target);
    }
    item = base;
    const int original_value = itemvalue(&item);
    if (packed_case) assert(original_value == 21); // 18 before F02; all charges use this corrected value.
    if (mixed_case) assert(original_value == 76); // 74 before F03.
    if (zero_case) {
        assert(original_value == 12); // 14 before zero-modifier neutrality.
        ch.player.level = 4; // Newly within the source limit 12; execute at this level below.
    }
    if (duplicate_case) assert(original_value == 13); // Split STR +2/+2 previously scored 12.
    if (packed_case || mixed_case || duplicate_case) {
        // Old values passed these limits; corrected ones do not.
        ch.player.level = duplicate_case ? 4 : packed_case ? 6 : 25;
        const auto unchanged = item;
        do_enhance(&ch, command, 0);
        assert(output.find("at your level") != std::string::npos);
        assert(charges == 0 && GET_MONEY(&ch) == 20000 && materials == initial_materials);
        assert(item.affected[0].modifier == 2 && item.affected[1].modifier == 2);
        assert(!std::memcmp(&item, &unchanged, sizeof(item)));
        clear_attempt();
        ch.player.level = 60;
    }
    const int per_ival = enhance_stat_platinum_per_ival;
    enhance_stat_platinum_per_ival = INT_MAX;
    do_enhance(&ch, command, 0);
    assert(output.find("No superior enhancement") != std::string::npos);
    assert(charges == 0 && materials == initial_materials && item.affected[0].modifier == 2);
    clear_attempt();
    enhance_stat_platinum_per_ival = per_ival;

    const double multiplier = enhance_stat_material_quantity_multiplier;
    // Each individual tribute fits in an int; aggregating two identical tributes does not.
    enhance_stat_material_quantity_multiplier = 600000000;
    do_enhance(&ch, command, 0);
    assert(output.find("No superior enhancement") != std::string::npos);
    assert(charges == 0 && materials == initial_materials && item.affected[1].modifier == 2);
    clear_attempt();
    enhance_stat_material_quantity_multiplier = 1e100;
    do_enhance(&ch, command, 0);
    assert(output.find("No superior enhancement") != std::string::npos);
    assert(charges == 0 && materials == initial_materials && item.affected[1].modifier == 2);
    clear_attempt();
    enhance_stat_material_quantity_multiplier = multiplier;

    for (double invalid_scale : {0., -1., std::numeric_limits<double>::infinity(),
                                  std::numeric_limits<double>::quiet_NaN()}) {
        enhance_stat_material_quantity_multiplier = invalid_scale;
        do_enhance(&ch, command, 0);
        assert(output.find("No superior enhancement") != std::string::npos);
        assert(charges == 0 && GET_MONEY(&ch) == 20000 && materials == initial_materials);
        assert(item.affected[0].modifier == 2 && item.affected[1].modifier == 2);
        clear_attempt();
    }
    enhance_stat_material_quantity_multiplier = multiplier;

    materials.clear();
    do_enhance(&ch, command, 0);
    assert(output.find("Materials required for the next enhancement") != std::string::npos);
    assert(charges == 0 && item.affected[0].modifier == 2 && item.affected[1].modifier == 2);
    clear_attempt();

    materials = initial_materials;
    GET_PLATINUM(&ch) = 0;
    do_enhance(&ch, command, 0);
    assert(output.find("It will require") != std::string::npos);
    const int expected_fee = 1000 + original_value * per_ival;
    assert(output.find(coin_stringv(expected_fee)) != std::string::npos);
    if (probe == superior_case::ordinary)
        assert(output.find("2 &+Wplatinum&N, and 2 &+Ygold&N") != std::string::npos);
    assert(charges == 0 && materials == initial_materials && item.affected[0].modifier == 2);
    clear_attempt();

    GET_PLATINUM(&ch) = 20;
    refuse_wallet_commit = true;
    do_enhance(&ch, command, 0);
    assert(charges == 0 && GET_MONEY(&ch) == 20000 && materials == initial_materials);
    assert(item.affected[0].modifier == 2 && item.short_description == base.short_description);
    clear_attempt();
    refuse_wallet_commit = false;

    do_enhance(&ch, command, 0);
    assert(item.affected[0].modifier == 3 && item.affected[1].modifier == 3);
    if (duplicate_case) assert(item.affected[0].location == APPLY_STR && item.affected[1].location == APPLY_STR);
    if (zero_case) assert(item.affected[2].location == APPLY_HITROLL && item.affected[2].modifier == 0);
    assert(itemvalue(&item) > original_value && strstr(item.short_description, "su&+wp"));
    assert(charges == 1 && GET_MONEY(&ch) == 20000 - (1000 + original_value * per_ival));
    assert(materials[low] == 20 - 2 * ((wis.ival + 4) % 5));
    assert(materials[high] == 20 - 2 * ((wis.ival + 4) / 5));
    clear_attempt();

    active_pouch = &prototypes[6];
    item = base;
    materials.clear();
    GET_PLATINUM(&ch) = 20;
    GET_GOLD(&ch) = 25;
    GET_SILVER(&ch) = 11;
    GET_COPPER(&ch) = 40;
    const int original_money = GET_MONEY(&ch);

    refuse_wallet_commit = true;
    do_enhance(&ch, command, 0);
    assert(charges == 0 && GET_MONEY(&ch) == original_money && pouch_usage == 0);
    assert(item.affected[0].modifier == 2 && item.short_description == base.short_description);
    clear_attempt();
    refuse_wallet_commit = false;

    refuse_pouch_write = true;
    do_enhance(&ch, command, 0);
    assert(output.find("ledger write failed") != std::string::npos && pouch_usage == 0);
    assert(GET_PLATINUM(&ch) == 20 && GET_GOLD(&ch) == 25);
    assert(GET_SILVER(&ch) == 11 && GET_COPPER(&ch) == 40);
    assert(item.affected[0].modifier == 2 && item.short_description == base.short_description);
    clear_attempt();
    refuse_pouch_write = false;

    do_enhance(&ch, command, 0);
    assert(item.affected[0].modifier == 3 && item.affected[1].modifier == 3);
    assert(charges == 1 && GET_MONEY(&ch) == original_money - (1000 + original_value * per_ival));
    assert(pouch_usage == 2 * ((wis.ival + 4) % 5 + (wis.ival + 4) / 5));
    assert(materials.empty());
    clear_attempt();
    active_pouch = nullptr;
    enhance_stat_table[enhance_stat_hash(APPLY_WIS)] = nullptr;
    enhance_stat_table[enhance_stat_hash(APPLY_STR)] = nullptr;
}

static bool config_logged(const char *text) {
    for (const auto &line : config_logs) if (line.find(text) != std::string::npos) return true;
    return false;
}
static void config_file(const std::string &text) {
    std::ofstream file("lib/enhance.cfg"); assert(file);
    file << text; file.close(); assert(!file.fail());
    config_logs.clear(); load_enhance_config();
}
static void restore_config() {
    std::filesystem::copy_file("lib/enhance-shipped.cfg", "lib/enhance.cfg", std::filesystem::copy_options::overwrite_existing);
    config_logs.clear(); load_enhance_config();
}
static std::vector<int> config_integers() {
    return {enhance_material_ival_delta, enhance_guild_insignia_ival_bonus,
        enhance_cost_low_ival_threshold, enhance_cost_low_amount, enhance_cost_high_amount,
        enhance_search_vnum_min, enhance_search_vnum_max, enhance_search_max_attempts,
        enhance_wear_skip_mask, enhance_original_max_roll, enhance_original_cascade_down_first,
        enhance_level_gate_multiplier, enhance_mod_max_steps, enhance_luck_extreme_range,
        enhance_luck_very_range, enhance_luck_lucky_range, enhance_ival_gain_extreme,
        enhance_ival_gain_very, enhance_ival_gain_lucky, enhance_ival_gain_normal,
        enhance_stat_enabled, enhance_stat_npc_material_fallback_enabled, enhance_stat_platinum_base,
        enhance_stat_platinum_per_ival, enhance_essence_drop_enabled, enhance_essence_primary_roll_max,
        enhance_essence_max_roll_max, enhance_essence_elite_level_multiplier,
        enhance_essence_minimum_level, enhance_essence_maximum_level};
}
static void test_config()
{
    const auto compiled = config_integers();
    const double cap_default = enhance_stat_cap_multiplier, quantity_default = enhance_stat_material_quantity_multiplier;
    restore_config();
    auto shipped = compiled; shipped[20] = 1;
    assert(config_integers() == shipped && enhance_stat_cap_multiplier == 1.5 && enhance_stat_material_quantity_multiplier == 1);
    assert(config_logs.size() == 1); // Shipped policy has only the successful-load record.
    assert(enhance_allow_mask == 0x3f01ab7e && enhance_allow_mask2 == 0x804b8df && enhance_allow_mask3 == 0xa3e67fe0);
    assert(enhance_allow_mask4 == 0x2737b430 && enhance_allow_mask5 == 0xf4fffff);
    config_file(std::string("[settings]\n# note") + '\0' + "hidden\nenhance.cost.low.amount=7\n");
    assert(enhance_cost_low_amount == 7 && !config_logged("overlong")); // A NUL does not hide the next line.
    restore_config();
    config_file("  [settings] # comment\n"
        "enhance.material.ival.delta=-7\nenhance.guild.insignia.ival.bonus=-3\n"
        "enhance.cost.low.ival.threshold=22\nenhance.cost.low.amount=1001\nenhance.cost.high.amount=10002\n"
        "enhance.search.vnum.min=10\nenhance.search.vnum.max=20\nenhance.search.max.attempts=44\n"
        "enhance.wear.skip.mask=7\nenhance.original.max.roll=8\nenhance.original.cascade.down.first=0\n"
        "enhance.level.gate.multiplier=4\nenhance.mod.max.steps=6\nenhance.luck.extreme.range=201\n"
        "enhance.luck.very.range=202\nenhance.luck.lucky.range=203\nenhance.ival.gain.extreme=5\n"
        "enhance.ival.gain.very=6\nenhance.ival.gain.lucky=7\nenhance.ival.gain.normal=8\n"
        "[enhance_stat]\nenhance_stat.enabled=1\nenhance_stat.npc_material_fallback.enabled=1\n"
        "enhance_stat.cap.multiplier=2.25\nenhance_stat.platinum.base=111\nenhance_stat.platinum.per.ival=123\n"
        "enhance_stat.material.quantity.mult=.5\n[essence_drop]\nenhance.essence_drop.enabled=0\n"
        "enhance.essence_drop.primary_roll_max=501\nenhance.essence_drop.max_roll_max=502\n"
        "enhance.essence_drop.elite_level_multiplier=3\nenhance.essence_drop.minimum_level=10\n"
        "enhance.essence_drop.maximum_level=90\n[bitvector]\nAFF_HASTE=0,1\n"
        "[bitvector2]\nAFF2_GLOBE=0,1\n[bitvector3]\nAFF3_REDUCE=0,1\n"
        "[bitvector4]\nAFF4_NOFEAR=0,1\n[bitvector5]\nAFF5_PROT_UNDEAD=0,1\n"
        "[essence_drop_zone]\nzone=42:1:2:3\n[pool_exclude_zone]\nzone=7\n[pool_exclude_vnum]\nvnum=90000");
    assert((config_integers() == std::vector<int>{-7,-3,22,1001,10002,10,20,44,7,8,0,4,6,201,202,203,5,6,7,8,1,1,111,123,0,501,502,3,10,90}));
    assert(enhance_stat_cap_multiplier == 2.25 && enhance_stat_material_quantity_multiplier == .5);
    assert(config_logs.size() == 1); // Only the successful-load record.
    assert(enhance_allow_mask && enhance_allow_mask2 && enhance_allow_mask3 && enhance_allow_mask4 && enhance_allow_mask5);
    obj_data allowed{};
    allowed.bitvector = AFF_HASTE; allowed.bitvector2 = AFF2_GLOBE;
    allowed.bitvector3 = AFF3_REDUCE; allowed.bitvector4 = AFF4_NOFEAR;
    allowed.bitvector5 = AFF5_PROT_UNDEAD;
    assert(!is_enhance_banned(&allowed));
    for (int bank = 0; bank < 5; ++bank) {
        auto blocked = allowed;
        if (bank == 0) blocked.bitvector |= AFF_FARSEE;
        if (bank == 1) blocked.bitvector2 |= AFF2_FIRESHIELD;
        if (bank == 2) blocked.bitvector3 |= AFF3_ABSORBING;
        if (bank == 3) blocked.bitvector4 |= AFF4_VAMPIRE_FORM;
        if (bank == 4) blocked.bitvector5 |= AFF5_SHADE_MOVEMENT;
        assert(is_enhance_banned(&blocked));
    }
    assert(enhance_essence_zone_rule_count == 1 && enhance_pool_excluded_zone_count == 1 && enhance_pool_excluded_vnum_count == 1);
    std::filesystem::remove("lib/enhance.cfg"); config_logs.clear(); load_enhance_config();
    assert(config_integers() == compiled && enhance_stat_cap_multiplier == cap_default && enhance_stat_material_quantity_multiplier == quantity_default);
    assert(!enhance_allow_mask && !enhance_allow_mask2 && !enhance_allow_mask3 && !enhance_allow_mask4 && !enhance_allow_mask5);
    assert(!enhance_essence_zone_rule_count && !enhance_pool_excluded_zone_count && !enhance_pool_excluded_vnum_count);
    config_file("[settings]\nenhance.cost.high.amount=12junk\nenhance.material.ival.delta=999999999999999999999999\n"
        "enhance.cost.low.amount=-1\nenhance.search.max.attempts=0\nenhance.original.cascade.down.first=2\n"
        "enhance.level.gate.multiplier=0\nenhance.mod.max.steps=0\nenhance.luck.extreme.range=0\n"
        "enhance.ival.gain.normal=-1\nenhance.typo=1\n=123\nmissing_equal\n"
        "[enhance_stat]\nenhance_stat.enabled=2\nenhance_stat.npc_material_fallback.enabled=broken\n"
        "enhance_stat.cap.multiplier=nan\nenhance_stat.platinum.base=-1\n"
        "enhance_stat.platinum.per.ival=2147483648\nenhance_stat.material.quantity.mult=inf\n"
        "[essence_drop]\nenhance.essence_drop.enabled=2\nenhance.essence_drop.primary_roll_max=0\n"
        "enhance.essence_drop.minimum_level=101\nenhance.essence_drop.maximum_level=0\n");
    assert(config_integers() == compiled && enhance_stat_cap_multiplier == cap_default && enhance_stat_material_quantity_multiplier == quantity_default);
    assert(config_logged("Invalid enhancement config") && config_logged("Unknown enhancement setting") && config_logged("Malformed enhancement setting"));
    config_file("[enhance_stat]\nenhance_stat.enabled=1\nenhance_stat.enabled=bad\n"
        "enhance_stat.cap.multiplier=2\nenhance_stat.cap.multiplier=1e9999\n");
    assert(enhance_stat_enabled == 1 && enhance_stat_cap_multiplier == 2);
    config_file("[settings]\nenhance.cost.high.amount=9" + std::string(1200, ' ') + "junk\nenhance.cost.low.amount=7\n");
    assert(enhance_cost_high_amount == 10000 && enhance_cost_low_amount == 7 && config_logged("overlong"));
    config_file("[settings] trailing\nenhance.cost.high.amount=7\n[unknown]\nenhance.cost.high.amount=8\n");
    assert(enhance_cost_high_amount == 10000 && config_logged("Invalid enhancement section") && config_logged("Unsupported enhancement section"));
    config_file("[spell]\nSPELL_SHADOW_SHIELD=0,0\nenhance.cost.high.amount=7\n"
        "[settings]\nenhance.cost.high.amount=23\n");
    assert(enhance_cost_high_amount == 23 && config_logged("Unsupported enhancement section [spell]"));
    config_file("[settings]\nenhance.search.vnum.min=20\nenhance.search.vnum.max=10\n"
        "[essence_drop]\nenhance.essence_drop.minimum_level=90\nenhance.essence_drop.maximum_level=80\n");
    assert(enhance_search_vnum_min == 1300 && enhance_search_vnum_max == 134000);
    assert(enhance_essence_minimum_level == 1 && enhance_essence_maximum_level == 1000000);
    config_file("[essence_drop_zone]\nzone=42: 2000 :0:2 # inline comment\nzone=43::4000\n"
        "zone=0:1\nzone=44:1junk\nzone=45:-1\nzone=46:1:2:3:4\n"
        "[pool_exclude_zone]\nzone=7\nzone=oops\n[pool_exclude_vnum]\nvnum=90000\nvnum=-1\n");
    assert(enhance_essence_zone_rule_count == 2 && enhance_essence_zone_rules[0].zone_number == 42);
    assert(enhance_essence_zone_rules[0].primary_roll_max == 2000 && enhance_essence_zone_rules[0].max_roll_max == 0 && enhance_essence_zone_rules[0].elite_level_multiplier == 2);
    assert(enhance_essence_zone_rules[1].zone_number == 43 && enhance_essence_zone_rules[1].primary_roll_max == 0 && enhance_essence_zone_rules[1].max_roll_max == 4000);
    assert(enhance_pool_excluded_zone_count == 1 && enhance_pool_excluded_zones[0] == 7);
    assert(enhance_pool_excluded_vnum_count == 1 && enhance_pool_excluded_vnums[0] == 90000);
    config_file("[bitvector]\nAFF_HASTE=reference,1\nAFF_HASTE=0,0\nAFF_FARSEE=0,1\nAFF_FARSEE=0,bad\n"
        "AFF_INVISIBLE=0,2\nAFF_NOT_REAL=0,1\n[bitvector2]\nAFF2_GLOBE=0,1\n"
        "[bitvector3]\nAFF3_REDUCE=0,1\n[bitvector4]\nAFF4_NOFEAR=0,1\n"
        "[bitvector5]\nAFF5_PROT_UNDEAD=0,1\n");
    assert(enhance_allow_mask == AFF_FARSEE && enhance_allow_mask2 == AFF2_GLOBE && enhance_allow_mask3 == AFF3_REDUCE);
    assert(enhance_allow_mask4 == AFF4_NOFEAR && enhance_allow_mask5 == AFF5_PROT_UNDEAD);
    assert(config_logged("Invalid enhancement flag permission") && config_logged("Unknown enhancement flag"));
    std::string many = "[essence_drop_zone]\n";
    for (int zone = 1; zone <= 260; ++zone) many += "zone=" + std::to_string(zone) + "\n";
    config_file(many);
    assert(enhance_essence_zone_rule_count == ENHANCE_ESSENCE_MAX_ZONE_RULES && config_logged("excessive"));
    restore_config();
}

static void test_wide_arithmetic()
{
    for (auto &bucket : enhance_ival_table) bucket = nullptr;
    char_data ch{}; ch.player.level = 60; ch.in_room = NOWHERE; ch.curr_stats.Luk = 100;
    GET_PLATINUM(&ch) = 20;
    auto &source = fixture(0, 90010);
    auto &donor = fixture(1, 90011);
    source.affected[0] = donor.affected[0] = {APPLY_HIT, 10};
    const auto original_source = source, original_donor = donor;
    enhance_level_gate_multiplier = INT_MAX;
    enhance_material_ival_delta = INT_MIN;
    enhance(&ch, &source, &donor);
    assert(output.find("requires an item") != std::string::npos && charges == 0 && GET_MONEY(&ch) == 20000);
    assert(!std::memcmp(&source, &original_source, sizeof(source)) && !std::memcmp(&donor, &original_donor, sizeof(donor)));
    clear_attempt();
    enhance_material_ival_delta = 5;
    enhance_search_max_attempts = INT_MAX; enhance_original_max_roll = 0;
    enhance_ival_gain_extreme = INT_MAX; lucky = true;
    const int before_luck_rolls = rolls;
    enhance(&ch, &source, &donor);
    assert(output.find("at your level") == std::string::npos && charges == 0 && GET_MONEY(&ch) == 20000);
    assert(loads.empty() && extracted.empty() && rolls == before_luck_rolls + 1); clear_attempt(); lucky = false;
    enhance_stat_cap_multiplier = std::numeric_limits<double>::max();
    assert(enhance_stat_cap(1) == SCHAR_MAX && enhance_stat_cap(127) == SCHAR_MAX);
    enhance_search_vnum_min = enhance_search_vnum_max = INT_MAX;
    load_enhance_index();
    assert(loads.empty()); clear_attempt();
    restore_config();
    room_data rooms[1]{}; zone_data zones[1]{};
    world = rooms; zone_table = zones; top_of_zone_table = 0; zones[0].number = 42;
    char_data mob{}, killer{}; npc_only_data npc{}; mob.only.npc = &npc;
    mob.specials.act = ACT_ISNPC | ACT_ELITE; mob.player.level = 60;
    mob.player.short_descr = const_cast<char *>("an elite"); killer.player.name = const_cast<char *>("Tester");
    fixture(11, 400253);
    enhance_essence_primary_roll_max = enhance_essence_max_roll_max = enhance_essence_elite_level_multiplier = INT_MAX;
    const int before_rolls = rolls;
    enhance_load_essence_drop(&mob, &killer);
    assert(result && OBJ_VNUM(result) == 400253 && rolls == before_rolls + 3);
    clear_attempt(); world = nullptr; zone_table = nullptr; top_of_zone_table = -1;
    restore_config();
}

static void test_unavailable()
{
    char_data ch{};
    ch.player.level = 60;
    ch.in_room = NOWHERE;
    GET_PLATINUM(&ch) = 20;
    materials = {{400010, 20}};
    for (bool invalid_source : {false, true}) {
        auto &source = fixture(0, 90010);
        auto &donor = fixture(1, 400254);
        auto &invalid = invalid_source ? source : donor;
        invalid.type = ITEM_WEAPON;
        invalid.value[0] = WEAPON_LONGSWORD;
        invalid.value[1] = invalid.value[2] = 50000;
        assert(itemvalue(&invalid) == 0);
        ch.carrying = &source;
        const auto original_source = source, original_donor = donor;
        const auto original_materials = materials;
        const int original_rolls = rolls;
        for (int mode = 0; mode < (invalid_source ? 3 : 2); ++mode) {
            if (mode == 0) enhance(&ch, &source, &donor);
            if (mode == 1) modenhance(&ch, &source, &donor);
            if (mode == 2) { char command[] = "fixture"; do_enhance(&ch, command, 0); }
            assert(output.find("value is unavailable") != std::string::npos);
            assert(!std::memcmp(&source, &original_source, sizeof(source)));
            assert(!std::memcmp(&donor, &original_donor, sizeof(donor)));
            assert(charges == 0 && GET_MONEY(&ch) == 20000 && materials == original_materials);
            assert(rolls == original_rolls && loads.empty() && extracted.empty());
            clear_attempt();
        }
    }
}


static void test_index() {
    for(int slot=0;slot<12;++slot) {
        auto &object=fixture(slot,10000+slot,10+slot);
        object.affected[0]={APPLY_STR,2}; object.affected[1]={APPLY_STR,3};
        object.affected[2]={APPLY_HIT,1}; object.affected[3]={APPLY_HIT,-1};
    }
    prototypes[1].value[0]=prototypes[0].value[0];
    clear_attempt();
    enhance_search_vnum_min=10000; enhance_search_vnum_max=10011;
    assert(load_enhance_index());
    assert(loads.empty() && extracted.empty() && temporary.empty());
    int count=0;
    for(auto *entry:enhance_stat_table) for(;entry;entry=entry->next) {
        assert(enhance_entry_modifier(entry,APPLY_STR)==5);
        assert(enhance_entry_modifier(entry,APPLY_HIT)==0); ++count;
    }
    assert(count==12); // One semantic STR entry per template, no duplicate/cancelled HP entry.
    const int score=itemvalue(&prototypes[0]);
    auto *head=enhance_ival_table[enhance_hash(score)];
    assert(head->vnum==10001 && head->next->vnum==10000); // Legacy prepend tie order.
    missing_template_vnum=10003;
    assert(!load_enhance_index() && enhance_ival_table[enhance_hash(score)]==head);
    missing_template_vnum=0; fail_next_allocation=true;
    assert(!load_enhance_index() && enhance_ival_table[enhance_hash(score)]==head);
    prototypes[0].value[0]=50; enhancement_system_ready=true;
    refresh_enhancement_item_values(); assert(enhancement_system_is_ready());
    bool updated=false;
    for(auto *entry:enhance_ival_table) for(;entry;entry=entry->next)
        if(entry->vnum==10000) { assert(entry->ival==itemvalue(&prototypes[0])); updated=true; }
    assert(updated && loads.empty() && extracted.empty());
    fail_next_allocation=true; refresh_enhancement_item_values();
    assert(!enhancement_system_is_ready());
    char_data actor{}; char command[]="fixture"; do_enhance(&actor,command,0);
    assert(output.find("unavailable")!=std::string::npos && charges==0);
}

int main()
{
    const auto expected_mask = ITEM_TAKE | ITEM_HOLD | ITEM_ATTACH_BELT | ITEM_WEAR_BACK;
    assert(enhance_wear_skip_mask == expected_mask);
    test_config();
    assert(enhance_wear_skip_mask == expected_mask);
    test_minimal_world_essence_command();
    enhancement_system_ready=true;
    test_donor_floor();
    test_replacement();
    test_level_gate_is_the_ceiling();
    test_essence();
    test_superior();
    test_superior(superior_case::packed);
    test_superior(superior_case::mixed_applies);
    test_superior(superior_case::zero_modifier);
    test_superior(superior_case::duplicate_applies);
    test_unavailable();
    test_wide_arithmetic();
    test_index();
}
"""


def main():
    tradeskill = source("tradeskill.c").read_text()
    get_matstart = tradeskill.split("int get_matstart(P_obj obj)\n", 1)[1].split(
        "\nvoid do_refine(", 1
    )[0]
    with tempfile.TemporaryDirectory(dir=ROOT / "bin") as tmp:
        cpp = Path(tmp) / "enhance.cpp"
        binary = Path(tmp) / "enhance"
        cpp.write_text(
            HARNESS + "\n" + extract_function("db.c", "obj_data inspect_object_template(")
            + "\n" + extract_function("tradeskill.c", "int material_start_vnum(int objmat)")
            + "\nint get_matstart(P_obj obj)\n" + get_matstart
            + "\n" + extract_function("utility.c", "char *coin_stringv(int amount, int padfront)")
        )
        subprocess.run(
            [
                "g++", "-std=c++20", "-g", "-ffunction-sections", "-fdata-sections",
                "-fsanitize=address,undefined,float-cast-overflow", "-fno-sanitize-recover=all",
                "-fno-pie", "-no-pie", "-Isrc", str(cpp), str(HARNESS_STUBS),
                "src/core/safe_format.c", "src/item/salvage.c", "src/item/item_value.c",
                "src/item/item_value_runtime.c", "-Wl,--gc-sections,--wrap=_Znwm", "-lbsd", "-o", str(binary),
            ],
            cwd=ROOT,
            check=True,
        )
        (Path(tmp) / "lib").mkdir()
        for name in ("enhance.cfg", "enhance-shipped.cfg"):
            shutil.copyfile(ROOT / "lib/enhance.cfg", Path(tmp) / "lib" / name)
        result = subprocess.run([binary], cwd=tmp, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
    print("native enhancement iVal regression passed")


if __name__ == "__main__":
    main()
