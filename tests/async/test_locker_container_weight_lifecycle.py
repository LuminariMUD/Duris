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
    "static int calculated_container_weight(",
    "void recalc_container_weight(",
    "int container_total_weight(",
    "static void reconcile_container_chain(",
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
#include "combat/trap_legacy.h"
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
// Include the unmodified #96443 Illithid and #83185 Shield Dwarves bag shells.
static int prototype_weights[] = {0, 5, -3000, 20, 10, 4, -300, -150};

int real_object(const int vnum) { return vnum; }
P_obj read_object(int rnum, int) {
    assert(rnum >= 0 && rnum < 8);
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

static void worn_movement(bool append, bool nested) {
    auto put = append ? obj_to_obj_at_end : obj_to_obj;
    for (int reduction : {0, 50}) {
        // Model the four-pound #494 gathering bag, directly worn or inside
        // another worn container. Preserve eleven pounds of unrelated load.
        char_data carrier = {};
        obj_data outer = {};
        outer.type = ITEM_CONTAINER;
        outer.R_num = 4;
        outer.weight = 10;
        outer.loc_p = LOC_WORN;
        outer.loc.wearing = &carrier;
        P_obj bag = read_object(5, REAL);
        bag->value[4] = reduction;
        bag->loc_p = LOC_WORN;
        bag->loc.wearing = &carrier;
        GET_CARRYING_W(&carrier) = 11 + (nested ? 5 : 2);
        if (nested) {
            bag->loc_p = LOC_NOWHERE;
            put(bag, &outer);
        }
        auto check = [&](int count) {
            const int bag_weight = 4 + count * 2 - count * 2 * reduction / 100;
            const int worn_weight = (nested ? 10 : 0) + bag_weight;
            assert(bag->weight == bag_weight);
            if (nested) assert(outer.weight == worn_weight);
            assert(GET_CARRYING_W(&carrier) == 11 + worn_weight / 2);
        };
        for (int cycle = 0; cycle < 50; ++cycle) {
            P_obj items[3];
            for (int i = 0; i < 3; ++i) {
                items[i] = read_object(3, REAL);
                items[i]->weight = 2;
                put(items[i], bag);
                check(i + 1);
            }
            for (int i = 2; i >= 0; --i) {
                obj_from_obj(items[i]);
                check(i);
                extract_obj(items[i], TRUE);
            }
        }
        if (nested) {
            obj_from_obj(bag);
            assert(outer.weight == 10 && GET_CARRYING_W(&carrier) == 16);
        }
        extract_obj(bag, TRUE);
    }
}

static void weight_changes(bool worn) {
    char_data carrier = {};
    obj_data obj = {};
    obj.weight = -3;
    obj.loc_p = worn ? LOC_WORN : LOC_CARRIED;
    if (worn) obj.loc.wearing = &carrier;
    else obj.loc.carrying = &carrier;
    GET_CARRYING_W(&carrier) = 11;
    for (int cycle = 0; cycle < 50; ++cycle) {
        int expected = -3;
        for (int delta : {2, 2, 1, 1, -1, -1, -2, -2, 4, -4}) {
            expected += delta;
            add_weight(&obj, delta);
            assert(obj.weight == expected);
            assert(GET_CARRYING_W(&carrier) == 11 + (expected > 0 ? expected : 0) / (worn ? 2 : 1));
        }
        assert(obj.weight == -3 && GET_CARRYING_W(&carrier) == 11);
    }
    add_weight(nullptr, 1);
    add_weight(&obj, 0);
    assert(obj.weight == -3 && GET_CARRYING_W(&carrier) == 11);
}

static void nested_reducing_chain(bool append, bool worn) {
    auto move = append ? obj_to_obj_at_end : obj_to_obj;
    for (int cycle = 0; cycle < 50; ++cycle) {
        char_data carrier = {};
        P_obj outer = read_object(5, REAL);
        outer->value[4] = 50;
        outer->loc_p = worn ? LOC_WORN : LOC_CARRIED;
        if (worn) outer->loc.wearing = &carrier;
        else outer->loc.carrying = &carrier;
        GET_CARRYING_W(&carrier) = 11 + (worn ? 2 : 4);

        P_obj inner = read_object(1, REAL); // normal 5-weight bag
        move(inner, outer);
        assert(outer->weight == 7); // 4 + 5 - floor(5 * 0.5)
        assert(GET_CARRYING_W(&carrier) == 11 + (worn ? 3 : 7));

        P_obj item = read_object(3, REAL);
        item->weight = 100;
        move(item, inner);
        assert(inner->weight == 105);
        assert(outer->weight == 57); // 4 + 105 - floor(105 * 0.5)
        assert(GET_CARRYING_W(&carrier) == 11 + (worn ? 28 : 57));

        // The same effective reduction must work in the reverse direction.
        obj_from_obj(item);
        assert(inner->weight == 5 && outer->weight == 7);
        assert(GET_CARRYING_W(&carrier) == 11 + (worn ? 3 : 7));
        obj_from_obj(inner);
        assert(outer->weight == 4);
        assert(GET_CARRYING_W(&carrier) == 11 + (worn ? 2 : 4));
        extract_obj(item, TRUE);
        extract_obj(inner, TRUE);
        extract_obj(outer, TRUE);
    }
}

static void empty_style_transfer_repairs_stale_bag() {
    for (int bag_vnum : {6, 7}) {
        const int shell = prototype_weights[bag_vnum];
        char_data carrier = {};
        P_obj source = read_object(4, REAL); // ordinary 10-weight bag
        P_obj target = read_object(bag_vnum, REAL);
        source->loc_p = target->loc_p = LOC_CARRIED;
        source->loc.carrying = target->loc.carrying = &carrier;
        GET_CARRYING_W(&carrier) = 10;
        P_obj contents = read_object(3, REAL);
        contents->weight = 350;
        obj_to_obj(contents, target);
        assert(target->weight == shell + 350);
        P_obj moving = read_object(3, REAL);
        moving->weight = 80;
        obj_to_obj(moving, source);
        assert(GET_CARRYING_W(&carrier) == 10 + 80 + (shell + 350));

        // Model stale persisted target with zero effective weight. The empty
        // command performs these two shared movements, not the put() function.
        target->weight = -3000;
        GET_CARRYING_W(&carrier) = 90;
        assert(container_total_weight(target) == shell + 350);
        assert(target->weight == -3000 && GET_CARRYING_W(&carrier) == 90);
        obj_from_obj(moving);
        obj_to_obj(moving, target);
        const int expected = shell + 350 + 80;
        assert(source->weight == 10 && target->weight == expected);
        assert(GET_CARRYING_W(&carrier) == 10 + expected);

        obj_from_obj(moving);
        obj_from_obj(contents);
        assert(target->weight == shell && source->weight == 10);
        assert(GET_CARRYING_W(&carrier) == 10);
        extract_obj(moving, TRUE);
        extract_obj(contents, TRUE);
        extract_obj(source, TRUE);
        extract_obj(target, TRUE);
    }
}

static void stale_bag_capacity_reads() {
    for (int vnum : {6, 7}) {
        const int shell = prototype_weights[vnum];
        const int limit = vnum == 6 ? 500 : 600;
        char_data carrier = {};
        P_obj bag = read_object(vnum, REAL);
        bag->value[0] = limit;
        bag->loc_p = LOC_CARRIED;
        bag->loc.carrying = &carrier;
        P_obj old_item = read_object(3, REAL);
        old_item->weight = 350;
        obj_to_obj(old_item, bag);
        const int correct_weight = shell + 350;
        assert(bag->weight == correct_weight);
        assert(GET_CARRYING_W(&carrier) == correct_weight);

        // Simulate an old persisted bag weight inconsistent with the prototype.
        // The same predicate used by single and bulk put must not repair weight
        // (or change encumbrance) when an oversized item is rejected.
        bag->weight = -3000;
        GET_CARRYING_W(&carrier) = 0;
        for (int attempt = 0; attempt < 100; ++attempt) {
            assert(container_total_weight(bag) == correct_weight);
            assert(container_total_weight(bag) + limit > bag->value[0]);
            assert(bag->weight == -3000);
            assert(GET_CARRYING_W(&carrier) == 0);
        }

        // A load/restore explicitly reconciles before inventory accounting.
        recalc_container_weight(bag);
        assert(bag->weight == correct_weight);
        assert(GET_CARRYING_W(&carrier) == correct_weight);

        // A successfully moved item repairs a live stale bag after transfer,
        // not during the preceding eligibility check.
        bag->weight = -3000;
        GET_CARRYING_W(&carrier) = 0;
        P_obj new_item = read_object(3, REAL);
        new_item->weight = 80;
        assert(container_total_weight(bag) + GET_OBJ_WEIGHT(new_item) <= limit);
        assert(bag->weight == -3000 && GET_CARRYING_W(&carrier) == 0);
        obj_to_obj(new_item, bag);
        assert(bag->weight == correct_weight + 80);
        assert(GET_CARRYING_W(&carrier) == correct_weight + 80);
        obj_from_obj(new_item);
        assert(bag->weight == correct_weight);
        assert(GET_CARRYING_W(&carrier) == correct_weight);
        extract_obj(new_item, TRUE);
        extract_obj(bag, TRUE);
    }
}

static void worn_recalculation() {
    char_data carrier = {};
    P_obj bag = read_object(5, REAL);
    bag->loc_p = LOC_WORN;
    bag->loc.wearing = &carrier;
    for (int stale : {7, 1, -3}) {
        bag->weight = stale;
        GET_CARRYING_W(&carrier) = 11 + (stale > 0 ? stale : 0) / 2;
        recalc_container_weight(bag);
        assert(bag->weight == 4 && GET_CARRYING_W(&carrier) == 13);
        recalc_container_weight(bag);
        assert(bag->weight == 4 && GET_CARRYING_W(&carrier) == 13);
    }
    extract_obj(bag, TRUE);
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
    else if (!strcmp(argv[1], "worn-insert")) worn_movement(false, false);
    else if (!strcmp(argv[1], "worn-append")) worn_movement(true, false);
    else if (!strcmp(argv[1], "worn-nested-insert")) worn_movement(false, true);
    else if (!strcmp(argv[1], "worn-nested-append")) worn_movement(true, true);
    else if (!strcmp(argv[1], "worn-weight-changes")) weight_changes(true);
    else if (!strcmp(argv[1], "carried-weight-changes")) weight_changes(false);
    else if (!strcmp(argv[1], "worn-recalculation")) worn_recalculation();
    else if (!strcmp(argv[1], "stale-bag-capacity")) stale_bag_capacity_reads();
    else if (!strcmp(argv[1], "nested-insert")) nested_reducing_chain(false, false);
    else if (!strcmp(argv[1], "nested-append")) nested_reducing_chain(true, false);
    else if (!strcmp(argv[1], "worn-nested-insert-chain")) nested_reducing_chain(false, true);
    else if (!strcmp(argv[1], "worn-nested-append-chain")) nested_reducing_chain(true, true);
    else if (!strcmp(argv[1], "empty-transfer")) empty_style_transfer_repairs_stale_bag();
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
        "-I", str(ROOT / "src"), str(source), str(ROOT / "src/combat/trap_legacy.c"), "-o", str(binary),
    ], check=True)
    failed = []
    for case in ("sorting", "insert", "append", "public-load", "private-load",
                 "worn-insert", "worn-append", "worn-nested-insert", "worn-nested-append",
                 "worn-weight-changes", "carried-weight-changes", "worn-recalculation",
                 "stale-bag-capacity", "nested-insert", "nested-append",
                 "worn-nested-insert-chain", "worn-nested-append-chain", "empty-transfer"):
        result = subprocess.run([str(binary), case], timeout=20,
                                env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1"})
        if result.returncode:
            failed.append(case)
    assert not failed, f"locker container weight regressions: {failed}"
