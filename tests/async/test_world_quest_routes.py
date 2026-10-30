#!/usr/bin/env python3
"""Execute the production bartender traversal against controlled room graphs."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function


(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="world-quest-routes-", dir=ROOT / "bin/tests") as temporary:
    work = Path(temporary)
    # These two read-only movement predicates live in otherwise large engine units.
    # Compile their owning source bodies; the traversal and map/trap rules link normally.
    predicates = work / "movement_predicates.cpp"
    predicates.write_text(
        '#include "core/prototypes.h"\n#include "core/utils.h"\n'
        'extern P_room world;\nextern P_index obj_index;\n'
        + extract_function("world/outposts.c", "bool check_castle_walls(")
        + extract_function("combat/range.c", "int check_wall(")
    )
    binary = work / "routes"
    subprocess.run([
        "g++", "-std=c++20", "-g", "-O1", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
        "-ffunction-sections", "-fdata-sections", "-fsanitize=address,undefined",
        "-fno-sanitize-recover=all", "-Isrc", "-Isrc/no_mysql", "-D__NO_MYSQL__",
        "tests/async/world_quest_routes_harness.cpp", str(predicates),
        "src/world/world_quest_policy.c", "src/combat/forced_movement.c", "src/combat/trap.c",
        "-Wl,--gc-sections", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=work, check=True, timeout=30)
