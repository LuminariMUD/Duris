#!/usr/bin/env python3
"""Execute WHERE and LOOKUP: shared name searches, colors, catalog text and bounded output."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function, source


text = source("actwiz.c").read_text()
line_info = text[text.index("struct line_info\n{"):text.index("// To sort the players")]
production = line_info + "\n" + "\n".join(
    extract_function("actwiz.c", signature)
    for signature in ("static bool staff_name_matches(", "void do_lookup(",
                      "int where_compare(", "void do_where(")
)

production = "\n".join(
    extract_function(file, signature)
    for file, signature in (
        ("handler.c", "bool isname(const char *str, const char *namelist)"),
        ("utility.c", "string strip_ansi("),
        ("utility.c", "void strToLower("),
        ("interp.c", "void half_chop("),
        ("interp.c", "char *one_argument("),
    )
) + "\n" + production

harness = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/utility.h"
#include "net/comm.h"
#include "core/mm.h"
#include "core/safe_format.h"
#include "world/db.h"
#include <cstdarg>
#include <algorithm>
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
int top_of_mobt = -1, top_of_objt = -1;
mm_ds *dead_mob_pool = nullptr, *dead_pconly_pool = nullptr;
static struct { char color = 'w'; } racewar_color[MAX_RACEWAR + 2]{};
static std::string output;
static int traps, pages;
bool ac_can_see(P_char, P_char, bool) { return true; }
bool ac_can_see_obj(P_char, P_obj, int) { return true; }
void send_to_char(const char *text, P_char) { output += text; }
void page_string(P_desc, char *text, int) { output += text; ++pages; }
void do_traplist(P_char, char *, int) { ++traps; output += "Traps\n"; }
void where_stat(P_char, char *) { abort(); }
void where_nowhere(P_char, char *) { abort(); }
char *where_obj(P_obj, int) { return const_cast<char *>("Test room"); }
std::string pad_ansi(const char *text, int, bool) { return text; }
char *FirstWord(char *text) { return text; }
void send_to_char_f(P_char, const char *format, ...) {
    char text[MAX_STRING_LENGTH]; va_list args; va_start(args, format);
    vsnprintf(text, sizeof(text), format, args); va_end(args); output += text;
}
void logit(const char *, const char *, ...) {}
int fill_word(char *) { return 0; }
void display_random_zones(P_char) { abort(); }
void ensure_pconly_pool() { abort(); }
void *_mm_get(mm_ds *, const char *, int) { abort(); }
int restoreCharOnly(P_char, char *) { abort(); }
int stripansi_2(const char *, char *) { abort(); }
const char *race_to_string(P_char) { abort(); }
char *get_class_string(P_char, char *) { abort(); }
char *skip_spaces(char *) { abort(); }
bool is_abbrev(const char *word, const char *full) {
    return *word && !strncmp(word, full, strlen(word));
}
bool is_number(char *) { return false; }
bool is_linked_to(P_char, P_char, unsigned short) { return false; }
int panic_corruption_int(const char *, const char *, ...) { abort(); }

// PRODUCTION

static void run(P_char viewer, const char *argument, bool lookup = false) {
    output.clear(); pages = 0;
    char input[MAX_INPUT_LENGTH]; strcpy(input, argument);
    if (lookup) do_lookup(viewer, input, 0);
    else do_where(viewer, input, 0);
}

static void check_name_searches(P_char viewer) {
    descriptor_data descriptor{};
    viewer->desc = &descriptor;
    viewer->player.level = 60;
    index_data entries[7]{};
    const char *keywords[] = {
        "giant fire guard", "sentinel", "fire giant", "thri-kreen",
        "giant fireball", "unspawned ember", nullptr,
    };
    const char *descriptions[] = {
        "&+Ra stone sentinel&n", "a &=Rbfi&+Gre &+Lgiant&n", "a fire giant",
        "a mantis guard", "a fireball construct", "a sleeping sentinel", nullptr,
    };
    char_data mobs[5]{};
    npc_only_data npc[5]{};
    obj_data objects[5]{};
    for (int i = 0; i < 7; ++i) {
        entries[i].virtual_number = 91001 + i;
        entries[i].keys = const_cast<char *>(keywords[i]);
        entries[i].desc2 = const_cast<char *>(descriptions[i]);
        entries[i].number = i < 5 ? 1 : 0;
        if (i >= 5) continue;
        mobs[i].specials.act = ACT_ISNPC;
        mobs[i].only.npc = &npc[i]; npc[i].R_num = i;
        mobs[i].player.name = entries[i].keys;
        mobs[i].player.short_descr = entries[i].desc2;
        mobs[i].in_room = 0;
        mobs[i].next = i < 4 ? &mobs[i+1] : nullptr;
        objects[i].R_num = i;
        objects[i].name = entries[i].keys;
        objects[i].short_description = entries[i].desc2;
        objects[i].next = i < 4 ? &objects[i+1] : nullptr;
    }
    mob_index = obj_index = entries;
    top_of_mobt = top_of_objt = 6;
    auto check = [&](const std::vector<int> &expected) {
        for (int i = 0; i < 7; ++i) {
            const std::string vnum = std::to_string(entries[i].virtual_number);
            const auto at = output.find(vnum);
            const bool wanted = std::find(expected.begin(), expected.end(), i) != expected.end();
            assert((at != std::string::npos) == wanted);
            if (wanted) assert(output.find(vnum, at + vnum.size()) == std::string::npos);
            assert(entries[i].number == (i < 5 ? 1 : 0));
        }
        assert(pages == !expected.empty());
    };
    for (const char *type : {"mob", "char", "obj"}) {
        character_list = !strcmp(type, "obj") ? nullptr : mobs;
        object_list = !strcmp(type, "obj") ? objects : nullptr;
        for (const char *pattern : {"fire-giant", "GIANT-FIRE", "fire giant"}) {
            const std::string query = std::string(type) + " " + pattern;
            run(viewer, query.c_str(), true);
            check(!strcmp(pattern, "fire giant") ? std::vector<int>{1, 2} : std::vector<int>{0, 1, 2});
            assert(output.find(descriptions[1]) != std::string::npos); // Preserve display colors.
            run(viewer, pattern);
            check(!strcmp(pattern, "fire giant") ? std::vector<int>{1, 2} : std::vector<int>{0, 1, 2});
        }
        for (const char *pattern : {"thri-kreen", "fire-troll", "fire--giant"}) {
            const std::string query = std::string(type) + " " + pattern;
            run(viewer, query.c_str(), true);
            check(!strcmp(pattern, "thri-kreen") ? std::vector<int>{3} : std::vector<int>{});
            run(viewer, pattern);
            check(!strcmp(pattern, "thri-kreen") ? std::vector<int>{3} : std::vector<int>{});
        }
        for (const char *pattern : {"StOnE", "tone sent", "#91001"}) {
            const std::string query = std::string(type) + " " + pattern;
            run(viewer, query.c_str(), true); check({0});
        }
        run(viewer, (std::string(type) + " re gi").c_str(), true); check({1, 2});
        run(viewer, "tone sent"); check({}); // Partial text remains LOOKUP-only.
        run(viewer, (std::string(type) + " unspawned-ember").c_str(), true); check({5});
        run(viewer, (std::string(type) + " 91006").c_str(), true); check({5});
        run(viewer, "unspawned-ember"); check({});
        run(viewer, (std::string(type) + " no-such-match").c_str(), true); check({});
        assert(output == "No matches found for pattern 'no-such-match'\n");
        run(viewer, (std::string(type) + " 91007").c_str(), true); check({6});
    }
    for (const char *query : {"", "mob", "obj", "unknown fire"}) {
        run(viewer, query, true);
        assert(output.starts_with("Syntax : lookup") && pages == 0);
    }
    // Empty catalogs and a catalog larger than the output limit stay bounded.
    top_of_mobt = top_of_objt = -1;
    mob_index = obj_index = nullptr;
    for (const char *type : {"mob", "obj"}) {
        run(viewer, (std::string(type) + " fire").c_str(), true);
        assert(output == "No matches found for pattern 'fire'\n" && !pages);
    }
    std::vector<index_data> many(2000);
    std::string description(200, 'x');
    for (int i = 0; i < 2000; ++i) {
        many[i].virtual_number = 100000 + i;
        many[i].keys = const_cast<char *>("crowd");
        many[i].desc2 = description.data();
    }
    mob_index = obj_index = many.data(); top_of_mobt = top_of_objt = 1999;
    for (const char *type : {"mob", "obj"}) {
        run(viewer, (std::string(type) + " crowd").c_str(), true);
        const std::string warning = "...and the list goes on...\n";
        assert(output.size() < MAX_STRING_LENGTH && pages == 1);
        assert(output.starts_with("#100000 ") && output.ends_with("~\n" + warning));
        assert(output.find(warning) == output.rfind(warning));
    }
    character_list = nullptr; object_list = nullptr;
    mob_index = obj_index = nullptr; top_of_mobt = top_of_objt = -1;
    viewer->desc = nullptr;
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
    check_name_searches(&viewer);
    puts("where/lookup: shared keywords, compounds, colors, partial text, cold prototypes, sorting and bounds passed");
}
'''

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="where-command-", dir=ROOT / "bin/tests") as directory:
    path, binary = Path(directory) / "test.cpp", Path(directory) / "test"
    path.write_text(harness.replace("// PRODUCTION", production))
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-Isrc", str(path), "src/core/safe_format.c", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
