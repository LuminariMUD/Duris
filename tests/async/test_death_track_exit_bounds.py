#!/usr/bin/env python3
"""A death leaves no track and reads no exit past the room's exit table.

death_cry() and the other death paths call add_track(ch, NUM_EXITS). add_track()
then tested EXIT(ch, NUM_EXITS), one past dir_option[NUM_EXITS], which reads the
next room field as an exit pointer and, when it was non-zero, left a track
"going" dirs[NUM_EXITS] (the "\\n" terminator). Found by an ASan/UBSan soak.

Compiles the production add_track() under ASan/UBSan with a room built as
db.c does and checks that no track is made for a death or for a real
direction with no exit.
"""

import os
import subprocess
import tempfile
from pathlib import Path

from _paths import HARNESS_STUBS, ROOT, extract_function, source

HARNESS = r'''
// INCLUDES
#include <cassert>
#include <cstdio>

#define MAX_TRACK_DURATION 90 * WAIT_SEC
P_room world;
const int track_limit[NUM_SECT_TYPES] = {};
const struct race_names race_names_table[LAST_RACE + 2] = {};
const char *dirs[NUM_EXITS + 1] = {};
static int tracks_made;
// Everything past add_track()'s exit check makes a track; reaching it fails the test.
P_obj read_object(int, int)
{
	tracks_made++;
	return nullptr;
}
int real_object(int) { return ++tracks_made, 0; }
int number(int low, int) { return ++tracks_made, low; }
int BOUNDED(int, int value, int) { return ++tracks_made, value; }
int IS_MORPH(P_char) { return 0; } // GET_PLYR() asks before the exit check
void extract_obj(P_obj, int) { ++tracks_made; }

// FUNCTIONS

int main()
{
	world = new room_data[2]{};
	world[1].room_flags = ~0UL; // the field after dir_option[]: non-zero, as most rooms
	char_data walker{};
	pc_only_data pc{};
	walker.only.pc = &pc;
	walker.in_room = 1;
	walker.player.race = RACE_HUMAN;
	walker.specials.position = POS_STANDING + STAT_NORMAL;

	add_track(&walker, NUM_EXITS); // what death_cry() passes
	add_track(&walker, DIR_NORTH); // a direction with no exit
	assert(tracks_made == 0);
	delete[] world;
	std::puts("deaths and walls leave no tracks");
}
'''

track = "cmd/track.c"
includes = "\n".join(line for line in source(track).read_text().splitlines()
                     if line.startswith("#include"))
(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="death-track-", dir=ROOT / "bin/tests") as tmp:
    harness = Path(tmp) / "track.cpp"
    harness.write_text(HARNESS.replace("// INCLUDES", includes).replace(
        "// FUNCTIONS", extract_function(track, "void add_track(P_char ch, int dir)")))
    binary = harness.with_suffix("")
    subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-fsanitize=address,undefined",
                    "-fno-sanitize-recover=undefined", "-fno-omit-frame-pointer",
                    "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                    "-Isrc", "-I/usr/include/mysql", str(harness), str(HARNESS_STUBS),
                    "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, env=dict(os.environ,
        ASAN_OPTIONS="detect_leaks=1:halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1"))
