#!/usr/bin/env python3
"""Execute the production command lookup for backstab aliases and nearby commands."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function, source
from contract_text import contains


interp = source("interp.c").read_text()
start = interp.index("const char *command[MAX_CMD] = {")
table = interp[start:interp.index("\n};", start) + 3]

# The interpreter must use the tested lookup and dispatch its result to backstab.
interpreter = extract_function("interp.c", "void command_interpreter(")
assert contains(interpreter, "cmd = old_search_block(argument, begin, look_at, command, 2);")
assert contains(interp, "CMD_N(CMD_BACKSTAB, STAT_NORMAL + POS_STANDING, do_backstab, 0, TRUE);")

prelude = r'''
#include <cassert>
#include <cctype>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include <sys/types.h>
#include "cmd/interp.h"

#define MAX_CMD 1024
#define MAX_INPUT_LENGTH 1024
#define LOWER(c) tolower(static_cast<unsigned char>(c))
'''

driver = r'''
int main()
{
    for (const char *verb : {"ba", "back", "backstab", "bs"})
    {
        assert(old_search_block(verb, 0, strlen(verb), command, 2) == CMD_BACKSTAB);
        assert(input_command_number(verb) == CMD_BACKSTAB);
        assert(ordered_command_number(verb) == CMD_BACKSTAB);

        char input[128];
        snprintf(input, sizeof(input), "  %s target", verb);
        assert(old_search_block(input, 2, strlen(verb), command, 2) == CMD_BACKSTAB);
        assert(input_command_number(input) == CMD_BACKSTAB);
        assert(ordered_command_number(input) == CMD_BACKSTAB);
        assert(!strcmp(input_command_label(input), "backstab"));
        for (char *letter = input; *letter; ++letter)
            *letter = toupper(static_cast<unsigned char>(*letter));
        assert(input_command_number(input) == CMD_BACKSTAB);
        assert(ordered_command_number(input) == CMD_BACKSTAB);
    }

    for (const char *verb : {"bsl", "bsla", "bslap"})
        assert(ordered_command_number(verb) == CMD_BSLAP);
    assert(ordered_command_number("bash target") == CMD_BASH);
    assert(ordered_command_number("b target") == CMD_BOUNCE);
    assert(ordered_command_number("bsx target") == -1);
    assert(ordered_command_number("") == CMD_NONE);
    assert(ordered_command_number(nullptr) == CMD_NONE);

    // This generic lookup also serves spells and toggles; only commands gain bs.
    const char *other_list[] = {"bslap", "backstab", "\n"};
    assert(old_search_block("bs", 0, 2, other_list, 2) == 1);
    assert(old_search_block("bs", 0, 2, other_list, 1) == -1);
    puts("Backstab aliases: ba, back, backstab and bs passed; bslap and other lookups preserved.");
}
'''

functions = [extract_function("interp.c", signature) for signature in (
    "int old_search_block(",
    "static bool is_retired_command_spelling(",
    "static int input_command_number(",
    "int ordered_command_number(",
    "const char *input_command_label(",
)]
build_root = ROOT / "bin" / "tests"
build_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="backstab-aliases-", dir=build_root) as directory:
    harness = Path(directory) / "backstab_aliases.cpp"
    binary = Path(directory) / "backstab_aliases"
    harness.write_text("\n".join([prelude, table, *functions, driver]))
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
        "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-no-pie",
        "-I", str(ROOT / "src"), str(harness), "-o", str(binary),
    ], check=True)
    subprocess.run([str(binary)], check=True)
