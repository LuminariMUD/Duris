#!/usr/bin/env python3
"""Exercise Entrapment's production flee hook and specialization contract."""

import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source


innates = source("innates.c").read_text(encoding="utf-8")
registration = re.findall(
    r"ADD_CLASS_INNATE\(INNATE_ENTRAPMENT,\s*CLASS_MERCENARY,\s*45,\s*SPEC_BRIGAND\);",
    innates,
)
assert len(registration) == 1, "Entrapment must belong exclusively to level-45 Brigands"
assert len(re.findall(r"ADD_CLASS_INNATE\(INNATE_ENTRAPMENT,", innates)) == 1
assert "SPEC_BRIGAND 1" in source("structs.h").read_text(encoding="utf-8")

production = extract_function("grapple.c", "int grapple_check_entrapment(")

# Use the actual production function; only its external game services are stubs.
prelude = r"""
#include <cassert>
#include <cstdio>
#include <cstring>

struct char_data {
    int in_room = 0;
    int level = 0;
    int spec = 0;
    int m_class = 0;
    int grappler_skill = 0;
    int position = 0;
    bool can_act = true;
    bool sees_opponent = true;
    char_data *next_in_room = nullptr;
    char_data *opponent = nullptr;
};
using P_char = char_data *;
using P_obj = void *;
struct room_data { P_char people = nullptr; };
static room_data rooms[1];
static room_data *world = rooms;
constexpr int INNATE_ENTRAPMENT = 128;
constexpr int CLASS_MERCENARY = 1;
constexpr int SPEC_BRIGAND = 1;
constexpr int SKILL_GRAPPLER_COMBAT = 1;
constexpr int POS_STANDING = 3;
constexpr int PULSE_VIOLENCE = 12;
constexpr int TO_CHAR = 1, TO_VICT = 2, TO_NOTVICT = 3;
constexpr int TRUE = 1;
static int roll = 1, lag = 0, messages = 0;

#define CAN_ACT(ch) ((ch)->can_act)
#define CAN_SEE(observer, target) ((observer)->sees_opponent)
#define GET_POS(ch) ((ch)->position)
#define GET_LEVEL(ch) ((ch)->level)
#define GET_OPPONENT(ch) ((ch)->opponent)
#define GET_CHAR_SKILL(ch, skill) ((ch)->grappler_skill)

bool has_innate(P_char ch, int innate) {
    return innate == INNATE_ENTRAPMENT && ch->m_class == CLASS_MERCENARY &&
           ch->spec == SPEC_BRIGAND && ch->level >= 45;
}
float get_property(const char *name, double fallback) {
    assert(std::strcmp(name, "grapple.entrapment.chance.mod") == 0);
    return static_cast<float>(fallback);
}
int number(int low, int high) {
    assert(low == 1 && high == 100);
    return roll;
}
void act(const char *, int, P_char, P_obj, P_char, int) { ++messages; }
void CharWait(P_char, int duration) { lag = duration; }
"""

driver = r"""
static char_data fleeing, brigand;
static void reset() {
    fleeing = {};
    brigand = {};
    fleeing.opponent = &brigand;
    brigand.level = 50;
    brigand.spec = SPEC_BRIGAND;
    brigand.m_class = CLASS_MERCENARY;
    brigand.position = POS_STANDING;
    brigand.sees_opponent = true;
    fleeing.sees_opponent = true;
    rooms[0].people = &brigand;
    roll = 1;
    lag = 0;
    messages = 0;
}
static bool trapped() {
    int result = grapple_check_entrapment(&fleeing);
    assert((result != 0) == (lag == PULSE_VIOLENCE));
    assert(messages == (result ? 3 : 0));
    return result != 0;
}
int main() {
    reset();
    assert(trapped());  // Level 50 Brigand prevents a visible opponent's escape.
    reset(); brigand.spec = 0; assert(!trapped());
    reset(); brigand.spec = 2; assert(!trapped());  // Bounty Hunter
    reset(); brigand.level = 44; assert(!trapped());
    reset(); brigand.m_class = 0; assert(!trapped());

    reset();
    fleeing.sees_opponent = false;  // The fleeing player cannot see the Brigand.
    assert(trapped());              // This must not prevent the Brigand from grabbing.
    reset();
    brigand.sees_opponent = false;  // The Brigand cannot see the fleeing player.
    assert(!trapped());

    reset(); brigand.can_act = false; assert(!trapped());
    reset(); brigand.position = 2; assert(!trapped());
    reset(); fleeing.opponent = nullptr; assert(!trapped());

    reset(); brigand.level = 45;
    roll = 21; assert(trapped());
    reset(); brigand.level = 45;
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
            "-fno-pie", "-no-pie", str(source_file), "-o", str(executable),
        ],
        check=True,
        cwd=ROOT,
    )
    subprocess.run([str(executable)], check=True, cwd=ROOT)
