#!/usr/bin/env python3
"""The bulletin boards: board_info[] against the world, and boards.c under sanitizers.

Every board_info[] row in boards.c names a board in the world make_all builds: an object,
in an area file areas/AREA lists, whose keywords include "board" or "bulletin".
Object 42 was taken for a pearl necklace from areas/obj/dalvik.obj, which is not in the
world; the world's 42 is heavens.obj's board of IDEAS.
No zone loads two different boards into one room: write, read <n> and remove <n> name
no board, so the first board in the room took them all and room 1213's second was dead.

The production board() and find_board() run under ASan and UBSan. A board answers for
its own board_info[] row, found from the object whose special fired (room 1213 holds two
boards), and only while it stands in the character's room: special() also calls the
special for boards a character carries. A row whose object the world lacks keeps rnum
-1 and matches nothing.

Board_write_message() keeps at most 70 characters of a headline and writes nothing into
the command line: it once cut the headline with arg[71] = '\0', past the end of the
1024-byte line when the headline started near its end. A write with no headline takes
no message slot: it once took one for good, and the boards share INDEX_SIZE slots.
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

boards_in_room = {}
for area in WORLD:
    path = AREAS / "zon" / f"{area}.zon"
    if path.is_file():
        for vnum, room in re.findall(r"^O\s+\d+\s+(\d+)\s+\d+\s+(\d+)",
                                     path.read_text(errors="replace"), re.M):
            if int(vnum) in rows:
                boards_in_room.setdefault(int(room), set()).add(int(vnum))
crowded = {room: sorted(vnums) for room, vnums in boards_in_room.items() if len(vnums) > 1}
assert boards_in_room and not crowded, f"rooms the zones give two boards: {crowded}"

PRELUDE = r'''
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <string>
#include <vector>
struct obj_data { obj_data *next_content = nullptr; int R_num = 0, loc_p = 0; struct { int room = -1; } loc; };
struct descriptor_data { char **str = nullptr; int max_str = 0; };
struct char_data {
    int in_room = 0, level = 0;
    descriptor_data *desc = nullptr;
    const char *name = "Writer";
    struct { unsigned act = 0; } specials;
};
typedef obj_data *P_obj;
typedef char_data *P_char;
#define NUM_OF_BOARDS 3
#include "BOARDS_H"
#define FALSE 0
#define TRUE 1
#define MAX_INPUT_LENGTH 1024
#define LOC_ROOM 1
#define TO_ROOM 1
#define PLR_WRITE 1
#define MEM_TAG_STRING 0
#define GET_LEVEL(ch) ((ch)->level)
#define GET_NAME(ch) ((ch)->name)
#define IS_NPC(ch) false
#define SET_BIT(flags, bit) ((flags) |= (bit))
#define CREATE(result, type, num, tag) ((result) = (type *)calloc((num), sizeof(type)))
#define OBJ_IN_ROOM(o, r) ((o) && ((o)->loc_p & LOC_ROOM) && (o)->loc.room == (r))
#define LOG_BOARD "board"
enum { CMD_SET_PERIODIC = -1, CMD_WRITE = 1, CMD_LOOK, CMD_EXAMINE, CMD_READ, CMD_REMOVE };
std::vector<std::string> logged;
void logit(const char *, const char *format, ...) { logged.push_back(format); }
std::vector<std::string> told;
void send_to_char(const char *text, char_data *) { told.push_back(text); }
void act(const char *, int, char_data *, void *, void *, int) {}
char *skip_spaces(char *text) { while (*text == ' ') text++; return text; }
char *msg_storage[INDEX_SIZE];
int msg_storage_taken[INDEX_SIZE];
int num_of_msgs[NUM_OF_BOARDS];
board_msginfo msg_index[NUM_OF_BOARDS][MAX_BOARD_MESSAGES];
board_info_type board_info[NUM_OF_BOARDS] = {
    {89, 0, 0, 0, "", 0}, {48101, 0, 0, 0, "", -1}, {90, 0, 0, 0, "", 1}};
int shown = -1;
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

    // A headline that starts near the end of the 1024-byte command line.
    char_data writer;
    writer.desc = &link;
    char *line = new char[MAX_INPUT_LENGTH];
    memset(line, ' ', MAX_INPUT_LENGTH);
    strcpy(line + MAX_INPUT_LENGTH - 3, "hi");
    Board_write_message(0, &writer, line + strlen("write"));
    delete[] line;
    assert(num_of_msgs[0] == 1 && strstr(MSG_HEADING(0, 0), "(Writer)] hi"));
    assert(writer.desc->str == &msg_storage[MSG_SLOTNUM(0, 0)]);

    // A long headline keeps 70 characters.
    std::string headline(100, 'x');
    Board_write_message(0, &writer, headline.data());
    std::string heading = MSG_HEADING(0, 1);
    assert(heading.substr(heading.find("] ") + 2) == std::string(70, 'x'));

    // No headline, no slot.
    char blank[] = "   ";
    Board_write_message(0, &writer, blank);
    assert(told.back() == "We must have a headline!\r\n" && num_of_msgs[0] == 2);
    int taken = 0;
    for (int slot : msg_storage_taken)
        taken += slot;
    assert(taken == 2);
}
'''

# A definition's signature ends its line; boards.c declares some of these above the table.
FUNCTIONS = ["int find_slot(void)\n", "int find_board(P_obj obj)\n",
             "int board(P_obj obj, P_char ch, int cmd, char *argument)\n",
             "void Board_write_message(int board_type, struct char_data *ch, char *arg)\n"]
harness = "\n".join([PRELUDE.replace("BOARDS_H", str(source("cmd/boards.h"))),
                     *(extract_function("cmd/boards.c", name) for name in FUNCTIONS), DRIVER])
with tempfile.TemporaryDirectory(prefix="boards-") as directory:
    cpp = Path(directory) / "test.cpp"
    binary = Path(directory) / "test"
    cpp.write_text(harness)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-g", str(cpp), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print(f"{len(rows)} board_info rows name world boards; each board answers for its own row; "
      "a headline is cut at 70 characters without writing into the command line, "
      "and a write without one takes no slot")
