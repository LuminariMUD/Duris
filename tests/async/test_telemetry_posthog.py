#!/usr/bin/env python3
"""PostHog encoding regressions and the declared event-volume fixture.

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
                str(ROOT / "tests/async/telemetry_posthog_harness.cc"),
                "-lcrypto", "-o", str(binary),
            ], cwd=ROOT, env=TEST_ENV, check=True, timeout=60)
            encoding_tests(binary)
            print(f"PostHog encodings ({backend}, UBSan): PASS")
    volume_tests()
    print("PostHog encoding/forecast fixtures: PASS; exporter acceptance still pending")


if __name__ == "__main__":
    main()
