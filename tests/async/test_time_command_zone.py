#!/usr/bin/env python3
"""`time` shows the server's time with the zone it is really in.

It used to add a second line, five hours earlier and labelled EST, which was an hour wrong
for the half of the year that is daylight time. This runs the command's own lines in a
zone that changes its clocks, in winter and in summer, and in a zone whose name is too long
for a small buffer.
"""
from _paths import SRC
import os
import subprocess
import tempfile
from pathlib import Path

source = (SRC / "actinf.c").read_text()
command = source[source.index("void do_time("):]
start = command.index("lt = localtime(&ct);")
end = command.index("send_to_char(Gbuf2, ch);", start) + len("send_to_char(Gbuf2, ch);")
assert "EST" not in command[:command.index("\n}\n")]

HARNESS = r'''
#include <cstdio>
#include <cstring>
#include <ctime>
#include <initializer_list>
constexpr int MAX_STRING_LENGTH = 4096;
struct character {};
using P_char = character *;
void send_to_char(const char *text, P_char) { fputs(text, stdout); }
void show(long ct)
{
	char Gbuf2[MAX_STRING_LENGTH];
	char *tmstr;
	struct tm *lt;
	P_char ch = nullptr;
''' + command[start:end] + r'''
}
int main()
{
	// 2026-01-15 and 2026-07-15, 12:00:00 UTC
	for (long at : { 1768478400L, 1784116800L })
		show(at);
}
'''

with tempfile.TemporaryDirectory(prefix="duris-time-zone-") as directory:
    temp = Path(directory)
    (temp / "time.cpp").write_text(HARNESS)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", str(temp / "time.cpp"),
                    "-o", str(temp / "time")], check=True)

    def shown(zone):
        return subprocess.run([str(temp / "time")], check=True, capture_output=True, text=True,
                              env={**os.environ, "TZ": zone}).stdout.splitlines()

    assert shown("America/New_York") == [
        "Current time is: Thu Jan 15 07:00:00 2026 (EST)",
        "Current time is: Wed Jul 15 08:00:00 2026 (EDT)",
    ], shown("America/New_York")
    # A 16-byte buffer for the zone printed stack bytes for a name this long.
    assert shown("<ABCDEFGHIJKLMNOP>5")[0] == \
        "Current time is: Thu Jan 15 07:00:00 2026 (ABCDEFGHIJKLMNOP)", \
        shown("<ABCDEFGHIJKLMNOP>5")

print("time command zone regression passed")
