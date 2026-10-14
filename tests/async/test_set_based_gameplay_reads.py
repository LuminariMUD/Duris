#!/usr/bin/env python3
"""Runtime and source contracts for set-based PvP and epic-task reads."""

from _paths import SRC, rel, extract_function, HARNESS_STUBS
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = (SRC / "player_load_repository.c").read_text()
MATERIALIZE = (SRC / "player_load_materialize.c").read_text()
FIGHT = (SRC / "fight.c").read_text()
EPIC = (SRC / "epic.c").read_text()
COMM = (SRC / "comm.c").read_text()
COPYOVER = (SRC / "copyover.c").read_text()

HARNESS = r'''
#include "world/epic_task_catalog.h"
#include "persistence/gameplay_read_state.h"

#include <cassert>
#include <cstdint>

int real_zone0(const int zone) { return zone == 999 ? -1 : zone; }

int number(int from, int to)
{
    static uint32_t state = 0x8a5cd789U;
    if (from == to)
        return from;
    state ^= state << 13;
    state ^= state >> 17;
    state ^= state << 5;
    return from + static_cast<int>(state % static_cast<uint32_t>(to - from + 1));
}

int main()
{
    gameplay_read_state state = {};
    int seconds = 0;
    assert(!gameplay_read_state_heaven_seconds(&state, 5000, 100, &seconds));

    const int64_t deaths[] = {4999, 4900, 1401, 1400};
    const int32_t completed[] = {20};
    assert(gameplay_read_state_publish(&state, deaths, 4, completed, 1));
    assert(gameplay_read_state_recent_count(&state, 5000) == 3);
    assert(gameplay_read_state_heaven_seconds(&state, 5000, 100, &seconds));
    assert(seconds == 400);
    assert(gameplay_read_state_heaven_seconds(&state, 5000, 500, &seconds));
    assert(seconds == 48000);

    const int64_t ascending[] = {10, 11};
    assert(!gameplay_read_state_publish(&state, ascending, 2, completed, 1));
    assert(gameplay_read_state_recent_count(&state, 5000) == 3);
    assert(gameplay_read_state_zone_completed(&state, 20));
    assert(!gameplay_read_state_zone_completed(&state, 30));
    assert(gameplay_read_state_add_completed_zone(&state, 30));
    assert(gameplay_read_state_add_completed_zone(&state, 30));
    assert(state.completed_zone_count == 2);

    const uint64_t rejected = gameplay_read_state_add_provisional(&state, 5001);
    assert(rejected && gameplay_read_state_recent_count(&state, 5001) == 3);
    assert(gameplay_read_state_finish_provisional(&state, rejected, false));
    assert(gameplay_read_state_recent_count(&state, 5001) == 2);
    const uint64_t committed = gameplay_read_state_add_provisional(&state, 5002);
    assert(committed && gameplay_read_state_finish_provisional(&state, committed, true));
    assert(gameplay_read_state_recent_count(&state, 5002) == 3);
    assert(!gameplay_read_state_finish_provisional(&state, committed, true));

    epic_task_catalog_reset_for_tests();
    epic_task_selection_status status = epic_task_selection_status::selected;
    assert(epic_task_catalog_select(&state, &status) == -1);
    assert(status == epic_task_selection_status::unavailable);
    assert(!epic_task_catalog_publish(nullptr, 0));
    assert(!epic_task_catalog_ready());
    const int32_t zones[] = {10, 20, 30, 40};
    assert(epic_task_catalog_publish(zones, 4));
    assert(epic_task_catalog_ready() && epic_task_catalog_size() == 4);
    assert(!epic_task_catalog_publish(nullptr, 0));
    assert(epic_task_catalog_ready() && epic_task_catalog_size() == 4);
    gameplay_read_state unavailable = {};
    assert(epic_task_catalog_select(&unavailable, &status) == -1);
    assert(status == epic_task_selection_status::unavailable);
    const int32_t invalid[] = {10, 999};
    assert(!epic_task_catalog_publish(invalid, 2));
    const int32_t duplicate[] = {10, 10};
    assert(!epic_task_catalog_publish(duplicate, 2));
    assert(epic_task_catalog_size() == 4);

    int selected_10 = 0;
    int selected_other = 0;
    for (int index = 0; index < 12000; ++index)
    {
        const int selected = epic_task_catalog_select(&state, &status);
        assert(status == epic_task_selection_status::selected);
        assert(selected == 10 || selected == 40);
        if (selected == 10)
            ++selected_10;
        else
            ++selected_other;
    }
    assert(selected_10 > 4800 && selected_10 < 7200);
    assert(selected_other > 4800 && selected_other < 7200);
    assert(gameplay_read_state_add_completed_zone(&state, 10));
    assert(gameplay_read_state_add_completed_zone(&state, 40));
    assert(epic_task_catalog_select(&state, &status) == -1);
    assert(status == epic_task_selection_status::exhausted);
    return 0;
}
'''

with tempfile.TemporaryDirectory(prefix="duris-gameplay-reads-") as temp_dir:
    source = Path(temp_dir) / "gameplay_reads_test.cpp"
    binary = Path(temp_dir) / "gameplay_reads_test"
    source.write_text(HARNESS)
    subprocess.run(
        [
            "g++", "-std=c++20", "-Wall", "-Wextra", "-Wpedantic",
            "-D__NO_MYSQL__", "-Isrc", str(source),
            rel("gameplay_read_state.c"), rel("epic_task_catalog.c"),
            "-o", str(binary),
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run([str(binary)], check=True, timeout=10)

player_load_header = (SRC / "player_load_repository.h").read_text()
assert "PLAYER_LOAD_QUERY_MAX = 23;" in player_load_header
assert "FROM pkill_info pi JOIN pkill_event pe" in REPOSITORY
assert "ORDER BY pe.stamp DESC, pi.id DESC LIMIT 20" in REPOSITORY
assert "FROM epic_gain" in REPOSITORY and "UNION" in REPOSITORY
assert "load_gameplay_reads(connection, &result)" in REPOSITORY
assert "gameplay_read_state_publish" in MATERIALIZE
assert "PLAYER_LOAD_SESSION04_READS" in MATERIALIZE

heaven = FIGHT[FIGHT.index("void setHeavenTime") : FIGHT.index("static combat_outcome_participant")]
assert "gameplay_read_state_heaven_seconds" in heaven
assert "qry(" not in heaven and "mysql_" not in heaven and "redis_" not in heaven
assert "gameplay_read_state_add_provisional" in FIGHT
assert "gameplay_read_state_finish_provisional" in FIGHT

task = EPIC[
    EPIC.index("int epic_random_task_zone") : EPIC.index("void epic_choose_new_epic_task")
]
assert "epic_task_catalog_select" in task
assert "ORDER BY RAND" not in task and "qry(" not in task and "mysql_" not in task
assert "gameplay_read_state_add_completed_zone" in EPIC
assert "epic_task_catalog_refresh" in COMM
assert "include_gameplay_reads" not in COPYOVER

print("set-based PvP and epic-task read contracts passed")


# Exercise both award entry points and task assignment from the production source,
# including the actual snapshot capture/codec used to save deferred assignments.
ASSIGNMENT_HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/files.h"
#include "world/epic.h"
#include "world/epic_transaction.h"
#include "world/epic_task_catalog.h"
#include "player/player_snapshot_capture.h"
#include "player/player_snapshot_codec.h"
#include "persistence/persistence_checkpoint.h"
#include "magic/spells.h"
#include "economy/nexus_stones.h"
#include <cassert>
#include <cstring>
#include <string>
#include <vector>

int errand_notch = 200;
zone_data zones[2] = {};
zone_data *zone_table = zones;
Skill skills[MAX_SKILLS] = {};
P_index obj_index = nullptr, mob_index = nullptr;
P_room world = nullptr;
int top_of_objt = 0, top_of_mobt = 0;
extern const int top_of_world = -1;
static int task_roll = 1, alternative_roll = 100, roll_count = 0, logs = 0, dirty = 0;
static std::string captured_messages;
static P_obj enemy_nexus = nullptr;
int real_zone0(const int zone) { return zone == 10 ? 0 : zone == 20 ? 1 : -1; }
int number(int from, int to)
{
    if (from == 0 && to == 19) { ++roll_count; return task_roll; }
    if (from == 1 && to == 100) return alternative_roll;
    return from;
}
void send_to_char(const char *text, P_char) { captured_messages += text; }
void logit(const char *, const char *, ...) { ++logs; }
void epiclog(int, const char *, ...) {}
void epic_bonus_record_gain(P_char, int, int) {}
void epic_free_level(P_char) { assert(false); }
int get_property(const char *, int fallback) { return fallback; }
P_obj get_random_enemy_nexus(P_char) { return enemy_nexus; }
bool training_dummy_capture_target_allowed(P_char) { return true; }
void mark_player_dirty_components(int pid, player_component_mask_t components)
{
    assert(pid == 42 && components == PLAYER_COMPONENT_AFFECTS);
    ++dirty;
}
affected_type *get_spell_from_char(P_char ch, int type, void *, int)
{
    for (auto *af = ch->affected; af; af = af->next)
        if (af->type == type) return af;
    return nullptr;
}
affected_type *affect_to_char(P_char ch, affected_type *af)
{
    auto *copy = new affected_type(*af);
    copy->next = ch->affected;
    return ch->affected = copy;
}
void affect_remove(P_char ch, affected_type *af)
{
    auto **link = &ch->affected;
    while (*link != af) { assert(*link); link = &(*link)->next; }
    *link = af->next;
    delete af;
}
// PRODUCTION_FUNCTIONS

static void clear(P_char ch)
{
    while (ch->affected) affect_remove(ch, ch->affected);
    captured_messages.clear(); logs = dirty = roll_count = 0;
    task_roll = 1; alternative_roll = 100; enemy_nexus = nullptr;
}
static bool pending(P_char ch) { return get_spell_from_char(ch, TAG_EPIC_TASK_PENDING); }
static void award(P_char ch, bool pvp, int amount)
{
    if (pvp) epic_publish_pvp_award(ch, amount);
    else {
        const epic_award_context context = {EPIC_QUEST, 0, amount, false, false};
        epic_award_committed(ch, true, {}, 0,
                             reinterpret_cast<const uint8_t *>(&context), sizeof(context));
    }
}
static void save_and_restore(P_char ch)
{
    for (int intent : {RENT_CRASH, RENT_QUIT, RENT_DEATH}) {
        player_snapshot snapshot;
        assert(player_snapshot_capture(ch, 1, PLAYER_COMPONENT_AFFECTS, intent, 0,
                                       &snapshot) == player_snapshot_capture_result::ok);
        std::vector<uint8_t> bytes;
        assert(player_snapshot_encode(snapshot, &bytes) == player_snapshot_codec_result::ok);
        player_snapshot loaded;
        assert(player_snapshot_decode(bytes.data(), bytes.size(), &loaded) == player_snapshot_codec_result::ok);
        while (ch->affected) affect_remove(ch, ch->affected);
        for (const auto &row : loaded.affects) {
            affected_type af = {};
            af.type = row.type; af.modifier = row.modifier;
            af.flags = row.flags; af.duration = row.duration;
            affect_to_char(ch, &af);
        }
        auto *af = get_spell_from_char(ch, TAG_EPIC_TASK_PENDING);
        assert(af && af->duration == -1 && af->flags == (AFFTYPE_STORE | AFFTYPE_PERM));
    }
}
int main()
{
    char_data ch = {};
    pc_only_data pc = {};
    ch.only.pc = &pc; pc.pid = 42;
    ch.player.level = 51; ch.specials.position = STAT_RESTING;
    ch.player.name = const_cast<char *>("TaskTest");
    zones[0].name = const_cast<char *>("First");
    zones[1].name = const_cast<char *>("Second");
    const int32_t catalogue[] = {10, 20};
    const int32_t completed[] = {10};
    assert(gameplay_read_state_publish(&pc.gameplay_reads, nullptr, 0, completed, 1));

    for (bool pvp : {false, true}) {
        clear(&ch);
        epic_task_catalog_reset_for_tests();
        award(&ch, pvp, 199);
        assert(!has_epic_task(&ch) && !pending(&ch));
        award(&ch, pvp, 1);
        assert(pending(&ch) && !has_epic_task(&ch) && dirty == 1);
        assert(get_spell_from_char(&ch, TAG_EPICS_GAINED)->modifier == 200);
        assert(captured_messages.find("assigned automatically") != std::string::npos);
        const auto initial_messages = captured_messages;
        task_roll = 0;
        for (int retry = 0; retry < 100; ++retry) epic_choose_new_epic_task(&ch);
        assert(pending(&ch) && !has_epic_task(&ch) && roll_count == 1);
        assert(logs == 1 && dirty == 1 && captured_messages == initial_messages);
        // Crossing further notches still retains only the one outstanding task.
        award(&ch, pvp, 500);
        assert(get_spell_from_char(&ch, TAG_EPICS_GAINED)->modifier == 700);
        assert(logs == 1 && roll_count == 1);
        save_and_restore(&ch);
        assert(epic_task_catalog_publish(catalogue, 2));
        epic_choose_new_epic_task(&ch);
        assert(!pending(&ch) && get_epic_task(&ch)->modifier == 20 && dirty == 2);
        epic_choose_new_epic_task(&ch);
        assert(get_epic_task(&ch)->modifier == 20 && dirty == 2 && roll_count == 1);
    }

    // The 5% roll does not need a catalogue or a ready per-player snapshot.
    for (bool reads_ready : {false, true}) {
        clear(&ch);
        epic_task_catalog_reset_for_tests();
        if (reads_ready) assert(gameplay_read_state_publish(&pc.gameplay_reads, nullptr, 0, nullptr, 0));
        else pc.gameplay_reads = {};
        task_roll = 0;
        epic_choose_new_epic_task(&ch);
        assert(get_epic_task(&ch)->modifier == SPILL_BLOOD && !pending(&ch));
        affect_remove(&ch, get_epic_task(&ch));
        obj_data nexus = {};
        STONE_ID(&nexus) = 1;
        enemy_nexus = &nexus; alternative_roll = 1;
        epic_choose_new_epic_task(&ch);
        assert(get_epic_task(&ch)->modifier == SPILL_BLOOD + 1 && !pending(&ch));
    }
    // With an available catalogue the 20 equally likely task rolls yield 19 zone tasks.
    clear(&ch);
    assert(epic_task_catalog_publish(catalogue, 2));
    int zone_tasks = 0, blood_tasks = 0;
    for (task_roll = 0; task_roll < 20; ++task_roll) {
        epic_choose_new_epic_task(&ch);
        auto *task = get_epic_task(&ch);
        assert(task && !pending(&ch));
        zone_tasks += task->modifier == 20;
        blood_tasks += task->modifier == SPILL_BLOOD;
        affect_remove(&ch, task);
    }
    assert(zone_tasks == 19 && blood_tasks == 1);
    // Exhaustion remains a deliberate alternative; unavailable player data waits.
    clear(&ch);
    assert(gameplay_read_state_publish(&pc.gameplay_reads, nullptr, 0, catalogue, 2));
    epic_choose_new_epic_task(&ch);
    assert(get_epic_task(&ch)->modifier == SPILL_BLOOD);
    clear(&ch);
    pc.gameplay_reads = {};
    epic_choose_new_epic_task(&ch);
    assert(pending(&ch) && !has_epic_task(&ch));
    assert(gameplay_read_state_publish(&pc.gameplay_reads, nullptr, 0, completed, 1));
    task_roll = 0;
    epic_choose_new_epic_task(&ch);
    assert(!pending(&ch) && get_epic_task(&ch)->modifier == 20);

    clear(&ch);
}
'''

assignment_functions = EPIC[EPIC.index("struct epic_award_context") : EPIC.index("struct epic_level_context")]
for signature in (
    "struct affected_type *get_epic_task(", "bool has_epic_task(",
    "int epic_random_task_zone(", "void epic_choose_new_epic_task(",
    "const char *epic_award_name(", "void epic_award_committed(",
    "void epic_publish_pvp_award(",
):
    assignment_functions += extract_function("epic.c", signature) + "\n"
assignment_functions = extract_function("achievements.c", "affected_type *apply_achievement(") + "\n" + assignment_functions

build = ROOT / "bin/tests/epic-task-assignment"
build.mkdir(parents=True, exist_ok=True)
source = build / "regression.cpp"
binary = build / "regression"
source.write_text(ASSIGNMENT_HARNESS.replace("// PRODUCTION_FUNCTIONS", assignment_functions))
subprocess.run([
    "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
    "-g", "-O1", "-fsanitize=address,undefined", "-ffunction-sections", "-fdata-sections",
    "-D__NO_MYSQL__", "-Isrc", str(source),
    rel("gameplay_read_state.c"), rel("epic_task_catalog.c"),
    rel("player_snapshot_capture.c"), rel("player_snapshot_codec.c"),
    rel("constant.c"),
    rel("pet_restore_state.c"), rel("pet_restore_runtime.c"),
    rel("item_ownership_runtime.c"), rel("item_transfer_command.c"),
    rel("critical_command.c"), str(HARNESS_STUBS),
    "-Wl,--gc-sections", "-lcrypto", "-o", str(binary),
], cwd=ROOT, check=True)
subprocess.run([str(binary)], check=True, timeout=30)

point_update = extract_function("limits.c", "void point_update(void)")
assert "if (affected_by_spell(i, TAG_EPIC_TASK_PENDING))\n\t\t\tepic_choose_new_epic_task(i);" in point_update
assert point_update.index("epic_choose_new_epic_task(i)") < point_update.index("gain_condition(i,")
assert 'TAG_CREATE("pending epic task", TAG_EPIC_TASK_PENDING)' in (SRC / "skills.c").read_text()
print("epic assignment: both award paths, saved pending tasks, retry, exhaustion and 95/5 rolls passed")
