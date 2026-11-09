#!/usr/bin/env python3
"""Execute the production compiled-object binding catalog without game boot."""
from pathlib import Path
import os
import re
import subprocess
import tempfile

from _paths import ROOT, extract_function, source


HARNESS = r'''
#include "core/prototypes.h"
#include "specs/object_bindings.h"
#include <array>
#include <cassert>
#include <cstring>
#include <map>
#include <vector>

static int callbacks;
// CALLBACKS
static std::array<index_data, 1024> indexes;
P_index obj_index = nullptr;
static std::map<int, int> slots;
static std::vector<int> lookups;
int real_object0(int vnum)
{
    lookups.push_back(vnum);
    auto found = slots.find(vnum);
    return found == slots.end() ? 0 : found->second;
}
int number(int, int) { assert(false); return 0; }

static void prepare(bool omit_thirty = false)
{
    indexes = {};
    obj_index = indexes.data(); slots.clear(); lookups.clear();
    for (auto stage : {object_proc_binding_stage::objects, object_proc_binding_stage::rooms})
        for (const auto &entry : object_proc_bindings(stage))
            if ((!omit_thirty || entry.vnum != 30) && !slots.contains(entry.vnum))
                slots.emplace(entry.vnum, slots.size() + 1);
    assert(slots.size() < indexes.size());
    for (auto &entry : indexes) { entry.number = 7; entry.limit = 99; }
}

int main()
{
    using stage = object_proc_binding_stage;
    const auto objects = object_proc_bindings(stage::objects);
    const auto rooms = object_proc_bindings(stage::rooms);
    assert(objects.size() == 479 && rooms.size() == 20);
    assert(objects.front().vnum == 500055 && rooms.back().vnum == 55434);
    assert(!std::strcmp(objects.front().name, "tharnrifts_portal"));
    assert(!std::strcmp(rooms.back().name, "blackjack_table"));
    assert(lookups.empty()); // Inspecting metadata does not touch even the object index.
    assign_object_proc_bindings(stage::objects); // An empty offline catalog is valid.
    assert(lookups.empty());

    prepare();
    assign_object_proc_bindings(stage::objects);
    assert(lookups.size() == 479 && lookups[0] == 500055 && lookups[1] == 55007);
    assert(indexes[slots.at(30)].func.obj == staff_of_power); // Later override beats varon.
    assert(indexes[slots.at(55434)].func.obj == nullptr); // The room stage is still separate.
    assign_object_proc_bindings(stage::rooms);
    assert(lookups.size() == 499);
    assert(indexes[slots.at(55434)].func.obj == blackjack_table);
    assert(indexes[slots.at(424)].func.obj == lucrot_mindstone);
    for (auto &entry : indexes) assert(entry.number == 7 && entry.limit == 99);

    prepare(true);
    assign_object_proc_bindings(stage::objects);
    assert(indexes[0].func.obj == staff_of_power); // Preserve the existing missing-vnum fallback.
    assert(callbacks == 0);
}
'''


def harness_source():
    text = source("specs.assign.c").read_text()
    rows = re.findall(r"^\s*OBJECT_BINDING\(\s*(\w+)\s*,\s*(\w+)\s*\)", text, re.M)
    assert len(rows) == 499
    callbacks = "\n".join(
        f"int {name}(P_obj, P_char, int, char *) {{ ++callbacks; return {index}; }}"
        for index, name in enumerate(sorted({name for _, name in rows}), 1))
    # Bindings must have one owner; normal boot delegates to the data-only API.
    for function, stage in (("assign_objects", "objects"), ("assign_rooms", "rooms")):
        body = extract_function("specs.assign.c", f"void {function}(void)\n{{")
        assert f"assign_object_proc_bindings(object_proc_binding_stage::{stage})" in body
        assert "obj_index[" not in body
    return HARNESS.replace("// CALLBACKS", callbacks)


def main():
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="object-binding-catalog-", dir=build) as tmp:
        path, binary = Path(tmp) / "test.cpp", Path(tmp) / "test"
        path.write_text(harness_source())
        subprocess.run([
            "g++", "-std=c++20", "-g", "-O1", "-Isrc", "-I/usr/include/mysql",
            "-I/usr/include/libxml2", "-ffunction-sections", "-fdata-sections",
            "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
            "-fno-omit-frame-pointer", "-fno-pie", "-no-pie", str(path),
            str(source("specs.assign.c")), "-Wl,--gc-sections", "-o", str(binary),
        ], cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True, env={**os.environ,
            "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1", "UBSAN_OPTIONS": "halt_on_error=1"})
    print("native object bindings: 499 entries, read-only inspection, stage/override/missing/empty policy passed")
    print("native object bindings: no callbacks, RNG, world/mobile setup, or object creation linked or executed")


if __name__ == "__main__":
    main()
