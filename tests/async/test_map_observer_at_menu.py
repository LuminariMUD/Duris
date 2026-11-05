#!/usr/bin/env python3
"""Execute map observer invalidation with real visibility and wrapped view geometry."""
from pathlib import Path
import os
import subprocess
import tempfile
from _paths import ROOT, extract_function, source
from _innate_numbers import with_innate_numbers

handler = source("handler.c").read_text()
start = handler.index("\t// if anything has moved on the map")
loop = handler[start:handler.index(
    "\tif (ch && ch->desc && ch->desc->term_type == TERM_MSP)", start)]

PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "world/map.h"
#include "world/weather.h"
#include "net/gmcp.h"
#include "ships/ships.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <initializer_list>
static room_data rooms[10003]{};
static zone_data zones[2]{};
P_room world = rooms;
zone_data *zone_table = zones;
extern const int top_of_world = 10002;
P_desc descriptor_list = nullptr;
time_info_data time_info{};
static double vertical_factor = 1.2;
bool has_innate(P_char, int) { return false; }
bool is_linked_to(P_char, P_char, ush_int) { return false; }
int GET_CLASS(P_char, uint) { return 0; }
bool IS_TWILIGHT_ROOM(int) { return false; }
bool IS_OUTDOORS(int) { return false; }
void logit(const char *, const char *, ...) { assert(false); }
P_ship get_ship_from_char(P_char) { return nullptr; }
int map_view_distance(P_char, int) { return 5; }
float get_property(const char *name, double fallback) {
    return strcmp(name, "map.verticalFactor") ? fallback : vertical_factor;
}
int real_room0(int vnum) {
    return vnum >= 500000 && vnum < 510000 ? vnum - 500000 + 1 : 0;
}
'''

CASES = r'''
int main() {
    zones[0].flags = ZONE_MAP; zones[0].number = 5000;
    zones[0].real_bottom = 1; zones[0].mapx = zones[0].mapy = 100;
    for (int i = 1; i <= 10000; ++i) {
        rooms[i].number = 500000 + i - 1;
        rooms[i].zone = 0;
    }
    rooms[10001].number = 1200; rooms[10001].zone = 1;
    rooms[10002].number = 510000; rooms[10002].zone = 0; // Non-grid tail.
    descriptor_data watching{}, at_menu{};
    char_data viewer{}, rented{}, mover{};
    watching.term_type = at_menu.term_type = TERM_MSP;
    watching.character = &viewer; watching.next = &at_menu; viewer.desc = &watching;
    at_menu.character = &rented; rented.desc = &at_menu; rented.in_room = NOWHERE;
    viewer.in_room = 5051; viewer.player.level = mover.player.level = 1;
    viewer.player.race = mover.player.race = RACE_HUMAN;
    SET_POS((&viewer), STAT_NORMAL + POS_STANDING);
    SET_POS((&mover), STAT_NORMAL + POS_STANDING);
    descriptor_list = &watching;
    auto refresh = [&](int old_room, int new_room) {
        watching.last_map_update = 0; mover.in_room = new_room;
        map_update(&mover, old_room);
        assert(!at_menu.last_map_update);
        return watching.last_map_update;
    };
    assert(refresh(10001, 5052)); // Arrival.
    for (int destination : {10001, 5060, 5053}) {
        assert(refresh(5052, destination)); // Departures, including off-map.
        map_update(&mover, 5052); // Updates coalesce.
        assert(watching.last_map_update == 1);
    }
    assert(!refresh(5060, 5061)); // Neither tile is drawn.
    SET_BIT(mover.specials.affected_by, AFF_INVISIBLE);
    assert(!refresh(10001, 5052)); // Invisible arrival has no glyph.
    assert(refresh(5052, 10001)); // Old visibility cannot be inferred at destination.
    REMOVE_BIT(mover.specials.affected_by, AFF_INVISIBLE);
    mover.player.race = RACE_LICH; mover.in_room = 5052;
    assert(ac_can_see(&viewer, &mover, false));
    mover.in_room = 10001;
    assert(!ac_can_see(&viewer, &mover, false));
    assert(refresh(5052, 10001)); // Actual destination-dependent visibility regression.
    mover.player.race = RACE_HUMAN;
    viewer.following = &mover;
    assert(refresh(5051, 5053)); // Exhausted/failed follower stays behind.
    char_data leader{}; leader.in_room = 5053;
    mover.following = viewer.following = &leader;
    SET_BIT(mover.specials.affected_by5, AFF5_FOLLOWING);
    assert(refresh(5051, 5053)); // Successful sibling must not hide departure.
    viewer.in_room = 5053;
    assert(!refresh(5051, 5053)); // Suppress only after both arrive.
    mover.following = &viewer;
    assert(!refresh(5051, 5053)); // Leader already at destination.
    REMOVE_BIT(mover.specials.affected_by5, AFF5_FOLLOWING);
    mover.following = viewer.following = nullptr;
    viewer.in_room = 1;
    for (unsigned tile : {100U, 9901U, 10000U}) {
        assert(tile == calculate_relative_room(1, tile == 9901 ? 0 : -1,
                                               tile == 100 ? 0 : -1));
        assert(refresh(10001, tile));
        assert(refresh(tile, 10001));
    }
    viewer.in_room = 5051;
    assert(!map_view_contains(5051, 5354, 5)); // Ellipse excludes x=3,y=3.
    assert(map_view_contains(5051, 5353, 5)); // x=2,y=3 is drawn.
    vertical_factor = 0.1;
    assert(map_view_contains(5051, 5356, 5)); // Configured footprint exceeds a circle.
    assert(refresh(10001, 5356));
    vertical_factor = 1.2;
    assert(!map_view_contains(5051, 10002, 5)); // Never fold tail rooms into the grid.
    assert(!map_view_contains(10002, 5051, 5));
    assert(map_view_contains(10002, 10002, 5));
    for (int dimension : {0, -1}) {
        zones[0].mapx = dimension;
        assert(!map_view_contains(1, 2, 5));
        assert(map_view_contains(1, 1, 5));
    }
    zones[0].mapx = 100;
    assert(!map_view_contains(1, 1, 1)); // No map was rendered.
    assert(!map_view_contains(1, 1, 501)); // Renderer rejects this width.
    puts("PASS: real visibility, wrapped arrivals/departures, view footprint, tail rooms, follows and menu observers");
}
'''

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="map-observer-", dir=build) as tmp:
    cpp, binary = Path(tmp) / "test.cpp", Path(tmp) / "test"
    bodies = [PRELUDE,
              extract_function("utility.c", "bool ac_can_see_from("),
              extract_function("utility.c", "bool ac_can_see(P_char sub, P_char obj, bool"),
              extract_function("map.c", "unsigned int calculate_relative_room("),
              extract_function("map.c", "bool map_view_contains("),
              "void map_update(P_char ch, int was_in) { P_desc d; P_char who;\n" + loop + "\n}",
              CASES]
    cpp.write_text(with_innate_numbers("\n".join(bodies)))
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
                    "-Isrc", str(cpp), "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True,
                   env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1"})
