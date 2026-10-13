#!/usr/bin/env python3
"""Execute specialization denials against the complete production allowance table."""

import os
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, source


DRIVER = r'''
#include "core/prototypes.h"
#include "classes/specializations.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>

int main() {
    // A normal denial must stop at the end of the real table, including rows
    // for restricted races and classes without specialization allowances.
    setenv("CREATION_ALL_CLASSES", "FALSE", 1);
    assert(is_allowed_race_spec(RACE_HUMAN, CLASS_WARRIOR, SPEC_GUARDIAN));
    assert(!is_allowed_race_spec(RACE_THRIKREEN, CLASS_WARRIOR, SPEC_GUARDIAN));
    assert(is_allowed_race_spec(RACE_THRIKREEN, CLASS_WARRIOR, SPEC_SWORDSMAN));
    for (int slot = 1; slot <= MAX_SPEC; ++slot) {
        assert(!is_allowed_race_spec(RACE_LICH, CLASS_WARRIOR, slot));
        assert(!is_allowed_race_spec(RACE_HUMAN, CLASS_ASSASSIN, slot));
    }
    // Traverse every defined race/class/slot under ASan/UBSan. This is memory
    // safety coverage; only the named assertions above characterize policy.
    for (int race = RACE_NONE; race <= LAST_RACE; ++race)
        for (int cls = 0; cls < CLASS_COUNT; ++cls)
            for (int slot = 0; slot <= MAX_SPEC; ++slot)
                (void)is_allowed_race_spec(race, 1u << cls, slot);
    setenv("CREATION_ALL_CLASSES", "TRUE", 1);
    assert(is_allowed_race_spec(RACE_THRIKREEN, CLASS_WARRIOR, SPEC_GUARDIAN));
    assert(is_allowed_race_spec(RACE_LICH, CLASS_ASSASSIN, SPEC_ASSMASTER));
    puts("Specialization eligibility: grants, denials, override and table bounds passed.");
}
'''

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="specialization-eligibility-", dir=build) as directory:
    harness, binary = Path(directory) / "harness.cpp", Path(directory) / "harness"
    harness.write_text(DRIVER)
    subprocess.run([
        "g++", "-std=c++20", "-g", "-D__NO_MYSQL__", "-ffunction-sections", "-fdata-sections",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        "-I" + str(ROOT / "src"), str(harness), str(source("specializations.c")),
        str(source("creation_availability_config.c")), str(HARNESS_STUBS),
        "-Wl,--gc-sections", "-lbsd", "-o", str(binary),
    ], check=True)
    env = dict(os.environ, CHAOS_MUD="FALSE", CREATION_ALL_RACES="FALSE",
               CREATION_ALL_CLASSES="FALSE")
    subprocess.run([str(binary)], env=env, check=True)
