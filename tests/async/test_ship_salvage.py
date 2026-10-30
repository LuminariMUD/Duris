#!/usr/bin/env python3
"""Salvage queues a clean ship and survives the real flat-file save boundary."""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function, source

HARNESS = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "economy/divine_trade_runtime.h"
#include "flatfile/flatfile_ship_repository.h"
#include "ships/ships.h"
#include <cassert>
#include <cmath>
#include <cstring>
#include <filesystem>
#include <limits>
#include <sys/stat.h>

static std::string state_root;
static ShipData boat;
static int extracted;
static room_data ocean[1];
static index_data crate_index[1];
P_room world = ocean;
P_index obj_index = crate_index;
ShipObjHash shipObjHash;
const char *persistence_mode_flatfile_root() { return state_root.c_str(); }
bool flatfile_player_identity_pid(const char *, int32_t *pid, std::string *) {
    *pid = 42; return true;
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

int main(int argc, char **argv) {
    assert(argc == 2);
    umask(0077);
    state_root = argv[1];
    std::filesystem::create_directories(state_root + "/domains");
    std::string error;
    assert(flatfile_ship_establish(state_root, {}, &error) == flatfile_ship_result::ok);
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

    // Read the durable authority again, rather than a copy of runtime slots.
    std::vector<flatfile_ship_record> restored;
    assert(flatfile_ship_list(state_root, &restored, &error) == flatfile_ship_result::ok);
    assert(restored.size() == 1 && restored[0].slots.size() == MAXSLOTS);
    const auto &cargo = restored[0].slots[0];
    const auto &contra = restored[0].slots[1];
    assert(cargo.slot_type == SLOT_CARGO && cargo.item_index == 2 &&
           cargo.values[0] == 1 && cargo.values[1] == 0);
    assert(contra.slot_type == SLOT_CONTRABAND && contra.item_index == 3 &&
           contra.values[0] == 1 && contra.values[1] == 0);
    assert(salvage_cargo(nullptr, &boat, 1) && !boat.save_pending);
    puts("PASS: salvage queues a clean saved ship and cargo survives flush/reload");
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
    ("ship_base.c", "static bool flat_ship_skill_milli("),
    ("ship_base.c", "static bool flat_ship_slot_is_loadable("),
    ("ship_base.c", "static bool flat_ship_capture("),
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
        "-D__NO_MYSQL__", "-Isrc/no_mysql", "-Isrc", "-I/usr/include/libxml2",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
        str(path / "test.cpp"), "src/flatfile/flatfile_ship_repository.c",
        "src/flatfile/flatfile_authority_transaction.c", "src/flatfile/flatfile_store.c",
        "-lcrypto", "-pthread", "-o", str(path / "test"),
    ], cwd=ROOT, check=True)
    subprocess.run([str(path / "test"), str(path / "state")], cwd=ROOT, check=True)
