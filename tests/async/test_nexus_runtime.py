#!/usr/bin/env python3
"""Run real Nexus lifecycle, capture and reward consumers with ASan/UBSan."""
from pathlib import Path
import os
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function, rel

# The controlled fixture's boundaries and payouts must track the shipped defaults.
properties = (ROOT / "lib/duris.properties").read_text().splitlines()
for name, expected in {
    "touchTimerSecs": 300, "turnTimerSecs": 3600, "expireDays": 12,
    "epicsMin": 15, "epicsMax": 25, "bonus.epics": .110, "bonus.cargo": .110,
}.items():
    key = f"nexusStones.{name}="
    values = [line[len(key):] for line in properties if line.startswith(key)]
    assert len(values) == 1 and float(values[0]) == expected, \
        f"{key} must match the qualified default {expected}"

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="nexus-runtime-", dir=build) as temporary:
    directory = Path(temporary)
    utility = directory / "char_stat.cpp"
    headers = '\n'.join(f'#include "{name}"' for name in (
        "core/prototypes.h", "core/defines.h", "core/utils.h", "core/utility.h",
        "economy/nexus_stones.h", "world/epic.h", "world/epic_bonus.h",
        "world/difficulty.h", "ships/ships.h",
    ))
    utility.write_text(headers + '\nextern int errand_notch;\n' +
        'int sell_cargo_slot(P_char, P_ship, int, int, int = 0);\n'
        'int sell_contra_slot(P_char, P_ship, int, int, int = 0);\n' +
        extract_function("utility.c", "sh_int *char_stat(") + '\n' +
        extract_function("epic.c", "struct epic_award_context") + ';\n' +
        extract_function("epic.c", "static bool prepare_epic_award(") + '\n' +
        extract_function("epic.c", "int epic_calculate_pvp_award(") + '\n' +
        'int fixture_epic_award(P_char ch, int type, int data, int amount) { '
        'epic_award_context result = {}; '
        'return prepare_epic_award(ch, type, data, amount, false, &result) ? result.amount : 0; }\n' +
        extract_function("ship_shop.c", "int sell_cargo(") + '\n' +
        extract_function("ship_shop.c", "int sell_contra("))
    binary = directory / "nexus_runtime"
    subprocess.run([
        "g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
        "-ffunction-sections", "-fdata-sections", "-D__NO_MYSQL__",
        "-Isrc", "-Isrc/no_mysql", "-Isrc/ships", "-I/usr/include/libxml2",
        "tests/async/nexus_runtime_harness.cpp", rel("nexus_stones.c"),
        rel("flatfile_nexus_repository.c"), rel("flatfile_store.c"),
        str(utility), str(HARNESS_STUBS), "-Wl,--gc-sections", "-lcrypto", "-pthread",
        "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary), str(directory / "state")], cwd=ROOT, check=True,
                   env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1",
                        "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1"})

print("Nexus lifecycle, capture and reward-consumer regression passed (ASan/UBSan).")
