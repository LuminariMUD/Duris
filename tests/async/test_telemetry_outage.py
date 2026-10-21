#!/usr/bin/env python3
"""Local bounded outage ledger: process replacement, kill and storage failures."""

from pathlib import Path
import json
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    artifacts = ROOT / "bin/tests"
    artifacts.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="telemetry-outage-", dir=artifacts) as directory:
        binary = Path(directory) / "telemetry-outage"
        subprocess.run([
            "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-pedantic",
            "-fsanitize=undefined", "-fno-sanitize-recover=all",
            "-I", str(ROOT / "src"),
            str(ROOT / "src/telemetry/telemetry_outage.c"),
            str(ROOT / "tests/async/telemetry_outage_harness.cc"),
            "-Wl,--wrap=write", "-Wl,--wrap=fsync", "-Wl,--wrap=renameat", "-lcrypto",
            "-o", str(binary),
        ], cwd=ROOT, check=True, timeout=60)
        completed = subprocess.run([str(binary)], cwd=ROOT, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        print(completed.stdout, end="")
        completed.check_returncode()
        assert "telemetry durable outage evidence qualification passed" in completed.stdout
        with tempfile.TemporaryDirectory(prefix="telemetry-evidence-") as evidence_path:
            evidence = Path(evidence_path)
            subprocess.run([str(binary), "--make-fixture", str(evidence)], check=True, timeout=10)
            before = (evidence / "outages.ledger").read_bytes()
            command = [sys.executable, str(ROOT / "scripts/telemetry/outage.py"), str(evidence)]
            exported = subprocess.run(command, check=True, text=True, capture_output=True, timeout=10)
            packet = json.loads(exported.stdout)
            assert packet["producer_count"] == 2 and packet["generation"] == 4
            previous, current = packet["observations"]
            assert previous["phase"] == "unknown_tail" and previous["tail_end_utc_usec"] is None
            assert previous["tail_end_monotonic_usec"] is None and previous["observed_monotonic_usec"] == 400
            assert previous["rejected_detail_admissions"] == 3 and previous["unattempted_records"] == 4
            assert previous["known_abandoned_unattempted_records"] == 0
            assert current["phase"] == "clean_drained" and current["tail_end_monotonic_usec"] == 500
            assert (evidence / "outages.ledger").read_bytes() == before
            # An archive the writer kept reads the same way under its own name.
            archive = evidence / "outages.ledger.1000.4"
            archive.write_bytes(before)
            archive.chmod(0o600)
            archived = subprocess.run(command + ["--ledger", archive.name], check=True, text=True,
                                      capture_output=True, timeout=10)
            assert json.loads(archived.stdout) == packet
            refused = subprocess.run(command + ["--ledger", "../outages.ledger"], text=True, capture_output=True, timeout=10)
            assert refused.returncode == 2 and json.loads(refused.stdout)["reason"] == "invalid_ledger_name"
            archive.unlink()
            pending = evidence / "outages.pending"
            pending.write_bytes(b"interrupted")
            pending.chmod(0o600)
            refused = subprocess.run(command, text=True, capture_output=True, timeout=10)
            assert refused.returncode == 2 and json.loads(refused.stdout)["reason"] == "pending_publication"
            assert pending.read_bytes() == b"interrupted"
            pending.unlink()
            (evidence / "outages.ledger").chmod(0o644)
            refused = subprocess.run(command, text=True, capture_output=True, timeout=10)
            assert refused.returncode == 2 and json.loads(refused.stdout)["reason"] == "unsafe_storage"
        with tempfile.TemporaryDirectory(prefix="telemetry-held-") as held:
            holder = subprocess.Popen([str(binary), "--hold-fixture", held], stdout=subprocess.PIPE,
                                      text=True)
            try:
                assert holder.stdout.readline().strip() == "held"
                refused = subprocess.run([sys.executable, str(ROOT / "scripts/telemetry/outage.py"), held],
                                         text=True, capture_output=True, timeout=10)
                assert refused.returncode == 2 and json.loads(refused.stdout)["reason"] == "owned_elsewhere"
            finally:
                holder.kill()
                holder.wait(timeout=10)
        print("outage offline bounded read-only evidence export passed")
        tool = Path(directory) / "telemetry-state"
        subprocess.run([
            "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-pedantic",
            "-I", str(ROOT / "src"), str(ROOT / "src/telemetry/telemetry_outage.c"),
            str(ROOT / "src/telemetry/telemetry_state.cc"), "-lcrypto", "-o", str(tool),
        ], cwd=ROOT, check=True, timeout=60)
        with tempfile.TemporaryDirectory(prefix="quota-state-", dir=artifacts) as quota_directory:
            path = Path(quota_directory)
            binding = ["678214", "1", "1000", "1", "19900", "19800", "100"]

            def invoke(command: str, fields: list[str] = [], valid: bool = True) -> dict:
                call = subprocess.run([str(tool), command, quota_directory, *fields],
                                      cwd=ROOT, text=True, capture_output=True, timeout=10)
                assert call.returncode == (0 if valid else 2), call
                assert not call.stderr, call.stderr
                return json.loads(call.stdout)

            initialized = invoke("initialize", binding)
            assert initialized["normal_reserved"] == initialized["health_reserved"] == 0
            assert initialized["total_limit"] == 19900
            before = (path / "outages.ledger").read_bytes()
            assert invoke("initialize", binding, valid=False)["result"] != 0
            assert (path / "outages.ledger").read_bytes() == before
            packet = subprocess.run([sys.executable, str(ROOT / "scripts/telemetry/outage.py"), quota_directory],
                                    text=True, capture_output=True, check=True, timeout=10)
            decoded = json.loads(packet.stdout)
            assert decoded["ledger_version"] == 2 and decoded["producer_count"] == 0
            assert decoded["quota"]["normal_limit"] == 19800 and decoded["quota"]["health_limit"] == 100
            wrong = ["678215", *binding[1:]]
            invoke("exhaust-day", wrong, valid=False)
            exhausted = invoke("exhaust-day", binding)
            assert exhausted["normal_reserved"] == 19800 and exhausted["health_reserved"] == 100
            assert len(list(path.glob("outages.ledger.recovery.*"))) == 1
            before_rollover = (path / "outages.ledger").read_bytes()
            new_season = [*binding[:3], "2", *binding[4:]]
            invoke("rollover-season", ["678215", *new_season[1:]], valid=False)
            assert (path / "outages.ledger").read_bytes() == before_rollover
            rolled = invoke("rollover-season", new_season)
            assert rolled["normal_reserved"] == 19800 and rolled["health_reserved"] == 100
            invoke("exhaust-day", binding, valid=False)
            packet = subprocess.run([sys.executable, str(ROOT / "scripts/telemetry/outage.py"), quota_directory],
                                    text=True, capture_output=True, check=True, timeout=10)
            assert json.loads(packet.stdout)["quota"]["season_id"] == 2
            assert len(list(path.glob("outages.ledger.recovery.*"))) == 2
            for item in path.iterdir():
                assert item.stat().st_mode & 0o777 == 0o600
        print("quota native initialize/restore-exhaustion/season-rollover commands and v2 offline export passed")


if __name__ == "__main__":
    main()
