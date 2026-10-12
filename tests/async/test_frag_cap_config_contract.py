#!/usr/bin/env python3
"""Source contract for configurable frag-cap behavior."""
from _paths import SRC
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"

config = (LIB / "frag_cap.cfg").read_text()
header = (SRC / "frag_cap_config.h").read_text()
impl = (SRC / "frag_cap_config.c").read_text()
sql = (SRC / "sql.c").read_text()
sql_h = (SRC / "sql.h").read_text()
comm = (SRC / "comm.c").read_text()
redis = (SRC / "redis.c").read_text()
report_cache = (SRC / "redis_report_cache.c").read_text()
fraglist = (SRC / "fraglist.c").read_text()
limits = (SRC / "limits.c").read_text()
makefile = (SRC / "Makefile").read_text()
maintenance = (SRC / "maintenance_repository.c").read_text()

assert "frag_cap_config.o" in makefile
assert "boot_frag_cap_config" in comm
assert "frag_cap_config.h" in sql
assert "frag_cap_config_get" in sql
assert "FRAG_LEVEL_RATIO" not in sql_h
assert "FRAGS_TO_LEVEL" not in sql_h

for key in (
    "cap.floor.level",
    "cap.reset.level",
    "cap.maximum.level",
    "timer.unlock.days",
    "unlock.victim.levels.below.open",
    "unlock.minimum.share.points",
    "hardcore.levels.beyond.cap",
):
    assert key + "=" in config, key
    assert '"' + key + '"' in impl, key

for token in (
    "cap_floor_level",
    "cap_reset_level",
    "cap_maximum_level",
    "unlock_timer_days",
    "unlock_victim_levels_below",
    "unlock_minimum_share_points",
    "hardcore_levels_beyond_cap",
):
    assert token in header, token
    assert token in impl, token

# Frag thresholds, per-level timers and the unlock boon are gone.
for retired in (
    "cap.frag.base.level", "cap.level.step", "cap.frags.per.level", "timer.default.days",
    "timer.circle.level", "timer.level.5", "boon.duration.minutes", "boon.bonus",
):
    assert retired not in config, retired
    assert retired not in impl, retired
for retired in ("frags_for_level", "cap_level_from_frags", "frag_cap_config_timer_days",
                "frag_cap_config_reset_timer_days", "boon_duration", "boon_bonus"):
    assert retired not in header, retired
    assert retired not in fraglist + report_cache + maintenance + sql, retired

assert "cap.reset.level=30" in config
assert "timer.unlock.days=3" in config
assert "unlock.victim.levels.below.open=5" in config
assert "unlock.minimum.share.points=20" in config
assert "hardcore.levels.beyond.cap=2" in config
assert "frag_cap_config_hardcore_level_cap" in limits
assert "IS_HARDCORE(ch)" in limits
assert "sql_level_cap(GET_RACEWAR(ch))" in limits

# Each side has its own cap; other sides have the level open to all.
level_cap = sql[sql.index("int sql_level_cap(int racewar_side)"):]
level_cap = level_cap[:level_cap.index("\n}\n")]
assert "RACEWAR_GOOD" in level_cap and "RACEWAR_EVIL" in level_cap
assert "SELECT level, level_good, level_evil, UNIX_TIMESTAMP(next_update) FROM level_cap" in sql
# A wipe opens cap.reset.level to all with no timer, so the first frag unlocks the next.
assert "level=%d, level_good=0, level_evil=0, next_update=NOW()" in sql
assert "frag_cap_config_reset_level" in sql
for column in ("level_good", "level_evil"):
    assert '{ "level_cap", "' + column + '" }' in sql

# The maintenance job unlocks levels; the game keeps the row in memory and reads it
# again when the job changed it, and announces the unlock.
job = maintenance[maintenance.index("maintenance_result execute_level_cap("):]
job = job[:job.index("\n}\n")]
for token in (
    "FROM level_cap ORDER BY id LIMIT 1 FOR UPDATE",
    "request.values[0] < strtoll(row[4].c_str(), nullptr, 10)",
    "COALESCE(SUM(total_frags),0) FROM frag_leaderboard",
    "p.frag_delta>0 AND (p.flags&",
    "COMBAT_PARTICIPANT_CAP_SHARE",
    "v.level>=",
    "unlock_victim_levels_below",
    "ORDER BY o.created_at,o.operation_id LIMIT 1",
    "(level - 1) % 5 == 0",
    "unlock_timer_days",
    "level_cap_changed",
):
    assert token in job, token
assert "boons" not in job
assert "maintenance_job_id::level_cap" in comm
assert "sql_level_cap_reload();" in comm
completion = comm[comm.index("result.job_id == maintenance_job_id::level_cap"):]
completion = completion[:completion.index("// The jobs that change zone alignments")]
assert "send_to_all(announcement)" in completion
assert "boon_notify_snapshot" not in completion
assert "sql_check_level_cap_periodic" not in sql + sql_h + comm

# Both fraglist views share one header: each side's cap, each side's frag total and what
# unlocks the next level.
for view in (fraglist, report_cache):
    assert "fraglist_cap_header(rows, before" in view
cap_header = report_cache[report_cache.index("time_t fraglist_cap_header("):]
cap_header = cap_header[:cap_header.index("\n}\n")]
for token in ("get_level_cap_info(&open_level, &good_level, &evil_level",
              "Goodies Total Frags", "unlock_victim_levels_below",
              "100 / config->unlock_minimum_share_points",
              "with at most %d of that side in the room"):
    assert token in cap_header, token
assert "SELECT 'total', racewar, SUM(total_frags)" in report_cache
assert "frag_cap_config" not in redis

# The kill records whether its base share (1.00 frag over the killer's side in the room,
# before level modifiers) met the minimum, compared without rounding; the job reads the flag.
command = (SRC / "combat_outcome_command.h").read_text()
assert "COMBAT_PARTICIPANT_CAP_SHARE = UINT8_C(1) << 3" in command
fight = (SRC / "fight.c").read_text()
award = fight[fight.index("static bool submit_pvp_outcome("):]
award = award[:award.index("\n}\n")]
for token in ("allies * frag_cap_config_get()->unlock_minimum_share_points <= 100",
              "entry->flags |= COMBAT_PARTICIPANT_CAP_SHARE"):
    assert token in award, token
assert award.index("float gain = 100.0F / allies") < award.index("frag.evil.penalty")
assert "CAP_SHARE = 8" in (ROOT / "tests/async/run_level_cap_mysql.py").read_text()
for retired in ("unlock.minimum.frag.points", "unlock_minimum_frag_points"):
    assert retired not in config + header + impl + maintenance + report_cache, retired

print("frag-cap configuration source contract passed")
