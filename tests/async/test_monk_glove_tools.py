#!/usr/bin/env python3
"""Execute the server/editor valuation functions and positional extra2 names."""
from pathlib import Path
import os
import subprocess
import tempfile
from _paths import ROOT, HARNESS_STUBS, extract_function

RUNTIME = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "item/objmisc.h"
#include <cassert>
#include <cstdio>
#include <cmath>
static index_data index_data_fixture[1]{};
P_index obj_index = index_data_fixture;
extern const stat_data stat_factor[LAST_RACE + 1]{};
int get_mincircle(int spell) { return spell == 32 ? 1 : 0; }
int get_ival_from_proc(obj_proc_type) { assert(false); return 0; }
// FUNCTIONS
int main() {
    obj_data obj{};
    obj.type = ITEM_ARMOR; obj.wear_flags = ITEM_TAKE | ITEM_WEAR_HANDS;
    assert(itemvalue(&obj) == 1);
    obj.extra2_flags = ITEM2_MONK_PROC;
    assert(itemvalue(&obj) == 1); // The marker alone has no value.
    obj.value[5] = 32; obj.value[6] = 60; obj.value[7] = 30;
    assert(itemvalue(&obj) == 6);
    obj.value[6] = 0; assert(itemvalue(&obj) == 1); obj.value[6] = 60;
    obj.value[7] = 0; assert(itemvalue(&obj) == 1);
    obj.value[7] = 30; obj.extra2_flags = 0; assert(itemvalue(&obj) == 1);
    obj.extra2_flags = ITEM2_MONK_PROC; obj.value[0] = -10;
    assert(itemvalue(&obj) == 21); // Armor value remains alongside the proc.
    obj.value[0] = 0; obj.type = ITEM_WORN; assert(itemvalue(&obj) == 6);
    assert(ITEM2_ACCOUNT_BOUND == (1u << 17) && ITEM2_ENHANCED == (1u << 18));
    assert(ITEM2_MONK_PROC == (1u << 19));
    std::puts("runtime: empty=1 packed=6 armor+packed=21");
}
'''
EDITOR = r'''
#include "types.h"
#include "fh.h"
#include "obj/object.h"
#include "spells.h"
#define IS_SET(flag, bit) ((flag) & (bit))
#include <cassert>
#include <cstdio>
int get_mincircle(int spell) { return spell == 32 ? 1 : 0; }
// FUNCTIONS
int main() {
    objectType obj{};
    obj.objType = ITEM_ARMOR; obj.wearBits = ITEM_TAKE | ITEM_WEAR_HANDS;
    assert(itemvalue(&obj) == 1);
    obj.extra2Bits = ITEM2_MONK_PROC; assert(itemvalue(&obj) == 1);
    obj.objValues[5] = 32; obj.objValues[6] = 60; obj.objValues[7] = 30;
    assert(itemvalue(&obj) == 6);
    obj.objValues[6] = 0; assert(itemvalue(&obj) == 1); obj.objValues[6] = 60;
    obj.objValues[7] = 0; assert(itemvalue(&obj) == 1);
    obj.objValues[7] = 30; obj.extra2Bits = 0; assert(itemvalue(&obj) == 1);
    obj.extra2Bits = ITEM2_MONK_PROC; obj.objType = ITEM_WORN;
    assert(itemvalue(&obj) == 6);
    std::puts("editor: empty=1 packed=6");
}
'''

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="monk-glove-tools-", dir=ROOT / "bin/tests") as tmp:
    for name, code, source, signature in (
        ("runtime", RUNTIME, None, None),
        ("editor", EDITOR, "../areas/de/src/obj/object.cpp", "int itemvalue(objectType *obj)"),
    ):
        path = Path(tmp) / (name + ".cpp")
        path.write_text(code.replace("// FUNCTIONS", extract_function(source, signature)
                                     if source else ""))
        binary = path.with_suffix("")
        command = ["g++", "-std=c++20", "-g", "-O1", "-fsanitize=address,undefined",
                   "-fno-omit-frame-pointer", "-Isrc", "-Iareas/de/src", str(path)]
        command += [str(HARNESS_STUBS), "src/item/item_value.c", "src/item/item_value_runtime.c"] if name == "runtime" else ["-D_DE_", "-D__UNIX__"]
        subprocess.run(command + ["-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True, env=dict(os.environ,
            ASAN_OPTIONS="detect_leaks=1:halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1"))

common = (ROOT / "src/core/common.c").read_text().split("flagDef extra2_bits[] =", 1)[1].split("{}", 1)[0]
import re
names = re.findall(r'\{ "([A-Z_]+)"', common)
assert names[16:20] == ["TRANSPARENT", "ACCOUNT_BOUND", "ENHANCED", "MONK_PROC"]
print("extra2 flag names retain their numeric positions")

encrust = (ROOT / "src/classes/salchemist.c").read_text().split("void do_encrust", 1)[1]
refusal = encrust.index("if (IS_MONK_PROC_GLOVE(item))")
assert refusal < encrust.index("extract_obj(item)")
assert refusal < encrust.index("new_item->value[5] = jewel->value[6]")
print("encrust refuses opted-in gloves before consuming them")
