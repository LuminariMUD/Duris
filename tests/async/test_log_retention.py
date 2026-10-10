#!/usr/bin/env python3
"""No log line is kept past 30 days (ADR 0003), run on the real expire_log_files().

The launcher archived the live logs only between two runs and deleted an archive by its
directory's age, which is when the archive was made. So a server kept up by copyovers never
archived or pruned its logs, and a 40-day run's first lines lived 70 days. The hourly
address_retention job now moves the live logs into logs/old-logs/<date>/ once they are a day
old (logs/log/.since marks when the live set began), and removes each archived file and core
dump 28 days after it was last written, whatever its directory's age, then any archive left
empty: a file holds at most about 25 hours of lines, so none of them reaches 30 days.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import time

from _paths import ROOT, extract_function

listing = extract_function("maintenance_repository.c",
                           "std::vector<std::filesystem::path> list_files(const char *directory)")
expire = extract_function("maintenance_repository.c", "void expire_log_files()")

HARNESS = r'''
#include <chrono>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>
''' + listing + "\n" + expire + r'''
int main() { expire_log_files(); }
'''

DAY = 86400


def write(path: Path, age_days: float = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("Sat Oct 10 08:17:04 2026:: a line with 192.0.2.7\n")
    stamp = time.time() - age_days * DAY
    os.utime(path, (stamp, stamp))


def files(root: Path) -> set[str]:
    return {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}


(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="log-retention-", dir=ROOT / "bin/tests") as tmp:
    test, binary = Path(tmp) / "test.cpp", Path(tmp) / "test"
    test.write_text(HARNESS)
    subprocess.run(["g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", str(test), "-o", str(binary)], check=True)

    def expire(setup) -> Path:
        run = Path(tempfile.mkdtemp(dir=tmp))
        setup(run)
        subprocess.run([str(binary)], check=True, cwd=run)
        return run

    # A live set that began over a day ago moves into a new archive, and a new one begins.
    def day_old(run: Path) -> None:
        write(run / "logs/log/.gitignore")
        write(run / "logs/log/comm", 0.1)
        write(run / "logs/player-log/new", 0.5)
        write(run / "logs/log/.since", 1.1)
    run = expire(day_old)
    archives = list((run / "logs/old-logs").iterdir())
    assert len(archives) == 1, archives
    archive = archives[0].name
    assert files(run) == {"logs/log/.gitignore", "logs/log/.since", f"logs/old-logs/{archive}/comm",
                          f"logs/old-logs/{archive}/.since",
                          f"logs/old-logs/{archive}/player-log/new"}, files(run)
    assert time.time() - (run / "logs/log/.since").stat().st_mtime < 60

    # A younger live set stays; a missing marker is made, and nothing moves.
    run = expire(lambda run: (write(run / "logs/log/comm", 2), write(run / "logs/log/.since", 0.9)))
    assert files(run) == {"logs/log/comm", "logs/log/.since"}, files(run)
    run = expire(lambda run: write(run / "logs/log/comm", 2))
    assert files(run) == {"logs/log/comm", "logs/log/.since"}, files(run)

    # Archived files and core dumps go 28 days after their last write, whatever the age of
    # their directory, which a run that lasted 40 days made at its end. An archive left
    # empty goes too.
    def archived(run: Path) -> None:
        write(run / "logs/log/.since")
        write(run / "logs/old-logs/2026.09.01-00.00.00/comm", 28.1)
        write(run / "logs/old-logs/2026.09.01-00.00.00/status", 27.9)
        write(run / "logs/old-logs/2026.09.01-00.00.00/player-log/new", 29)
        write(run / "logs/old-logs/2026.08.20-00.00.00/comm", 45)
        write(run / "logs/old-logs/2026.08.20-00.00.00/player-log/new", 45)
        write(run / "core.2026.09.01-00.00.00", 28.1)
        write(run / "core.2026.09.03-00.00.00", 27.9)
    run = expire(archived)
    assert files(run) == {"logs/log/.since", "logs/old-logs/2026.09.01-00.00.00/status",
                          "core.2026.09.03-00.00.00"}, files(run)
    assert sorted(path.name for path in (run / "logs/old-logs").iterdir()) == \
        ["2026.09.01-00.00.00"]
print("log files are archived daily and kept 28 days after their last line")
