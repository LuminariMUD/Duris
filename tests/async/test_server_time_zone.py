#!/usr/bin/env python3
"""`time` and the staff login channel show the server's time with the zone it is really in.

`time` used to add a second line, five hours earlier and labelled EST, and the channel's
lines carried the same kind of stamp: each an hour wrong for half of the year. This runs
the command's own lines and the production loginlog() in a zone that changes its clocks, in
winter and in summer, and in a zone whose name is too long for a small buffer.
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


def function(text, signature):
    return text[text.index(signature):].split("\n}\n", 1)[0] + "\n}\n"


utility = (SRC / "utility.c").read_text()

HARNESS = r'''
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <initializer_list>
constexpr int MAX_STRING_LENGTH = 4096;
constexpr int CON_PLAYING = 0;
constexpr unsigned PLR_PLRLOG = 1;
struct character
{
	int level;
	struct
	{
		unsigned act;
	} specials;
};
using P_char = character *;
struct descriptor
{
	descriptor *next;
	int connected;
	P_char character;
};
using P_desc = descriptor *;
#define IS_TRUSTED(ch) true
#define GET_LEVEL(ch) ((ch)->level)
#define IS_SET(flag, bit) ((flag) & (bit))
P_desc descriptor_list;
void send_to_char(const char *text, P_char) { fputs(text, stdout); }
void show(long ct)
{
	char Gbuf2[MAX_STRING_LENGTH];
	char *tmstr;
	struct tm *lt;
	P_char ch = nullptr;
''' + command[start:end] + r'''
}
time_t now;
#define time(ignored) now
''' + function(utility, "static char *format_variadic_message(") + function(
    utility, "void loginlog(") + r'''
int main()
{
	character staff{ 62, { PLR_PLRLOG } };
	descriptor link{ nullptr, CON_PLAYING, &staff };
	descriptor_list = &link;
	// 2026-01-15 and 2026-07-15, 12:00:00 UTC
	for (long at : { 1768478400L, 1784116800L })
	{
		show(at);
		now = at;
		loginlog(1, "%s has voided in [%d].", "Kavorin", 3001);
	}
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
        "&+c*** LOGMSG: 07:00:00 EST&n Kavorin has voided in [3001].",
        "Current time is: Wed Jul 15 08:00:00 2026 (EDT)",
        "&+c*** LOGMSG: 08:00:00 EDT&n Kavorin has voided in [3001].",
    ], shown("America/New_York")
    # A 16-byte buffer for the zone printed stack bytes for a name this long.
    assert shown("<ABCDEFGHIJKLMNOP>5")[:2] == [
        "Current time is: Thu Jan 15 07:00:00 2026 (ABCDEFGHIJKLMNOP)",
        "&+c*** LOGMSG: 07:00:00 ABCDEFGHIJKLMNOP&n Kavorin has voided in [3001].",
    ], shown("<ABCDEFGHIJKLMNOP>5")

print("server time zone regression passed")
