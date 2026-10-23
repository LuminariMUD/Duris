#!/usr/bin/env python3
"""Exercise Entrapment's production flee hook and specialization contract."""

import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, HARNESS_STUBS, extract_function, source


innates = source("innates.c").read_text(encoding="utf-8")
registration = re.findall(
    r"ADD_CLASS_INNATE\(INNATE_ENTRAPMENT,\s*CLASS_MERCENARY,\s*45,\s*SPEC_BRIGAND\);",
    innates,
)
assert len(registration) == 1, "Entrapment must belong exclusively to level-45 Brigands"
assert len(re.findall(r"ADD_CLASS_INNATE\(INNATE_ENTRAPMENT,", innates)) == 1
assert "SPEC_BRIGAND 1" in source("structs.h").read_text(encoding="utf-8")

macros = innates[innates.index("#define ADD_RACIAL_INNATE"):innates.index("float regen_factor")]
arrays = innates[innates.index("char racial_innates["):innates.index("extern const struct race_names")]
production = macros + arrays + "\n" + "\n".join(
    extract_function(file, signature) for file, signature in [
        ("utility.c", "int flag2idx("),
        ("utility.c", "int GET_CLASS("),
        ("innates.c", "static int innate_char_race("),
        ("innates.c", "static int innate_unlock_level("),
        ("innates.c", "bool has_innate("),
        ("innates.c", "void assign_innates("),
        ("grapple.c", "int grapple_check_entrapment("),
    ])

# Use the actual production function; only its external game services are stubs.
prelude = r"""
#include <cassert>
#include <cstdio>
#include <cstring>
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/utility.h"
#include "net/comm.h"
#include "magic/spells.h"
#include "world/events.h"
#include "classes/necromancy.h"
static room_data rooms[1];
P_room world = rooms;
static int roll = 1, lag = 0, message_count = 0;
static char_data fleeing, brigand;
static bool brigand_sees = true, fleeing_sees = true;
// Visibility is a directional fixture; eligibility uses real structs/macros/innates.
#undef CAN_SEE
#define CAN_SEE(observer, target) ((observer) == &brigand ? brigand_sees : fleeing_sees)
int GET_CHAR_SKILL_P(P_char, int) { return 0; }
bool affected_by_spell(P_char, int) { return false; }
affected_type *get_spell_from_char(P_char, int, void *, int) { return nullptr; }
float get_property(const char *name, double fallback) {
    assert(std::strcmp(name, "grapple.entrapment.chance.mod") == 0);
    return static_cast<float>(fallback);
}
int number(int low, int high) {
    assert(low == 1 && high == 100);
    return roll;
}
void act(const char *, int, P_char, P_obj, void *, int) { ++message_count; }
void CharWait(P_char, int duration) { lag = duration; }
"""

driver = r"""
static void reset() {
    fleeing = {};
    brigand = {};
    fleeing.specials.fighting = &brigand;
    brigand.player.level = 50;
    brigand.player.spec = SPEC_BRIGAND;
    brigand.player.m_class = CLASS_MERCENARY;
    brigand.specials.position = POS_STANDING | STAT_NORMAL;
    brigand_sees = fleeing_sees = true;
    rooms[0].people = &brigand;
    roll = 1;
    lag = 0;
    message_count = 0;
}
static bool trapped() {
    int result = grapple_check_entrapment(&fleeing);
    assert((result != 0) == (lag == PULSE_VIOLENCE));
    assert(message_count == (result ? 3 : 0));
    return result != 0;
}
int main() {
    assign_innates();
    reset();
    assert(trapped());  // Level 50 Brigand prevents a visible opponent's escape.
    reset(); brigand.player.spec = 0; assert(!trapped());
    reset(); brigand.player.spec = SPEC_BOUNTY; assert(!trapped());
    reset(); brigand.player.level = 44; assert(!trapped());
    reset(); brigand.player.m_class = 0; assert(!trapped());

    reset();
    fleeing_sees = false;          // The fleeing player cannot see the Brigand.
    assert(trapped());              // This must not prevent the Brigand from grabbing.
    reset();
    brigand_sees = false;          // The Brigand cannot see the fleeing player.
    assert(!trapped());

    reset(); brigand.specials.act2 |= PLR2_WAIT; assert(!trapped());
    reset(); brigand.specials.position = POS_PRONE | STAT_NORMAL; assert(!trapped());
    reset(); fleeing.specials.fighting = nullptr; assert(!trapped());
    for (auto affect : {AFF2_STUNNED, AFF2_MAJOR_PARALYSIS, AFF2_MINOR_PARALYSIS}) {
        reset(); brigand.specials.affected_by2 |= affect; assert(!trapped());
    }
    reset(); fleeing.specials.affected_by4 |= AFF4_PHANTASMAL_FORM; assert(!trapped());
    reset(); fleeing.specials.affected_by |= AFF_WRAITHFORM; assert(!trapped());
    reset(); fleeing.player.race = RACE_GHOST; assert(!trapped());
    reset(); fleeing.player.race = RACE_WRAITH; assert(!trapped());
    reset(); brigand.specials.act |= ACT_ISNPC; assert(trapped());

    reset(); brigand.player.level = 45;
    roll = 21; assert(trapped());
    reset(); brigand.player.level = 45;
    roll = 22; assert(!trapped());  // Strict '<' probability boundary.
    reset();
    roll = 24; assert(trapped());
    reset();
    roll = 25; assert(!trapped());
    puts("Entrapment runtime regressions passed");
}
"""

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="entrapment-", dir=build) as directory:
    source_file = Path(directory) / "entrapment.cpp"
    executable = Path(directory) / "entrapment"
    source_file.write_text(prelude + production + driver, encoding="utf-8")
    subprocess.run(
        [
            "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
            "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
            "-fno-pie", "-no-pie", "-Isrc", "-I/usr/include/mysql",
            str(source_file), str(HARNESS_STUBS), "-o", str(executable),
        ],
        check=True,
        cwd=ROOT,
    )
    subprocess.run([str(executable)], check=True, cwd=ROOT)
