#!/usr/bin/env python3
"""The bulletin boards: board_info[] against the world, and find_board() under sanitizers.

Every board_info[] row in boards.c names a board in the world make_all builds: an object,
in an area file areas/AREA lists, whose keywords include "board" or "bulletin".
Object 42 was taken for a pearl necklace from areas/obj/dalvik.obj, which is not in the
world; the world's 42 is heavens.obj's board of IDEAS.

find_board() skips a row whose object the world lacks: initialize_boards() leaves such a
row's rnum at -1, and find_board() used it as an index into obj_index[]. The production
function runs under ASan and UBSan with a missing row before the board in the room.
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
#include <vector>
struct obj_data { obj_data *next_content = nullptr; int R_num = 0; };
struct index_data { int virtual_number = 0; };
struct room_data { obj_data *contents = nullptr; };
struct char_data { int in_room = 0; };
typedef obj_data *P_obj;
struct board_info_type { int vnum, rnum; };
#define NUM_OF_BOARDS 3
#define BOARD_RNUM(i) (board_info[i].rnum)
board_info_type board_info[NUM_OF_BOARDS] = {{89, 0}, {48101, -1}, {29, 1}};
std::vector<index_data> objects(2);
index_data *obj_index;
room_data world[1];
'''

DRIVER = r'''
int main() {
    obj_index = objects.data();
    objects[0].virtual_number = 89;
    objects[1].virtual_number = 29;
    obj_data board_29;
    board_29.R_num = 1;
    world[0].contents = &board_29;
    char_data reader;
    assert(find_board(&reader) == 2);
    world[0].contents = nullptr;
    assert(find_board(&reader) == -1);
}
'''

harness = "\n".join([PRELUDE, extract_function("cmd/boards.c", "int find_board("), DRIVER])
with tempfile.TemporaryDirectory(prefix="board-lookup-") as directory:
    cpp = Path(directory) / "test.cpp"
    binary = Path(directory) / "test"
    cpp.write_text(harness)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-g", str(cpp), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print(f"{len(rows)} board_info rows name world boards; find_board skips a missing one")
