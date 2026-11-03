#!/usr/bin/env python3
"""#611: production spawn assignment, heartbeat, contacts and NPC target AI.

The lower-level hull factory, captains, ammunition, steering/combat maneuvers,
map rendering and world/persistence services are controlled. Ships stay still;
this proves pursuit dispatch and assignment retention, not a live sailing trip.
"""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function

FUNCTIONS = "\n\n".join(
    extract_function(file, signature)
    for file, signatures in (
        ("ship_utils.c", (
            "ShipObjHash::ShipObjHash()", "P_ship ShipObjHash::find(P_obj key)",
            "bool ShipObjHash::add(P_ship ship)", "bool ShipObjHash::erase(P_ship ship)\n",
            "bool ShipObjHash::erase(P_ship ship, unsigned t_index)",
            "bool ShipObjHash::get_first(visitor &vs)", "bool ShipObjHash::get_next(visitor &vs)",
            "float range(float x1, float y1, float z1, float x2,",
            "static float ship_range(P_ship ship, P_ship target, int x, int y)\n",
            "void normalize_direction(float &dir)", "int get_arc(float heading, float bearing)",
            "const char *get_arc_indicator(int arc_no)",
            "float bearing(float x1, float y1, float x2, float y2)",
            "void setcontact(int i, P_ship target, P_ship ship, int x, int y)",
            "bool ship_target_in_contact(P_ship ship)", "int getcontacts(P_ship ship, bool limit_range)",
        )),
        ("map.c", ("bool calculate_map_coords(int room1, int room2, int &x, int &y)",)),
        ("ship_base.c", ("void ship_activity()",)),
        ("ship_npc.c", ("P_ship try_load_npc_ship(P_ship target, NPC_AI_Type type, int level, P_char ch)",)),
        ("ship_npc_ai.c", (
            "NPCShipAI::NPCShipAI(P_ship s, P_char ch)", "void NPCShipAI::activity()",
            "void NPCShipAI::escort_attacked_by(P_ship attacker)",
            "bool NPCShipAI::find_current_target()", "bool NPCShipAI::find_new_target()",
            "bool NPCShipAI::is_valid_target(P_ship tar)", "void NPCShipAI::update_target(int i)",
        )),
    )
    for signature in signatures
)

HARNESS = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "core/utility.h"
#include "net/comm.h"
#include "world/db.h"
#include "world/map.h"
#include "ships/ships.h"
#include "ships/ship_auto.h"
#include "ships/ship_npc.h"
#include "ships/ship_npc_ai.h"
#include "magic/spells.h"
#include "economy/divine_trade_runtime.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

static room_data rooms[64]{};
P_room world = rooms;
static zone_data zones[3]{};
zone_data *zone_table = zones;
ShipObjHash shipObjHash;
P_ship cyrics_revenge = nullptr;
ShipMap tactical_map[101][101]{};
ContactData contacts[MAXSHIPS]{};
const ShipTypeData ship_type_data[MAXSHIPCLASS] = {{ ._hull = 100, ._mxsail = 100, ._mxspeed = 20, ._speedgain = 1 }};
const WeaponData weapon_data[MAXWEAPON]{};
static int contact_bonus, basic_calls, advanced_calls;
static std::vector<P_ship> allocated;

// Only the outer spawn overload is production code: the factory creates a
// minimal loaded hull/brain at the requested room, without world I/O or crew.
static P_ship make_ship(int race, int location) {
    auto ship = static_cast<P_ship>(calloc(1, sizeof(ShipData)));
    ship->race = race;
    ship->flags = LOADED;
    ship->location = location;
    ship->x = ship->y = 50;
    ship->crew.stamina = ship->crew.max_stamina = 100;
    ship->shipobj = new obj_data{};
    if (race == NPCSHIP) ship->npc_ai = new NPCShipAI(ship);
    assert(shipObjHash.add(ship));
    allocated.push_back(ship);
    return ship;
}
P_ship try_load_npc_ship(P_ship, NPC_AI_Type type, int, int location, P_char) {
    P_ship ship = make_ship(NPCSHIP, location);
    ship->npc_ai->type = type;
    return ship;
}
bool getmap(P_ship ship, bool) {
    // Deterministic northward spawn cell, exactly 45 rooms from the victim.
    const int spawn = ship->location + 8;
    assert(spawn < 64);
    world[spawn].zone = world[ship->location].zone;
    world[spawn].number = world[ship->location].number - 45000;
    tactical_map[50][5].rroom = spawn;
    tactical_map[50][50].rroom = ship->location;
    return true;
}
int number(int low, int high) { return low == -45 ? 0 : high; }
int ShipCrew::get_contact_range_mod() const { return contact_bonus; }
int ShipData::get_maxspeed(P_char) const { return 10; }
float ShipTypeData::get_hull_mod() const { return 1; }
float ShipCrew::get_stamina_mod() { return 1; }
int ShipCrew::get_sail_repair_mod() const { abort(); }
int ShipCrew::get_weapon_repair_mod() const { abort(); }
int ShipCrew::get_hull_repair_mod() const { abort(); }
void ShipCrew::reduce_stamina(float, P_ship) { abort(); }
void ShipCrew::rpar_skill_raise(float) { abort(); }
void ShipCrew::sail_skill_raise(float) { abort(); }
void ShipCrew::guns_skill_raise(float) { abort(); }
char *ShipSlot::get_description() { abort(); }
bool divine_trade_runtime_busy(const ShipData *) { return false; }
void check_contraband(P_ship, int) { abort(); }
void queue_ship_save(P_ship, const char *) { abort(); }
void act_to_all_in_ship(P_ship, const char *) {}
void act_to_all_in_ship_f(P_ship, const char *, ...) { abort(); }
void send_to_char_f(P_char, const char *, ...) { abort(); }
void update_ship_status(P_ship, P_ship) { abort(); }
void finish_sinking(P_ship) { abort(); }
void assignid(P_ship, const char *, bool) { abort(); }
void update_crew(P_ship) { abort(); }
P_char captain_is_aboard(P_ship) { return nullptr; }
int get_next_speed_change(P_ship) { abort(); }
float get_next_heading_change(P_ship) { abort(); }
bool is_valid_sailing_location(P_ship, int) { abort(); }
void obj_from_room(P_obj) { abort(); }
void obj_to_room(P_obj, int) { abort(); }
void everyone_look_out_ship(P_ship) { abort(); }
void stop_autopilot(P_ship) { abort(); }
void crash_land(P_ship) { abort(); }
int dice(int, int) { abort(); }
int try_ram_ship(P_ship, P_ship, float) { abort(); }
void land_ship(P_ship) { abort(); }
void autopilot_activity(P_ship) { abort(); }
bool has_eq_diplomat(const ShipData *) { return false; }
int get_property(const char *, int fallback) { return fallback; }
P_ship try_load_pirate_ship(P_ship) { abort(); }
void send_to_room_f(int, const char *, ...) { abort(); }

// Captains and ammunition are available. Navigation, firing and boarding are
// outside this fixture; count dispatch so an early AI return cannot pass it.
static bool is_boardable(P_ship) { return false; }
bool NPCShipAI::check_for_captain_on_bridge() { return true; }
bool NPCShipAI::check_ammo() { return true; }
void NPCShipAI::check_for_jettison() {}
int NPCShipAI::check_dir_for_land_from(float, float, float, float) { return 0; }
void NPCShipAI::b_attack() { abort(); }
bool NPCShipAI::go_around_land(P_ship) { abort(); }
bool NPCShipAI::worth_ramming() { return false; }
bool NPCShipAI::check_ram() { abort(); }
void NPCShipAI::ram_target() { abort(); }
bool NPCShipAI::check_boarding_conditions() { abort(); }
void NPCShipAI::board_target() { abort(); }
bool NPCShipAI::charge_target(bool) { abort(); }
void NPCShipAI::immobile_maneuver() { abort(); }
void NPCShipAI::basic_combat_maneuver() { assert(ship->target && t_range > 37); ++basic_calls; }
void NPCShipAI::advanced_combat_maneuver() { assert(ship->target && t_range > 37); ++advanced_calls; }
void NPCShipAI::run_away() { abort(); }
bool NPCShipAI::do_escort() { return false; }
void NPCShipAI::cruise() {}
bool NPCShipAI::try_unload() { return false; }
void fly_ship(P_ship) { abort(); }
''' + FUNCTIONS + r'''

static void reset() {
    for (P_ship ship : allocated) {
        assert(shipObjHash.erase(ship));
        delete ship->npc_ai;
        delete ship->shipobj;
        free(ship);
    }
    allocated.clear();
    assert(shipObjHash.size() == 0);
    memset(rooms, 0, sizeof rooms);
    memset(zones, 0, sizeof zones);
    for (int i = 0; i < 2; ++i) {
        zones[i].flags = ZONE_MAP;
        zones[i].mapx = zones[i].mapy = 1000;
        zones[i].real_bottom = 1;
    }
    world[1].number = 500000;
    basic_calls = advanced_calls = 0;
}

static P_ship spawn(P_ship victim, NPC_AI_Type type, int advanced, int idle) {
    P_ship ship = try_load_npc_ship(victim, type, advanced ? 3 : 1, nullptr);
    assert(ship && ship->target == victim && ship->npc_ai->mode == NPC_AI_ENGAGING);
    assert(ship->npc_ai->advanced == advanced);
    assert(ship->speed == 10 && ship->setspeed == 10);
    const int count = getcontacts(ship, false);
    bool found = false;
    for (int i = 0; i < count; ++i) if (contacts[i].ship == victim) {
        assert(fabs(contacts[i].range - 45) < 0.01);
        found = true;
    }
    assert(found && !ship_target_in_contact(ship));
    ship->speed = ship->setspeed = 0;
    ship->timer[T_TARGET_IDLE] = idle;
    return ship;
}

static void check_group() {
    for (contact_bonus = 0; contact_bonus <= 2; ++contact_bonus)
    for (int advanced = 0; advanced <= 1; ++advanced)
    for (int idle = 0; idle <= 1; ++idle)
    for (int rotation = 0; rotation < 2; ++rotation) {
        reset();
        for (int i = 0; i < 4; ++i) {
            world[2+i].number = 600100 + i;
            make_ship(GOODIESHIP, 2+i);
        }
        // Derive actual production hash order; no allocation-address assumptions.
        std::vector<P_ship> ordered;
        ShipVisitor visitor;
        for (bool ok = shipObjHash.get_first(visitor); ok; ok = shipObjHash.get_next(visitor))
            ordered.push_back(visitor.get_value());
        assert(ordered.size() == 4);
        for (int i = 0; i < 4; ++i) {
            ordered[i]->frags = i ? (rotation ? 40000-i*10000 : i*10000) : 0;
            SET_BIT(ordered[i]->flags, ATTACKBYNPC);
        }
        P_ship attackers[3], victims[3];
        for (int i = 0; i < 3; ++i) {
            victims[i] = ordered[1 + (i+rotation)%3];
            attackers[i] = spawn(victims[i], i == 1 ? NPC_AI_HUNTER : NPC_AI_PIRATE, advanced, idle);
            // The competing first eligible contact is already marked attacked.
            assert(attackers[i]->npc_ai->is_valid_target(ordered[0]));
            P_ship first = nullptr;
            const int count = getcontacts(attackers[i], false);
            for (int j = 0; j < count; ++j)
                if (attackers[i]->npc_ai->is_valid_target(contacts[j].ship)) { first = contacts[j].ship; break; }
            assert(first == ordered[0]);
        }
        for (int tick = 0; tick < 305; ++tick) {
            ship_activity();
            for (int i = 0; i < 3; ++i) {
                assert(attackers[i]->target == victims[i]);
                assert(attackers[i]->npc_ai->mode == NPC_AI_ENGAGING);
                assert(attackers[i]->timer[T_TARGET_IDLE] == 0);
                assert(attackers[i]->timer[T_BSTATION] == BSTATION);
                assert(fabs(attackers[i]->npc_ai->t_range - 45) < 0.01);
            }
            assert((advanced ? advanced_calls : basic_calls) == (tick+1)*3);
            assert((advanced ? basic_calls : advanced_calls) == 0);
        }
    }
    reset();
    puts("PASS distinct pirate/hunter spawn assignments: scouts 0/1/2, idle 0/1, both maneuvers, 305 ticks, permuted victims/frags");
}

static void check_escort() {
    reset();
    contact_bonus = 0;
    world[2].number = 600100;
    world[3].number = 555100;
    P_ship charge = make_ship(GOODIESHIP, 2), attacker = make_ship(EVILSHIP, 3);
    P_ship escort = try_load_npc_ship(charge, NPC_AI_ESCORT, 1, nullptr);
    assert(escort->npc_ai->escort == charge && !escort->target);
    escort->speed = escort->setspeed = 0;
    escort->npc_ai->escort_attacked_by(attacker);
    assert(escort->target == attacker && !ship_target_in_contact(escort));
    for (int tick = 0; tick < 305; ++tick) {
        ship_activity();
        assert(escort->target == attacker && escort->npc_ai->escort == charge);
        assert(escort->npc_ai->mode == NPC_AI_ENGAGING && basic_calls == tick+1);
    }
    reset();
    puts("PASS escort retaliation retains distant attacker and separate escort relationship");
}

static void check_unavailable() {
    contact_bonus = 0;
    for (int npc = 0; npc <= 1; ++npc)
    for (int invalid = 0; invalid < 5; ++invalid) {
        reset();
        world[2].number = 600100;
        world[3].number = 600101;
        P_ship ship = make_ship(npc ? NPCSHIP : GOODIESHIP, 2);
        P_ship target = make_ship(EVILSHIP, 3);
        ship->target = target;
        ship->timer[T_TARGET_IDLE] = 300;
        if (npc) {
            ship->npc_ai->type = NPC_AI_HUNTER;
            ship->npc_ai->mode = NPC_AI_ENGAGING;
        }
        switch (invalid) {
        case 0: REMOVE_BIT(target->flags, LOADED); break;
        case 1: SET_BIT(target->flags, DOCKED); break;
        case 2: SET_BIT(target->flags, SINKING); target->timer[T_SINKING] = 1000; break;
        case 3: world[3].zone = 2; break; // off-map zone
        case 4: world[3].zone = 1; break; // another usable map zone
        }
        for (int tick = 0; tick < 3; ++tick) {
            ship_activity();
            assert(!ship->target);
            if (npc) assert(ship->npc_ai->mode == NPC_AI_CRUISING);
            assert(basic_calls == 0 && advanced_calls == 0);
        }
        assert(shipObjHash.find(target->shipobj) == target); // Still enumerated if on-map.
    }
    reset();
    puts("PASS NPC/player unavailable targets: unloaded (no reacquisition), docked, sinking, off-map and different zones");
}

int main(int argc, char **argv) {
    assert(argc == 2);
    if (!strcmp(argv[1], "group")) check_group();
    else if (!strcmp(argv[1], "escort")) check_escort();
    else if (!strcmp(argv[1], "unavailable")) check_unavailable();
    else abort();
}
'''

build_root = ROOT / "bin" / "tests"
build_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="npc-ship-targeting-", dir=build_root) as directory:
    path = Path(directory)
    failures = []
    (path / "test.cpp").write_text(HARNESS, encoding="utf-8")
    for backend in ("mysql", "flatfile"):
        defines = ["-D__NO_MYSQL__", "-Isrc/no_mysql"] if backend == "flatfile" else ["-I/usr/include/mysql"]
        binary = path / backend
        subprocess.run(
            ["g++", "-std=c++20", "-g", "-Og", "-Isrc", "-I/usr/include/libxml2", *defines,
             "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
             str(path / "test.cpp"), str(HARNESS_STUBS), "-o", str(binary)],
            cwd=ROOT, check=True,
        )
        for case in ("group", "escort", "unavailable"):
            print(f"{backend}: {case}", flush=True)
            result = subprocess.run([str(binary), case], timeout=30)
            if result.returncode:
                failures.append(f"{backend}: {case}")
    assert not failures, f"Failed cases: {', '.join(failures)}"
