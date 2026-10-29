#!/usr/bin/env python3
"""Exercise production visibility and person names during detached cleanup."""

import os
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "world/map.h"
#include "world/weather.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include <string>

static room_data rooms[2];
static zone_data zones[1];
P_room world = rooms;
zone_data *zone_table = zones;
extern const int top_of_world = 1;
time_info_data time_info{};
char GS_buf1[MAX_STRING_LENGTH];
extern const race_names race_names_table[1] = {};
static int rendered_messages;

void logit(const char *, const char *, ...) { assert(false); }
bool has_innate(P_char, int) { return false; }
bool IS_TWILIGHT_ROOM(int room) { assert(room >= 0 && room <= top_of_world); return false; }
bool IS_OUTDOORS(int room) { assert(room >= 0 && room <= top_of_world); return false; }
bool racewar(P_char, P_char) { return false; }
bool is_linked_to(P_char, P_char, ush_int) { return false; }
int GET_CLASS(P_char, uint) { return 0; }
int is_introd(P_char, P_char) { return true; }
std::string strip_ansi(const char *text) { return text; }

// Deliver the real guard-break callback through its $n/$N person-name path.
// Network delivery and the surrounding act formatting remain fixture services.
void act(const char *text, int, P_char ch, P_obj, void *target, int destination)
{
    P_char recipient = destination == TO_CHAR ? ch : static_cast<P_char>(target);
    P_char named = std::strstr(text, "$N") ? static_cast<P_char>(target) : ch;
    const char *name = PERS(named, recipient, false);
    assert(std::strcmp(name, "someone") == 0);
    ++rendered_messages;
}
'''

DRIVER = r'''
int main()
{
    rooms[0].zone = rooms[1].zone = 0;
    rooms[0].light = rooms[1].light = 1;
    time_info.hour = 12;
    char_data viewer{}, subject{};
    char viewer_name[] = "Viewer", subject_name[] = "Subject";
    viewer.player.name = viewer_name;
    subject.player.name = subject.player.short_descr = subject_name;
    SET_POS((&viewer), STAT_NORMAL + POS_STANDING);
    SET_POS((&subject), STAT_NORMAL + POS_STANDING);
    viewer.in_room = subject.in_room = 0;

    // Valid visibility and person-name behavior remain intact.
    assert(ac_can_see(&viewer, &subject, true));
    assert(std::strcmp(PERS(&subject, &viewer, false), "Subject") == 0);
    SET_BIT(subject.specials.affected_by, AFF_INVISIBLE);
    assert(!ac_can_see(&viewer, &subject, true));
    assert(std::strcmp(PERS(&subject, &viewer, false), "someone") == 0);
    REMOVE_BIT(subject.specials.affected_by, AFF_INVISIBLE);

    // Projection uses the supplied observer room without moving either actor.
    viewer.in_room = NOWHERE; subject.in_room = 1;
    assert(!ac_can_see(&viewer, &subject, true));
    assert(ac_can_see_from(&viewer, &subject, 1));
    assert(viewer.in_room == NOWHERE && subject.in_room == 1);
    assert(!ac_can_see_from(&viewer, &subject, NOWHERE));
    assert(!ac_can_see_from(&viewer, &subject, top_of_world + 1));
    viewer.in_room = 0;
    rooms[1].light = 0;
    subject.player.race = RACE_SKELETON;
    assert(!ac_can_see_from(&viewer, &subject, 1));
    SET_BIT(viewer.specials.affected_by4, AFF4_MAGE_FLAME);
    assert(ac_can_see_from(&viewer, &subject, 1));
    assert(viewer.in_room == 0 && subject.in_room == 1);
    REMOVE_BIT(viewer.specials.affected_by4, AFF4_MAGE_FLAME);
    rooms[1].light = 1;
    subject.player.race = 0;
    subject.in_room = NOWHERE;
    assert(!ac_can_see_from(&viewer, &subject, 1));
    int cases = 0;
    for (bool npc : {false, true})
        for (bool trusted : {false, true})
            for (int invalid_room : {NOWHERE, -2, top_of_world + 1})
            {
                viewer.specials.act = npc ? ACT_ISNPC : 0;
                viewer.player.level = trusted ? MAXLVLMORTAL + 1 : 1;
                viewer.in_room = 0; subject.in_room = invalid_room;
                assert(!ac_can_see(&viewer, &subject, true));
                assert(std::strcmp(PERS(&subject, &viewer, false), "someone") == 0);
                assert(std::strcmp(PERS(&subject, &viewer, false, true), "someone") == 0);
                viewer.in_room = invalid_room; subject.in_room = 0;
                assert(!ac_can_see(&viewer, &subject, false));
                assert(std::strcmp(PERS(&subject, &viewer, false), "someone") == 0);
                assert(!ac_can_see(&viewer, &viewer, true));
                ++cases;
            }

    viewer.specials.act = 0; viewer.player.level = 1;
    viewer.in_room = 0; subject.in_room = NOWHERE;
    char_link_data outgoing{};
    outgoing.linking = &subject; outgoing.linked = &viewer;
    guard_broken(&outgoing);
    char_link_data incoming{};
    incoming.linking = &viewer; incoming.linked = &subject;
    guard_broken(&incoming);
    assert(rendered_messages == 4);
    assert(!ac_can_see(&viewer, nullptr, true));
    std::printf("Character visibility/name rendering: %d room-bound cases and four guard cleanup messages passed\n", cases);
}
'''

build_root = Path(os.environ.get("BIN_ROOT", ROOT / "bin")) / "tests"
build_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="visibility-room-bounds-", dir=build_root) as directory:
    harness = Path(directory) / "harness.cpp"
    binary = Path(directory) / "harness"
    harness.write_text("\n".join((
        PRELUDE,
        extract_function("utility.c", "bool ac_can_see_from("),
        extract_function("utility.c", "bool ac_can_see(P_char sub, P_char obj, bool"),
        extract_function("utility.c", "char *PERS(P_char ch, P_char vict, int short_d)"),
        extract_function("utility.c", "char *PERS(P_char ch, P_char vict, int short_d, bool noansi)"),
        extract_function("guard.c", "void guard_broken(struct char_link_data *cld)"),
        DRIVER,
    )), encoding="utf-8")
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        f"-I{ROOT / 'src'}", str(harness), "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True)
