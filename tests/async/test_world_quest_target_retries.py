#!/usr/bin/env python3
"""Real cached policy and creation against controlled reset/live-world fixtures."""

from pathlib import Path
import re
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function, source as repo_source


(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
share_limit = re.search(r"^world\.quest\.share\.max=(.+)$",
                        (ROOT / "lib/duris.properties").read_text(), re.MULTILINE).group(1)
with tempfile.TemporaryDirectory(prefix="quest-live-targets-", dir=ROOT / "bin/tests") as temporary:
    work = Path(temporary)
    adapters = work / "production_adapters.cpp"
    mobile = repo_source("specs.mobile.c").read_text()
    payment_context = mobile[mobile.index("enum class world_quest_payment_action"):
                             mobile.index("static void world_quest_report_creation_failure")]
    objects = repo_source("specs.object.c").read_text()
    set_context = objects[objects.index("typedef int (*set_func)"):
                          objects.index("void event_random_set_proc(")]
    set_table = objects[objects.index("struct set_data\n"):
                        objects.index("int set_proc(")]
    adapters.write_text(
        '#include "core/prototypes.h"\n#include "core/utils.h"\n'
        '#include "magic/spells.h"\n#include "world/map.h"\n'
        '#include "world/weather.h"\n#include "combat/justice.h"\n'
        '#include "world/world_quest_policy.h"\n#include "world/difficulty.h"\n#include "world/buildings.h"\n'
        '#include "persistence/persistence_checkpoint.h"\n'
        '#include "economy/currency_transaction.h"\n#include "sql/sql.h"\n'
        '#include "player/player_save_pipeline.h"\n'
        '#include "net/gmcp.h"\n#include "world/world_quest_policy_math.h"\n'
        '#include <ctime>\n#include "cmd/interp.h"\n#include "core/utility.h"\n#include "net/comm.h"\n#include "world/zone_story_quest_runtime.h"\n'
        'extern P_room world;\nextern P_index obj_index;\nextern zone_data *zone_table;\n'
        'extern int top_of_world;\nextern int CheckFor_remember(P_char, P_char);\n'
        'extern time_info_data time_info;\nextern const char *month_name[];\n'
        'bool aggressive_to_race(P_char, P_char);\nbool aggressive_to_class(P_char, P_char);\n'
        '#include "world/specs.prototypes.h"\n#include "world/vnum.obj.h"\n'
        '#include <cassert>\n'
        'extern int top_of_zone_table;\n'
        'void event_random_set_proc(P_char, P_char, P_obj, void *);\n'
        'void event_balance_affects(P_char, P_char, P_obj, void *);\n'
        'void event_object_proc(P_char, P_char, P_obj, void *);\n'
        + set_context + extract_function("specs.object.c", "int random_set(")
        + set_table + extract_function("specs.object.c", "int set_proc(")
        + payment_context + "\n".join(extract_function(file, signature) for file, signature in (
            ("cmd/interp.c", "void half_chop("),
            ("cmd/interp.c", "bool special("),
            ("world/handler.c", "bool isname(const char *str, const char *namelist)"),
            ("world/outposts.c", "bool check_castle_walls("),
            ("combat/range.c", "int check_wall("),
            ("core/utility.c", "bool ac_can_see_from("),
            ("core/utility.c", "bool has_native_planar_affinity_at("),
            ("core/utility.c", "bool aggressive_to_at("),
            ("world/world_quest.c", "static int world_quest_share_limit("),
            ("world/world_quest.c", "bool createQuestForGiverVnum("),
            ("world/world_quest.c", "world_quest_target_status world_quest_refresh("),
            ("world/world_quest.c", "bool world_quest_replace("),
            ("world/world_quest.c", "void resetQuest("),
            ("world/world_quest.c", "bool createQuest("),
            ("world/world_quest.c", "int quest_buy_map(P_char ch, world_quest_target_status"),
            ("world/world_quest.c", "void world_quest_describe("),
            ("world/world_quest.c", "void do_quest("),
            ("specs.mobile.c", "static void world_quest_report_creation_failure("),
            ("specs.mobile.c", "static void world_quest_refund_payment("),
            ("specs.mobile.c", "static void world_quest_payment_committed("),
            ("specs.mobile.c", "static bool world_quest_begin_progressed_abandon("),
            ("specs.mobile.c", "int world_quest(P_char"),
        )) + r'''
void assert_equipment_sets_ignore_ask(P_char actor)
{
    // Exercise every delegate in the production table, including real random/master
    // set callbacks. A new ASK-intercepting delegate must invalidate this audit.
    const int old_vnum = obj_index[0].virtual_number;
    obj_data item{};
    item.R_num = 0;
    item.short_description = const_cast<char *>("armor &+rfrom Fixture");
    char message[] = "target message";
    for (const auto &set : sets)
        for (int vnum : set.items)
        {
            if (!vnum)
                break;
            obj_index[0].virtual_number = vnum;
            item.loc_p = LOC_WORN;
            item.loc.wearing = actor;
            actor->equipment[WEAR_BODY] = &item;
            assert(!set_proc(&item, actor, CMD_ASK, message));
            actor->equipment[WEAR_BODY] = nullptr;
            item.loc_p = LOC_CARRIED;
            item.loc.carrying = actor;
            assert(!set_proc(&item, actor, CMD_ASK, message));
        }
    obj_index[0].virtual_number = old_vnum;
}
void run_payment(P_char player, int origin, int fee, bool committed)
{
    world_quest_payment_context payment{world_quest_payment_action::quest, fee, 9000, origin};
    world_quest_payment_committed(player, committed, {}, 0,
        reinterpret_cast<const uint8_t *>(&payment), sizeof(payment));
}
void run_map_payment(P_char player, int fee)
{
    world_quest_payment_context payment{world_quest_payment_action::map, fee, 9000, 1000};
    world_quest_payment_committed(player, true, {}, 0,
        reinterpret_cast<const uint8_t *>(&payment), sizeof(payment));
}
'''
    )
    binary = work / "targets"
    compile_command = [
        "g++", "-std=c++20", "-g", "-O1", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
        "-ffunction-sections", "-fdata-sections", "-fsanitize=address,undefined",
        "-fno-sanitize-recover=all", "-Isrc", "-Isrc/no_mysql", "-D__NO_MYSQL__",
        "tests/async/world_quest_live_targets_harness.cpp", str(HARNESS_STUBS),
        "src/world/world_quest_policy.c", "src/combat/forced_movement.c", "src/combat/trap.c",
        "src/core/safe_format.c",
        "src/specs/specs.set.c",
        "-Wl,--gc-sections",
    ]
    subprocess.run([*compile_command, str(adapters), "-o", str(binary)], cwd=ROOT, check=True)
    scenarios = [(level, "normal", "kill") for level in (10, 11, 29, 30, 40, 41, 49, 50)]
    # The target's prototype belongs to a different interval from its live zone,
    # keeping the destination average fixed while checking each level separately.
    scenarios += [(level, f"levels_{authored}_{live}", kind)
                  for level in (11, 29, 30, 49, 56)
                  for kind in ("ask", "kill")
                  for authored, live in (
                      (level - 5, level), (level, level - 5),
                      (level + 6, level), (level, level + 6),
                      (level - 4, level), (level, level - 4),
                      (level + 5, level), (level, level + 5),
                      (61, level), (level, 61), (62, level), (level, 62),
                      (63, level), (level, 63))]
    scenarios += [(30, "cosmetic", "ask")]
    scenarios += [(31, "diagnostics", "ask")]
    scenarios += [(level, "random_armor", "ask") for level in (23, 31)]
    scenarios += [(level, "replacement_level", kind)
                  for level in (23, 31, 46) for kind in ("ask", "kill")]
    scenarios += [(level, f"geography_{origin}_{family}", kind)
                  for origin in (1734, 74339)
                  for level in (11, 29, 30, 56)
                  for kind in ("ask", "kill")
                  for family in ("surface", "underdark", "foreign_surface", "foreign_underdark",
                                 "ambiguous_surface")]
    scenarios += [(29, f"zone_average_{average}", kind)
                  for average in (22, 23, 33, 34) for kind in ("ask", "kill")]
    scenarios += [(level, "validate", kind) for level in (11, 29, 30, 41) for kind in ("ask", "kill")]
    scenarios += [(level, "normal", "ask") for level in (11, 29, 30, 49, 50)]
    scenarios += [(level, "gear", kind) for level in (11, 29, 56) for kind in ("ask", "kill")]
    scenarios += [(level, "foreign", "kill") for level in (11, 29, 30)]
    scenarios += [(level, "mapless", "kill") for level in (40, 41)]
    scenarios += [(11, mode, "ask") for mode in (
        "rare", "conditional", "mixed", "random", "follower", "mount", "staging_release",
        "moved", "unspeaking", "invisible", "hidden", "aggressive", "silent", "sleeping", "zero",
    )]
    scenarios += [(11, mode, "kill") for mode in (
        "zero", "unroomed", "one_usable", "safe", "protected", "noexp", "summoned", "summon_kind",
        "charmed", "following", "no_reset",
        "no_reward", "no_level_window", "no_return", "history_error", "quota", "cross_zone_retry",
    )]
    scenarios += [(56, mode, "kill") for mode in (
        "history_cap", "history_cap_zones", "last_history", "last_history_zones",
        "probe_cap", "probe_cap_zones", "last_probe",
    )]
    for level, mode, kind in scenarios:
        result = subprocess.run([str(binary), str(level), mode, kind, share_limit], cwd=work,
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=15)
        if result.returncode:
            raise AssertionError(f"{level} {mode} {kind}:\n{result.stdout}")
        print(result.stdout.strip().splitlines()[-1])
    print(f"{len(scenarios)} production live-target/creation/payment scenarios passed")

    # Reuse the same production command/selector fixture with the real SQL
    # history cache. Only the clock and SQL transport are controlled here.
    sql = repo_source("sql/sql.c").read_text()
    history_start = sql.index("struct world_quest_history\n")
    history = sql[history_start:sql.index("const char *sql_select_IP_info(", history_start)]
    publication_start = sql.index("struct world_quest_reward_publication\n")
    publication = sql[publication_start:sql.index("// End world quest reward publication.", publication_start)]
    finish = sql[sql.index("bool sql_world_quest_finish_async("):]
    history += "\n#undef __NO_MYSQL__\n" + publication + finish + "\n#define __NO_MYSQL__\n"
    sql_adapters = work / "sql_history_adapters.cpp"
    sql_adapters.write_text(adapters.read_text() + r'''
#include "sql/sql_async.h"
#include "net/unicode.h"
#include "player/player_snapshot_capture.h"
#include "player/player_load_items.h"
#include "item/item_ownership_runtime.h"
#include <cstdarg>
#include <cassert>
#include <unordered_set>
#include <unordered_map>
extern int history_writes;
static time_t history_clock = 20000LL * 86400 + 86399;
static std::vector<int64_t> history_stamps;
static std::vector<player_pending_world_quest> history_extra;
static std::function<void(bool, const sql_rows &)> history_callback;
static sql_rows history_rows;
static std::function<void(bool, const sql_rows &)> parked_history_callback;
static sql_rows parked_history_rows;
static int history_level = 30;
static bool history_reject_writes = false;
static bool history_defer_writes = false;
static P_char history_pending_actor = nullptr;
static player_pending_world_quest history_pending_quest;
static std::function<bool(P_char, const player_pending_world_quest &)> history_pending_done;
extern P_obj object_list;
bool item_ownership_runtime_hydrate_many_atomic(const item_ownership_runtime_entry *, size_t)
{
    return false;
}
bool player_load_item_graph_materialize_detached(
    const std::vector<player_item_snapshot> &, const std::vector<player_load_item_identity> &,
    const item_owner_identity &, uint64_t, bool, bool, std::vector<P_obj> *,
    player_load_item_materialize_metrics *)
{
    return false;
}
static time_t quest_test_time(time_t *out)
{
    if (out) *out = history_clock;
    return history_clock;
}
std::string sql_format(const char *format, ...)
{
    char text[8192];
    va_list args;
    va_start(args, format);
    const int size = vsnprintf(text, sizeof(text), format, args);
    va_end(args);
    assert(size >= 0 && static_cast<size_t>(size) < sizeof(text));
    return text;
}
bool sql_read_at(persistence_query_site, std::string query,
                 std::function<void(bool, const sql_rows &)> done)
{
    assert(!history_callback);
    const bool timestamps = query.find("UNIX_TIMESTAMP(timestamp)") != std::string::npos;
    assert(timestamps || query.find("TO_DAYS(timestamp)") != std::string::npos);
    history_rows.clear();
    int target = 999000;
    for (int64_t stamp : history_stamps)
        history_rows.push_back({{std::to_string(++target), std::to_string(history_level),
            std::to_string(timestamps ? stamp : stamp / 86400 == history_clock / 86400)}});
    for (const auto &quest : history_extra)
        history_rows.push_back({{std::to_string(quest.target), std::to_string(quest.level),
            std::to_string(timestamps ? quest.occurred_at : quest.occurred_at / 86400 == history_clock / 86400)}});
    history_callback = std::move(done);
    return true;
}
bool sql_queue_at(persistence_query_site, const char *, ...)
{
    ++history_writes;
    return !history_reject_writes;
}
char *mysql_str(const char *text, char *out)
{
    strcpy(out, text);
    return out;
}
P_char find_player_by_pid(int) { return nullptr; }
int difficulty_scale_world_quest_allowance(int value) { return value; }
#define time quest_test_time
''' + history + r'''
#undef time
static void publish_history(bool ok = true)
{
    assert(history_callback);
    auto callback = std::move(history_callback);
    history_callback = {};
    callback(ok, history_rows);
}
bool player_save_pipeline_world_quest_pending(int)
{
    return bool(history_pending_done);
}
player_snapshot_capture_result player_item_snapshot_tree_capture(
    P_obj, std::vector<player_item_snapshot> *, size_t *)
{
    return player_snapshot_capture_result::invalid_identity;
}
void quest_test_finish_history_write(bool committed)
{
    assert(history_pending_done);
    if (!committed) return; // the real pipeline retains and retries the capture
    auto done = std::move(history_pending_done);
    history_pending_done = {};
    history_extra.push_back(history_pending_quest);
    assert(done(history_pending_actor, history_pending_quest));
    if (history_callback) publish_history();
}
bool player_save_pipeline_submit_world_quest(
    P_char ch, const player_pending_world_quest &quest,
    std::function<bool(P_char, const player_pending_world_quest &)> done)
{
    ++history_writes;
    if (history_reject_writes) return false;
    assert(!history_pending_done);
    history_pending_actor = ch;
    history_pending_quest = quest;
    history_pending_done = std::move(done);
    if (!history_defer_writes) quest_test_finish_history_write(true);
    return true;
}
void quest_test_history_empty(P_char ch)
{
    history_level = GET_LEVEL(ch) >= 50 ? 30 : GET_LEVEL(ch);
    history_stamps.clear();
    history_extra.clear();
    sql_world_quest_history_load(ch);
    publish_history();
}
void quest_test_history_begin_rollover(P_char ch, int completed)
{
    world_quest_histories.clear();
    history_extra.clear();
    history_stamps.assign(completed, history_clock - 60);
    sql_world_quest_history_load(ch);
}
void quest_test_history_advance()
{
    history_clock += 2;
}
void quest_test_refuse_history_writes()
{
    history_reject_writes = true;
}
void quest_test_defer_history_write()
{
    history_defer_writes = true;
}
void quest_test_park_history_read()
{
    assert(history_callback && !parked_history_callback);
    parked_history_callback = std::move(history_callback);
    history_callback = {};
    parked_history_rows = history_rows;
}
void quest_test_publish_parked_history()
{
    assert(parked_history_callback);
    auto callback = std::move(parked_history_callback);
    parked_history_callback = {};
    callback(true, parked_history_rows);
}
void quest_test_history_publish(int seconds, bool ok)
{
    history_clock += seconds;
    publish_history(ok);
}
''')
    sql_binary = work / "sql-history-targets"
    subprocess.run([*compile_command, "-DWORLD_QUEST_SQL_HISTORY", str(sql_adapters),
                    "-o", str(sql_binary)], cwd=ROOT, check=True)
    history_failures = []
    for level in (30, 56):
        for mode in ("history_rollover", "history_same_day", "history_unready",
                     "history_failed_read", "history_write_rollover", "history_write_failure",
                     "history_write_pending", "history_stale_read"):
            result = subprocess.run([str(sql_binary), str(level), mode, "kill", share_limit],
                                    cwd=work, text=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, timeout=15)
            print(result.stdout)
            if result.returncode:
                history_failures.append((level, mode))
    assert not history_failures, history_failures
