#!/usr/bin/env python3
"""Real keyword matching and GET parsing retain literals and support combinations."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function


production = "\n".join(
    extract_function(file, signature) + (";" if signature == "const char *fill_words[]" else "")
    for file, signatures in (
        ("utility.c", ("int strn_cmp(",)),
        ("interp.c", (
            "const char *fill_words[]", "int search_block(", "int fill_word(",
            "void argument_interpreter(",
        )),
        ("handler.c", (
            "bool isname(const char *str, const char *namelist)",
            "int get_number(", "bool obj_name_matches(", "P_obj get_obj_in_list_vis(",
        )),
    )
    for signature in signatures
)

harness = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "item/item_command_parser.h"
#include "world/handler.h"
#include "world/vnum.obj.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>

P_index obj_index = nullptr;
bool ac_can_see_obj(P_char, P_obj, int) { return true; }
bool gmcp_item_selector_matches(P_char, P_obj, const char *) { abort(); }
int panic_corruption_int(const char *, const char *, ...) { abort(); }
void logit(const char *, const char *, ...) {}

// PRODUCTION

int main() {
    assert(!isname(nullptr, "fire giant") && !isname("fire", nullptr));
    for (const char *literal : {"thri-kreen", "yuan-ti", "two-handed", "Half-Elf"})
        assert(isname(literal, literal)); // whole-word priority: parts are absent
    for (const char *target : {"fire-giant", "GIANT-FIRE", "fire-red-giant", "fire-fire"})
        assert(isname(target, "red giant fire guard"));
    for (const char *target : {"-", "fire-", "-giant", "-5", "fire--giant",
                              "fire-gi", "fire-troll", "fire", "2.fire-giant"})
        assert(!isname(target, "giant fireball"));
    for (const char *target : {"-", "fire-", "-giant", "fire--giant", "fire-gi"})
        assert(!isname(target, "fire giant"));
    assert(!isname("two-handed-sword", "two-handed sword"));
    assert(isname("  FIRE", "sword fire giant"));
    assert(isname("fire giant", "guard fire giant sword")); // existing exact phrases
    assert(!isname("fire giant", "fire red giant"));
    assert(!isname("fir", "fire giant"));
    assert(!isname("", "fire giant") && !isname("   ", "fire giant"));
    assert(!isname("fire", "fireball") && !isname("giant", "fire-giant"));

    char_data viewer{};
    obj_data fire{}, first{}, second{}, literal{};
    fire.name = const_cast<char *>("fire staff");
    first.name = const_cast<char *>("sword fire red");
    second.name = const_cast<char *>("fire sword blue");
    literal.name = const_cast<char *>("fire-sword");
    fire.next_content = &first; first.next_content = &second;
    second.next_content = &literal;
    item_get_command parsed{};
    assert(item_get_command_parse("2.fire-sword", &parsed));
    assert(parsed.kind == item_get_command_kind::floor_item);
    assert(get_obj_in_list_vis(&viewer, parsed.object, &fire, false) == &second);
    assert(!get_obj_in_list_vis(&viewer, "fire--sword", &fire, false));
    assert(item_get_command_parse("all.fire-sword", &parsed));
    assert(parsed.kind == item_get_command_kind::floor_all && parsed.alldot);
    assert(!strcmp(parsed.filter, "fire-sword"));
    int matches = 0;
    for (P_obj item = &fire; item; item = item->next_content)
        matches += obj_name_matches(&viewer, item, parsed.filter);
    assert(matches == 3);
    puts("hyphen targets: literal priority, combinations, empty parts, exact phrases, GET filters and ordinals passed");
}
'''

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="hyphen-targets-", dir=ROOT / "bin/tests") as directory:
    path, binary = Path(directory) / "test.cpp", Path(directory) / "test"
    path.write_text(harness.replace("// PRODUCTION", production))
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-Isrc", str(path),
        "src/item/item_command_parser.c", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
