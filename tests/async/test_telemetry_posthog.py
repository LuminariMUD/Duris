#!/usr/bin/env python3
"""PostHog worker reducer, encoding regressions and declared volume fixture.

No host .env, network, database, player data or live journal is used. The volume
fixture is a forecast oracle; exporter-emitted counts must later match it before
it can establish delivery volume or normal-load acceptance.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/async/fixtures/telemetry/posthog"
TEST_ENV = {
    "PATH": os.environ.get("PATH", os.defpath),
    "ENVIRONMENT": "local",
    "TZ": "Pacific/Honolulu",
    "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1",
}


def encoding_tests(binary: Path) -> None:
    fixture = json.loads((FIXTURES / "encodings.json").read_text())

    def invoke(*arguments: object, valid: bool = True) -> str:
        result = subprocess.run([str(binary), *(str(value) for value in arguments)],
                                cwd=ROOT, env=TEST_ENV,
                                text=True, capture_output=True, timeout=10)
        assert result.returncode == (0 if valid else 1), (arguments, result)
        assert not result.stderr, result.stderr
        if not valid:
            assert not result.stdout, result.stdout
        return result.stdout.rstrip("\n")

    key = fixture["key_hex"]  # Synthetic 00..1f, never a real environment key.
    identities = []
    for vector in fixture["characters"]:
        fields = [int(vector[name]) for name in ("environment", "season", "subject")]
        message = b"duris:posthog:character:v1" + b"".join(
            field.to_bytes(8, "big") for field in fields)
        reference = "dc1_" + hmac.new(bytes.fromhex(key), message, hashlib.sha256).hexdigest()
        assert reference == vector["expected"]
        actual = invoke("character", key, *fields)
        assert actual == reference
        assert invoke("character", key.upper(), *fields) == actual
        assert invoke("character", key, *fields) == actual  # Restart stable.
        identities.append(actual)
    assert len(set(identities)) == len(identities)
    assert invoke("character", "ff" * 32, 1000, 1, 44) != identities[0]

    for invalid_key in ("", "a" * 63, "a" * 65, "00" * 32, "z0" * 32,
                        "gg" + key[2:], key[:62] + "xx"):
        invoke("character", invalid_key, 1000, 1, 44, valid=False)
    for fields in ((0, 1, 44), (1000, 0, 44), (1000, 1, 0)):
        invoke("character", key, *fields, valid=False)

    for vector in fixture["scoped"]:
        fields = [int(vector[name]) for name in ("environment", "season", "boot", "process", "sequence")]
        session = invoke("session", *fields)
        assert session == vector["session"]
        assert invoke("session", *fields) == session  # Handoff retains original producer.
        assert invoke("run", *fields) == vector["run"]
    for kind in ("session", "run"):
        for index in range(5):
            fields = [1000, 1, 11, 22, 33]
            fields[index] = 0
            invoke(kind, *fields, valid=False)

    for vector in fixture["timestamps"]:
        assert invoke("timestamp", vector["usec"]) == vector["expected"]
    for value in fixture["invalid_timestamps"]:
        invoke("timestamp", value, valid=False)

    ids = [invoke("uuid") for _ in range(16)]
    assert len(set(ids)) == len(ids)
    for identity in ids:
        parsed = uuid.UUID(identity)
        assert parsed.version == 4 and parsed.variant == uuid.RFC_4122
        assert str(parsed) == identity


def reducer_tests(binary: Path) -> None:
    cases = (
        "conservation", "boundaries", "midnight", "unknown-utc", "missing-clock",
        "buckets", "byte-capacity", "integer-overflow", "bucket-overflow", "sessions", "config-capacity",
        "checkpoint", "checkpoint-late-detail", "dimension-unknown", "level-config",
        "gap-scope", "long-interval", "expiry", "allocation-failure", "missing-config",
        "clock-flag", "unimplemented-encounters", "initialization", "lost-exit",
    )
    observed = {}
    forbidden = {"pid", "subject_id", "actor_pid", "name", "email", "account_id", "ip",
                 "command", "chat", "room", "room_id", "api_key", "identity_key",
                 "$session_id", "$groups", "$set", "$set_once"}
    decimal_names = {"requested_xp", "computed_xp", "applied_xp", "threshold_xp", "attempts",
                     "zero_applied", "revision", "interval_observations", "duris_config_id",
                     "duris_environment_id", "duris_season_id"}

    def walk(value: object) -> None:
        if isinstance(value, dict):
            assert not forbidden.intersection(value), forbidden.intersection(value)
            for key, item in value.items():
                if item is not None and (key.endswith("_usec") or key in decimal_names):
                    assert isinstance(item, str), (key, item)
                    assert str(int(item)) == item, (key, item)
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    def summaries(rows: list[dict]) -> list[dict]:
        return [row["properties"] for row in rows if row["event"] == "duris_character_summary"]

    for case in cases:
        result = subprocess.run([str(binary), "reduce", case], cwd=ROOT, env=TEST_ENV,
                                text=True, capture_output=True, timeout=20)
        assert result.returncode == 0, (case, result.stderr)
        assert not result.stderr, (case, result.stderr)
        decoded = [json.loads(line) for line in result.stdout.splitlines()]
        health = decoded.pop()["_fixture_health"]
        assert health["output_events"] == len(decoded)
        assert health["output_events"] <= 128 and health["output_bytes"] <= 512 * 1024
        seen = set()
        for row in decoded:
            walk(row)
            props = row["properties"]
            assert uuid.UUID(row["uuid"]).version == 4
            assert props["duris_event_id"] == row["uuid"]
            assert row["uuid"] not in seen
            seen.add(row["uuid"])
            assert props["$process_person_profile"] is False
            assert props["duris_schema_version"] == 1
            assert props["duris_environment_id"] == "1000" and props["duris_season_id"] == "1"
            assert props["duris_test_run"] == "native-unit-fixture"
            assert len(props["duris_coverage"]) == len(set(props["duris_coverage"]))
            assert len(json.dumps(row, separators=(",", ":"))) <= 32 * 1024
            if props["duris_character_id"] is not None:
                assert props["distinct_id"] == props["duris_character_id"]
                original = "7:8" if case == "checkpoint" else "11:22"
                assert props["duris_session_id"].startswith(f"ds1:1000:1:{original}:")
            else:
                assert props["distinct_id"] == "dh1:1000:1"
            if row["event"] == "duris_character_summary":
                assert len(props["time_allocations"]) <= 32 and len(props["xp_allocations"]) <= 32
                for metric, value in props["time"].items():
                    if value is not None:
                        parts = [part[metric] for part in props["time_allocations"]]
                        parts.append(props["unattributed_time"][metric])
                        if all(part is not None for part in parts):
                            assert int(value) == sum(int(part) for part in parts), (case, metric)
                        else:
                            assert "counter_overflow" in props["duris_coverage"]
                for metric, value in props["xp"].items():
                    if value is not None:
                        parts = [part[metric] for part in props["xp_allocations"]]
                        parts.append(props["unattributed_xp"][metric])
                        if all(part is not None for part in parts):
                            assert int(value) == sum(int(part) for part in parts), (case, metric)
                        else:
                            assert "counter_overflow" in props["duris_coverage"]
        observed[case] = (decoded, health)

    rows, health = observed["conservation"]
    parts = summaries(rows)
    assert len(parts) == 2 and health["sessions"] == 0
    expected_time = {"connected_usec": 35000000, "active_usec": 20000000, "idle_usec": 10000000,
                     "unknown_usec": 5000000, "resident_usec": 42000000, "linkdead_usec": 7000000}
    assert parts[0]["time"] == {key: str(value) for key, value in expected_time.items()}
    assert parts[0]["xp"] == {"requested_xp": "100", "computed_xp": "140", "applied_xp": "110",
                              "attempts": "3", "zero_applied": "1"}
    assert parts[1]["xp"]["applied_xp"] == "5"
    assert [part["xp_observed_level"] for part in parts] == [12, 13]
    reconcile = parts[0]["reconciliation"]
    assert reconcile["comparison_available"] is True
    assert reconcile["checkpoint"]["resident_usec"] == "44000000"
    assert reconcile["missing_detail"]["active_usec"] == "2000000"
    assert reconcile["missing_detail"]["linkdead_usec"] == "0"
    transitions = [row["properties"]["transition"] for row in rows if row["event"] == "duris_session"]
    assert transitions == ["logical_entry", "connection_detached", "connection_attached", "logical_exit"]
    levels = [row["properties"] for row in rows if row["event"] == "duris_level_change"]
    assert len(levels) == 1 and levels[0]["before_level"] == 12 and levels[0]["after_level"] == 13
    assert levels[0]["threshold_xp"] == "9223372036854775809"
    assert "applied_xp" not in levels[0]
    assert len({part["duris_character_id"] for part in parts}) == 1
    assert not health["output_suppressed"]

    parts = summaries(observed["boundaries"][0])
    assert len(parts) == 3
    assert sum(int(part["time"]["active_usec"]) for part in parts) == 1500000
    late = [part for part in parts if "late_fragment" in part["duris_coverage"]]
    assert len(late) == 1 and late[0]["time"]["active_usec"] == "500000"
    assert sum(int(part["xp"]["applied_xp"]) for part in parts) == 1
    assert observed["boundaries"][1]["invalid_records"] == 1  # Re-consuming never adds XP.

    midnight = [row for row in observed["midnight"][0] if row["event"] == "duris_character_summary"]
    assert len(midnight) == 2
    assert [row["properties"]["time"]["active_usec"] for row in midnight] == ["2000000", "2000000"]
    assert midnight[0]["timestamp"][:10] != midnight[1]["timestamp"][:10]
    assert int(midnight[1]["properties"]["window_start_utc_usec"]) % 86400000000 == 0
    unknown = summaries(observed["unknown-utc"][0])[0]
    assert unknown["timestamp_basis"] == "emitted_at"
    assert unknown["occurrence_start_utc_usec"] is None and unknown["occurrence_end_utc_usec"] is None
    assert unknown["window_start_utc_usec"] is None and unknown["time"]["active_usec"] == "1000"
    assert unknown["xp"]["applied_xp"] == "2"
    assert "occurrence_utc_unknown" in unknown["duris_coverage"]
    assert not summaries(observed["missing-clock"][0])
    assert observed["missing-clock"][1]["clock_failures"] == 1

    bucket = summaries(observed["buckets"][0])[0]
    assert len(bucket["time_allocations"]) == len(bucket["xp_allocations"]) == 32
    assert bucket["time"]["active_usec"] == "34" and bucket["unattributed_time"]["active_usec"] == "2"
    assert bucket["xp"]["requested_xp"] == "340000000000000000"
    assert bucket["unattributed_xp"]["requested_xp"] == "20000000000000000"
    assert bucket["xp"]["attempts"] == "34" and bucket["xp"]["zero_applied"] == "34"
    assert {"unattributed_time", "unattributed_xp"} <= set(bucket["duris_coverage"])
    byte_health = observed["byte-capacity"][1]
    assert byte_health["output_suppressed"] > 0 and byte_health["http_acknowledged"] > 0
    assert byte_health["output_events"] < 128  # Byte limit, not the row count, was reached.
    overflow = summaries(observed["integer-overflow"][0])
    assert len(overflow) == 3
    for part in overflow[:2]:
        assert all(part["xp"][key] is None for key in ("requested_xp", "computed_xp", "applied_xp"))
        assert part["xp"]["attempts"] == "2" and "counter_overflow" in part["duris_coverage"]
    assert overflow[2]["time"]["active_usec"] is None
    assert "counter_overflow" in overflow[2]["duris_coverage"]
    assert observed["integer-overflow"][1]["counter_overflow_rows"] == 3
    bucket_overflow = summaries(observed["bucket-overflow"][0])[0]
    assert bucket_overflow["xp"]["applied_xp"] == "9223372036854775807"
    assert bucket_overflow["xp_allocations"][0]["applied_xp"] is None
    assert {"counter_overflow", "unattributed_xp"} <= set(bucket_overflow["duris_coverage"])

    assert observed["sessions"][1]["sessions"] == 256 and observed["sessions"][1]["session_refusals"] == 1
    assert observed["sessions"][1]["http_acknowledged"] == 128
    assert observed["config-capacity"][1]["configurations"] == 64
    assert observed["config-capacity"][1]["configuration_refusals"] == 2
    assert len(observed["config-capacity"][0]) == 64  # Duplicate publication stays coalesced.
    checkpoint = summaries(observed["checkpoint"][0])[0]["reconciliation"]
    assert checkpoint["revision"] == "2" and checkpoint["comparison_available"] is False
    assert checkpoint["missing_detail"] is None  # No invented pre-copyover baseline.
    assert observed["checkpoint"][1]["checkpoint_conflicts"] == 2
    assert observed["checkpoint"][1]["stale_checkpoints"] == 1
    late_checkpoint = summaries(observed["checkpoint-late-detail"][0])[0]["reconciliation"]
    assert late_checkpoint["comparison_available"] is True
    assert set(late_checkpoint["missing_detail"].values()) == {"0"}
    unknown_dims = summaries(observed["dimension-unknown"][0])
    assert len(unknown_dims) == 1  # Unknown context does not trigger per-minute cloud rows.
    assert unknown_dims[0]["class_id"] is None
    assert unknown_dims[0]["time"]["active_usec"] == "19"
    assert unknown_dims[0]["unattributed_time"]["active_usec"] == "9"
    assert unknown_dims[0]["xp_allocations"][0]["class_id"] == 3
    assert [part["xp"]["applied_xp"] for part in summaries(observed["level-config"][0])] == ["1", "2", "3", "4"]
    assert observed["gap-scope"][1]["reduction_refusals"] == 1
    assert observed["gap-scope"][1]["input_sequence_gaps"] == 1
    assert observed["gap-scope"][1]["native_dropped_records"] == 2
    assert "native_gap" in summaries(observed["gap-scope"][0])[0]["duris_coverage"]
    long_parts = summaries(observed["long-interval"][0])
    assert len(long_parts) == 65
    assert sum(int(part["time"]["active_usec"]) for part in long_parts) == 900000000000000
    assert any("occurrence_utc_unknown" in part["duris_coverage"] for part in long_parts)
    assert observed["expiry"][1]["output_expired"] == 1 and observed["expiry"][1]["ambiguous_events"] == 1
    assert not observed["expiry"][0]
    assert observed["allocation-failure"][1]["serialization_failures"] == 4
    assert observed["allocation-failure"][1]["output_suppressed"] == 4
    assert "missing_configuration" in summaries(observed["missing-config"][0])[0]["duris_coverage"]
    assert observed["missing-config"][1]["missing_configuration_rows"] == 1
    flagged_clock = summaries(observed["clock-flag"][0])[0]
    assert flagged_clock["timestamp_basis"] == "emitted_at" and flagged_clock["window_start_utc_usec"] is None
    assert flagged_clock["occurrence_start_utc_usec"] is None
    assert observed["unimplemented-encounters"][1]["unsupported_records"] == 2
    assert observed["unimplemented-encounters"][1]["reduction_refusals"] == 2
    assert not observed["initialization"][0] and observed["initialization"][1]["invalid_records"] == 1
    abandoned = summaries(observed["lost-exit"][0])
    assert len(abandoned) == 2 and observed["lost-exit"][1]["abandoned_sessions"] == 1
    assert "unclosed_tail" in abandoned[0]["duris_coverage"]
    assert abandoned[0]["duris_session_id"] == abandoned[1]["duris_session_id"]
    assert len([row for row in observed["lost-exit"][0] if row["event"] == "duris_session"]) == 1
    print(f"PostHog reducer: {len(cases)} executable semantic/capacity/fault scenarios PASS")


def volume_tests() -> None:
    fixture = json.loads((FIXTURES / "volume.json").read_text())
    days = fixture["days"]
    assumptions = fixture["assumptions"]
    for profile in fixture["profiles"]:
        population = profile["average_connected"]
        residents = population + math.ceil(population * assumptions["detached_percent"] / 100)
        counts = {
            "periodic_summaries": residents * days * 86400 // profile["window_seconds"],
            "boundary_summaries": population * days * assumptions["extra_summary_boundaries_per_character_day"],
            "session": population * days * (
                assumptions["logical_entries_per_character_day"] * 4
                + assumptions["reconnects_per_character_day"] * 2
            ) + population * assumptions["copyovers"],
            "level_change": population * days // assumptions["character_days_per_level_change"],
            "encounter": population * days * assumptions["encounter_rows_per_run"]
            // assumptions["character_days_per_run"],
            "configuration": days * assumptions["configuration_rows_per_day"],
            "health": days * (24 + assumptions["health_incidents_per_day"]),
            "cloud_test": assumptions["cloud_test_submissions"],
        }
        # Tests already count all their attempts; only the game mix gets retries.
        retry_base = sum(counts.values()) - counts["cloud_test"]
        counts["retries"] = math.ceil(retry_base * assumptions["retry_percent"] / 100)
        assert counts == profile["expected"], (profile, counts)
        total = sum(counts.values())
        assert (total <= fixture["normal_target"]) == profile["fits_normal_target"]
        print(f"forecast: {population} average connected, {profile['window_seconds']}s, "
              f"{total} submissions/31 days; fixture assumptions only")
    assert 24 + assumptions["health_incidents_per_day"] <= 100
    assert assumptions["cloud_test_submissions"] <= 100
    # A rolling 31-day billing window can touch 32 UTC dates.
    assert fixture["daily_ceiling"] * 32 == 640000


def main() -> None:
    output_root = ROOT / "bin/tests"
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="telemetry-posthog-", dir=output_root) as directory:
        for backend, defines in (("mariadb", []), ("flatfile", ["-D__NO_MYSQL__"])):
            binary = Path(directory) / backend
            subprocess.run([
                *shlex.split(os.environ.get("CXX", "g++")), "-std=c++20", "-O1", "-g",
                "-Wall", "-Wextra", "-Werror", "-pedantic", "-fsanitize=undefined",
                "-fno-sanitize-recover=all", *defines, "-I", str(ROOT / "src"),
                str(ROOT / "src/telemetry/telemetry_posthog.c"),
                str(ROOT / "src/telemetry/telemetry_config.c"),
                str(ROOT / "tests/async/telemetry_posthog_harness.cc"),
                str(ROOT / "tests/async/telemetry_posthog_reducer_harness.cc"),
                "-lcrypto", "-lcjson", "-o", str(binary),
            ], cwd=ROOT, env=TEST_ENV, check=True, timeout=60)
            encoding_tests(binary)
            reducer_tests(binary)
            print(f"PostHog encodings ({backend}, UBSan): PASS")
    volume_tests()
    print("PostHog encoding/reducer/forecast fixtures: PASS; delivery acceptance still pending")


if __name__ == "__main__":
    main()
