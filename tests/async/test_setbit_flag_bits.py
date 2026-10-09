#!/usr/bin/env python3
"""setbit sets a flag bit only where its 32-bit field has one.

ac_bitCopy() sets bit N of a 32-bit field. `setbit obj <item> race firbolg 1` asked
it for bit 35, an undefined shift that x86 wraps to bit 3, so the item denied grey
elves. The real setbit_parseTable() and ac_bitCopy() run against an item race list
built as setbit_obj() builds it, with UBSan stopping at its first report.
"""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, SRC, extract_function

source = (SRC / "actset.c").read_text()
# The file's own flag macros and table type, from bad_on_off to the SetBitTable typedef.
declarations = source[source.index("char bad_on_off"):source.index("/* Private Interface */")]
functions = [extract_function("actset.c", signature) for signature in (
    "static int ac_strcasecmp(const char *str1", "static void ac_bitCopy(void *where",
    "static void setbit_parseTable(P_char ch")]

HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include <cassert>
#include <cctype>
#include <cstddef>
#include <cstdio>
#include <string>

''' + declarations + r'''
static std::string sent;
void send_to_char(const char *message, P_char) { sent += message; }
bool is_number(char *value) { return value[0] && value[strspn(value, "-0123456789")] == 0; }
int checked_snprintf_at(const char *, int, char *, size_t, const char *, ...) { return 0; }
static void setbit_printOutTable(P_char, SetBitTable *, int) {}
static void setbit_printOutSubTable(P_char, const char **, int) {}
static void setbit_syntax(P_char, int) {}
static void ac_tongueCopy(void *, int, char *, int, int) {}
static void ac_skillCopy(void *, int, char *, int, int) {}
static int ac_strcasecmp(const char *, const char *);
''' + "\n".join(functions) + r'''
int main()
{
    static race_names races[LAST_RACE + 2]{};
    static char names[LAST_RACE + 1][16];
    for (int race = 1; race <= LAST_RACE; ++race) {
        snprintf(names[race], sizeof(names[race]), "race%d", race);
        races[race].no_spaces = names[race];
    }
    SetBitTable table[] = {
        { "race", int(offsetof(obj_data, anti2_flags)), (const char **)&races[1], ac_bitCopy,
          sizeof(race_names), int(offsetof(race_names, no_spaces)) },
        { "extra", int(offsetof(obj_data, extra_flags)), nullptr, ac_bitCopy },
    };
    obj_data obj{};
    char race[] = "race", extra[] = "extra";
    auto set = [&](char *flag, const char *value, int on_off) {
        char text[16];
        snprintf(text, sizeof(text), "%s", value);
        sent.clear();
        setbit_parseTable(nullptr, &obj, table, 2, flag, text, on_off, SETBIT_OBJ);
    };
    // Races 1-32 own bits 0-31, on and off; a race above 32 has no bit.
    set(race, "race1", 1);
    set(race, "race32", 1);
    assert(obj.anti2_flags == (1U | 1U << 31) && sent.empty());
    set(race, "race36", 1);
    assert(obj.anti2_flags == (1U | 1U << 31) && sent == "That field has no bit for that value.\r\n");
    set(race, "race32", 0);
    assert(obj.anti2_flags == 1U && sent.empty());
    // A flag given by number reaches only bits 0-31 as well.
    for (const char *number : {"-1", "32", "40"}) {
        set(extra, number, 1);
        assert(obj.extra_flags == 0 && sent == "That field has no bit for that value.\r\n");
    }
    set(extra, "31", 1);
    assert(obj.extra_flags == 1U << 31 && sent.empty());
    puts("setbit sets only the flag bits a field has");
}
'''


def main():
    with tempfile.TemporaryDirectory(prefix="duris-setbit-bits-") as directory:
        harness, binary = Path(directory) / "harness.cpp", Path(directory) / "harness"
        harness.write_text(HARNESS)
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
                        "-Isrc", str(harness), "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
