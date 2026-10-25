#!/usr/bin/env python3
"""Execute the area editor's trap formatter with the runtime direction bits."""
from pathlib import Path
import re
import subprocess
import tempfile

from _paths import ROOT

editor = ROOT / "areas/de/src"
source = (editor / "obj/objtypes.cpp").read_text()
formatter = source[source.index("char *getObjTrapFlagsStrn("):]
formatter = formatter[:formatter.index("\n}") + 2]
flags = (editor / "flagdef.cpp").read_text().split("g_objTrapFlagDef[] =", 1)[1]
labels = re.findall(r'\{ "([A-Z]+)"', flags.split("};", 1)[0])
assert labels == ["MOVE", "OBJECT", "ROOM", "NORTH", "EAST", "SOUTH", "WEST",
                  "UP", "DOWN", "OPEN", "MULTI", "GLYPH"], labels

harness = r'''
#include <cassert>
#include <cstring>
#include <string>
#include "obj/traps.h"
using uint = unsigned int;
''' + formatter + r'''
int main() {
    static_assert(TRAP_EFF_NORTH == 8 && TRAP_EFF_EAST == 16);
    static_assert(TRAP_EFF_SOUTH == 32 && TRAP_EFF_WEST == 64);
    static_assert(TRAP_EFF_UP == 128 && TRAP_EFF_DOWN == 256);
    char text[128];
    const char *directions[] = {"&+yN", "&+yE", "&+yS", "&+yW", "&+yU", "&+yD"};
    for (uint mask = 0; mask < 4096; ++mask) {
        assert(getObjTrapFlagsStrn(mask, text) == text);
        assert(strlen(text) < sizeof(text));
        if (!mask) assert(!strcmp(text, "none"));
        for (int dir = 0; dir < 6; ++dir)
            assert((strstr(text, directions[dir]) != nullptr) == !!(mask & (8 << dir)));
        assert((strstr(text, "&+cO") != nullptr) == !!(mask & TRAP_EFF_OPEN));
        assert((strstr(text, "&+GM") != nullptr) == !!(mask & TRAP_EFF_MULTI));
        assert((strstr(text, "&+BG") != nullptr) == !!(mask & TRAP_EFF_GLYPH));
    }
    assert(!strcmp(getObjTrapFlagsStrn(17, text), "&+WM&n|&+yE"));
    assert(!strcmp(getObjTrapFlagsStrn(65, text), "&+WM&n|&+yW"));
    assert(!strcmp(getObjTrapFlagsStrn(516, text), "&+rR&n|&+cO&n"));
}
'''
build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="legacy-trap-editor-", dir=build) as directory:
    cpp = Path(directory) / "test.cpp"
    binary = Path(directory) / "test"
    cpp.write_text(harness)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
                    "-I" + str(editor), str(cpp), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print("legacy trap editor: all 4096 flag combinations passed (ASan/UBSan)")
