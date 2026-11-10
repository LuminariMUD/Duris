#!/usr/bin/env python3
"""Run the production level gain and loss bodies: re-earning a level adds no base HP (#899)."""

from pathlib import Path
import subprocess
import tempfile

from _paths import HARNESS_STUBS, ROOT, extract_function


ADVANCE = extract_function(
    "limits.c",
    "static void advance_level_impl(P_char ch, bool notify_player, bool process_boons,\n"
    "\t\t\t       std::uint64_t threshold_xp)\n{",
)
LOSE = extract_function(
    "limits.c",
    "static void lose_level_impl(P_char ch, std::uint64_t threshold_xp,\n"
    "\t\t\t    telemetry_progression_source source,\n"
    "\t\t\t    telemetry_progression_reason reason)\n{",
)
THRESHOLD = extract_function("limits.c", "int death_exp_loss_level_threshold(")
NOTIFY = extract_function("limits.c", "static void notify_level_advancement(")

HARNESS = f"""
#include <cassert>
#include <cstdint>
#include "core/prototypes.h"
#include "core/utils.h"
#include "economy/boon.h"
#include "economy/nexus_stones.h"
#include "guild/assocs.h"
#include "net/gmcp.h"
#include "persistence/persistence_checkpoint.h"
#include "telemetry/telemetry_runtime.h"
#include "world/hardcore_config.h"

int roll = 0;
bool hardcore_loss_allowed = true;
const char *PLAYERLOG = "player";

int number(int, int) {{ return roll; }}
int get_property(const char *, int fallback) {{ return fallback; }}
int GET_CLASS(P_char, uint) {{ return 0; }}
int GET_PRIME_CLASS(P_char, uint) {{ return 0; }}
int GET_SECONDARY_CLASS(P_char, uint) {{ return 0; }}
bool Guild::save() {{ return true; }}
void send_to_char(const char *, P_char) {{}}
void send_to_char(const char *, P_char, int) {{}}
void send_to_char_f(P_char, const char *, ...) {{}}
void logit(const char *, const char *, ...) {{}}
void sql_update_level(P_char) {{}}
void sql_log(P_char, const char *, const char *, ...) {{}}
void update_skills(P_char) {{}}
void update_pos(P_char) {{}}
void check_boon_completion(P_char, P_char, double, int) {{}}
void githyanki_weapon(P_char) {{}}
void gmcp_char_status(P_char) {{}}
void update_group_vitals(P_char) {{}}
void persistence_schedule_level_checkpoint(P_char, int, int, const char *) {{}}
int forget_spells(P_char, int) {{ return 0; }}
bool hardcore_config_level_loss_allowed(int) {{ return hardcore_loss_allowed; }}
int check_nexus_bonus(P_char, int amount, int) {{ return amount; }}
char affect_total(P_char, int) {{ return 0; }}
void balance_affects(P_char) {{}}
telemetry_capture_result telemetry_runtime_game_progression(
    P_char, P_desc, telemetry_progression_observation) {{ return {{}}; }}

{THRESHOLD}
{NOTIFY}
{ADVANCE}
{LOSE}

struct Player {{
    pc_only_data pc{{}};
    char_data ch{{}};
    Player(int race, int level, int base_hit)
    {{
        ch.only.pc = &pc;
        ch.player.race = race;
        ch.player.level = level;
        ch.points.base_hit = base_hit;
        ch.points.base_mana = 50;
    }}
    void lose()
    {{
        lose_level_impl(&ch, 0U, telemetry_progression_source::system,
                        telemetry_progression_reason::system_adjustment);
    }}
    void gain() {{ advance_level_impl(&ch, false, false, 0U); }}
}};

int main()
{{
    for (int race : {{RACE_HUMAN, RACE_ILLITHID}}) {{
        // 26 is the boundary: loss tests the level left, gain the level reached.
        for (int level : {{26, 27, 30, 50, 56}}) {{
            Player player(race, level, 100);
            player.lose();
            assert(player.ch.player.level == level - 1);
            assert(player.ch.points.base_hit == 99);
            player.gain();
            assert(player.ch.player.level == level);
            assert(player.ch.points.base_hit == 100);
            assert(player.ch.points.base_mana == 50);
        }}

        Player cycled(race, 30, 100);
        for (int cycle = 0; cycle < 100; ++cycle) {{
            cycled.lose();
            cycled.gain();
        }}
        assert(cycled.ch.player.level == 30);
        assert(cycled.ch.points.base_hit == 100);
    }}

    // Below 26 the existing fixed loss and rolled gain stay as they were.
    for (roll = 0; roll <= 3; ++roll) {{
        Player human(RACE_HUMAN, 25, 100);
        human.lose();
        assert(human.ch.points.base_hit == 97);
        human.gain();
        assert(human.ch.points.base_hit == 98 + roll);
        assert(human.ch.points.base_mana == 47 + roll);

        Player illithid(RACE_ILLITHID, 25, 100);
        illithid.lose();
        illithid.gain();
        assert(illithid.ch.points.base_hit == 98);
    }}
    roll = 0;

    Player floor(RACE_HUMAN, 30, 1);
    floor.lose();
    assert(floor.ch.points.base_hit == 1);

    // A refused hardcore loss must not take the HP either.
    Player hardcore(RACE_HUMAN, 30, 100);
    SET_BIT(hardcore.ch.specials.act2, PLR2_HARDCORE_CHAR);
    hardcore_loss_allowed = false;
    hardcore.lose();
    assert(hardcore.ch.player.level == 30);
    assert(hardcore.ch.points.base_hit == 100);
    return 0;
}}
"""

directory = ROOT / "bin/tests"
directory.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="level-loss-base-hp-", dir=directory) as temporary:
    root = Path(temporary)
    harness = root / "level_loss_base_hp.cpp"
    binary = root / "level_loss_base_hp"
    harness.write_text(HARNESS, encoding="utf-8")
    subprocess.run(
        ["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Og", "-g",
         "-fsanitize=address,undefined", "-fno-pie", "-no-pie", "-Isrc",
         str(harness), "src/telemetry/telemetry_progression.c", str(HARNESS_STUBS),
         "-o", str(binary)],
        check=True, cwd=ROOT, timeout=180,
    )
    subprocess.run([str(binary)], check=True, timeout=30)

print("level loss and regain base HP regression passed")
