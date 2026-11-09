#!/usr/bin/env python3
"""Salvage queues a clean ship, and the save carries what it salvaged."""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function, source

HARNESS = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "economy/divine_trade_runtime.h"
#include "ships/ships.h"
#include <cassert>
#include <cmath>
#include <cstring>
#include <limits>

static ShipData boat;
static ShipSlot saved_slots[MAXSLOTS];
static int extracted;
static room_data ocean[1];
static index_data crate_index[1];
P_room world = ocean;
P_index obj_index = crate_index;
ShipObjHash shipObjHash;
bool sql_save_ship(P_ship ship) {
    for (int index = 0; index < MAXSLOTS; ++index) saved_slots[index] = ship->slot[index];
    return true;
}
uint64_t divine_trade_runtime_ship_revision(uint32_t) { return 0; }
bool divine_trade_runtime_save_busy(const ShipData *) { return false; }
std::vector<divine_trade_book> divine_trade_runtime_ship_books(uint32_t) { return {}; }
bool divine_trade_book_encode(const divine_trade_book &, std::vector<uint8_t> *) {
    assert(false); return false;
}
void divine_trade_runtime_ship_saved(uint32_t) {}
void logit(const char *, const char *, ...) {}
void send_to_char(const char *, P_char) {}
void send_to_char_f(P_char, const char *, ...) {}
void update_ship_status(P_ship, P_ship) {}
float ShipCrew::get_maxcargo_mod() const { return 1.0; }
int eq_ram_weight(const ShipData *) { return 0; }
int eq_levistone_weight(const ShipData *) { return 0; }
const WeaponData weapon_data[MAXWEAPON] = {};
const EquipmentData equipment_data[MAXEQUIPMENT] = {};
void extract_obj(P_obj obj, int) {
    assert(world[0].contents == obj);
    world[0].contents = obj->next_content;
    ++extracted;
}
P_ship find_ship_by_runtime_ref(ShipRuntimeRef) { assert(false); return nullptr; }
void delete_ship(P_ship, bool) { assert(false); }

// REAL_FUNCTIONS

int main() {
    boat.m_class = SH_CLIPPER;
    boat.name = const_cast<char *>("Salvager");
    boat.ownername = const_cast<char *>("Captain");
    boat.flags = LOADED;
    for (auto &slot : boat.slot) slot.clear();
    obj_data hull{};
    boat.shipobj = &hull;
    assert(shipObjHash.add(&boat));
    assert(write_ship(&boat) && !boat.save_pending);
    const auto saved_signature = boat.save_saved_signature;

    // Invalid requests, empty water and a full hold must not queue saves.
    assert(salvage_cargo(nullptr, &boat, 0) && !boat.save_pending);
    assert(salvage_cargo(nullptr, &boat, 1) && !boat.save_pending);
    obj_data crates[2]{};
    crate_index[0].virtual_number = VOBJ_CARGO_CRATE;
    crates[0].next_content = &crates[1];
    crates[0].value[0] = 2; crates[0].value[1] = 1;
    crates[1].value[0] = 3; crates[1].value[1] = 2;
    world[0].contents = &crates[0];
    for (auto &slot : boat.slot) {
        slot.type = SLOT_CARGO; slot.index = 0;
        slot.position = SLOT_HOLD; slot.val0 = 1; slot.val1 = 100;
    }
    assert(salvage_cargo(nullptr, &boat, 1) && !boat.save_pending && !extracted);
    for (auto &slot : boat.slot) slot.clear();

    // Starting from the clean saved hold, consume both floating commodities.
    assert(boat.save_saved_signature == saved_signature);
    assert(salvage_cargo(nullptr, &boat, 2));
    assert(extracted == 2 && !world[0].contents);
    assert(boat.save_pending && boat.save_saved_signature == saved_signature);
    flush_pending_ship_saves();
    assert(!boat.save_pending && boat.save_saved_signature != saved_signature);

    // What the save received, rather than a copy of runtime slots.
    const auto &cargo = saved_slots[0];
    const auto &contra = saved_slots[1];
    assert(cargo.type == SLOT_CARGO && cargo.index == 2 && cargo.val0 == 1 && cargo.val1 == 0);
    assert(contra.type == SLOT_CONTRABAND && contra.index == 3 && contra.val0 == 1 && contra.val1 == 0);
    assert(salvage_cargo(nullptr, &boat, 1) && !boat.save_pending);
    puts("PASS: salvage queues a clean saved ship and the save carries the cargo");
}
'''

variables = source("ship_variables.c").read_text()
start = variables.index("const ShipTypeData ship_type_data[MAXSHIPCLASS] = {")
functions = variables[start:variables.index("\n};", start) + 3] + "\n"
functions += "\n".join(extract_function(filename, signature) for filename, signature in (
    ("ship_utils.c", "ShipObjHash::ShipObjHash()"),
    ("ship_utils.c", "bool ShipObjHash::add("),
    ("ship_utils.c", "bool ShipObjHash::erase(P_ship ship)"),
    ("ship_utils.c", "bool ShipObjHash::erase(P_ship ship, unsigned t_index)"),
    ("ship_utils.c", "bool ShipObjHash::get_first("),
    ("ship_utils.c", "bool ShipObjHash::get_next("),
    ("ship_utils.c", "void ShipSlot::clear()"),
    ("ship_utils.c", "int ShipSlot::get_weight("),
    ("ship_utils.c", "int ShipData::slot_weight("),
    ("ship_utils.c", "int add_crate("),
    ("ship_utils.c", "int salvage_cargo(P_char ch, P_ship ship, int crates)"),
    ("ship_base.c", "static unsigned long long ship_save_signature_mix("),
    ("ship_base.c", "unsigned long long ship_save_signature("),
    ("ship_base.c", "void queue_ship_save("),
    ("ship_base.c", "int write_ship("),
    ("ship_base.c", "void flush_pending_ship_saves("),
))

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="ship-salvage-", dir=ROOT / "bin/tests") as directory:
    path = Path(directory)
    (path / "test.cpp").write_text(HARNESS.replace("// REAL_FUNCTIONS", functions))
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-g",
        '-I/usr/include/mysql', "-Isrc", "-I/usr/include/libxml2",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
        str(path / "test.cpp"), "-o", str(path / "test"),
    ], cwd=ROOT, check=True)
    subprocess.run([str(path / "test")], cwd=ROOT, check=True)
