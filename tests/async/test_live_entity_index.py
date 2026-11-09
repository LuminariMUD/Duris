#!/usr/bin/env python3
"""Liveness lookups must stay correct without walking the global lists."""

import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, SRC, extract_function

HARNESS = r'''
#include <assert.h>
#include <stdint.h>
#include <unordered_map>
#include <unordered_set>

struct obj_data { uint64_t obj_uid; };
struct char_data { uint64_t runtime_id; char_data *next; };
typedef obj_data *P_obj;
typedef char_data *P_char;
P_char character_list = nullptr;
static std::unordered_set<P_obj> live_objects;
static std::unordered_map<uint64_t, P_char> live_characters;
OBJECTS
CHARACTERS

int main()
{
	obj_data sword = { 11 }, shield = { 12 };
	remember_live_object(&sword);
	assert(find_live_object(&sword, 11) == &sword);
	assert(!find_live_object(&shield, 12));
	assert(!find_live_object(&sword, 99));
	forget_live_object(&sword);
	assert(!find_live_object(&sword, 11));
	// A pool slot reused by a new object is not the old object.
	sword.obj_uid = 13;
	remember_live_object(&sword);
	assert(!find_live_object(&sword, 11) && find_live_object(&sword, 13) == &sword);

	char_data first = { 1, nullptr }, second = { 2, nullptr }, unset = { 0, nullptr };
	character_list_add(&second);
	character_list_add(&first);
	character_list_add(&unset);
	assert(character_list == &unset && unset.next == &first && first.next == &second);
	assert(find_character_by_runtime_id(1) == &first);
	assert(find_character_by_runtime_id(2) == &second);
	assert(!find_character_by_runtime_id(0) && !find_character_by_runtime_id(3));
	forget_live_character(&first);
	assert(!find_character_by_runtime_id(1) && find_character_by_runtime_id(2) == &second);
	return 0;
}
'''


def source_text():
    for path in SRC.rglob("*.c"):
        yield path, path.read_text(errors="replace")


def main():
    objects = "\n".join(extract_function("handler.c", signature) for signature in (
        "void remember_live_object(", "void forget_live_object(", "P_obj find_live_object("))
    characters = "\n".join(extract_function("character_identity.c", signature) for signature in (
        "P_char find_character_by_runtime_id(", "void character_list_add(", "void forget_live_character("))
    harness = HARNESS.replace("OBJECTS", objects).replace("CHARACTERS", characters)
    with tempfile.TemporaryDirectory(dir=ROOT / "bin") as temp:
        source = Path(temp) / "index.cpp"
        binary = Path(temp) / "index"
        source.write_text(harness)
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-g",
                        "-fsanitize=address,undefined", str(source), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)

    # Any new way onto a global list would be invisible to the lookups.
    head_write = re.compile(r"(?<![\w>.])(character_list|object_list)\s*=(?!=)")
    writers = {}
    for path, text in source_text():
        for match in head_write.finditer(text):
            line = text[text.rfind("\n", 0, match.start()) + 1:text.find("\n", match.start())]
            if "P_char character_list" in line or "P_obj object_list" in line or "for (" in line:
                continue
            writers.setdefault((path.name, match[1]), 0)
            writers[(path.name, match[1])] += 1
    assert writers == {
        ("character_identity.c", "character_list"): 1,
        ("handler.c", "character_list"): 1,
        ("db.c", "character_list"): 1,  # boot reset
        ("db.c", "object_list"): 2,  # boot reset and read_object
        ("handler.c", "object_list"): 1,
    }, writers
    read_object = (SRC / "world" / "db.c").read_text()
    assert "object_list = obj;\n\tremember_live_object(obj);" in read_object
    handler = (SRC / "world" / "handler.c").read_text()
    assert "forget_live_object(obj);" in handler and "forget_live_character(ch);" in handler
    print("live entity index: OK")


if __name__ == "__main__":
    main()
