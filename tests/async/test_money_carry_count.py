#!/usr/bin/env python3
"""Execute money and salvage pickup gates below, at and above the count cap.

Money moving in memory is covered separately by test_currency_in_memory.py;
this harness checks which objects reach the pickup.
"""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, SRC


def extract(signature):
    source = (SRC / "actobj.c").read_text()
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for end in range(brace, len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if not depth:
            return source[start:end + 1]
    raise AssertionError(signature)


PRELUDE = r'''
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
constexpr int ITEM_MONEY = 20, ITEM_CORPSE = 21, ITEM2_ACCOUNT_BOUND = 1,
              ITEM2_NOLOOT = 2, CORPSE_FLAGS = 1, PC_CORPSE = 1;
constexpr size_t CURRENCY_DENOMINATION_COUNT = 4;
constexpr int LOWEST_MAT_VNUM = 400000, HIGHEST_MAT_VNUM = 400209;
constexpr int MAX_STRING_LENGTH = 1024;
constexpr bool TRUE = true, FALSE = false;
struct character { int count = 11, cap = 11, weight = 0, max_weight = 100; };
struct object {
    int type = ITEM_MONEY, vnum = 3, weight = 0, condition = 1;
    int value[8] = {};
    uint64_t obj_uid = 1;
    const char *name = "coins", *short_description = "coins";
    bool visible = true, takeable = true;
    character *hitched_to = nullptr;
};
using P_char = character *;
using P_obj = object *;
struct synchronous_item { uint64_t uid; P_obj object; bool scrap;
    std::array<int32_t, CURRENCY_DENOMINATION_COUNT> coin_amount = {};
    bool coin_amount_valid = false; };
struct bulk_get_state {
    uint64_t container_uid = 0;
    std::vector<std::string> rejections;
    bool failed = false;
    bool count_limit_reported = false;
    std::vector<synchronous_item> synchronous_items;
};
#define GET_ITEM_TYPE(o) ((o)->type)
#define GET_OBJ_WEIGHT(o) ((o)->weight)
#define IS_CARRYING_N(c) ((c)->count)
#define CAN_CARRY_N(c) ((c)->cap)
#define CAN_CARRY_W(c) ((c)->max_weight)
#define CAN_SEE_OBJ(c,o) ((o)->visible)
#define OBJ_VNUM(o) ((o)->vnum)
#define GETDBG_LOG(...) ((void)0)
#define IS_OBJ_STAT2(o,f) false
#define IS_SET(value,flag) ((value) & (flag))
#define IS_TRUSTED(c) false
#define OBJS(o,c) ((o)->name)
#define PERS(...) "someone"
#define checked_snprintf snprintf
int finalized = 0;
int total_carried_weight(P_char ch) { return ch->weight; }
void send_to_char(const char *, P_char) {}
void do_get_reject_out_of_sight(P_char, P_obj, bool &fail) { fail = true; }
bool do_get_finalize_container_item_or_reject(P_char, P_char, P_obj, P_obj obj,
    int &, bool &, bool, int, int, int, const char *, const char *, bool &fail)
{ if (!obj->takeable) { fail = true; return false; } ++finalized; return true; }
bool isname(const char *filter, const char *name) { return !strcmp(filter, name); }
bool item_command_object_is_takeable(P_char, P_obj obj) { return obj->takeable; }
bool account_bound_reward_owner(P_char, P_obj) { return true; }
bool artifact_second_of_type(P_char, P_obj) { return false; }
bool artifact_second_of_type(P_char, P_obj, P_obj) { return false; }
bool checkgetput(P_char, P_obj) { return false; }
P_obj find_live_object(P_obj obj, uint64_t uid) {
    return obj && obj->obj_uid == uid ? obj : nullptr;
}
void writeCorpse(P_obj) {}
void reject_bulk_get_object(bulk_get_state &state, P_obj, const char *) { state.failed = true; }
'''

DRIVER = r'''
bool direct(P_char actor, P_obj bag, P_obj item, bool local = false)
{
    int total = 0;
    bool found = false, stop = false, fail = false;
    return do_get_try_container_item(actor, nullptr, bag, item, total, found,
        false, local, stop, fail, "", "", "", "", "", true);
}
int main()
{
    for (int count : {10, 11, 28}) {
        for (int vnum : {3, 402013}) {
            for (bool local : {false, true}) {
                character actor;
                actor.count = count;
                object bag, money, ordinary;
                money.vnum = vnum;
                ordinary.type = 1;
                ordinary.name = "sword";
                ordinary.obj_uid = 2;
                const int before = finalized;
                assert(direct(&actor, &bag, &money, local));
                assert(finalized == before + 1);
                assert(direct(&actor, &bag, &ordinary, local) == (count < actor.cap));
                // all.coins and take all selection; an ordinary item precedes coins.
                for (const char *filter : {"coins", static_cast<const char *>(nullptr)}) {
                    bulk_get_state state;
                    int carried = count;
                    int64_t weight = 0;
                    bool stop = false;
                    bool accepted = select_bulk_get_item(&actor, &bag, &ordinary,
                        filter, local, carried, weight, state, stop);
                    assert(accepted == (!filter && count < actor.cap));
                    assert(!stop);
                    if (!filter && count >= actor.cap) {
                        assert(!select_bulk_get_item(&actor, &bag, &ordinary,
                            filter, local, carried, weight, state, stop));
                        assert(state.rejections.size() == 1);
                    }
                    const int before_coins = carried;
                    assert(select_bulk_get_item(&actor, &bag, &money, filter,
                        local, carried, weight, state, stop));
                    assert(carried == before_coins);
                    if (filter)
                        assert(state.rejections.empty());
                    assert(state.synchronous_items.size() == (accepted ? 2u : 1u));
                }
                // Other eligibility gates still reject money.
                money.visible = false;
                assert(!direct(&actor, &bag, &money));
                money.visible = true;
                money.takeable = false;
                assert(!direct(&actor, &bag, &money));
                money.takeable = true;
                money.weight = actor.max_weight + 1;
                assert(!direct(&actor, &bag, &money));
                assert(direct(&actor, &bag, &money, true));
                assert(actor.count == count);
            }
        }
    }
    // Restore the historical inclusive material range for container pickup.
    // Floor pickup keeps its existing exclusive lower bound.
    for (int count : {10, 11, 28}) {
        for (int vnum : {LOWEST_MAT_VNUM - 1, LOWEST_MAT_VNUM,
                         LOWEST_MAT_VNUM + 1, HIGHEST_MAT_VNUM,
                         HIGHEST_MAT_VNUM + 1}) {
            for (bool local : {false, true}) {
                character actor;
                actor.count = count;
                object bag, material;
                material.type = 1;
                material.vnum = vnum;
                material.name = "material";
                material.weight = 1;
                const bool is_material = vnum >= LOWEST_MAT_VNUM &&
                                         vnum <= HIGHEST_MAT_VNUM;
                const bool fits = count < actor.cap || is_material;
                const int before = finalized;
                assert(direct(&actor, &bag, &material, local) == fits);
                assert(finalized == before + (fits ? 1 : 0));
                for (const char *filter : {"material", static_cast<const char *>(nullptr)}) {
                    bulk_get_state state;
                    int carried = count;
                    int64_t weight = 0;
                    bool stop = false;
                    assert(select_bulk_get_item(&actor, &bag, &material, filter,
                        local, carried, weight, state, stop) == fits);
                    assert(!stop);
                    assert(carried == count + (fits ? 1 : 0));
                    assert(weight == (fits && !local ? 1 : 0));
                    assert(state.synchronous_items.size() == (fits ? 1u : 0u));
                }
                bulk_get_state floor;
                int carried = count;
                int64_t weight = 0;
                bool stop = false;
                const bool floor_fits = count < actor.cap ||
                    (vnum > LOWEST_MAT_VNUM && vnum <= HIGHEST_MAT_VNUM);
                assert(select_bulk_get_item(&actor, nullptr, &material, nullptr,
                    false, carried, weight, floor, stop) == floor_fits);
                assert(carried == count + (floor_fits ? 1 : 0));

                if (!is_material)
                    continue;
                // The count exception must not bypass visibility, takeability
                // or the existing weight check for containers on the ground.
                material.visible = false;
                assert(!direct(&actor, &bag, &material));
                material.visible = true;
                material.takeable = false;
                assert(!direct(&actor, &bag, &material));
                material.takeable = true;
                material.weight = actor.max_weight + 1;
                assert(!direct(&actor, &bag, &material));
                assert(direct(&actor, &bag, &material, true));
                for (bool carried_bag : {false, true}) {
                    bulk_get_state state;
                    carried = count; weight = 0; stop = false;
                    assert(select_bulk_get_item(&actor, &bag, &material, nullptr,
                        carried_bag, carried, weight, state, stop) == carried_bag);
                    assert(stop == !carried_bag);
                    assert(carried == count + (carried_bag ? 1 : 0));
                }
                assert(actor.count == count);
            }
        }
    }
    // An ordinary rejection must not hide later materials or money in get all.
    character actor;
    object bag, ordinary, material, money;
    ordinary.type = material.type = 1;
    material.vnum = LOWEST_MAT_VNUM;
    bulk_get_state state;
    int carried = actor.cap;
    int64_t weight = 0;
    bool stop = false;
    assert(!select_bulk_get_item(&actor, &bag, &ordinary, nullptr, false,
                                carried, weight, state, stop));
    assert(!stop);
    assert(select_bulk_get_item(&actor, &bag, &material, nullptr, false,
                               carried, weight, state, stop));
    assert(select_bulk_get_item(&actor, &bag, &money, nullptr, false,
                               carried, weight, state, stop));
    assert(carried == actor.cap + 1 && state.synchronous_items.size() == 2);
    assert(state.rejections.size() == 1 && !stop);
    puts("Money and salvage count gates passed: single, filtered/mixed bulk, carried/room containers, floor, material boundaries, weight, counts 10/11/28.");
}
'''


if __name__ == "__main__":
    harness = "\n".join((PRELUDE, extract("static bool do_get_try_container_item("),
                         extract("static bool select_bulk_get_item("), DRIVER))
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / "bin/tests") as directory:
        source = Path(directory) / "money_carry_count.cpp"
        binary = Path(directory) / "money_carry_count"
        source.write_text(harness)
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                        "-Wno-unused-parameter", "-fsanitize=address,undefined",
                        "-g", str(source), "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True)
