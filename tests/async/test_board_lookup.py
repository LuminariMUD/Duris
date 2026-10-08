#!/usr/bin/env python3
"""find_board() skips a board_info[] row whose object the world lacks.

initialize_boards() leaves such a row's rnum at -1 (the minimal world has 13 of the 44
board objects), and find_board() used it as an index into obj_index[]. The production
function runs under ASan and UBSan with a missing row before the board in the room.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import extract_function

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
print("find_board skips a board whose object the world lacks")
