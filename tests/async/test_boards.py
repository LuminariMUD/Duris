#!/usr/bin/env python3
"""The bulletin boards: board_info[] against the world, and boards.c under sanitizers.

Every board_info[] row in boards.c names a board in the world make_all builds: an object,
in an area file areas/AREA lists, whose keywords include "board" or "bulletin".
Object 42 was taken for a pearl necklace from areas/obj/dalvik.obj, which is not in the
world; the world's 42 is heavens.obj's board of IDEAS.

The production board() and find_board() run under ASan and UBSan. A board answers for
its own board_info[] row, found from the object whose special fired (room 1213 holds two
boards), and only while it stands in the character's room: special() also calls the
special for boards a character carries. A row whose object the world lacks keeps rnum
-1 and matches nothing.
"""
from pathlib import Path
import re
import subprocess
import tempfile

from _paths import ROOT, extract_function, source

AREAS = ROOT / "areas"
BOARDS = source("cmd/boards.c").read_text()
WORLD = [line.split()[0] for line in (AREAS / "AREA").read_text(errors="replace").splitlines()
         if line.strip() and not line.startswith("*")]

keywords = {}
for area in WORLD:
    path = AREAS / "obj" / f"{area}.obj"
    if path.is_file():
        for vnum, names in re.findall(r"^#(\d+)\s*\n([^~\n]*)~", path.read_text(errors="replace"),
                                      re.M):
            keywords[int(vnum)] = names.lower().split()
rows = [int(vnum) for vnum in re.findall(r"^\t\{ (\d+), ", BOARDS, re.M)]
assert len(rows) == int(re.search(r"#define NUM_OF_BOARDS (\d+)", BOARDS)[1]), rows
not_boards = [vnum for vnum in rows if not {"board", "bulletin"} & set(keywords.get(vnum, []))]
assert not not_boards, f"board_info[] rows that name no board in the world: {not_boards}"

PRELUDE = r'''
#include <cassert>
#include <string>
#include <vector>
struct obj_data { obj_data *next_content = nullptr; int R_num = 0, loc_p = 0; struct { int room = -1; } loc; };
struct descriptor_data { int unused = 0; };
struct char_data { int in_room = 0; descriptor_data *desc = nullptr; };
typedef obj_data *P_obj;
typedef char_data *P_char;
#define NUM_OF_BOARDS 3
#include "BOARDS_H"
#define FALSE 0
#define LOC_ROOM 1
#define OBJ_IN_ROOM(o, r) ((o) && ((o)->loc_p & LOC_ROOM) && (o)->loc.room == (r))
#define LOG_BOARD "board"
enum { CMD_SET_PERIODIC = -1, CMD_WRITE = 1, CMD_LOOK, CMD_EXAMINE, CMD_READ, CMD_REMOVE };
std::vector<std::string> logged;
void logit(const char *, const char *format, ...) { logged.push_back(format); }
board_info_type board_info[NUM_OF_BOARDS] = {
    {89, 0, 0, 0, "", 0}, {48101, 0, 0, 0, "", -1}, {90, 0, 0, 0, "", 1}};
int shown = -1;
void Board_write_message(int, char_data *, char *) {}
int Board_show_board(int board_type, char_data *, char *) { shown = board_type; return 1; }
int Board_display_msg(int, char_data *, char *) { return 1; }
int Board_remove_msg(int, char_data *, char *) { return 1; }
'''

DRIVER = r'''
int main() {
    descriptor_data link;
    char_data reader;
    reader.in_room = 7;
    reader.desc = &link;
    char look[] = "board";

    // Room 1213: the holy board (row 0) and the feedback board (row 2) side by side.
    obj_data holy, feedback;
    holy.R_num = 0;
    feedback.R_num = 1;
    for (obj_data *standing : {&holy, &feedback}) {
        standing->loc_p = LOC_ROOM;
        standing->loc.room = 7;
    }
    feedback.next_content = &holy;
    assert(board(&holy, &reader, CMD_LOOK, look) == 1 && shown == 0);
    assert(board(&feedback, &reader, CMD_LOOK, look) == 1 && shown == 2);

    // A carried board is not the room's: no answer, nothing logged.
    obj_data carried;
    carried.R_num = 1;
    shown = -1;
    assert(board(&carried, &reader, CMD_LOOK, look) == FALSE && shown == -1 && logged.empty());

    // An object with no row passes over the rnum -1 row and is logged.
    obj_data plain;
    plain.R_num = 5;
    plain.loc_p = LOC_ROOM;
    plain.loc.room = 7;
    assert(find_board(&plain) == -1);
    assert(board(&plain, &reader, CMD_LOOK, look) == FALSE && logged.size() == 1);
}
'''

FUNCTIONS = ["int find_board(", "int board("]
harness = "\n".join([PRELUDE.replace("BOARDS_H", str(source("cmd/boards.h"))),
                     *(extract_function("cmd/boards.c", name) for name in FUNCTIONS), DRIVER])
with tempfile.TemporaryDirectory(prefix="boards-") as directory:
    cpp = Path(directory) / "test.cpp"
    binary = Path(directory) / "test"
    cpp.write_text(harness)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-g", str(cpp), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print(f"{len(rows)} board_info rows name world boards; each board answers for its own row")
