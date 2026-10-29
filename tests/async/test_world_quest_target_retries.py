#!/usr/bin/env python3
"""Real cached policy and creation against controlled reset/live-world fixtures."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function, source as repo_source


(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="quest-live-targets-", dir=ROOT / "bin/tests") as temporary:
    work = Path(temporary)
    adapters = work / "production_adapters.cpp"
    mobile = repo_source("specs.mobile.c").read_text()
    payment_context = mobile[mobile.index("enum class world_quest_payment_action"):
                             mobile.index("static void world_quest_report_creation_failure")]
    adapters.write_text(
        '#include "core/prototypes.h"\n#include "core/utils.h"\n'
        '#include "magic/spells.h"\n#include "world/map.h"\n'
        '#include "world/weather.h"\n#include "combat/justice.h"\n'
        '#include "world/world_quest_policy.h"\n#include "world/difficulty.h"\n'
        '#include "persistence/persistence_checkpoint.h"\n'
        '#include "economy/currency_transaction.h"\n#include "sql/sql.h"\n'
        '#include "net/gmcp.h"\n#include "world/world_quest_policy_math.h"\n'
        '#include <ctime>\n'
        'extern P_room world;\nextern P_index obj_index;\nextern zone_data *zone_table;\n'
        'extern int top_of_world;\nextern int CheckFor_remember(P_char, P_char);\n'
        'extern time_info_data time_info;\n'
        'bool aggressive_to_race(P_char, P_char);\nbool aggressive_to_class(P_char, P_char);\n'
        + payment_context + "\n".join(extract_function(file, signature) for file, signature in (
            ("world/outposts.c", "bool check_castle_walls("),
            ("combat/range.c", "int check_wall("),
            ("core/utility.c", "bool ac_can_see_from("),
            ("core/utility.c", "bool has_native_planar_affinity_at("),
            ("core/utility.c", "bool aggressive_to_at("),
            ("world/world_quest.c", "static int world_quest_share_limit("),
            ("world/world_quest.c", "bool createQuestForGiverVnum("),
            ("world/world_quest.c", "void resetQuest("),
            ("world/world_quest.c", "bool createQuest("),
            ("world/world_quest.c", "int quest_buy_map("),
            ("specs.mobile.c", "static void world_quest_report_creation_failure("),
            ("specs.mobile.c", "static void world_quest_refund_payment("),
            ("specs.mobile.c", "static void world_quest_payment_committed("),
        )) + r'''
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
    subprocess.run([
        "g++", "-std=c++20", "-g", "-O1", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
        "-ffunction-sections", "-fdata-sections", "-fsanitize=address,undefined",
        "-fno-sanitize-recover=all", "-Isrc", "-Isrc/no_mysql", "-D__NO_MYSQL__",
        "tests/async/world_quest_live_targets_harness.cpp", str(adapters), str(HARNESS_STUBS),
        "src/world/world_quest_policy.c", "src/combat/forced_movement.c", "src/combat/trap.c",
        "-Wl,--gc-sections", "-o", str(binary),
    ], cwd=ROOT, check=True)
    scenarios = [(level, "normal", "kill") for level in (10, 11, 29, 30, 40, 41, 49, 50)]
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
        result = subprocess.run([str(binary), str(level), mode, kind], cwd=work,
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=15)
        if result.returncode:
            raise AssertionError(f"{level} {mode} {kind}:\n{result.stdout}")
        print(result.stdout.strip().splitlines()[-1])
    print(f"{len(scenarios)} production live-target/creation/payment scenarios passed")
