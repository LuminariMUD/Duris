#!/usr/bin/env python3
"""Run the production quest retry/selection functions against deterministic fixtures."""

import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source as repo_source


PRELUDE = r'''
#include <algorithm>
#include <cassert>
#include <ctime>
#include <cstring>
#include <string>
#include <cstdint>
#include <vector>
#include "world/world_quest_policy_math.h"
using namespace std;
constexpr int FIND_AND_KILL = 1, FIND_AND_ASK = 2, MAXLVL = 62, NOWHERE = -1;
constexpr int ACT_SPEC = 1;
#define TRUE true
#define FALSE false
#define MIN(a, b) std::min(a, b)
#define GET_LEVEL(ch) ((ch)->level)
#define IS_NPC(ch) ((ch)->npc)
#define IS_PC(ch) (!IS_NPC(ch))
#define IS_TRUSTED(ch) false
#define GET_NAME(ch) "fixture"
#define GET_VNUM(ch) 16553
#define GET_PID(ch) 1
#define REMOVE_BIT(value, bits) ((value) &= ~(bits))
#define BOUNDED(low, value, high) std::max((low), std::min((value), (high)))
float get_property(const char *, double fallback) { return static_cast<float>(fallback); }
// The difficulty module is not linked; a neutral world quest dial leaves the kill count alone.
int difficulty_scale_world_quest_kills(int kills) { return kills; }
struct pc_data {
    int quest_shares_left = 0, quest_active = 0, quest_mob_vnum = 0, quest_type = 0;
    int quest_accomplished = 0, quest_zone_number = 0, quest_giver = 0, quest_level = 0;
    int quest_receiver = 0, quest_kill_how_many = 0, quest_kill_original = 0;
    int quest_map_room = 0, quest_map_bought = 0, quest_origin_room = 0, quest_replacement_due = 0;
    time_t quest_started = 0;
    bool operator==(const pc_data &) const = default;
};
struct character {
    int level = 56;
    bool npc = false;
    struct { pc_data *pc = nullptr; } only;
    struct { int act = 0; } specials;
    int in_room = NOWHERE;
};
using P_char = character *;
#include "world/world_quest.h"
struct index_entry { int number = 2, limit = 10, virtual_number = 0; };
vector<index_entry> mob_index;
int top_of_mobt;
struct zone_entry { int number = 100; };
vector<zone_entry> zone_table;
struct quest_mob_profile {
    int rnum, vnum, level;
    bool can_speak = true, invisible = false, hidden = false;
};
struct quest_zone_profile { vector<quest_mob_profile> mobs; };
vector<quest_zone_profile> zones;
vector<int> history_reads;
vector<int> probe_reads;
int fresh_target = -1, error_target = -1;
struct room_entry { int number = 16633; };
room_entry world[1];
int real_room(int vnum) { return vnum == 16633 ? 0 : NOWHERE; }
constexpr unsigned PLAYER_COMPONENT_STATUS = 1;
int dirty_marks = 0;
void mark_player_dirty_components(int, unsigned component) {
    assert(component == PLAYER_COMPONENT_STATUS); ++dirty_marks;
}
constexpr int CURRENCY_PENDING_CONTEXT_MAX_BYTES = 64;
struct currency_command_result {};
constexpr int MAXLVLMORTAL = 56;
constexpr const char *LOG_WIZ = "", *LOG_DEBUG = "";
#define GET_MONEY(ch) (wallet)
#define ADD_MONEY(ch, amount) (wallet += (amount))
int wallet = 0;
void logit(const char *, const char *, ...) {}
std::string output;
void send_to_char(const char *text, P_char) { output += text; }
void do_quest(P_char, char *, int) {}
void gmcp_quest_status(P_char) {}
int quest_buy_map(P_char) { std::abort(); }
char *writable_arg(const char *s) { return const_cast<char *>(s); }
void sql_world_quest_finished(P_char, int) { std::abort(); }
int sql_world_quest_can_do_another(P_char) { return 1; }

int number(int low, int) { return low; }
void wizlog(int, const char *, ...) {}
void debug(const char *, ...) {}
int real_mobile(int vnum) { return vnum - 1000; }
void getQuestZoneList(P_char, vector<int> &out) {
    for (size_t i = 0; i < zones.size(); ++i) out.push_back(static_cast<int>(i));
}
int world_quest_policy_select_zone(P_char, const vector<int> &valid) { return valid.front(); }
int sql_world_quest_done_already(P_char, int target) {
    // A repeated history lookup is a bug even when the request eventually succeeds.
    assert(find(history_reads.begin(), history_reads.end(), target) == history_reads.end());
    history_reads.push_back(target);
    if (target == error_target) return -1;
    return target == fresh_target ? 0 : 1;
}
P_char read_mobile_probe(int vnum, int) {
    probe_reads.push_back(vnum);
    return new character;
}
constexpr int VIRTUAL = 1;
struct mobile_probe_guard {
    P_char value;
    ~mobile_probe_guard() { delete value; }
};
void char_to_room(P_char ch, int room, int) { ch->in_room = room; }
bool aggressive_to(P_char, P_char) { return false; }
'''

ADAPTER = r'''
int world_quest_policy_suggest_mob(int zone, P_char ch, int type, int *budget,
                                  const vector<int> &excluded = {}) {
    return select_cached_mob(zones[zone], ch, type, budget, excluded);
}
'''

SCENARIOS = r'''
void setup(int zone_count, int mobs_per_zone, int level, int instances) {
    zones.assign(zone_count, {});
    zone_table.assign(zone_count, {});
    mob_index.assign(zone_count * mobs_per_zone, {});
    history_reads.clear();
    probe_reads.clear();
    fresh_target = error_target = -1;
    top_of_mobt = static_cast<int>(mob_index.size()) - 1;
    for (int i = 0; i <= top_of_mobt; ++i) {
        mob_index[i].number = instances;
        mob_index[i].virtual_number = 1000 + i;
        zones[i / mobs_per_zone].mobs.push_back({i, 1000 + i, level});
    }
}
int main() {
    pc_data pc;
    character player;
    player.only.pc = &pc;
    quest_creation_failure failure;

    // At level 56 there is only one quest type. Skip completed A and issue B.
    setup(1, 2, 56, 2);
    fresh_target = 1001;
    assert(createQuestForGiverVnum(&player, 16553, 16633, &failure));
    assert((history_reads == vector<int>{1000, 1001}));
    assert(pc.quest_active == 1 && pc.quest_mob_vnum == 1001);
    assert(pc.quest_origin_room == 16633 && pc.quest_replacement_due == 0);
    assert(dirty_marks > 0);
    assert(pc.quest_type == FIND_AND_KILL && failure == QUEST_CREATION_NO_FAILURE);

    // The same retry must work for ask quests and retain the shared probe budget.
    pc = {};
    player.level = 30;
    setup(1, 2, 30, 1);
    fresh_target = 1001;
    assert(createQuestForGiverVnum(&player, 16553, 16633, &failure));
    assert((history_reads == vector<int>{1000, 1001}));
    assert(probe_reads == history_reads);
    assert(pc.quest_type == FIND_AND_ASK && pc.quest_mob_vnum == 1001);

    // All duplicates: stop after each distinct target, preserving existing state.
    const pc_data before = pc;
    setup(1, 2, 30, 1);
    assert(!createQuestForGiverVnum(&player, 16553, 16633, &failure));
    assert((history_reads == vector<int>{1000, 1001}));
    assert(pc == before && failure == QUEST_CREATION_NO_ELIGIBLE_TARGET);

    // A backend error must stop immediately, even if a fresh target follows it.
    setup(1, 2, 30, 1);
    error_target = 1000;
    fresh_target = 1001;
    assert(!createQuestForGiverVnum(&player, 16553, 16633, &failure));
    assert((history_reads == vector<int>{1000}));
    assert(pc == before && failure == QUEST_CREATION_NO_ELIGIBLE_TARGET);

    // Caps are per request, including retries within and across zones.
    player.level = 56;
    for (int zone_count : {1, 4}) {
        setup(zone_count, 64 / zone_count, 56, 2);
        fresh_target = 1000 + WORLD_QUEST_MAX_HISTORY_CHECKS;
        assert(!createQuestForGiverVnum(&player, 16553, 16633, &failure));
        assert(history_reads.size() == WORLD_QUEST_MAX_HISTORY_CHECKS);
        assert(pc == before);
    }
    player.level = 30;
    setup(4, 16, 30, 1);
    assert(!createQuestForGiverVnum(&player, 16553, 16633, &failure));
    assert(probe_reads.size() <= WORLD_QUEST_MAX_TARGET_PROBES);
    assert(history_reads.size() <= WORLD_QUEST_MAX_HISTORY_CHECKS);
    assert(pc == before);

    // The last permitted history check can still grant a valid quest.
    player.level = 56;
    setup(1, WORLD_QUEST_MAX_HISTORY_CHECKS, 56, 2);
    fresh_target = 999 + WORLD_QUEST_MAX_HISTORY_CHECKS;
    assert(createQuestForGiverVnum(&player, 16553, 16633, &failure));
    assert(history_reads.size() == WORLD_QUEST_MAX_HISTORY_CHECKS);
    assert(pc.quest_mob_vnum == fresh_target);
    // Reject an unknown explicit origin without touching the current contract.
    const auto accepted = pc;
    assert(!createQuestForGiverVnum(&player, 16553, 0, &failure));
    assert(pc == accepted && failure == QUEST_CREATION_INVALID_ACTOR);
    assert(!createQuestForGiverVnum(&player, 16553, 999999, &failure));
    assert(pc == accepted && failure == QUEST_CREATION_INVALID_ACTOR);

    // Run the real payment continuation after the customer has moved away.
    resetQuest(&player);
    assert(pc.quest_origin_room == 0 && pc.quest_replacement_due == 0);
    setup(1, 1, 56, 2);
    fresh_target = 1000;
    player.in_room = 999;
    world_quest_payment_context payment{world_quest_payment_action::quest, 100, 16553, 16633};
    world_quest_payment_committed(&player, true, {}, 0,
        reinterpret_cast<const uint8_t *>(&payment), sizeof(payment));
    assert(pc.quest_active == 1 && pc.quest_origin_room == 16633);
    assert(player.in_room == 999); // Neither route setup nor creation moves the actor.
    assert(wallet == 0);

    // A bad captured origin refunds the committed fee and leaves no active task.
    resetQuest(&player);
    payment.origin_vnum = 999999;
    world_quest_payment_committed(&player, true, {}, 0,
        reinterpret_cast<const uint8_t *>(&payment), sizeof(payment));
    assert(!pc.quest_active && !pc.quest_origin_room && wallet == 100);
    assert(output.find("You get your money back") != std::string::npos);

    // A rejected payment never creates a quest.
    payment.origin_vnum = 16633;
    world_quest_payment_committed(&player, false, {}, 0,
        reinterpret_cast<const uint8_t *>(&payment), sizeof(payment));
    assert(!pc.quest_active && wallet == 100);
    // The live-giver entry point captures the same room and rejects remote givers.
    setup(1, 1, 56, 2);
    fresh_target = 1000;
    character giver;
    giver.npc = true;
    giver.in_room = player.in_room = 0;
    assert(createQuest(&player, &giver, &failure));
    assert(pc.quest_origin_room == 16633);
    const auto colocated = pc;
    giver.in_room = 999;
    assert(!createQuest(&player, &giver, &failure));
    assert(pc == colocated && failure == QUEST_CREATION_INVALID_ACTOR);
    // Quests are unshareable by default: a granted quest carries no shares.
    assert(pc.quest_shares_left == 0);
}
'''


def main() -> None:
    mobile = repo_source("specs.mobile.c").read_text()
    payment_context = mobile[mobile.index("enum class world_quest_payment_action"):
                             mobile.index("static void world_quest_report_creation_failure")]
    harness = (
        PRELUDE
        + extract_function("world/world_quest_policy.c", "int select_cached_mob(")
        + ADAPTER
        + extract_function("world_quest.c", "static int world_quest_share_limit(")
        + extract_function("world_quest.c", "bool createQuestForGiverVnum(")
        + extract_function("world_quest.c", "bool createQuest(")
        + payment_context
        + extract_function("world_quest.c", "void resetQuest(")
        + extract_function("specs.mobile.c", "static void world_quest_report_creation_failure(")
        + extract_function("specs.mobile.c", "static void world_quest_refund_payment(")
        + extract_function("specs.mobile.c", "static void world_quest_payment_committed(")
        + SCENARIOS
    )
    build_root = ROOT / "bin/tests"
    build_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="world-quest-retries-", dir=build_root) as directory:
        path = Path(directory)
        source = path / "retries.cpp"
        binary = path / "retries"
        source.write_text(harness)
        subprocess.run(
            ["g++", "-std=c++20", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
             "-Isrc", str(source), "-o", str(binary)],
            cwd=ROOT, check=True,
        )
        subprocess.run([str(binary)], cwd=ROOT, check=True)
    print("world quest target retry runtime regression passed")


if __name__ == "__main__":
    main()
