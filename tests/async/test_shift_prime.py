#!/usr/bin/env python3
"""Execute shift-prime selection against rooms from the four replacement zones."""
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source

zones = [("lizard", 60, 6000), ("bugentol", 958, 95800),
         ("quietus", 17, 1700), ("stormport", 224, 22400)]
fixtures = []
bounds = []
for index, (name, zone_number, anchor) in enumerate(zones, 1):
    header = (ROOT / f"areas/zon/{name}.zon").read_text().split("~", 1)
    assert int(header[0].splitlines()[0][1:]) == zone_number
    top = int(header[1].split()[0])
    rooms = [int(vnum) for vnum in re.findall(
        r"^#(\d+)\s*$", (ROOT / f"areas/wld/{name}.wld").read_text(), re.M)]
    assert anchor in rooms and all(zone_number * 100 <= room <= top for room in rooms)
    bottom = len(fixtures)
    fixtures.extend((vnum, index) for vnum in rooms)
    bounds.append((bottom, len(fixtures) - 1))

fixed = [2381, 11545, 23691, 93001, 4437, 90803, 96803, 619036, 17607, 6405, 53122]
zerai = [41767, 20484, 6224, 66651, 7117, 93665, 16805,
         5759, 2018, 99295, 93919, 16302, 574427, 557620]
phantom = [5927, 98731, 14373, 99465, 18305, 217481, 15100, 8486, 8430]
fixtures.extend((vnum, 5) for vnum in fixed + zerai + phantom)
fixtures.append((19701, 0))

prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include <cassert>
#include <deque>
#include <string>
#include <utility>
#include <vector>
static std::vector<room_data> rooms;
P_room world;
static zone_data zones[6]{};
zone_data *zone_table = zones;
static std::deque<int> choices;
static std::vector<std::pair<int, int>> rng_ranges;
static std::string output;
static bool cooldown_allowed = true, move_allowed = true;
static int cooldown_checks, moved, lag, departures, missing = NOWHERE;
static bool destinations_missing;
static int only_destination = NOWHERE;
bool SanityCheck(P_char ch, const char *) { return ch != nullptr; }
int real_room(const int vnum) {
    if (vnum == missing) return NOWHERE;
    if (vnum != 19701 && (destinations_missing ||
        (only_destination != NOWHERE && vnum != only_destination))) return NOWHERE;
    for (size_t i = 0; i < rooms.size(); ++i)
        if (rooms[i].number == vnum) return static_cast<int>(i);
    return NOWHERE;
}
int number(int low, int high) {
    assert(!choices.empty());
    int value = choices.front(); choices.pop_front();
    assert(value >= low && value <= high);
    rng_ranges.emplace_back(low, high);
    return value;
}
bool check_innate_time(P_char, int innate, int) {
    assert(innate == INNATE_SHIFT_PRIME); ++cooldown_checks;
    return cooldown_allowed;
}
void send_to_char(const char *text, P_char) { output += text; }
void CharWait(P_char, int pulses) { lag += pulses; }
void act(const char *, int, P_char, P_obj, void *, int) {}
void char_from_room(P_char ch) { ++departures; ch->in_room = NOWHERE; }
bool char_to_room(P_char ch, int room, int direction) {
    assert(direction == -1 && room >= 0 && room < static_cast<int>(rooms.size()));
    moved = room;
    if (move_allowed) ch->in_room = room;
    return move_allowed;
}
#define PLANE_ZONETARG_ROOMNUMB 19701
'''

driver = r'''
static void reset(P_char ch, int race = RACE_GITHYANKI) {
    destinations_missing = false; only_destination = missing = NOWHERE;
    *ch = char_data{};
    ch->player.race = race; ch->in_room = real_room(19701);
    choices.clear(); rng_ranges.clear(); output.clear();
    cooldown_allowed = move_allowed = true;
    cooldown_checks = lag = departures = 0; moved = missing = NOWHERE;
}
static void shift(P_char ch) { do_shift_prime(ch, nullptr, 0); assert(choices.empty()); }
int main() {
    const std::pair<int, int> fixture[] = { FIXTURES };
    rooms.resize(sizeof(fixture) / sizeof(fixture[0])); world = rooms.data();
    for (size_t i = 0; i < rooms.size(); ++i) {
        world[i].number = fixture[i].first; world[i].zone = fixture[i].second;
    }
    const std::pair<int, int> bounds[] = { BOUNDS };
    for (int z = 1; z <= 4; ++z) {
        zones[z].real_bottom = bounds[z-1].first; zones[z].real_top = bounds[z-1].second;
    }
    const int slots[] = {0, 3, 13, 5};
    const int anchors[] = {6000, 95800, 1700, 22400};
    const int expected[] = {6000, 2381, 11545, 95800, 23691, 22400, 93001, 4437,
                           90803, 96803, 619036, 17607, 6405, 1700, 53122};
    char_data ch{};
    int landings = 0;
    for (int race : {RACE_GITHYANKI, RACE_PILLITHID, RACE_ILLITHID}) {
        for (int z = 1; z <= 4; ++z) {
            assert(world[real_room(anchors[z-1])].zone == z);
            for (int room = zones[z].real_bottom; room <= zones[z].real_top; ++room) {
                reset(&ch, race); choices = {slots[z-1], room}; shift(&ch);
                assert(ch.in_room == room && world[ch.in_room].zone == z);
                assert(rng_ranges.size() == 2 && rng_ranges[0] == std::make_pair(0, 14));
                assert(rng_ranges[1] == std::make_pair(zones[z].real_bottom, zones[z].real_top));
                assert(cooldown_checks == 1 && departures == 1 && lag == PULSE_VIOLENCE);
                assert(output == "You materialize elsewhere!\n"); ++landings;
            }
        }
        for (int slot = 0; slot < 15; ++slot) {
            if (slot == 0 || slot == 3 || slot == 5 || slot == 13) continue;
            reset(&ch, race); choices = {slot}; shift(&ch);
            assert(world[ch.in_room].number == expected[slot] && rng_ranges.size() == 1);
        }
        // Missing anchors are excluded before drawing; every surviving slot stays reachable.
        for (int z = 1; z <= 4; ++z) {
            for (int slot = 0; slot < 15; ++slot) {
                if (slot == slots[z-1]) continue;
                reset(&ch, race); missing = anchors[z-1];
                choices = {slot - (slot > slots[z-1] ? 1 : 0)};
                int target = real_room(expected[slot]);
                for (int zone = 1; zone <= 4; ++zone) {
                    if (slot != slots[zone-1]) continue;
                    target = zones[zone].real_top; choices.push_back(target);
                }
                shift(&ch);
                assert(ch.in_room == target && rng_ranges[0] == std::make_pair(0, 13));
            }
        }
    }
    const int zerai[] = { ZERAI_ROOMS };
    const int phantom[] = { PHANTOM_ROOMS };
    for (int i = 0; i < 14; ++i) {
        reset(&ch, RACE_GITHZERAI); choices = {i}; shift(&ch);
        assert(world[ch.in_room].number == zerai[i] && rng_ranges.size() == 1);
    }
    for (int i = 0; i < 9; ++i) {
        reset(&ch, RACE_PHANTOM); choices = {i}; shift(&ch);
        assert(world[ch.in_room].number == phantom[i] && rng_ranges.size() == 1);
    }
    // Empty and partially loaded worlds must terminate for every supported race.
    for (int race : {RACE_GITHYANKI, RACE_PILLITHID, RACE_ILLITHID,
                     RACE_GITHZERAI, RACE_PHANTOM}) {
        reset(&ch, race); destinations_missing = true; shift(&ch);
        assert(ch.in_room == real_room(19701) && !departures && !lag && rng_ranges.empty());
        assert(output.find("cannot find a path") != std::string::npos);
        reset(&ch, race);
        only_destination = race == RACE_GITHZERAI ? 557620 : race == RACE_PHANTOM ? 8430 : 53122;
        choices = {0}; shift(&ch);
        assert(world[ch.in_room].number == only_destination);
        assert(rng_ranges.size() == 1 && rng_ranges[0] == std::make_pair(0, 0));
    }
    reset(&ch); missing = 19701; shift(&ch);
    assert(!departures && !cooldown_checks && !lag && rng_ranges.empty());
    assert(output.find("will not work here") != std::string::npos);
    reset(&ch); ch.specials.fighting = &ch; shift(&ch);
    assert(!departures && !cooldown_checks && lag == PULSE_VIOLENCE);
    assert(output.find("too busy fighting") != std::string::npos);
    reset(&ch); ch.in_room = real_room(6000); shift(&ch);
    assert(!departures && !cooldown_checks && !lag);
    assert(output.find("will not work here") != std::string::npos);
    reset(&ch); cooldown_allowed = false; shift(&ch);
    assert(!departures && cooldown_checks == 1 && !lag);
    assert(output.find("too tired") != std::string::npos);
    reset(&ch, RACE_HUMAN); shift(&ch);
    assert(!departures && !lag && output.find("cannot find a path") != std::string::npos);
    reset(&ch); move_allowed = false; choices = {1}; shift(&ch);
    assert(moved == real_room(2381) && !lag);
    printf("Shift prime: %d replacement-zone landings passed across three shared races.\n", landings);
    puts("All 11 fixed destinations, Githzerai/Phantom lists, missing/empty destinations, missing Astral anchor, combat, Astral restriction, cooldown and movement failure passed.");
}
'''
driver = (driver.replace("FIXTURES", ",".join(f"{{{v}, {z}}}" for v, z in fixtures))
          .replace("BOUNDS", ",".join(f"{{{a}, {b}}}" for a, b in bounds))
          .replace("ZERAI_ROOMS", ",".join(map(str, zerai)))
          .replace("PHANTOM_ROOMS", ",".join(map(str, phantom))))

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="shift-prime-", dir=build) as directory:
    cpp, binary = Path(directory) / "harness.cpp", Path(directory) / "harness"
    innates = source("innates.c").read_text()
    selector = innates[innates.index("struct shift_prime_destination\n"):
                      innates.index("#define PLANE_ZONETARG_ROOMNUMB")]
    cpp.write_text(prelude + selector + extract_function("innates.c", "void do_shift_prime(P_char ch") + driver)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wpedantic",
                    "-Og", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    "-fno-pie", "-no-pie", "-I" + str(ROOT / "src"), str(cpp),
                    "-o", str(binary)], check=True, timeout=120)
    subprocess.run([str(binary)], check=True, timeout=120)
for (name, _, _), (bottom, top) in zip(zones, bounds):
    print(f"{name}: {top - bottom + 1} loaded rooms verified")
