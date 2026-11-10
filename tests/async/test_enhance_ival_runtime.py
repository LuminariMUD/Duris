#!/usr/bin/env python3
"""Run the native enhancement paths with controlled inventory, loads and RNG."""

import subprocess
import tempfile
from pathlib import Path

from _paths import HARNESS_STUBS, ROOT, source, extract_function


HARNESS = r"""
#include <cassert>
#include <map>
#include <string>
#include <unordered_set>
#include <vector>

#include "item/enhance.c"

static index_data indices[12]{};
index_data *obj_index = indices;
P_room world = nullptr;
struct zone_data *zone_table = nullptr;
int top_of_zone_table = -1;

static obj_data prototypes[12]{};
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
int get_ival_from_proc(obj_proc_type) { std::abort(); }
int number(int low, int high) { return lucky ? low : high; }
void logit(const char *, const char *, ...) {}
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
    assert(itemvalue(&over_cap) > enhance_ival_cap + enhance_original_max_roll);
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
    assert((loads == std::vector<int>{90003, 90004, 90002, 90000, 83277, 83202}));
    assert((extracted == std::vector<int>{90004, 90002, 90000, 83277, 98963, 90001}));
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
    unavailable_vnum = OBJ_VNUM(&source);
    modenhance(&ch, &source, &health);
    assert(source.affected[2].location == APPLY_NONE && source.extra2_flags == 0);
    assert(source.name == base.name && extracted.empty());
    assert(health.loc_p == LOC_CARRIED && charges == 0 && GET_MONEY(&ch) == 10000);
    unavailable_vnum = 0;
    clear_attempt();

    refuse_wallet_commit = true;
    modenhance(&ch, &source, &health);
    assert(source.affected[2].location == APPLY_NONE && source.extra2_flags == 0);
    assert(source.name == base.name && health.loc_p == LOC_CARRIED);
    assert(charges == 0 && GET_MONEY(&ch) == 10000);
    assert((extracted == std::vector<int>{90010}));
    clear_attempt();
    refuse_wallet_commit = false;

    modenhance(&ch, &source, &health);
    assert(source.affected[2].location == APPLY_HIT && source.affected[2].modifier == 3);
    assert(IS_OBJ_STAT2(&source, ITEM2_ENHANCED) && strstr(source.name, "enhanced"));
    assert(health.loc_p == LOC_NOWHERE && charges == 1 && GET_MONEY(&ch) == 9000);
    assert((extracted == std::vector<int>{400254, 90010}));
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
    if (duplicate_case) base.affected[0].location = APPLY_STR;
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

    materials.clear();
    do_enhance(&ch, command, 0);
    assert(output.find("Materials required for the next enhancement") != std::string::npos);
    assert(charges == 0 && item.affected[0].modifier == 2 && item.affected[1].modifier == 2);
    clear_attempt();

    materials = initial_materials;
    GET_PLATINUM(&ch) = 0;
    do_enhance(&ch, command, 0);
    assert(output.find("It will require") != std::string::npos);
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

int main()
{
    const auto expected_mask = ITEM_TAKE | ITEM_HOLD | ITEM_ATTACH_BELT | ITEM_WEAR_BACK;
    assert(enhance_wear_skip_mask == expected_mask);
    load_enhance_config();
    assert(enhance_wear_skip_mask == expected_mask);
    test_replacement();
    test_essence();
    test_superior();
    test_superior(superior_case::packed);
    test_superior(superior_case::mixed_applies);
    test_superior(superior_case::zero_modifier);
    test_superior(superior_case::duplicate_applies);
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
            HARNESS + "\n" + extract_function("tradeskill.c", "int material_start_vnum(int objmat)")
            + "\nint get_matstart(P_obj obj)\n" + get_matstart
        )
        subprocess.run(
            [
                "g++", "-std=c++20", "-g", "-ffunction-sections", "-fdata-sections",
                "-fsanitize=address,undefined,float-cast-overflow", "-fno-sanitize-recover=all",
                "-fno-pie", "-no-pie", "-Isrc", str(cpp), str(HARNESS_STUBS),
                "src/core/safe_format.c", "src/item/salvage.c", "src/item/item_value.c",
                "src/item/item_value_runtime.c", "-Wl,--gc-sections", "-lbsd", "-o", str(binary),
            ],
            cwd=ROOT,
            check=True,
        )
        subprocess.run([binary], cwd=ROOT, check=True)
    print("native enhancement iVal regression passed")


if __name__ == "__main__":
    main()
