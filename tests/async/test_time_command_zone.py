#!/usr/bin/env python3
"""`time` shows the server's time with the zone it is really in.

It used to add a second line, five hours earlier and labelled EST, which was an hour wrong
for the half of the year that is daylight time. This runs the command's own lines in a
zone that changes its clocks, in winter and in summer.
"""
from _paths import SRC
import os
import subprocess
import tempfile
from pathlib import Path

source = (SRC / "actinf.c").read_text()
command = source[source.index("void do_time("):]
start = command.index("char zone[16];")
end = command.index("send_to_char(Gbuf2, ch);", start) + len("send_to_char(Gbuf2, ch);")
assert "EST" not in command[:command.index("\n}\n")]

HARNESS = r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <string>
constexpr int MAX_STRING_LENGTH = 4096;
struct character {};
using P_char = character *;
std::string shown;
void send_to_char(const char *text, P_char) { shown = text; }
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
	show(1768478400); // 2026-01-15 12:00:00 UTC
	assert(shown == "Current time is: Thu Jan 15 07:00:00 2026 (EST)\n");
	show(1784116800); // 2026-07-15 12:00:00 UTC
	assert(shown == "Current time is: Wed Jul 15 08:00:00 2026 (EDT)\n");
}
'''

with tempfile.TemporaryDirectory(prefix="duris-time-zone-") as directory:
    temp = Path(directory)
    (temp / "time.cpp").write_text(HARNESS)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", str(temp / "time.cpp"),
                    "-o", str(temp / "time")], check=True)
    subprocess.run([str(temp / "time")], check=True, env={**os.environ, "TZ": "America/New_York"})

print("time command zone regression passed")
