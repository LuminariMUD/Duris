#!/usr/bin/env python3
"""Guardian rescue all costs 6 seconds of lag, and Guardians guard two people.

Evaluates the real rescue() lag expression against config.h, runs the real do_guard
and its guard-list helpers from guard.c against the shipped skill.guard.* properties,
and checks that the help entries describe the same rules.
"""

from pathlib import Path
import re
import subprocess
import tempfile

from _paths import HARNESS_STUBS, ROOT, extract_function

properties = {}
for line in (ROOT / "lib/duris.properties").read_text(encoding="utf-8").splitlines():
    if line.startswith("skill.guard.max"):
        key, value = line.split("=", 1)
        properties[key] = float(value)
assert properties == {"skill.guard.max": 1.0, "skill.guard.max.multi": 2.0}, properties

# Rescue all stays a level 46 Guardian ability.
do_rescue = extract_function("actoff.c", "void do_rescue(")
assert re.search(
    r"GET_SPEC\(ch, CLASS_WARRIOR, SPEC_GUARDIAN\) && strstr\(argument, \"all\"\) &&\s*"
    r"GET_LEVEL\(ch\) >= 46\)\s*rescue\(ch, target, TRUE\);",
    do_rescue,
), "rescue all must stay gated on Guardian level 46"

rescue = extract_function("actoff.c", "void rescue(P_char ch, P_char rescuee, bool rescue_all)")
lag = re.findall(r"CharWait\(ch, ([^;]*)\);", rescue)
assert len(lag) == 1, lag

LAG_HARNESS = r"""
#include "core/config.h"
#include <cassert>
#include <cstdio>

static int rescue_lag(bool rescue_all) { return """ + lag[0] + r"""; }

int main() {
    assert(rescue_lag(true) == 6 * WAIT_SEC);
    assert(rescue_lag(false) == PULSE_VIOLENCE);
    std::puts("rescue lag regression passed");
}
"""

GUARD_FUNCTIONS = "\n".join(
    extract_function("guard.c", signature)
    for signature in (
        "P_char guarding2(P_char ch, int n)",
        "P_char guarded_by(P_char ch)",
        "int number_guarding(P_char ch)",
        "void drop_one_guard(P_char ch)",
        "void do_guard(P_char ch, char *argument, int /*cmd*/)",
    )
)

GUARD_PRELUDE = r"""
#include "core/prototypes.h"
#include "core/structs.h"
#include "net/comm.h"
#include "core/utils.h"
#include "combat/guard.h"
#include "core/defines.h"
#include "magic/spells.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>

static char_data *room[8];

// Only the guards know guard; a target who knows it refuses to be guarded.
int GET_CHAR_SKILL_P(P_char ch, int skill) {
    for (char_data *target : room)
        if (target == ch)
            return 0;
    return skill == SKILL_GUARD ? 100 : 0;
}
P_char get_linked_char(P_char, ush_int) { return nullptr; }
bool isname(const char *a, const char *b) { return !std::strcmp(a, b); }
void act(const char *, int, P_char, P_obj, void *, int) {}
P_char get_char_room_vis(P_char, const char *name) {
    for (char_data *tch : room)
        if (tch && !std::strcmp(tch->player.name, name))
            return tch;
    return nullptr;
}
int get_property(const char *key, int fallback) {
    if (!std::strcmp(key, "skill.guard.max"))
        return """ + str(int(properties["skill.guard.max"])) + r""";
    if (!std::strcmp(key, "skill.guard.max.multi"))
        return """ + str(int(properties["skill.guard.max.multi"])) + r""";
    return fallback;
}

struct char_link_data *link_char(P_char ch, P_char target, ush_int type) {
    auto *cld = new char_link_data{};
    cld->type = type;
    cld->linking = ch;
    cld->linked = target;
    cld->next_linking = ch->linking;
    ch->linking = cld;
    cld->next_linked = target->linked;
    target->linked = cld;
    return cld;
}
static void remove_link(char_link_data *cld) {
    for (auto **at = &cld->linking->linking; *at; at = &(*at)->next_linking)
        if (*at == cld) { *at = cld->next_linking; break; }
    for (auto **at = &cld->linked->linked; *at; at = &(*at)->next_linked)
        if (*at == cld) { *at = cld->next_linked; break; }
    delete cld;
}
void unlink_char(P_char ch, P_char target, ush_int type) {
    for (auto *cld = ch->linking; cld; cld = cld->next_linking)
        if (cld->linked == target && cld->type == type) { remove_link(cld); return; }
}
void clear_links(P_char ch, ush_int type) {
    for (auto *cld = ch->linking; cld;) {
        auto *next = cld->next_linking;
        if (cld->type == type)
            remove_link(cld);
        cld = next;
    }
}
"""

GUARD_DRIVER = r"""
static char_data make_char(const char *name, int m_class, int spec) {
    char_data ch{};
    ch.player.name = const_cast<char *>(name);
    ch.player.m_class = m_class;
    ch.player.spec = spec;
    return ch;
}

static void guard(P_char ch, const char *name) {
    std::string argument = name;
    do_guard(ch, argument.data(), 0);
}

static void check_multi_guard(P_char guardian, P_char a, P_char b, P_char c) {
    guard(guardian, "alpha");
    guard(guardian, "bravo");
    assert(number_guarding(guardian) == 2);
    assert(guarded_by(a) == guardian && guarded_by(b) == guardian);

    guard(guardian, "charlie");
    assert(number_guarding(guardian) == 2);
    assert(guarded_by(c) == guardian);
    assert((guarded_by(a) == guardian) != (guarded_by(b) == guardian));

    guard(guardian, "off");
    assert(number_guarding(guardian) == 0);
}

int main() {
    char_data a = make_char("alpha", CLASS_CLERIC, 0);
    char_data b = make_char("bravo", CLASS_CLERIC, 0);
    char_data c = make_char("charlie", CLASS_CLERIC, 0);
    room[0] = &a;
    room[1] = &b;
    room[2] = &c;

    char_data guardian = make_char("guardian", CLASS_WARRIOR, SPEC_GUARDIAN);
    check_multi_guard(&guardian, &a, &b, &c);

    char_data cavalier = make_char("cavalier", CLASS_PALADIN, SPEC_CAVALIER);
    check_multi_guard(&cavalier, &a, &b, &c);

    // Other warriors, specialised or not, still guard one person at a time.
    for (int spec : {0, SPEC_SWORDSMAN, SPEC_SWASHBUCKLER}) {
        char_data warrior = make_char("warrior", CLASS_WARRIOR, spec);
        guard(&warrior, "alpha");
        guard(&warrior, "bravo");
        assert(number_guarding(&warrior) == 1);
        assert(guarded_by(&b) == &warrior && !guarded_by(&a));
        guard(&warrior, "off");
    }

    // A Guardian spec number on another class grants nothing.
    char_data cleric = make_char("cleric", CLASS_CLERIC, SPEC_GUARDIAN);
    guard(&cleric, "alpha");
    guard(&cleric, "bravo");
    assert(number_guarding(&cleric) == 1);
    guard(&cleric, "off");

    std::puts("guardian multi-guard regression passed");
}
"""


def run_harness(directory: Path, name: str, code: str, stubs: bool) -> None:
    harness = directory / f"{name}.cpp"
    binary = directory / name
    harness.write_text(code, encoding="utf-8")
    command = [
        "g++",
        "-std=c++20",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-fsanitize=address,undefined",
        "-I" + str(ROOT / "src"),
        str(harness),
    ]
    if stubs:
        command.append(str(HARNESS_STUBS))
    subprocess.run(command + ["-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)


with tempfile.TemporaryDirectory(prefix="duris-guardian-") as directory:
    run_harness(Path(directory), "rescue_lag", LAG_HARNESS, stubs=False)
    run_harness(
        Path(directory),
        "multi_guard",
        GUARD_PRELUDE + GUARD_FUNCTIONS + GUARD_DRIVER,
        stubs=True,
    )

# The help entries players read describe the same rules.
for help_file in ("help/duris_help_parsed.hlp", "lib/information/help_index"):
    text = (ROOT / help_file).read_text(encoding="utf-8")
    assert "At level 51" not in text and "51st level:     Rescue All" not in text, help_file
    assert "Specialized Warriors possess the added ability" not in text, help_file
    assert "Guardians of level 46 and above can rescue someone" in text, help_file
    assert "unable\nto act for 6 seconds" in text, help_file
    assert "Guardians, Cavaliers and\nDemonic Riders can guard two people at once" in text, help_file
    assert "Guardians can also guard two people at once." in text or (
        "Guardians can guard two people at once." in text
    ), help_file
