#!/usr/bin/env python3
"""Execute the production socket-peak rollover with controlled server time."""

from _paths import ROOT, extract_function, source
from pathlib import Path
import subprocess
import tempfile

comm = source("comm.c").read_text(encoding="utf-8")
who = extract_function("actinf.c", "void do_who(")
rollover = extract_function("comm.c", "static void update_completed_hour_connection_peak(")
assert "update_completed_hour_connection_peak(time(0), loop_monotonic_us()," in comm
assert "max_descs_this_hour = used_descs;\n\tmax_descs_previous_hour_valid = false;" in comm
assert "if (used_descs > max_descs_this_hour)" in comm
assert "max_descs_this_hour" not in who
assert "max_descs_previous_hour_valid" in who

harness = r"""
#include <cassert>
#include <cstdint>
int used_descs = 0;
int max_descs_this_hour = 0;
int max_descs_previous_hour = 0;
bool max_descs_previous_hour_valid = false;

@ROLLOVER@

int main()
{
    long start = 1000;
    uint64_t monotonic_start = 1000ULL * 1000000;
    auto update = [&](long wall, uint64_t monotonic_seconds) {
        update_completed_hour_connection_peak(wall, monotonic_seconds * 1000000,
                                              start, monotonic_start);
    };
    used_descs = 3;
    max_descs_this_hour = used_descs; // cold boot/recovery baseline
    update(4599, 4599);
    assert(!max_descs_previous_hour_valid && max_descs_this_hour == 3);
    assert(start == 1000);

    // The highest accepted concurrency, not accumulated logins, is published.
    max_descs_this_hour = 7;
    used_descs = 2;
    update(4600, 4600);
    assert(max_descs_previous_hour_valid && max_descs_previous_hour == 7);
    assert(max_descs_this_hour == 2 && start == 4600);

    // The published sample is frozen during the next reporting period.
    max_descs_this_hour = 12;
    update(8199, 8199);
    assert(max_descs_previous_hour == 7 && max_descs_this_hour == 12);
    used_descs = 0;
    update(8200, 8200);
    assert(max_descs_previous_hour_valid && max_descs_previous_hour == 12);
    assert(max_descs_this_hour == 0 && start == 8200);

    // No active socket and no new connection is a measured zero peak.
    update(11800, 11800);
    assert(max_descs_previous_hour_valid && max_descs_previous_hour == 0);

    // Backwards wall-clock jumps cannot publish a partial/unknown hour.
    max_descs_this_hour = 15;
    used_descs = 4;
    update(11000, 11801);
    assert(!max_descs_previous_hour_valid && start == 11000);
    assert(max_descs_this_hour == 4);

    // Long pauses also invalidate the old sample, rather than re-label it.
    max_descs_this_hour = 9;
    update(18200, 19001);
    assert(!max_descs_previous_hour_valid && start == 18200);
    assert(max_descs_this_hour == 4);
    update(21800, 22601);
    assert(max_descs_previous_hour_valid && max_descs_previous_hour == 4);

    // A fresh process/copyover starts without carrying an unverified sample.
    max_descs_previous_hour_valid = false;
    used_descs = 6;
    max_descs_this_hour = used_descs;
    start = 22000;
    monotonic_start = 22000ULL * 1000000;
    update(25599, 25599);
    assert(!max_descs_previous_hour_valid);
    update(25600, 25600);
    assert(max_descs_previous_hour_valid && max_descs_previous_hour == 6);

    // A forward wall-clock correction cannot publish a partial interval.
    start = 30000;
    monotonic_start = 30000ULL * 1000000;
    max_descs_previous_hour_valid = false;
    max_descs_this_hour = 11;
    update(33600, 30005);
    assert(!max_descs_previous_hour_valid && start == 33600);
    assert(max_descs_this_hour == used_descs);
    update(37199, 33604);
    assert(!max_descs_previous_hour_valid);
    update(37200, 33605);
    assert(max_descs_previous_hour_valid && max_descs_previous_hour == used_descs);
}
""".replace("@ROLLOVER@", rollover)

output = ROOT / "bin/tests"
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="completed-hour-connections-", dir=output) as directory:
    directory = Path(directory)
    source_file = directory / "rollover.cpp"
    binary = directory / "rollover"
    source_file.write_text(harness)
    subprocess.run(
        ["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", str(source_file), "-o", str(binary)],
        check=True,
    )
    subprocess.run([str(binary)], check=True)
