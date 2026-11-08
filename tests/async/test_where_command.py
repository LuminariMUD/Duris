#!/usr/bin/env python3
"""Execute production WHERE: trap dispatch, sorted lists and bounded zone output."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function, source


text = source("actwiz.c").read_text()
line_info = text[text.index("struct line_info\n{"):text.index("// To sort the players")]
production = line_info + "\n" + "\n".join(
    extract_function("actwiz.c", signature)
    for signature in ("int where_compare(", "void do_where(")
)

harness = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/utility.h"
#include "net/comm.h"
#include <cassert>
#include <climits>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

static room_data rooms[3]{};
P_room world = rooms;
const int top_of_world = 2;
static zone_data zones[1]{};
zone_data *zone_table = zones;
P_desc descriptor_list = nullptr;
P_char character_list = nullptr;
P_obj object_list = nullptr;
P_index mob_index = nullptr, obj_index = nullptr;
static struct { char color = 'w'; } racewar_color[MAX_RACEWAR + 2]{};
static std::string output;
static int traps, pages;
bool ac_can_see(P_char, P_char, bool) { return true; }
bool ac_can_see_obj(P_char, P_obj, int) { abort(); }
void send_to_char(const char *text, P_char) { output += text; }
void page_string(P_desc, char *text, int) { output += text; ++pages; }
void do_traplist(P_char, char *, int) { ++traps; output += "Traps\n"; }
void where_stat(P_char, char *) { abort(); }
void where_nowhere(P_char, char *) { abort(); }
char *where_obj(P_obj, int) { abort(); }
std::string pad_ansi(const char *text, int, bool) { return text; }
char *FirstWord(char *text) { return text; }
bool isname(const char *word, const char *list) { return !strcmp(word, list); }
bool is_abbrev(const char *word, const char *full) {
    return *word && !strncmp(word, full, strlen(word));
}
bool is_number(char *) { return false; }
bool is_linked_to(P_char, P_char, unsigned short) { return false; }
int panic_corruption_int(const char *, const char *, ...) { abort(); }
char *one_argument(const char *text, char *word) {
    strcpy(word, text); return const_cast<char *>(text + strlen(text));
}

// PRODUCTION

static void run(P_char viewer, const char *argument) {
    output.clear(); pages = 0;
    char input[MAX_INPUT_LENGTH]; strcpy(input, argument);
    do_where(viewer, input, 0);
}

int main() {
    line_info low{}, equal{}, high{};
    low.room_number = INT_MIN; equal.room_number = INT_MIN; high.room_number = INT_MAX;
    assert(where_compare(&low, &high) < 0);
    assert(where_compare(&high, &low) > 0);
    assert(where_compare(&low, &equal) == 0);

    char_data viewer{};
    run(&viewer, "trap");
    assert(traps == 1 && output == "Traps\n" && !pages);
    run(&viewer, "tr");
    assert(traps == 2 && output == "Traps\n" && !pages);

    std::vector<char_data> players(MAX_CONNECTIONS);
    std::vector<descriptor_data> descriptors(MAX_CONNECTIONS);
    for (int i = 0; i < MAX_CONNECTIONS; ++i) {
        players[i].player.name = const_cast<char *>("Player");
        players[i].player.racewar = RACEWAR_GOOD;
        players[i].in_room = i % 3;
        descriptors[i].character = &players[i];
        descriptors[i].connected = CON_PLAYING;
        descriptors[i].next = i+1 < MAX_CONNECTIONS ? &descriptors[i+1] : nullptr;
    }
    descriptor_list = descriptors.data();
    rooms[0].number = 300; rooms[1].number = 100; rooms[2].number = 200;
    for (auto &room : rooms) room.name = const_cast<char *>("Test room");
    players[0].player.name = const_cast<char *>("Last");
    players[1].player.name = const_cast<char *>("First");
    players[2].player.name = const_cast<char *>("Middle");
    descriptors[2].next = nullptr;
    for (const char *argument : {"", "goods"}) {
        run(&viewer, argument);
        assert(output.starts_with(*argument ? "Players (goods):\n" : "Players:\n"));
        assert(output.find("First") < output.find("Middle"));
        assert(output.find("Middle") < output.find("Last"));
        assert(!pages);
    }
    // Reserve a row for the warning when the final legal connection crosses
    // the output limit. Keep rows at 254 bytes, with room 0 one byte longer.
    for (auto &room : rooms) room.name = const_cast<char *>("");
    run(&viewer, "");
    const size_t header = output.find('\n', output.find('\n') + 1) + 1;
    const size_t row = output.find('\n', header) + 1 - header;
    std::string boundary_name(254 - row, 'x');
    std::string longer_name = boundary_name + "x";
    for (auto &room : rooms) room.name = boundary_name.data();
    rooms[0].name = longer_name.data();
    descriptors[2].next = &descriptors[3];
    for (const char *argument : {"", "goods"}) {
        run(&viewer, argument);
        assert(output.ends_with("   ...the list is too long...\n"));
    }
    // Long legal room text fills the output within the connection limit.
    std::string room_name(400, 'x');
    for (auto &room : rooms) room.name = room_name.data();
    descriptors[2].next = &descriptors[3];
    run(&viewer, "zone");
    const std::string warning = "   ...the list is too long...\n";
    assert(output.size() < MAX_STRING_LENGTH && pages == 1);
    assert(output.starts_with("Players in this zone:\n"));
    assert(output.ends_with(warning));
    assert(output.find(warning) == output.rfind(warning));
    puts("where command: trap-only output, room sorting, headers and bounded zone list passed");
}
'''

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="where-command-", dir=ROOT / "bin/tests") as directory:
    path, binary = Path(directory) / "test.cpp", Path(directory) / "test"
    path.write_text(harness.replace("// PRODUCTION", production))
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-Isrc", str(path), "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
