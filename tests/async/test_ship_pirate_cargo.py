#!/usr/bin/env python3
"""Exercise pirate theft with the real cargo functions, capacity macros and hulls."""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function, source

HARNESS = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "economy/divine_trade_runtime.h"
#include "ships/ship_npc_ai.h"
#include "ships/ships.h"
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

static int lost_roll = 60, left_roll = 40, draws, ram_weight;
static int rejected_slot = -1, saves;
static bool busy;
static P_ship victim, message_ship;
static std::string message;
static std::vector<int> removals;
NPCShipAI::NPCShipAI(P_ship s, P_char ch) : ship(s), debug_char(ch) {}
int number(int low, int high) {
    assert(low == 40 && high == 60);
    return draws++ % 2 ? left_roll : lost_roll;
}
float ShipCrew::get_maxcargo_mod() const { return 1.0; }
bool divine_trade_runtime_busy(const ShipData *s) { assert(s == victim); return busy; }
bool divine_trade_runtime_loss(P_ship s, int slot, int quantity) {
    assert(s == victim && quantity > 0 && quantity <= s->slot[slot].val0);
    if (slot == rejected_slot) return false;
    removals.push_back(quantity);
    return true;
}
void update_ship_status(P_ship, P_ship) {}
void queue_ship_save(P_ship s, const char *reason) {
    assert(s == victim && !strcmp(reason, "NPC cargo theft"));
    ++saves;
}
void act_to_all_in_ship_f(P_ship s, const char *format, ...) {
    assert(message.empty());
    char text[256];
    va_list args;
    va_start(args, format);
    vsnprintf(text, sizeof(text), format, args);
    va_end(args);
    message = text;
    message_ship = s;
}
int eq_ram_weight(const ShipData *) { return ram_weight; }
int eq_levistone_weight(const ShipData *) { return 0; }
const WeaponData weapon_data[MAXWEAPON] = {};
const EquipmentData equipment_data[MAXEQUIPMENT] = {};

// REAL_FUNCTIONS

static void reset(ShipData &pirate, ShipData &target, int hull = SH_CLIPPER) {
    pirate = {}; target = {};
    pirate.m_class = hull;
    target.m_class = SH_GALLEON;
    for (auto &slot : pirate.slot) slot.clear();
    for (auto &slot : target.slot) slot.clear();
    pirate.target = victim = &target;
    lost_roll = 60; left_roll = 40; draws = ram_weight = saves = 0;
    busy = false; rejected_slot = -1;
    message.clear(); message_ship = nullptr; removals.clear();
}
static void cargo(ShipData &s, int slot, int count, int port = 0,
                  int goods = SLOT_CARGO, int basis = 0) {
    s.slot[slot].type = goods;
    s.slot[slot].position = SLOT_HOLD;
    s.slot[slot].index = port;
    s.slot[slot].val0 = count;
    s.slot[slot].val1 = basis;
}
static void summary(int stolen, int destroyed) {
    if (!stolen) {
        assert(!saves && message.empty() && removals.empty());
        return;
    }
    assert(saves == 1 && message_ship == victim);
    assert(message == "&+YThe pirates steal " + std::to_string(stolen) +
           (stolen == 1 ? " crate" : " crates") + " and destroy " +
           std::to_string(destroyed) + " during the raid!&N\r\n");
    int removed = 0;
    for (int quantity : removals) removed += quantity;
    assert(removed == stolen + destroyed);
}
int main() {
    ShipData pirate{}, target{};
    NPCShipAI ai(&pirate);

    // The reported 16-crate loss is still valid: only 10 go aboard the pirate.
    reset(pirate, target);
    cargo(target, 0, 20, 0, SLOT_CARGO, 2000);
    ai.steal_target_cargo();
    assert(SHIP_CARGO_LOAD(&pirate) == 10 && SHIP_CARGO_LOAD(&target) == 4);
    assert(pirate.slot[0].val1 == 0);
    summary(10, 6);

    // All RNG pairs preserve the distinction between carried and destroyed.
    for (int lost = 40; lost <= 60; ++lost)
        for (int left = 40; left <= 60; ++left) {
            reset(pirate, target);
            lost_roll = lost; left_roll = left;
            cargo(target, 0, 20);
            ai.steal_target_cargo();
            int stolen = SHIP_CARGO_LOAD(&pirate);
            int removed = 20 - SHIP_CARGO_LOAD(&target);
            assert(stolen > 0 && stolen <= 10 && removed >= stolen && removed <= 16);
            summary(stolen, removed - stolen);
        }

    // Per-slot rounding must share one allowance, including contraband.
    for (bool mixed : {false, true}) {
        reset(pirate, target);
        cargo(target, 0, 10, 0, SLOT_CARGO, 1000);
        for (int i = 1; i <= 10; ++i)
            cargo(target, i, 1, i % 10,
                  mixed && i % 2 ? SLOT_CONTRABAND : SLOT_CARGO,
                  i == 10 ? 0 : 100);
        ai.steal_target_cargo();
        assert(SHIP_CARGO_LOAD(&pirate) == 10 && SHIP_CARGO_LOAD(&target) == 7);
        assert(target.slot[6].val0 == 1 && target.slot[10].val0 == 1);
        if (mixed) assert(SHIP_CONTRA(&pirate) == 3);
        summary(10, 3);
    }

    // Small lots consume rounding allowance before a larger lot is reached.
    reset(pirate, target);
    cargo(pirate, 0, 5);
    for (int i = 0; i < 3; ++i) cargo(target, i, 1, i);
    cargo(target, 3, 17, 3);
    ai.steal_target_cargo();
    assert(SHIP_CARGO_LOAD(&pirate) == 10 && SHIP_CARGO_LOAD(&target) == 13);
    summary(5, 2);

    // A nearly full merchant or warship can take only its remaining crate.
    for (int hull : {SH_CLIPPER, SH_CORVETTE}) {
        reset(pirate, target, hull);
        int limit = hull == SH_CLIPPER ? 10 : SHIP_MAX_WEIGHT(&pirate) / 5;
        cargo(pirate, 0, limit - 1);
        cargo(target, 0, 19, 0, SLOT_CARGO, 1900);
        cargo(target, 1, 1, 1);
        ai.steal_target_cargo();
        assert(SHIP_CARGO_LOAD(&pirate) == limit && SHIP_CARGO_LOAD(&target) == 19);
        summary(1, 0);
    }

    // Weight allowance can run out before the cargo rating.
    reset(pirate, target);
    pirate.slot[15].type = SLOT_EQUIPMENT;
    pirate.slot[15].index = E_RAM;
    ram_weight = 53;
    cargo(target, 0, 19); cargo(target, 1, 1, 1);
    ai.steal_target_cargo();
    assert(SHIP_CARGO_LOAD(&pirate) == 1 && SHIP_SLOT_WEIGHT(&pirate) == 55);
    summary(1, 0);
    for (int weight : {55, 56}) {
        reset(pirate, target);
        pirate.slot[15].type = SLOT_EQUIPMENT;
        pirate.slot[15].index = E_RAM;
        ram_weight = weight;
        cargo(target, 0, 20);
        ai.steal_target_cargo();
        assert(SHIP_CARGO_LOAD(&pirate) == 0 && SHIP_CARGO_LOAD(&target) == 20 && !draws);
        summary(0, 0);
    }
    reset(pirate, target);
    cargo(pirate, 0, 10); cargo(target, 0, 20);
    ai.steal_target_cargo();
    assert(SHIP_CARGO_LOAD(&target) == 20 && !draws);
    summary(0, 0);

    // Purchased lots cannot absorb salvage. A failed addition removes nothing.
    reset(pirate, target, SH_GALLEON);
    for (int i = 0; i < MAXSLOTS; ++i) cargo(pirate, i, 1, 0, SLOT_CARGO, 100);
    cargo(target, 0, 20, 0, SLOT_CARGO, 2000);
    ai.steal_target_cargo();
    assert(SHIP_CARGO_LOAD(&pirate) == 16 && target.slot[0].val0 == 20 &&
           target.slot[0].val1 == 2000);
    summary(0, 0);
    // A later compatible salvage stack remains usable even with no empty slot.
    pirate.slot[15].val1 = 0;
    target.slot[0].clear();
    cargo(target, 0, 1, 1); cargo(target, 1, 1);
    ai.steal_target_cargo();
    assert(target.slot[0].val0 == 1 && target.slot[1].type == SLOT_EMPTY &&
           pirate.slot[15].val0 == 2 && pirate.slot[0].val1 == 100);
    summary(1, 0);

    // A loss veto restores both new slots and existing stacks; later lots work.
    for (bool stack : {false, true}) {
        reset(pirate, target);
        if (stack) cargo(pirate, 0, 9);
        cargo(target, 0, 1, 0, SLOT_CARGO, 100);
        cargo(target, 1, 1, 1, SLOT_CONTRABAND);
        rejected_slot = 0;
        ai.steal_target_cargo();
        assert(SHIP_CARGO_LOAD(&pirate) == (stack ? 10 : 1) && SHIP_CONTRA(&pirate) == 1);
        assert(target.slot[0].val0 == 1 && target.slot[0].val1 == 100 &&
               target.slot[1].type == SLOT_EMPTY);
        summary(1, 0);
    }
    reset(pirate, target);
    cargo(target, 0, 20);
    rejected_slot = 0;
    ai.steal_target_cargo();
    assert(SHIP_CARGO_LOAD(&pirate) == 0 && target.slot[0].val0 == 20);
    summary(0, 0);

    reset(pirate, target);
    cargo(target, 0, 20); busy = true;
    ai.steal_target_cargo();
    assert(SHIP_CARGO_LOAD(&pirate) == 0 && target.slot[0].val0 == 20);
    summary(0, 0);
    reset(pirate, target);
    ai.steal_target_cargo();
    summary(0, 0);
    puts("PASS: pirate cargo/weight limits, failed transfers, loss vetoes and raid totals");
}
'''

variables = source("ship_variables.c").read_text()
start = variables.index("const ShipTypeData ship_type_data[MAXSHIPCLASS] = {")
functions = variables[start:variables.index("\n};", start) + 3] + "\n"
functions += "\n".join(extract_function(filename, signature) for filename, signature in (
    ("ship_utils.c", "void ShipSlot::clear()"),
    ("ship_utils.c", "int ShipSlot::get_weight("),
    ("ship_utils.c", "int ShipData::slot_weight("),
    ("ship_utils.c", "int add_crate("),
    ("ship_npc_ai.c", "void NPCShipAI::steal_target_cargo()"),
))
output = ROOT / "bin/tests"
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="pirate-cargo-", dir=output) as directory:
    cpp = Path(directory) / "pirate.cpp"
    binary = Path(directory) / "pirate"
    cpp.write_text(HARNESS.replace("// REAL_FUNCTIONS", functions))
    subprocess.run([
        "g++", "-std=c++20", "-g", "-Og", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        "-Isrc", "-Itests/async", "-I/usr/include/mysql", str(cpp), "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True)
