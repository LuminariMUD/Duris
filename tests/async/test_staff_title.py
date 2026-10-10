#!/usr/bin/env python3
"""Staff `title <text>` titles themselves unless the first word names a player.

A level 62 typing "title can be reached on Discord" in a room with a mob called
"can hy trader" used to title the mob: the server printed "Title Bestowed" with
the mob's keywords, then refused with "That field is undefined for monsters", and
the staff title stayed blank.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function
from _paths import HARNESS_STUBS

title = extract_function("actinf.c", "void do_title(P_char ch, char *arg, int /*cmd*/)")

HARNESS = r'''
#include "core/structs.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include <cassert>
#include <cctype>
#include <cstring>
#include <map>
#include <sstream>
#include <string>
#include <vector>

static std::map<P_char, std::string> screen;
static std::vector<P_char> everyone;
static std::string strung;

void send_to_char(const char *text, P_char ch) { screen[ch] += text; }
void clear_title(P_char ch) { strung = std::string("cleared ") + GET_NAME(ch); }
void do_string(P_char, char *arg, int) { strung = arg; }
P_char get_char_vis(P_char, const char *name)
{
    for (P_char ch : everyone)
    {
        std::istringstream words(GET_NAME(ch));
        for (std::string word; words >> word;)
            if (!strcasecmp(word.c_str(), name))
                return ch;
    }
    return nullptr;
}
char *one_argument(const char *argument, char *first)
{
    while (isspace(*argument))
        ++argument;
    while (*argument > ' ')
        *first++ = static_cast<char>(tolower(*argument++));
    *first = '\0';
    return const_cast<char *>(argument);
}
''' + title + r'''

struct being
{
    char_data ch = {};
    char name[64];

    being(const char *who, int level, bool npc = false)
    {
        snprintf(name, sizeof(name), "%s", who);
        ch.player.name = name;
        ch.player.level = level;
        if (npc)
            SET_BIT(ch.specials.act, ACT_ISNPC);
        everyone.push_back(&ch);
    }
};

static std::string type(being &who, const char *text)
{
    std::string line = text;
    strung.clear();
    screen[&who.ch].clear();
    do_title(&who.ch, line.data(), 0);
    return screen[&who.ch];
}

int main()
{
    being mob("can hy trader human man", 40, true);
    being zusuk("Zusuk", 62);
    being builder("Builder", 61);
    being tanen("Tanen", 30);

    // The report: a mob's name is part of the staff member's own title.
    assert(type(zusuk, "can be reached on Discord") ==
           "Title Bestowed:\nZusuk can be reached on Discord\n");
    assert(strung == "char Zusuk title can be reached on Discord");

    // Naming a player still titles that player, and naming oneself works too.
    type(zusuk, "tanen the Brave");
    assert(strung == "char Tanen title the Brave");
    type(zusuk, "zusuk the Great");
    assert(strung == "char Zusuk title the Great");

    // A bare "title" clears one's own title.
    assert(type(zusuk, "") == "Zusuk's title cleared.\n" && strung == "cleared Zusuk");

    // Staff still cannot retitle a superior.
    assert(type(builder, "zusuk nope") ==
           "Sorry, you can't change the title of your superiors!\n" && strung.empty());

    // A mortal's first word is never a target.
    type(tanen, "zusuk fan");
    assert(strung == "char Tanen title zusuk fan");
    puts("staff title names a player or titles themselves");
}
'''

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="staff-title-", dir=ROOT / "bin/tests") as tmp:
    test, binary = Path(tmp) / "test.cpp", Path(tmp) / "test"
    test.write_text(HARNESS)
    subprocess.run(["g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-I", str(ROOT / "src"), str(test), str(HARNESS_STUBS), "-o",
                    str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
