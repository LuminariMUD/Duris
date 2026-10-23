#!/usr/bin/env python3
"""Execute the committed reports locally against native reducer fixtures.

First run test_telemetry_posthog.py to build its native fixture binary, then:
  python3 -m pip install --target bin/tests/posthog-report-deps chdb==4.4.0
  PYTHONPATH=bin/tests/posthog-report-deps python3 tests/async/run_telemetry_posthog_reports.py

ClickHouse runs the SQL unchanged. A local toInt function supplies HogQL's
nullable conversion, and dotted columns supply its event-property access.
No PostHog credentials, captured data or network connection are used.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import subprocess

from chdb import session

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "docs/telemetry/posthog"
NOW = datetime.now(timezone.utc).replace(microsecond=0)


def native(scenario):
    output = subprocess.check_output(
        [str(ROOT / "bin/tests/telemetry-posthog-mariadb"), "reduce", scenario], text=True)
    rows = [json.loads(line) for line in output.splitlines()]
    return [row for row in rows if "event" in row]


def literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, (int, bool)):
        return str(int(value))
    if isinstance(value, (dict, list)):
        value = json.dumps(value, separators=(",", ":"))
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def run(db, name, rows):
    sql = (REPORTS / (name + ".sql")).read_text()
    fields = sorted(set(re.findall(r"properties\.[A-Za-z_][A-Za-z_0-9.]*", sql)))
    sources = []
    for original in rows:
        row = deepcopy(original)
        row["properties"].update(duris_schema_version=1, duris_environment_id="1",
                                 duris_season_id="1", duris_test_run=None)
        columns = [literal(row["event"]) + " AS event",
                   "toDateTime(" + literal(row.get("_captured_at", NOW - timedelta(hours=1))
                                          .strftime("%Y-%m-%d %H:%M:%S")) + ") AS timestamp"]
        for field in fields:
            value = row
            for key in field.split("."):
                value = value.get(key) if isinstance(value, dict) else None
            columns.append(literal(value) + " AS `" + field + "`")
        sources.append("SELECT " + ", ".join(columns))
    query = sql.replace("WITH ", "WITH events AS (" + " UNION ALL ".join(sources) + "), ", 1)
    result = json.loads(str(db.query(query, "JSON")))["data"]
    return result


def stable(rows):
    return [{key: value for key, value in row.items() if key != "snapshot_age_seconds"}
            for row in rows]


def main():
    with session.Session() as db:
        db.query("CREATE FUNCTION toInt AS value -> toInt64OrNull(toString(value))")
        ordinary = native("conservation")
        for name in ("activity", "time", "xp", "encounters", "health"):
            rows = ordinary + native("health-incidents") + native("encounter-open")
            result = run(db, name, rows)
            assert result, name
            assert stable(result) == stable(run(db, name, rows + rows)), name
        print("PASS: all five committed SQL reports execute and deduplicate repeated event IDs")

        health = [row for row in native("health-incidents")
                  if row["event"] == "duris_telemetry_health"]
        assert health[-1]["properties"]["active_reason_mask"] == 0
        assert health[-1]["properties"]["coalesced_reason_mask"] != 0
        for index, row in enumerate(health):
            row["_captured_at"] = NOW - timedelta(hours=index + 1)
            props = row["properties"]
            props["sampled_monotonic_usec"] = str(100 + index)
            props["http_delivery"].update(quota_day=str(2000 + index), normal_reserved=2 + index,
                                          health_reserved=1, normal_limit=19800, health_limit=100,
                                          total_limit=19900)
        selected, = run(db, "health", health)
        assert selected["as_of_utc"] == health[-1]["_captured_at"].strftime("%Y-%m-%d %H:%M:%S")
        assert selected["health_trigger"] == "incident"
        assert selected["coalesced_reason_mask"] == health[-1]["properties"]["coalesced_reason_mask"]
        assert selected["coalesced_severity"] == "warning"
        assert selected["quota_day"] == "2001" and selected["normal_reserved"] == 3
        assert selected["health_reserved"] == 1 and selected["total_limit"] == 19900
        assert selected["normal_limit"] == 19800 and selected["health_limit"] == 100
        for field in ("output_event_limit", "output_byte_limit", "session_limit", "run_limit",
                      "configuration_limit"):
            assert selected[field] == health[-1]["properties"]["reducer"][field], field
        print("PASS: latest monotonic health retains UTC rollback, daily quota, capacities and recovered incidents")

        encounters = native("encounter-overflow") + native("encounter-open")
        result = run(db, "encounters", encounters)
        assert any(row["participant_time_basis"] == "observed_lower_bound" for row in result)
        assert any(row["participant_time_basis"] == "terminal" for row in result)
        overflow, = [row for row in result if row["row_type"] == "run" and row["unattributed_pet_rows"]]
        assert json.loads(overflow["unattributed_pet_combat"])["damage_dealt"] == "640"
        original, = [row["properties"] for row in encounters
                     if row["event"] == "duris_encounter_summary" and
                     row["properties"].get("unattributed_pet_rows")]
        for field in ("unattributed_player_rows", "unattributed_pet_rows", "unattributed_roster_usec"):
            assert overflow[field] == original[field], field
        assert json.loads(overflow["unattributed_player_combat"]) == original["unattributed_player_combat"]
        print("PASS: encounter overflow contributions and lower-bound/terminal duration qualifiers survive")

        summary = next(row for row in ordinary if row["event"] == "duris_character_summary")
        quality_rows = []
        for quality, duration in ((1, 100), (2, 200)):
            row = deepcopy(summary)
            row["properties"]["duris_event_id"] = "quality-" + str(quality)
            bucket = deepcopy(row["properties"]["time_allocations"][0])
            bucket.update(context_quality=quality, connected_usec=str(duration), active_usec=str(duration),
                          idle_usec="0", unknown_usec="0", resident_usec=str(duration), linkdead_usec="0")
            row["properties"].update(time_allocations=[bucket], unattributed_time={"resident_usec": "0"},
                                     reconciliation={"checkpoint_available": False})
            quality_rows.append(row)
        result = run(db, "time", quality_rows)
        assert {(row["context_quality"], row["resident_usec"]) for row in result} == {(1, "100"), (2, "200")}
        print("PASS: equal time contexts with different evidence quality remain separate")

        xp_summary = deepcopy(next(row for row in ordinary if row["event"] == "duris_character_summary"
                                   and row["properties"]["xp_allocations"]))
        xp_buckets = []
        for zone, group, amount in ((100, 1, 10), (200, 1, 20), (100, 2, 30)):
            bucket = deepcopy(xp_summary["properties"]["xp_allocations"][0])
            bucket.update(zone=zone, group_size=group, requested_xp=str(amount),
                          computed_xp=str(amount), applied_xp=str(amount), attempts="1", zero_applied="0")
            xp_buckets.append(bucket)
        xp_summary["properties"].update(xp_allocations=xp_buckets, unattributed_xp={"attempts": "0"})
        result = run(db, "xp", [xp_summary])
        assert {(row["zone"], row["group_size"], row["applied_xp"]) for row in result} == {
            (100, 1, "10"), (200, 1, "20"), (100, 2, "30")}
        assert result == run(db, "xp", [xp_summary, xp_summary])
        print("PASS: XP allocation preserves independent captured zone and group-size dimensions")

        comparisons = []
        for index, observed in enumerate((400, 800)):
            row = deepcopy(summary)
            row["_captured_at"] = NOW - timedelta(hours=index + 1)
            props = row["properties"]
            props["duris_event_id"] = "z-stale" if index == 0 else "a-late"
            totals = {name: "1000" if name in ("connected_usec", "active_usec", "resident_usec") else "0"
                      for name in ("connected_usec", "active_usec", "idle_usec", "unknown_usec",
                                   "resident_usec", "linkdead_usec")}
            props.update(time_allocations=[], unattributed_time={"resident_usec": "0"}, reconciliation={
                "checkpoint_available": True, "comparison_available": True, "revision": "7",
                "checkpoint": totals,
                "observed_at_checkpoint": {key: str(observed) if value == "1000" else "0"
                                           for key, value in totals.items()},
                "missing_detail": {key: str(1000 - observed) if value == "1000" else "0"
                                   for key, value in totals.items()}})
            comparisons.append(row)
        latest, = [row for row in run(db, "time", comparisons) if row["row_plane"] != "interval_delta"]
        assert latest["resident_usec"] == "200"
        invalid = deepcopy(comparisons[-1])
        invalid["properties"]["duris_event_id"] = "unavailable"
        invalid["properties"]["reconciliation"].update(comparison_available=False, missing_detail=None)
        latest, = run(db, "time", comparisons + [invalid])
        assert latest["resident_usec"] is None and latest["unavailable_inputs"] == 1
        print("PASS: late checkpoint evidence wins over occurrence/UUID order and unavailable comparisons stay unknown")


if __name__ == "__main__":
    main()
