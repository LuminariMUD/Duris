#!/usr/bin/env python3
"""Exercise production locker sorting, row loading, and container weight accounting."""

import os
from pathlib import Path
import subprocess
import tempfile

from _paths import extract_function, HARNESS_STUBS


ROOT = Path(__file__).resolve().parents[2]
SQL = (ROOT / "src/sql/sql_player.c").read_text()

# Compile the production functions and chest predicates. Only their unrelated
# world, persistence, and prototype services are replaced by fixture stubs.
handler = "\n".join(extract_function("world/handler.c", signature) for signature in (
    "static const object_template *container_prototype(",
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
files = "\n".join(extract_function("core/files.c", signature) for signature in (
    "ush_int getShort(", "uint getInt(", "long getLong(",
    "unsigned long long getUnsignedLongLong(", "char *getString(",
    "int writeObject(", "P_obj restoreObjects(",
))
commands = "\n".join(extract_function("cmd/actobj.c", signature) for signature in (
    "bool bulk_put_permitted(", "void start_empty(",
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
#include "core/mm.h"
#include "combat/trap_legacy.h"
#include "classes/necromancy.h"
#include "item/storage_lockers.h"
#include "item/encumbrance_policy.h"
#include "item/objmisc.h"
#include "world/object_template.h"
#include "world/events.h"
#include "world/db.h"
#include "world/difficulty.h"
#include "economy/currency_transaction.h"
#include "economy/collector_death_enrollment.h"
#include "persistence/persistence_checkpoint.h"
#include "core/safe_format.h"
#include "net/comm.h"
#include "magic/spells.h"
#include "sql/sql_work.h"
#include "sql/item_extra_descr_codec.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdarg>
#include <climits>
#include <map>
#include <string>
#include <vector>

int top_of_objt = 1000;
static index_data indices[10] = {};
P_index obj_index = indices;
P_index mob_index = indices;
extern const struct race_names race_names_table[];
const struct race_names race_names_table[] = {{"human", "human", "human", "hum"}};
// Include the unmodified #96443 Illithid and #83185 Shield Dwarves bag shells.
static int prototype_weights[] = {0, 5, -3000, 20, 10, 4, -300, -150};
static object_template prototypes[10];
static int prototype_loads;
static int int_size = sizeof(int), short_size = sizeof(short), long_size = sizeof(long);
static int save_count, obj_vers, corpse_room;
P_obj save_equip[MAX_WEAR] = {};
unsigned long next_obj_uid = 1;

const object_template *find_object_template(int vnum) {
    assert(vnum >= 0 && vnum < 10);
    return &prototypes[vnum];
}

int real_object(const int vnum) { return vnum; }
P_obj read_object(int rnum, int mode) {
    ++prototype_loads;
    if (rnum == 9) return nullptr; // A retired prototype in a legacy subtree.
    assert(rnum >= 0 && rnum < 8);
    P_obj obj = new obj_data{};
    obj->R_num = rnum;
    obj->type = mode == VIRTUAL && rnum == 2 ? ITEM_CORPSE :
                (rnum == 3 ? ITEM_TREASURE : ITEM_CONTAINER);
    obj->weight = obj->type == ITEM_CORPSE ? 0 : prototype_weights[rnum];
    obj->loc_p = LOC_NOWHERE;
    return obj;
}
void extract_obj(P_obj obj, int) {
    while (obj->contains) {
        P_obj child = obj->contains;
        obj->contains = child->next_content;
        extract_obj(child, TRUE);
    }
    if (obj->str_mask & STRUNG_KEYS) free(obj->name);
    if (obj->str_mask & STRUNG_DESC1) free(obj->description);
    if (obj->str_mask & STRUNG_DESC2) free(obj->short_description);
    if (obj->str_mask & STRUNG_DESC3) free(obj->action_description);
    delete obj;
}
void logit(const char *, const char *, ...) {}
int panic_corruption_int(const char *, const char *, ...) { std::abort(); }
char *str_dup(const char *text) { return strdup(text); }
void str_free(const char *text) { free(const_cast<char *>(text)); }
void *__malloc(size_t bytes, const char *, const char *, int) { return calloc(1, bytes); }
void __free(void *ptr, const char *, int) { free(ptr); }
int obj_affect_time(P_obj, obj_affect *) { std::abort(); }
extra_descr_data *find_spell_description(P_obj) { return nullptr; }
void set_obj_affected(P_obj obj, int, sh_int type, sh_int) {
    assert(obj->type == ITEM_CORPSE && type == TAG_OBJ_DECAY);
}
void set_obj_affected_extra(P_obj, int, sh_int, sh_int, ulong) { std::abort(); }
void proclib_obj_event(P_char, P_char, P_obj, void *) { std::abort(); }
P_nevent get_scheduled(P_obj, event_func) { return nullptr; }
int number(int low, int) { return low; }
nevent_schedule_result add_event(event_func, int, P_char, P_char, P_obj, int, const void *, int) {
    std::abort();
}
void obj_to_char_at_end(P_obj obj, P_char ch) {
    assert(OBJ_NOWHERE(obj));
    obj->loc_p = LOC_CARRIED;
    obj->loc.carrying = ch;
    P_obj *tail = &ch->carrying;
    while (*tail) tail = &(*tail)->next_content;
    *tail = obj;
    GET_CARRYING_W(ch) += GET_OBJ_WEIGHT(obj);
}
P_char training_dummy_item_owner(P_obj) { return nullptr; }
void obj_to_room(P_obj obj, int room) { obj->loc_p = LOC_ROOM; obj->loc.room = room; }
static void mark_container_dirty(P_obj) {}
void artifact_update_location_sql(P_obj) {}
void writeSavedItem(P_obj obj) { assert(obj->type == ITEM_STORAGE); }
void add_weight(P_obj, int);
bool item_movement_transaction_player_busy(P_char) { return false; }
bool empty_source_available(P_char actor, P_obj obj) { return OBJ_CARRIED_BY(obj, actor); }
bool empty_target_available(P_char actor, P_obj obj) { return OBJ_CARRIED_BY(obj, actor); }
bool empty_item_restrictions_allow(P_char, P_obj, P_obj) { return true; }
void save_filled_container(P_obj) {}
int char_light(P_char) { return 0; }
int room_light(int, int) { return 0; }
void send_to_char_f(P_char, const char *, ...) {}
bool money_to_inventory(P_char) { return true; }
void currency_transaction_save_first(P_char) {}
void hold_durable_pet_items(P_char) {}
void unequip_all(P_char) {}
int total_carried_weight(P_char ch) { return GET_CARRYING_W(ch); }
int get_property(const char *, int fallback) { return fallback; }
int difficulty_pc_corpse_decay_minutes() { return 120; }
void account_bound_reward_prepare_player_corpse(P_char, P_obj) {}
void collector_death_enrollment_begin(P_char, P_obj) {}
void writeCorpse(P_obj) {}
void mark_player_dirty_components(int, uint64_t) {}
void DECAP(char *) {}
bool remove_owned_artifact_sql(P_obj, int) { std::abort(); }
void obj_from_room(P_obj) { std::abort(); }
int real_room(int) { std::abort(); }
void spell_darkness(int, P_char, char *, int, P_char, P_obj) { std::abort(); }
void spell_continual_light(int, P_char, char *, int, P_char, P_obj) { std::abort(); }
int checked_snprintf_at(const char *, int, char *dest, size_t size, const char *format, ...) {
    va_list args;
    va_start(args, format);
    const int result = vsnprintf(dest, size, format, args);
    va_end(args);
    return result;
}

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
        pc_only_data player = {};
        carrier.only.pc = &player;
        player.pid = 42;
        P_obj source = read_object(4, REAL); // ordinary 10-weight bag
        P_obj target = read_object(bag_vnum, REAL);
        target->value[0] = bag_vnum == 6 ? 500 : 600;
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

        // Execute empty against a stale target; a rejected transfer must leave
        // both membership and carried weight untouched before a successful retry.
        target->weight = -3000;
        GET_CARRYING_W(&carrier) = 90;
        assert(container_total_weight(target) == shell + 350);
        assert(target->weight == -3000 && GET_CARRYING_W(&carrier) == 90);
        const int capacity = target->value[0];
        target->value[0] = 1;
        start_empty(&carrier, source, target);
        assert(moving->loc.inside == source && target->weight == -3000);
        assert(GET_CARRYING_W(&carrier) == 90);
        target->value[0] = capacity;
        start_empty(&carrier, source, target);
        assert(moving->loc.inside == target && !source->contains);
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

static void legacy_record(char *&cursor, int rnum, int weight, bool contains,
                          int capacity = 500, int type = ITEM_CONTAINER) {
    obj_data object = {};
    object.R_num = rnum;
    object.type = type;
    object.weight = weight;
    object.value[0] = capacity;
    cursor += writeObject(&object, O_F_UNIQUE | (contains ? O_F_CONTAINS : 0),
                          O_U_WEIGHT | O_U_VAL0 | O_U_TYPE, 1, 0, cursor);
}

static void legacy_nested_restore() {
    for (bool missing_parent : {false, true})
    for (int stale : {5, 900, -3000}) {
        for (int capacity : {500, 30}) {
            char bytes[SAV_MAXSIZE] = {};
            char *cursor = bytes;
            ADD_BYTE(cursor, SAV_ITEMVERS);
            ADD_INT(cursor, missing_parent ? 4 : 3);
            legacy_record(cursor, 4, 700, true, capacity);
            if (missing_parent) legacy_record(cursor, 9, 0, true);
            legacy_record(cursor, 1, stale, true);
            legacy_record(cursor, 3, 20, false, 0, ITEM_TREASURE);
            ADD_BYTE(cursor, O_F_EOL);
            ADD_BYTE(cursor, O_F_EOL);
            if (missing_parent) ADD_BYTE(cursor, O_F_EOL);
            ADD_BYTE(cursor, O_F_EOL);
            char_data carrier = {};
            P_obj root = restoreObjects(bytes, &carrier, 0);
            assert(root && root != reinterpret_cast<P_obj>(1));
            P_obj inner = capacity == 500 ? root->contains : carrier.carrying;
            assert(inner && inner != root && inner->weight == 25);
            assert(inner->contains && inner->contains->weight == 20);
            assert(OBJ_INSIDE(inner->contains) && inner->contains->loc.inside == inner);
            if (capacity == 500) {
                assert(carrier.carrying == root && !root->next_content);
                assert(root->weight == 35 && OBJ_INSIDE(inner) && inner->loc.inside == root);
                extract_obj(root, TRUE);
            } else {
                // Truly over-capacity subtrees still move to inventory, intact.
                assert(root->weight == 10 && !root->contains);
                assert(OBJ_CARRIED(inner) && inner->next_content == root);
                extract_obj(inner, TRUE);
                extract_obj(root, TRUE);
            }
            assert(GET_CARRYING_W(&carrier) == 35);
        }
    }
    for (int bag : {6, 7}) {
        char bytes[SAV_MAXSIZE] = {};
        char *cursor = bytes;
        ADD_BYTE(cursor, SAV_ITEMVERS);
        ADD_INT(cursor, 2);
        legacy_record(cursor, bag, 700, true);
        legacy_record(cursor, 3, 10, false, 0, ITEM_TREASURE);
        ADD_BYTE(cursor, O_F_EOL);
        ADD_BYTE(cursor, O_F_EOL);
        char_data carrier = {};
        P_obj root = restoreObjects(bytes, &carrier, 0);
        assert(carrier.carrying == root && !root->next_content && root->contains);
        assert(root->weight == prototype_weights[bag] + 10);
        assert(GET_CARRYING_W(&carrier) == 0);
        extract_obj(root, TRUE);
    }
}

static void instance_weight_restore() {
    for (int type : {ITEM_CORPSE, ITEM_STORAGE, ITEM_QUIVER}) {
        int saved_shell = 160;
        for (int pass = 0; pass < 3; ++pass) {
            // writeObjectlist stores the runtime weight minus direct contents.
            // A PC corpse starts at body weight 180 with a directly linked item.
            char bytes[SAV_MAXSIZE] = {};
            char *cursor = bytes;
            ADD_BYTE(cursor, SAV_ITEMVERS);
            ADD_INT(cursor, 2);
            legacy_record(cursor, 0, saved_shell, true, 500, type);
            legacy_record(cursor, 3, 20, false, 0, ITEM_TREASURE);
            ADD_BYTE(cursor, O_F_EOL);
            ADD_BYTE(cursor, O_F_EOL);
            char_data carrier = {};
            P_obj corpse = restoreObjects(bytes, &carrier, 0);
            assert(corpse->weight == 180 && GET_CARRYING_W(&carrier) == 180);
            P_obj item = corpse->contains;
            obj_from_obj(item);
            assert(corpse->weight == 160 && GET_CARRYING_W(&carrier) == 160);
            recalc_container_weight(corpse);
            assert(container_total_weight(corpse) == (type == ITEM_CORPSE ? 0 : 160));
            assert(corpse->weight == 160);
            obj_to_obj(item, corpse);
            assert(corpse->weight == 180 && GET_CARRYING_W(&carrier) == 180);
            saved_shell = corpse->weight - GET_OBJ_WEIGHT(item);
            extract_obj(corpse, TRUE);
        }
    }
}

static void corpse_creation_and_loot() {
    for (bool npc : {false, true}) {
        char_data victim = {};
        pc_only_data player = {};
        npc_only_data mobile = {};
        victim.player.name = const_cast<char *>("Tester");
        victim.player.short_descr = const_cast<char *>("a test creature");
        victim.player.weight = 180;
        victim.player.level = 10;
        if (npc) {
            victim.specials.act = ACT_ISNPC;
            victim.only.npc = &mobile;
        } else {
            victim.only.pc = &player;
            player.pid = 42;
        }
        P_obj item = read_object(3, REAL);
        obj_to_char_at_end(item, &victim);
        P_obj corpse = make_corpse(&victim, 0);
        const int expected = npc ? 40 : 180;
        assert(corpse && corpse->weight == expected && corpse->contains == item);
        assert(container_total_weight(corpse) == 20);
        assert(corpse->value[CORPSE_WEIGHT] == 20);
        assert(!victim.carrying && GET_CARRYING_W(&victim) == 0);
        obj_from_obj(item);
        assert(corpse->weight == expected - 20 && !corpse->contains);
        int64_t weight = container_total_weight(corpse), space = 0, quiver_count = 0;
        assert(weight == 0);
        assert(bulk_put_permitted(&victim, item, corpse, weight, space, quiver_count));
        assert(weight == 20);
        obj_to_obj(item, corpse);
        assert(corpse->weight == expected && corpse->contains == item);
        assert(!bulk_put_permitted(&victim, item, corpse, weight, space, quiver_count));
        extract_obj(corpse, TRUE);
    }
}

static void bulk_movement_cost() {
    P_obj outer = read_object(5, REAL);
    outer->value[4] = 50;
    P_obj source = read_object(4, REAL);
    P_obj target = read_object(1, REAL);
    obj_to_obj(source, outer);
    obj_to_obj(target, outer);
    for (int i = 0; i < 100; ++i) obj_to_obj(read_object(3, REAL), source);
    const int before = prototype_loads;
    while (source->contains) {
        P_obj item = source->contains;
        obj_from_obj(item);
        obj_to_obj(item, target);
    }
    assert(source->weight == 10 && target->weight == 2005 && outer->weight == 1012);
    assert(prototype_loads == before);
    extract_obj(outer, TRUE);
}

int main(int argc, char **argv) {
    assert(argc == 2);
    for (int i = 0; i < 8; ++i) {
        indices[i].virtual_number = i;
        prototypes[i].weight = prototype_weights[i];
    }
    indices[9].virtual_number = 9;
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
    else if (!strcmp(argv[1], "legacy-nested")) legacy_nested_restore();
    else if (!strcmp(argv[1], "instance-restore")) instance_weight_restore();
    else if (!strcmp(argv[1], "corpse-creation-loot")) corpse_creation_and_loot();
    else if (!strcmp(argv[1], "bulk-movement-cost")) bulk_movement_cost();
    else std::abort();
    std::printf("locker container weight %s PASS\n", argv[1]);
}
'''.replace("// PRODUCTION", handler + "\n" + files + "\n" + commands + "\n" + chests + "\n" + loader + "\n" +
            extract_function("combat/fight.c", "P_obj make_corpse("))

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
        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
        "-I", str(ROOT / "src"), str(source), str(ROOT / "src/combat/trap_legacy.c"),
        str(HARNESS_STUBS), "-o", str(binary),
    ], check=True)
    failed = []
    for case in ("sorting", "insert", "append", "public-load", "private-load",
                 "worn-insert", "worn-append", "worn-nested-insert", "worn-nested-append",
                 "worn-weight-changes", "carried-weight-changes", "worn-recalculation",
                 "stale-bag-capacity", "nested-insert", "nested-append",
                 "worn-nested-insert-chain", "worn-nested-append-chain", "empty-transfer",
                 "legacy-nested", "instance-restore", "corpse-creation-loot", "bulk-movement-cost"):
        result = subprocess.run([str(binary), case], timeout=20,
                                env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1"})
        if result.returncode:
            failed.append(case)
    assert not failed, f"locker container weight regressions: {failed}"
