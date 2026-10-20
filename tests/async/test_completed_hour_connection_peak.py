#!/usr/bin/env python3
"""Execute the production socket-peak rollover with controlled server time."""

from _paths import ROOT, extract_function, source
from pathlib import Path
import subprocess
import tempfile

comm = source("comm.c").read_text(encoding="utf-8")
who = extract_function("actinf.c", "void do_who(")
rollover = extract_function("comm.c", "static void update_completed_hour_connection_peak(")
assert "update_completed_hour_connection_peak(time(0), last_desc_per_hour_reset);" in comm
assert "max_descs_this_hour = used_descs;\n\tmax_descs_previous_hour_valid = false;" in comm
assert "if (used_descs > max_descs_this_hour)" in comm
assert "max_descs_this_hour" not in who
assert "max_descs_previous_hour_valid" in who

harness = r"""
#include <cassert>
int used_descs = 0;
int max_descs_this_hour = 0;
int max_descs_previous_hour = 0;
bool max_descs_previous_hour_valid = false;

@ROLLOVER@

int main()
{
    long start = 1000;
    used_descs = 3;
    max_descs_this_hour = used_descs; // cold boot/recovery baseline
    update_completed_hour_connection_peak(4599, start);
    assert(!max_descs_previous_hour_valid && max_descs_this_hour == 3);
    assert(start == 1000);

    // The highest accepted concurrency, not accumulated logins, is published.
    max_descs_this_hour = 7;
    used_descs = 2;
    update_completed_hour_connection_peak(4600, start);
    assert(max_descs_previous_hour_valid && max_descs_previous_hour == 7);
    assert(max_descs_this_hour == 2 && start == 4600);

    // The published sample is frozen during the next reporting period.
    max_descs_this_hour = 12;
    update_completed_hour_connection_peak(8199, start);
    assert(max_descs_previous_hour == 7 && max_descs_this_hour == 12);
    used_descs = 0;
    update_completed_hour_connection_peak(8200, start);
    assert(max_descs_previous_hour_valid && max_descs_previous_hour == 12);
    assert(max_descs_this_hour == 0 && start == 8200);

    // No active socket and no new connection is a measured zero peak.
    update_completed_hour_connection_peak(11800, start);
    assert(max_descs_previous_hour_valid && max_descs_previous_hour == 0);

    // Backwards wall-clock jumps cannot publish a partial/unknown hour.
    max_descs_this_hour = 15;
    used_descs = 4;
    update_completed_hour_connection_peak(11000, start);
    assert(!max_descs_previous_hour_valid && start == 11000);
    assert(max_descs_this_hour == 4);

    // Long pauses also invalidate the old sample, rather than re-label it.
    max_descs_this_hour = 9;
    update_completed_hour_connection_peak(18200, start);
    assert(!max_descs_previous_hour_valid && start == 18200);
    assert(max_descs_this_hour == 4);
    update_completed_hour_connection_peak(21800, start);
    assert(max_descs_previous_hour_valid && max_descs_previous_hour == 4);

    // A fresh process/copyover starts without carrying an unverified sample.
    max_descs_previous_hour_valid = false;
    used_descs = 6;
    max_descs_this_hour = used_descs;
    start = 22000;
    update_completed_hour_connection_peak(25599, start);
    assert(!max_descs_previous_hour_valid);
    update_completed_hour_connection_peak(25600, start);
    assert(max_descs_previous_hour_valid && max_descs_previous_hour == 6);
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
