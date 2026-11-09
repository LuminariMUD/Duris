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
#include "item/item_value_procs.h"
#include <cassert>
#include <cstdio>
#include <cmath>
static index_data index_data_fixture[1]{};
P_index obj_index = index_data_fixture;
int top_of_objt = 0;
extern const stat_data stat_factor[LAST_RACE + 1]{};
int get_mincircle(int spell) { return spell == 32 ? 1 : 0; }
item_value_proc_entry item_value_proc(obj_proc_type proc) { assert(!proc); return {nullptr, "none", 0, item_value_proc_policy::none}; }
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
    // COMMON CASES
    std::puts("runtime: empty=1 packed=6 armor+packed=21");
}
'''
EDITOR = r'''
#include "types.h"
#include "fh.h"
#include "obj/object.h"
#include "spells.h"
#include "item/item_value.h"
#include "item/objmisc.h"
#include <cassert>
#include <cstdio>
#include <string>
int get_mincircle(int spell) { return spell == 32 ? 1 : 0; }
static std::string output;
static objectType *catalog_fixture[2]{};
objectType **g_objLookup = catalog_fixture;
uint getLowestObjNumber() { return 0; }
uint getHighestObjNumber() { return 1; }
void _outtext(const char *text) { output += text; }
void displayColorString(const char *text) { output += text; }
void displayColorString(char *text) { output += text; }
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
    // COMMON CASES
    obj = {}; obj.objType = ITEM_WORN; obj.wearBits = ITEM_TAKE;
    obj.objApply[0] = {APPLY_HIT, 0, 10};
    obj.objApply[3] = {APPLY_STR_RACE, 0, 1};
    assert(itemvalue(&obj) == 29); // Racial context is unavailable; no invented factor.
    obj.objApply[3] = {};
    std::snprintf(obj.objShortName, sizeof(obj.objShortName), "valuation fixture");
    catalog_fixture[1] = &obj;
    huntForOPEquipment("29");
    assert(output.find("Estimate only:") != std::string::npos);
    assert(output.find("native procs, racial bonuses, specialization circles") != std::string::npos);
    assert(output.find("valuation fixture") != std::string::npos);
    assert(output.find("has estimated ival &n29") != std::string::npos);
    output.clear(); huntForOPEquipment("30");
    assert(output.find("valuation fixture") == std::string::npos);
    std::puts("editor: empty=1 packed=6");
}
'''

COMMON = r'''
    obj = {}; obj.type = ITEM_WORN; obj.wear_flags = ITEM_TAKE;
    obj.affected[0].location = APPLY_HIT; obj.affected[0].modifier = 10;
    assert(itemvalue(&obj) == 29);
    obj.affected[0].location = APPLY_HITROLL; obj.affected[0].modifier = 3;
    assert(itemvalue(&obj) == 37);
    obj = {}; obj.type = ITEM_ARMOR; obj.wear_flags = ITEM_TAKE;
    obj.value[0] = 10; assert(itemvalue(&obj) == 15);
    obj = {}; obj.type = ITEM_WORN; obj.wear_flags = ITEM_TAKE;
    obj.affected[3].location = APPLY_STR; obj.affected[3].modifier = 6;
    assert(itemvalue(&obj) == 25);
    obj = {}; obj.type = ITEM_WORN; obj.wear_flags = ITEM_TAKE;
    obj.bitvector4 = AFF4_PROT_LIVING; assert(itemvalue(&obj) == 45);
    obj = {}; obj.type = ITEM_WEAPON; obj.wear_flags = ITEM_TAKE;
    obj.value[0] = WEAPON_LONGSWORD; obj.value[1] = 2; obj.value[2] = 6;
    assert(itemvalue(&obj) == 12);
    obj = {}; obj.type = ITEM_WORN; obj.wear_flags = ITEM_TAKE;
    obj.affected[0].location = APPLY_HIT; obj.affected[0].modifier = 10;
    obj.affected[3].location = APPLY_HITROLL; obj.affected[3].modifier = 0;
    assert(itemvalue(&obj) == 29); // Zero hitroll is neutral in both shared consumers.
'''

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="monk-glove-tools-", dir=ROOT / "bin/tests") as tmp:
    for name, code, source, signature in (
        ("runtime", RUNTIME, None, None),
        ("editor", EDITOR, "../areas/de/src/obj/object.cpp", "int itemvalue(objectType *obj)"),
    ):
        path = Path(tmp) / (name + ".cpp")
        common = COMMON
        if name == "editor":
            for runtime, editor in ((".type", ".objType"), (".wear_flags", ".wearBits"),
                                    (".value[", ".objValues["), (".affected[", ".objApply["),
                                    (".bitvector4", ".affect4Bits"),
                                    (".location", ".applyWhere"), (".modifier", ".applyModifier")):
                common = common.replace(runtime, editor)
        functions = extract_function(source, signature) if source else ""
        if name == "editor":
            functions += "\n" + extract_function(source, "void huntForOPEquipment(const char *args)\n{")
        path.write_text(code.replace("// FUNCTIONS", functions).replace("// COMMON CASES", common))
        binary = path.with_suffix("")
        command = ["g++", "-std=c++20", "-g", "-O1", "-fsanitize=address,undefined",
                   "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                   "-fno-omit-frame-pointer", "-Isrc", "-Iareas/de/src", str(path)]
        command += ["src/item/item_value.c"]
        command += [str(HARNESS_STUBS), "src/item/item_value_runtime.c"] if name == "runtime" else ["-D_DE_", "-D__UNIX__"]
        subprocess.run(command + ["-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True, env=dict(os.environ,
            ASAN_OPTIONS="detect_leaks=1:halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1"))

    circles = r'''
#include "types.h"
#include "fh.h"
#include "obj/object.h"
#include "spells.h"
#include <cassert>
#include <initializer_list>
Skill skills[MAX_AFFECT_TYPES]{};
// CIRCLES
int main() {
    assert(get_mincircle(0) == 0 && get_mincircle(LAST_SPELL + 1) == 0);
    for (int spell : {FIRST_SPELL, LAST_SPELL}) {
        assert(get_mincircle(spell) == 13);
        skills[spell].minLevel[0] = 2;
        assert(get_mincircle(spell) == 2);
        skills[spell].minLevel[0] = 0;
        skills[spell].minLevel[CLASS_COUNT - 1] = 3;
        skills[spell].minLevel[CLASS_COUNT] = 1; // The sentinel is not a class.
        assert(get_mincircle(spell) == 3);
    }
}
'''
    source, binary = Path(tmp) / "circles.cpp", Path(tmp) / "circles"
    source.write_text(circles.replace("// CIRCLES", extract_function(
        "../areas/de/src/obj/object.cpp", "int get_mincircle(int spell)\n{")))
    subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-D_DE_", "-D__UNIX__",
                    "-Isrc", "-Iareas/de/src", "-fsanitize=address,undefined",
                    "-fno-pie", "-no-pie", str(source), "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)

menu = (ROOT / "areas/de/src/menudef.cpp").read_text()
view = (ROOT / "areas/de/src/misc/menu.cpp").read_text()
assert '"ival estimate: "' in menu and '"%d (verify on server)"' in view

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
