#!/usr/bin/env python3
"""Exercise group teleport's real destination search and group movement."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function

fixture = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "net/comm.h"
#include "world/map.h"
#include <cassert>
#include <cstdio>
#include <string>
static room_data rooms[4]{};
static zone_data zones[2]{};
P_room world = rooms;
zone_data *zone_table = zones;
static int draws, rejected, moved, stopped, close_checks, close_result;
static bool raidable = true;
static std::string feedback;
int number(int low, int high) {
    assert(low == 1 && high == 2);
    assert(++draws <= 1000); // One bounded search per cast, including map rooms.
    return draws <= rejected ? 1 : 2;
}
int is_Raidable(P_char, char *, int) { return raidable; }
int how_close(int, int, int max_steps) { assert(max_steps == 5); ++close_checks; return close_result; }
void send_to_char(const char *text, P_char) { feedback += text; }
void act(const char *, int, P_char, P_obj, void *, int) {}
void stop_fighting(P_char ch) { ++stopped; ch->specials.fighting = nullptr; }
void char_from_room(P_char ch) { ch->in_room = NOWHERE; }
bool char_to_room(P_char ch, int room, int) { ++moved; ch->in_room = room; return true; }
''' + extract_function('magic.c', 'static bool teleport_blocked_destination(') + \
    extract_function('magic.c', 'static void group_teleport_move(') + \
    extract_function('magic.c', 'void spell_group_teleport(') + r'''
int main() {
    zones[0].real_bottom = 1;
    zones[0].real_top = 2;
    for (bool map : {false, true}) {
        zones[0].flags = map ? ZONE_MAP : 0;
        for (bool group : {false, true}) {
            for (int failures : {0, 1, 999, 1000}) {
                // Exercise each destination rejection rule and eventual exhaustion.
                for (int restriction : std::initializer_list<int>{ROOM_PRIVATE, ROOM_NO_MAGIC, ROOM_NO_TELEPORT, -1, 0}) {
                    rooms[1].zone = 1;
                    rooms[1].room_flags = restriction > 0 ? restriction : 0;
                    zones[1].hometown = restriction == -1;
                    rooms[1].sector_type = restriction ? SECT_CITY : SECT_OCEAN;
                    char_data caster{}, ally{}, absent{}, opponent{};
                    absent.in_room = 3;
                    caster.specials.fighting = ally.specials.fighting = &opponent;
                    ally.specials.affected_by = AFF_HIDE;
                    group_list away{}, local{}, leader{};
                    away.ch = &absent;
                    local.ch = &ally; local.next = &away;
                    leader.ch = &caster; leader.next = &local;
                    caster.group = group ? &leader : nullptr;
                    draws = moved = stopped = 0;
                    rejected = failures;
                    spell_group_teleport(50, &caster, nullptr, SPELL_TYPE_SPELL, nullptr, nullptr);
                    const int destination = failures >= 999 ? 0 : 2;
                    assert(draws == (failures >= 999 ? 1000 : failures + 1));
                    assert(caster.in_room == destination);
                    assert(ally.in_room == (group ? destination : 0) && absent.in_room == 3);
                    assert(moved == (group ? 2 : 1) && stopped == (group ? 2 : 1));
                    assert(!caster.specials.fighting && (group || ally.specials.fighting));
                    assert(bool(IS_AFFECTED(&ally, AFF_HIDE)) == !group);
                }
            }
        }
        // Source-room and raidable refusals must not search or move anyone.
        for (int restriction : std::initializer_list<int>{ROOM_NO_TELEPORT, -1, 0}) {
            rooms[0].room_flags = restriction > 0 ? restriction : 0;
            zones[0].hometown = restriction == -1;
            rooms[0].sector_type = restriction ? SECT_CITY : SECT_OCEAN;
            char_data caster{};
            draws = moved = 0;
            spell_group_teleport(50, &caster, nullptr, SPELL_TYPE_SPELL, nullptr, nullptr);
            assert(!draws && !moved && caster.in_room == 0);
        }
        rooms[0] = {};
        zones[0].hometown = 0;
        raidable = false;
        char_data caster{};
        draws = moved = 0;
        spell_group_teleport(50, &caster, nullptr, SPELL_TYPE_SPELL, nullptr, nullptr);
        assert(!draws && !moved);
        raidable = true;
    }
    // A limited teleport zone refuses destinations beyond the solo spell's range.
    zones[0].flags = 0;
    rooms[0].number = 5700;
    for (bool in_range : {false, true}) {
        char_data caster{};
        group_list leader{};
        leader.ch = &caster;
        caster.group = &leader;
        moved = close_checks = draws = 0;
        rejected = 0;
        close_result = in_range ? 3 : -1;
        spell_group_teleport(50, &caster, nullptr, SPELL_TYPE_SPELL, nullptr, nullptr);
        assert(close_checks == 1 && moved == in_range && caster.in_room == (in_range ? 2 : 0));
    }
    std::puts("PASS group teleport: bounded map/zone search, rejection rules, exhaustion, solo/group movement");
}
'''

out = ROOT / 'bin/tests'
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='group-teleport-', dir=out) as temporary:
    cpp, binary = Path(temporary) / 'test.cpp', Path(temporary) / 'test'
    cpp.write_text(fixture)
    subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    '-g', '-Isrc', str(cpp), '-o', str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=30)
