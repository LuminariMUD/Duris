#!/usr/bin/env python3
"""Statistics capture, SQL/file agreement, I/O faults and durable restart replay.

Run with run_statistics_mysql.sh under with_disposable_mariadb.sh. Uses the actual
scheduler and repository against the authoritative schema, never the game DB.
"""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import os
import shlex
import struct
import subprocess
import tempfile

from _paths import HARNESS_STUBS

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "bin/tests"
ZONE = ZoneInfo("America/New_York")
# One second before local midnight, not UTC midnight.
CAPTURED = int(datetime(2026, 10, 12, 23, 59, 59, tzinfo=ZONE).timestamp())


def main():
    assert os.environ["TEST_DB_HOST"] == "127.0.0.1", "disposable loopback DB required"
    database = os.environ["STATISTICS_TEST_DB"]
    mysql = ["mysql", "--protocol=tcp", "-h", os.environ["TEST_DB_HOST"],
             "-P", os.environ["TEST_DB_PORT"], "-u", os.environ["TEST_DB_USER"],
             "-N", "-B", database]

    def sql(statement):
        return subprocess.check_output(mysql, input=statement, text=True).strip()

    OUT.mkdir(parents=True, exist_ok=True)
    binary = OUT / "statistics_mysql_harness"
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-pthread", "-Isrc",
        "-ffunction-sections", "-fdata-sections",
        *shlex.split(subprocess.check_output(["mysql_config", "--cflags"], text=True)),
        "tests/async/statistics_mysql_harness.cpp",
        "src/persistence/maintenance_scheduler.c", "src/persistence/maintenance_repository.c", "src/combat/frag_cap.c", "src/combat/frag_cap_repository.c",
        "src/economy/divine_boon.c", "src/economy/divine_boon_repository.c",
        "src/economy/divine_trade.c", "src/economy/divine_trade_command.c", "src/economy/divine_trade_repository.c", "src/economy/currency_command.c", "src/persistence/critical_command.c",
        "src/persistence/persistence_observability.c", "src/combat/frag_cap_config.c",
        str(HARNESS_STUBS), "-Wl,--wrap=write", "-Wl,--wrap=fsync",
        "-Wl,--wrap=mysql_real_query",
        *shlex.split(subprocess.check_output(["mysql_config", "--libs"], text=True)),
        "-lcrypto", "-Wl,--gc-sections", "-o", str(binary)], cwd=ROOT, check=True)

    def run(directory, mode="normal", captured=CAPTURED):
        result = subprocess.run([str(binary), mode, str(captured)], cwd=directory,
                                env=dict(os.environ, TZ=ZONE.key), capture_output=True,
                                text=True, timeout=25)
        expected = 42 if mode.startswith("crash_") else 0
        assert result.returncode == expected, result.stdout + result.stderr
        print(result.stdout.strip() or mode, flush=True)

    def verify(directory, times, legacy=b""):
        expected = sorted([timestamp, *range(1, 12)] for timestamp in times)
        rows = sql("SELECT date,goods_count,evils_count,illithids_count,undeads_count,"
                   "gods_count,in_guildhall_count,sum_goods_levels,sum_evils_levels,"
                   "sum_undeads_levels,sum_illithids_levels,unique_ips_count FROM statistics")
        actual = sorted(list(map(int, row.split())) for row in rows.splitlines())
        assert actual == expected, (actual, expected)
        by_date = {}
        for timestamp in times:
            local = datetime.fromtimestamp(timestamp, ZONE)
            by_date.setdefault(local.strftime("%Y%m%d"), []).append([local.hour, *range(1, 12)])
        identities = []
        for date, samples in by_date.items():
            data = (directory / "lib/statistics" / f"statistics_general{date}").read_bytes()
            if date == "20261012" and legacy:
                assert data.startswith(legacy)
                data = data[len(legacy):]
            assert data.endswith(b"\r\n")
            file_rows = [list(map(int, row.split())) for row in data.split(b"\r\n")[:-1]]
            assert sorted(row[:-1] for row in file_rows) == sorted(samples), file_rows
            identities.extend(row[-1] for row in file_rows)
        assert len(identities) == len(set(identities))
        assert len(list((directory / "lib/statistics").iterdir())) == len(by_date)

    def reset(directory):
        directory.mkdir()
        (directory / "lib/statistics").mkdir(parents=True)
        sql("TRUNCATE statistics; DELETE FROM timers WHERE name LIKE 'maintenance_statistics_%'")

    def legacy_state(path, version, jobs):
        current = path.read_bytes()
        assert current[:8] == b"DMSMNT4\0"
        job_size = (len(current) - 24) // 13
        old_id = struct.unpack_from("=Q", current, 16 + job_size * 10)[0]
        assert old_id
        legacy_id = (1740 << 8) | 11
        current = current.replace(struct.pack("=Q", old_id), struct.pack("=Q", legacy_id))
        sql(f"UPDATE timers SET date=CASE name WHEN 'maintenance_statistics_high' "
            f"THEN 0 ELSE {legacy_id} END WHERE name IN "
            "('maintenance_statistics_high','maintenance_statistics_low')")
        for daily in (path.parent / "lib/statistics").iterdir():
            daily.write_bytes(daily.read_bytes().replace(f" {old_id}\r\n".encode(),
                                                        f" {legacy_id}\r\n".encode()))
        state = bytearray(f"DMSMNT{version}\0".encode() + struct.pack("=II", version, jobs))
        state.extend(current[16:16 + job_size * jobs])
        checksum = 1469598103934665603
        for byte in state:
            checksum = ((checksum ^ byte) * 1099511628211) & ((1 << 64) - 1)
        path.write_bytes(state + struct.pack("=Q", checksum))

    with tempfile.TemporaryDirectory(prefix="statistics-", dir=OUT) as temporary:
        base = Path(temporary)
        case = base / "boots"
        reset(case)
        # Real legacy file rows stay intact. Every old tick-derived identity in
        # the first sample's schedule is represented in the final 8 KiB.
        legacy = b"".join(f"22 0 0 0 0 0 0 0 0 0 0 0 {tick * 256 + 11}\r\n".encode()
                          for tick in range(300))
        (case / "lib/statistics/statistics_general20261012").write_bytes(legacy)
        run(case, captured=CAPTURED - 90)
        run(case, captured=CAPTURED - 90)  # distinct sample, identical counters AND timestamp
        (case / "scheduler.state").unlink()  # loss of scheduler state starts new work
        run(case, captured=CAPTURED)
        run(case, captured=CAPTURED + 1)  # local date rollover
        verify(case, [CAPTURED - 90, CAPTURED - 90, CAPTURED, CAPTURED + 1], legacy)
        print("PASS fresh/same-day boots, legacy IDs, identical samples, missing state, midnight")

        for mode in ("slow_state", "sql", "commit_ack", "file", "partial", "fsync"):
            case = base / mode
            reset(case)
            run(case, mode)
            verify(case, [CAPTURED])
            print(f"PASS {mode}: retry preserves all counters, date, SQL/file multiplicity")

        for mode in ("crash_file", "crash_partial", "crash_complete", "unacked"):
            for version, jobs in ((2, 11), (3, 12), (4, 13)):
                case = base / f"{mode}-{version}"
                reset(case)
                run(case, mode)
                legacy_state(case / "scheduler.state", version, jobs)
                # Even when the next process would capture another day, recovered
                # work must keep the first timestamp and all eleven counters.
                run(case, "resume", CAPTURED + 86400)
                verify(case, [CAPTURED])
                print(f"PASS {mode}: v{version} pending request/completion replay")

        for mode in ("corrupt", "conflict_resume"):
            case = base / mode
            reset(case)
            daily = case / "lib/statistics/statistics_general20261012"
            if mode == "conflict_resume":
                run(case, "crash_complete")
                bad = daily.read_bytes().replace(b"23 1 2 ", b"23 99 2 ")
            else:
                bad = b"unrelated damaged data"
            daily.write_bytes(bad)
            run(case, mode)
            assert daily.read_bytes() == bad
            assert sql("SELECT COUNT(*) FROM statistics") == "1"
            print(f"PASS {mode}: EILSEQ, no silent rewrite or success")

        case = base / "invalid"
        reset(case)
        (case / "scheduler.state").write_bytes(b"invalid durable state")
        run(case, "invalid")
        assert sql("SELECT COUNT(*) FROM statistics") == "0"
        print("PASS invalid state refuses startup without producing outputs")


if __name__ == "__main__":
    main()
