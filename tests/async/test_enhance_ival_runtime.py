#!/usr/bin/env python3
"""Run the native enhancement paths with controlled inventory, loads and RNG."""

import subprocess
import tempfile
from pathlib import Path

from _paths import HARNESS_STUBS, ROOT, source


HARNESS = r"""
#include <cassert>
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
static int charges;

extern const struct stat_data stat_factor[LAST_RACE + 1] = {};
int get_mincircle(int) { std::abort(); }
int get_ival_from_proc(obj_proc_type) { std::abort(); }
int number(int low, int high) { return lucky ? low : high; }
void logit(const char *, const char *, ...) {}
bool chaos_starter_materials_enabled() { return true; }
P_obj chaos_material_pouch_find(P_char) { return active_pouch; }
void set_obj_extra_flags(P_obj obj, unsigned flags) { obj->extra_flags = flags; }

int SUB_MONEY(P_char ch, int amount, int)
{
    assert(amount == 10000);
    GET_PLATINUM(ch) -= amount / 1000;
    ++charges;
    return 0;
}

P_obj read_object(int vnum, int mode)
{
    assert(mode == VIRTUAL);
    loads.push_back(vnum);
    for (const auto &prototype : prototypes)
        if (vnum && indices[prototype.R_num].virtual_number == vnum)
        {
            auto obj = new obj_data(prototype);
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

static obj_data &fixture(int slot, int vnum, int ac = 0)
{
    auto &obj = prototypes[slot];
    obj = {};
    obj.R_num = slot;
    indices[slot].virtual_number = vnum;
    obj.wear_flags = ITEM_TAKE | ITEM_HOLD | ITEM_WEAR_ARMS;
    obj.type = ac ? ITEM_ARMOR : ITEM_WORN;
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
    loads.clear();
    extracted.clear();
    charges = 0;
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
    enhance_index_entry stale_lower{}, stale_equal{}, stale_wear{}, missing{}, same_bucket{};
    index_entry(same_bucket, 83202, 89);
    index_entry(stale_lower, 83277, 89);
    index_entry(stale_equal, 90000, 89);
    index_entry(stale_wear, 90002, 89);
    index_entry(missing, 90003, 89);
    GET_PLATINUM(&ch) = 20;
    source.loc_p = donor.loc_p = LOC_CARRIED;
    enhance(&ch, &source, &donor);
    assert(result && OBJ_VNUM(result) == 83202);
    assert((loads == std::vector<int>{90003, 90002, 90000, 83277, 83202}));
    assert((extracted == std::vector<int>{90002, 90000, 83277, 98963, 90001}));
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

int main()
{
    load_enhance_config();
    test_replacement();
}
"""


def main():
    tradeskill = source("tradeskill.c").read_text()
    # Compile the real valuation function, isolating unrelated spell and object procs.
    itemvalue = tradeskill.split("int itemvalue(P_obj obj)\n", 1)[1].split(
        "\nvoid do_salvation(", 1
    )[0]
    with tempfile.TemporaryDirectory(dir=ROOT / "bin") as tmp:
        cpp = Path(tmp) / "enhance.cpp"
        binary = Path(tmp) / "enhance"
        cpp.write_text(HARNESS + "\nint itemvalue(P_obj obj)\n" + itemvalue)
        subprocess.run(
            [
                "g++", "-std=c++20", "-g", "-ffunction-sections", "-fdata-sections",
                "-fsanitize=address,undefined,float-cast-overflow", "-fno-sanitize-recover=all",
                "-fno-pie", "-no-pie", "-Isrc", str(cpp), str(HARNESS_STUBS),
                "src/core/safe_format.c", "-Wl,--gc-sections", "-lbsd", "-o", str(binary),
            ],
            cwd=ROOT,
            check=True,
        )
        subprocess.run([binary], cwd=ROOT, check=True)
    print("native enhancement iVal regression passed")


if __name__ == "__main__":
    main()
