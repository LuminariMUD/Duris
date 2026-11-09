#!/usr/bin/env python3
"""Execute reset admission at every RNG outcome, including artifact halving."""
from pathlib import Path
import os
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function


HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include <cassert>
#include <cstdio>

static int roll, calls;
int number(int low, int high)
{
    assert(low == 0 && high == 99);
    ++calls;
    return roll;
}

// PRODUCTION

int main()
{
    obj_data object{};
    for (bool artifact : {false, true})
    {
        object.extra_flags = artifact ? ITEM_ARTIFACT : 0;
        for (int chance : {-1, 0, 1, 49, 50, 51, 99, 100, 101})
        {
            const int effective_chance = artifact ? chance / 2 : chance;
            for (roll = 0; roll < 100; ++roll)
            {
                calls = 0;
                assert(ITEM_LOAD_CHECK(&object, chance) == (roll < effective_chance));
                assert(calls == 1); // Rejections, guarantees and artifacts all consume one roll.
            }
        }
    }
    std::puts("reset admission: 1,800 chance/artifact/roll cases, one RNG draw each");
}
'''


def main():
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="item-load-check-", dir=build) as tmp:
        source, binary = Path(tmp) / "test.cpp", Path(tmp) / "test"
        source.write_text(HARNESS.replace("// PRODUCTION", extract_function(
            "utility.c", "bool item_load_check(P_obj item,")))
        subprocess.run([
            "g++", "-std=c++20", "-g", "-O1", "-Wall", "-Wextra", "-Werror",
            "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
            "-Isrc", str(source), str(HARNESS_STUBS), "-o", str(binary),
        ], cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True, env={**os.environ,
            "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1", "UBSAN_OPTIONS": "halt_on_error=1"})


if __name__ == "__main__":
    main()
