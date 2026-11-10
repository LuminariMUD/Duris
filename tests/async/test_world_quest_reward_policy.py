#!/usr/bin/env python3
"""Contracts for bartender quest rewards.

Rewards come from the quest's zone, including its most valuable items and ordinary items
that static quests reference; each completed quest pays a personal reward batch;
quests may be shared with four companions; and the fee is a property.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source


PROPERTIES = (ROOT / "lib" / "duris.properties").read_text()


def _run_harness(body: str, prefix: str) -> None:
    with tempfile.TemporaryDirectory(prefix=prefix) as directory:
        root = Path(directory)
        source_path = root / "harness.cpp"
        binary = root / "harness"
        source_path.write_text(body)
        subprocess.run(
            ["g++", "-std=c++20", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
             "-Isrc", str(source_path), "-o", str(binary)],
            cwd=ROOT,
            check=True,
        )
        subprocess.run([str(binary)], cwd=ROOT, check=True)


def test_catalog_keeps_every_source_eligible_item() -> None:
    _run_harness(r"""
#include "world/world_quest_policy_math.h"
#include <array>
#include <cassert>
#include <vector>
constexpr int TOTALLVLS = 62;
constexpr int VIRTUAL = 0;
struct object_data { int ivalue; bool eligible; };
using P_obj = object_data *;
using object_template=object_data;
struct quest_reward_profile { int vnum = 0; int ivalue = 0; };
struct quest_zone_profile {
    std::vector<quest_reward_profile> rewards;
    std::vector<int> reward_vnums;
    std::array<std::vector<int>, TOTALLVLS> reward_vnums_by_level;
    std::array<int, TOTALLVLS> reward_count{};
    std::array<double, TOTALLVLS> reward_average{};
};
struct index_entry { int virtual_number; };
// Zone 0 has tied top-value items and one the source filter rejects; zone 1 has one item.
static object_data objects[] = {{10, true}, {40, true}, {40, true}, {90, false}, {25, true}};
static index_entry obj_index[] = {{100}, {101}, {102}, {103}, {200}};
static int top_of_objt = 4;
static std::vector<quest_zone_profile> quest_zones(2);
static int zone_for_vnum(int vnum) { return vnum / 100 - 1; }
static bool cache_object_template(int) { return true; }
static const object_template *find_object_template(int vnum) { return &objects[vnum >= 200 ? 4 : vnum - 100]; }
static object_data inspect_object_template(const object_template &object) { return object; }
static void logit(const char *,const char *,...) {}
#define LOG_STATUS "status"
static bool source_eligible_reward(P_obj obj) { return obj->eligible; }
static int itemvalue(const object_template &obj) { return obj.ivalue; }
""" + extract_function("world/world_quest_policy.c", "void load_reward_profiles(") + r"""
int main() {
    load_reward_profiles();
    load_reward_profiles(); // Rebuilds replace old values/counts rather than accumulating them.
    assert((quest_zones[0].reward_vnums == std::vector<int>{100, 101, 102}));
    assert((quest_zones[1].reward_vnums == std::vector<int>{200}));
    // The floor still applies: only the tied 40s satisfy 2 * value >= 61.
    assert((quest_zones[0].reward_vnums_by_level[61] == std::vector<int>{101, 102}));
    assert(quest_zones[0].reward_count[61] == 2 && quest_zones[0].reward_average[61] == 40);
    assert(quest_zones[0].reward_count[20] == 3 && quest_zones[0].reward_average[20] == 30);
    assert(quest_zones[1].reward_count[50] == 1 && quest_zones[1].reward_count[51] == 0);
}
""", "duris-world-quest-catalog-")


def test_longstanding_source_exclusions_remain() -> None:
    eligible = extract_function("world/world_quest_policy.c", "bool source_eligible_reward(")
    for exclusion in ("IS_OBJ_STAT2(obj, ITEM2_QUESTITEM)", "IS_ARTIFACT(obj)",
                      'isname("_noquest_", obj->name)', "IS_SET(obj->extra_flags, ITEM_NORENT)",
                      # A mortal drawing one of these fails the whole reward batch.
                      "IS_OBJ_STAT2(obj, ITEM2_CRUMBLELOOT)"):
        assert exclusion in eligible, exclusion


def test_removed_restrictions_stay_removed() -> None:
    policy = source("world/world_quest_policy.c").read_text()
    assert "collect_quest_item_vnums" not in policy and "quest_index" not in policy
    assert "withheld" not in policy
    assert "withheld" not in source("world/world_quest_policy_math.h").read_text()
    assert "world.quest.reward.top.withheld.percent" not in PROPERTIES
    assert policy.index("load_reward_profiles();") < policy.index("load_zone_scores();")


def test_nofear_block_reads_the_fourth_affect_field() -> None:
    eligible = extract_function("world/world_quest_policy.c", "bool source_eligible_reward(")
    assert "IS_SET(obj->bitvector4, AFF4_NOFEAR)" in eligible
    assert "IS_SET(obj->bitvector, AFF4_NOFEAR)" not in eligible
    # The same copied blocklist lives in crafting's has_affect(); no affect flag anywhere
    # may be tested against a different affect word.
    wrong_word = re.compile(
        r"IS_SET\([^,]*->bitvector, AFF[234]_|IS_SET\([^,]*->bitvector2, AFF[34]?_[A-Z]|"
        r"IS_SET\([^,]*->bitvector3, AFF[24]?_[A-Z]|IS_SET\([^,]*->bitvector4, AFF[23]?_[A-Z]")
    offenders = [f"{path.relative_to(ROOT)}:{number}"
                 for path in sorted((ROOT / "src").rglob("*.[ch]"))
                 for number, line in enumerate(path.read_text(errors="replace").splitlines(), 1)
                 if wrong_word.search(line)]
    assert not offenders, offenders


def test_kill_quests_pay_a_batch_on_completion() -> None:
    kill = extract_function("world_quest.c", "void quest_kill(")
    assert "obj_to_char(reward, quest_mob)" not in kill
    assert "obj_to_char(reward, ch)" not in kill
    assert "quest_kill_original + 1) <= 2" not in kill
    done = kill[kill.index("quest_kill_how_many - ch->only.pc->quest_kill_original == 0"):]
    assert "world_quest_start_reward(ch, quest_mob, FIND_AND_KILL, true)" in done
    assert "--ch->only.pc->quest_kill_how_many" not in done
    start = extract_function("world_quest.c", "static bool world_quest_start_reward(")
    assert start.count("quest_item_reward(ch)") == 1
    assert "item < quest.quest_reward_item_count" in start
    assert "PLAYER_WORLD_QUEST_KILL_HISTORY_PENDING" in start
    assert kill.index("gain_exp(ch, NULL") < kill.index("world_quest_start_reward(")
    assert start.index("sql_world_quest_finish_async(") < start.index("world_quest_deliver_reward(")


def test_independent_bonus_rolls() -> None:
    _run_harness(r'''
#include "player/player_snapshot.h"
#include <cassert>
#include <cmath>
#include <climits>
static unsigned outcomes = 0;
static int calls = 0, expected_high = 0, fixed = 0;
int number(int low, int high) {
    assert(low == 1 && high == expected_high);
    if (fixed) { ++calls; return fixed; }
    return (outcomes >> calls++) & 1 ? 1 : high;
}
''' + extract_function("world_quest.c", "static int world_quest_roll_item_count(") + r'''
// Enumerates every roll sequence, so the distribution is exact rather than sampled.
static void check_quota(int quota) {
    const double p=1.0/(quota+1);
    double mass=0, mean=0;
    expected_high=quota+1;
    for (outcomes=0; outcomes<(1u<<(quota-1)); ++outcomes) {
        calls=0;
        const int count=world_quest_roll_item_count(quota);
        const int successes=__builtin_popcount(outcomes);
        assert(calls==quota-1 && count==1+successes && count>=1 && count<=quota);
        const double probability=std::pow(p,successes)*std::pow(1-p,quota-1-successes);
        mass+=probability; mean+=count*probability;
    }
    assert(std::abs(mass-1)<1e-12);
    assert(std::abs(mean-2.0*quota/(quota+1))<1e-12);
}
int main() {
    for (int quota=1; quota<=9; ++quota) check_quota(quota);
    check_quota(12);
    expected_high=0;
    calls=0;
    for (int invalid : {0, -1, INT_MAX})
        assert(world_quest_roll_item_count(invalid) == 0 && calls == 0);
    // Only an exact 1 is a bonus: 2 at the same quota pays nothing, and all 1s pay every item.
    expected_high=19; fixed=2; calls=0;
    assert(world_quest_roll_item_count(18)==1 && calls==17);
    fixed=1; calls=0;
    assert(world_quest_roll_item_count(18)==18 && calls==17);
}
''', "duris-world-quest-bonus-")


def test_quest_sharing_remains_configurable() -> None:
    limit = extract_function("world_quest.c", "static int world_quest_share_limit(")
    assert '"world.quest.share.max", 0.000' in limit
    create = extract_function("world_quest.c", "bool createQuestForGiverVnum(")
    assert "quest_shares_left = world_quest_share_limit();" in create
    assert "quest_shares_left = 4;" not in create
    quest = extract_function("world_quest.c", "void do_quest(")
    share = quest[quest.index('isname(name, "share")'):]
    refusal = share.index("if (world_quest_share_limit() == 0)")
    assert refusal < share.index("quest_receiver != GET_PID(ch)")
    assert refusal < share.index("victim = ParseTarget(ch, who);")
    # Quests granted before the limit dropped cannot share past it.
    assert share.index("MIN(ch->only.pc->quest_shares_left, world_quest_share_limit())") < \
        share.index("if (ch->only.pc->quest_shares_left == 0)")


def test_bartender_fee_is_a_property() -> None:
    mobile = source("specs.mobile.c").read_text()
    assert "temp = 20 * GET_LEVEL(pl);" not in mobile
    assert '"world.quest.cost.per.level", 20.000' in mobile


def test_properties_ship_the_documented_defaults() -> None:
    section = PROPERTIES[PROPERTIES.index("[worldQuest]"):]
    section = section[: section.index("\n[", 1)].splitlines()
    for line in ("world.quest.share.max=4.000", "world.quest.cost.per.level=20.000"):
        assert line in section, line


if __name__ == "__main__":
    tests = [
        test_catalog_keeps_every_source_eligible_item,
        test_longstanding_source_exclusions_remain,
        test_removed_restrictions_stay_removed,
        test_nofear_block_reads_the_fourth_affect_field,
        test_kill_quests_pay_a_batch_on_completion,
        test_independent_bonus_rolls,
        test_quest_sharing_remains_configurable,
        test_bartender_fee_is_a_property,
        test_properties_ship_the_documented_defaults,
    ]
    for test in tests:
        test()
    print("world-quest reward policy contracts passed")
