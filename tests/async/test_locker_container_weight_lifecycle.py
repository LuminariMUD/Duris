#!/usr/bin/env python3
"""Exercise production locker sorting, row loading, and container weight accounting."""

import os
from pathlib import Path
import subprocess
import tempfile

from _paths import extract_function


ROOT = Path(__file__).resolve().parents[2]
SQL = (ROOT / "src/sql/sql_player.c").read_text()

# Compile the production functions and chest predicates. Only their unrelated
# world, persistence, and prototype services are replaced by fixture stubs.
handler = "\n".join(extract_function("world/handler.c", signature) for signature in (
    "static bool obj_is_container_type(",
    "static int obj_prototype_weight(",
    "static int container_weight_reduction_pct(",
    "static int sum_direct_contents_weight(",
    "static void encumbrance_adjust(",
    "void recalc_container_weight(",
    "static void resync_reducing_container(",
    "static void propagate_weight_delta(",
    "void add_weight(P_obj obj, int weight)\n{",
    "bool obj_can_nest(",
    "bool obj_is_in_container(",
    "void obj_to_obj(",
    "static void append_obj_to_list(",
    "void obj_to_obj_at_end(",
    "void obj_from_obj(",
))
chests = "\n".join(extract_function("item/storage_lockers.c", signature) for signature in (
    "bool locker_eq_type_fits_for_storage(",
    "bool ComboChest::ItemFits(",
    "bool EqApplyChest::ItemFits(",
    "bool EqAffectChest::ItemFits(",
))
loader = SQL[SQL.index("#define MAX_CONTAINER_LOAD_DEPTH"):SQL.index(
    "/* The statement that deletes the personal", SQL.index("#define MAX_CONTAINER_LOAD_DEPTH"))]

harness = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/files.h"
#include "item/storage_lockers.h"
#include "sql/sql_work.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>
#include <vector>

int top_of_objt = 1000;
static index_data indices[10] = {};
P_index obj_index = indices;
static int prototype_weights[] = {0, 5, -3000, 20, 10, 4};

int real_object(const int vnum) { return vnum; }
P_obj read_object(int rnum, int) {
    assert(rnum >= 0 && rnum < 6);
    P_obj obj = new obj_data{};
    obj->R_num = rnum;
    obj->type = rnum == 3 ? ITEM_TREASURE : ITEM_CONTAINER;
    obj->weight = prototype_weights[rnum];
    obj->loc_p = LOC_NOWHERE;
    return obj;
}
void extract_obj(P_obj obj, int) {
    while (obj->contains) {
        P_obj child = obj->contains;
        obj->contains = child->next_content;
        extract_obj(child, TRUE);
    }
    delete obj;
}
void logit(const char *, const char *, ...) {}
int panic_corruption_int(const char *, const char *, ...) { std::abort(); }
char *str_dup(const char *) { std::abort(); }
P_char training_dummy_item_owner(P_obj) { return nullptr; }
void obj_to_room(P_obj, int) { std::abort(); }
static void mark_container_dirty(P_obj) {}
void artifact_update_location_sql(P_obj) {}
void writeSavedItem(P_obj) { std::abort(); }
void add_weight(P_obj, int);

LockerChest::~LockerChest() {}
void LockerChest::FillExtraDescBuf(char *) {}
ComboChest::~ComboChest() {}
void ComboChest::FillExtraDescBuf(char *) {}

static int sql_validate_loaded_item_type(P_obj, int type, const char *) { return type; }
static bool sql_persistence_item_owner_fields_match(
    unsigned long long, const char *, unsigned long long, unsigned long long, const char *const *) {
    return true;
}
static void sql_set_item_affects(P_obj, const std::vector<std::pair<int, int>> &) {}
static void sql_add_item_extra_descr(P_obj, const char *, const char *, const char *, int,
                                   extra_descr_data **) {}

// PRODUCTION

struct SlotChest : EqSlotChest { SlotChest() : EqSlotChest(ITEM_HOLD, "held", "held") {} };
struct WearChest : EqWearChest { WearChest() : EqWearChest(1, "warrior", "warrior") {} };
struct ApplyChest : EqApplyChest { ApplyChest() : EqApplyChest(APPLY_STR, "str", "str") {} };
struct AffectChest : EqAffectChest { AffectChest() : EqAffectChest(1, 1, "affect", "affect") {} };
struct TestOreChest : OreChest { TestOreChest() : OreChest("", "ore", "ore") {} };
struct TestComboChest : ComboChest { TestComboChest() : ComboChest(nullptr) {} };

static void sorting() {
    SlotChest slot;
    WearChest wear;
    ApplyChest apply;
    AffectChest affect;
    TestOreChest ore;
    TestComboChest combo;
    LockerChest *chests[] = {&slot, &wear, &apply, &affect, &ore, &combo};
    char name[] = "test_ore_";
    obj_data obj = {};
    obj.name = name;
    obj.wear_flags = ITEM_HOLD;
    obj.affected[0].location = APPLY_STR;
    obj.affected[0].modifier = 1;
    obj.bitvector = 1;
    for (int type : {ITEM_CONTAINER, ITEM_CORPSE}) {
        obj.type = type;
        for (LockerChest *chest : chests) assert(!chest->ItemFits(&obj));
    }
    obj.type = ITEM_TREASURE;
    for (LockerChest *chest : chests) {
        assert(chest->ItemFits(&obj));
        assert(!chest->ItemFits(nullptr));
    }
}

static void movement(bool append) {
    obj_data chest = {};
    chest.type = ITEM_CONTAINER;
    chest.R_num = 4;
    chest.weight = 10;
    char_data carrier = {};
    chest.loc_p = LOC_CARRIED;
    chest.loc.carrying = &carrier;
    GET_CARRYING_W(&carrier) = 10;
    P_obj hole = read_object(2, REAL);
    P_obj item = read_object(3, REAL);
    auto put = append ? obj_to_obj_at_end : obj_to_obj;
    for (int i = 0; i < 50; ++i) {
        put(hole, &chest);
        assert(chest.weight == 10 && GET_CARRYING_W(&carrier) == 10);
        put(item, &chest);
        assert(chest.weight == 30 && GET_CARRYING_W(&carrier) == 30);
        obj_from_obj(hole);
        assert(chest.weight == 30 && GET_CARRYING_W(&carrier) == 30);
        obj_from_obj(item);
        assert(chest.weight == 10 && GET_CARRYING_W(&carrier) == 10);
    }
    extract_obj(hole, TRUE);
    extract_obj(item, TRUE);
}

static void worn_movement(bool append, int reduction) {
    P_obj bag = read_object(5, REAL);
    bag->value[4] = reduction;
    char_data wearer = {};
    bag->loc_p = LOC_WORN;
    bag->loc.wearing = &wearer;
    GET_CARRYING_W(&wearer) = 102; // Other equipment contributes 100, the shell 2.
    P_obj items[3];
    const int item_weight = reduction ? 2 : 1;
    for (P_obj &item : items) {
        item = read_object(3, REAL);
        item->weight = item_weight;
    }
    auto put = append ? obj_to_obj_at_end : obj_to_obj;
    for (int cycle = 0; cycle < 50; ++cycle) {
        for (int count = 1; count <= 3; ++count) {
            put(items[count - 1], bag);
            const int contents = count * item_weight;
            assert(bag->weight == 4 + contents - contents * reduction / 100);
            assert(GET_CARRYING_W(&wearer) == 100 + bag->weight / 2);
        }
        for (int count = 2; count >= 0; --count) {
            obj_from_obj(items[count]);
            const int contents = count * item_weight;
            assert(bag->weight == 4 + contents - contents * reduction / 100);
            assert(GET_CARRYING_W(&wearer) == 100 + bag->weight / 2);
        }
        assert(bag->weight == 4 && GET_CARRYING_W(&wearer) == 102);
    }
    for (P_obj item : items) extract_obj(item, TRUE);
    extract_obj(bag, TRUE);
}

static void worn_weight_boundaries() {
    obj_data bag = {};
    char_data wearer = {};
    bag.weight = -4;
    bag.loc_p = LOC_WORN;
    bag.loc.wearing = &wearer;
    GET_CARRYING_W(&wearer) = 100;
    for (int cycle = 0; cycle < 50; ++cycle) {
        for (int weight : {-4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 4, 3, 2, 1, 0, -1, -4}) {
            add_weight(&bag, weight - bag.weight);
            assert(bag.weight == weight);
            assert(GET_CARRYING_W(&wearer) == 100 + (weight > 0 ? weight / 2 : 0));
        }
    }
}

static sql_row item_row(int id, int vnum, int parent, int weight, int reduction = 0) {
    sql_row row;
    row.fields.resize(40);
    for (auto [column, value] : std::vector<std::pair<int, int>>{
             {1, id}, {2, vnum}, {3, weight}, {8, vnum == 3 ? ITEM_TREASURE : ITEM_CONTAINER},
             {13, reduction}, {29, 7}, {30, parent}})
        row.fields[column] = std::to_string(value);
    row.fields[0] = "item";
    return row;
}

static void loading(bool private_chest) {
    // A stale 999-lb outer bag contains a 50% reducing gathering bag and a
    // negative-weight portable hole. Normalize children before their parent.
    sql_rows rows = {item_row(1, 4, 0, 999), item_row(2, 1, 1, 999, 50),
                     item_row(3, 3, 2, 20), item_row(4, 2, 1, -3000)};
    for (int cycle = 0; cycle < 50; ++cycle) {
        P_obj chest = private_chest ? read_object(0, REAL) : nullptr;
        P_obj root = sql_locker_items_from_rows(rows, 1, 7, chest);
        if (private_chest) {
            assert(!root);
            root = chest->contains;
            assert(chest->weight == 25);
        }
        assert(root && root->weight == 25);
        P_obj bag = root->contains;
        P_obj hole = bag->next_content;
        assert(bag->weight == 15 && hole->weight == -3000);
        assert(bag->contains->weight == 20);
        // Repeated capacity checks and movement into/out of a sorting chest
        // must leave both the loaded weight and the chest shell unchanged.
        recalc_container_weight(bag);
        recalc_container_weight(root);
        assert(root->weight == 25);
        if (private_chest) {
            obj_from_obj(root);
            assert(chest->weight == 0);
            obj_to_obj(root, chest);
            assert(chest->weight == 25);
        }
        rows[0].fields[3] = std::to_string(root->weight);
        rows[1].fields[3] = std::to_string(bag->weight);
        extract_obj(chest ? chest : root, TRUE);
    }
}

int main(int argc, char **argv) {
    assert(argc == 2);
    if (!strcmp(argv[1], "sorting")) sorting();
    else if (!strcmp(argv[1], "insert")) movement(false);
    else if (!strcmp(argv[1], "append")) movement(true);
    else if (!strcmp(argv[1], "worn-insert")) worn_movement(false, 50);
    else if (!strcmp(argv[1], "worn-append")) worn_movement(true, 50);
    else if (!strcmp(argv[1], "worn-plain-insert")) worn_movement(false, 0);
    else if (!strcmp(argv[1], "worn-plain-append")) worn_movement(true, 0);
    else if (!strcmp(argv[1], "worn-boundaries")) worn_weight_boundaries();
    else if (!strcmp(argv[1], "public-load")) loading(false);
    else if (!strcmp(argv[1], "private-load")) loading(true);
    else std::abort();
    std::printf("locker container weight %s PASS\n", argv[1]);
}
'''.replace("// PRODUCTION", handler + "\n" + chests + "\n" + loader)

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="locker-container-weight-", dir=build) as tmp:
    path = Path(tmp)
    source = path / "test.cpp"
    binary = path / "test"
    source.write_text(harness)
    subprocess.run([
        "g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        "-I", str(ROOT / "src"), str(source), "-o", str(binary),
    ], check=True)
    failed = []
    for case in ("sorting", "insert", "append", "public-load", "private-load",
                 "worn-insert", "worn-append", "worn-plain-insert", "worn-plain-append",
                 "worn-boundaries"):
        result = subprocess.run([str(binary), case], timeout=20,
                                env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1"})
        if result.returncode:
            failed.append(case)
    assert not failed, f"locker container weight regressions: {failed}"
