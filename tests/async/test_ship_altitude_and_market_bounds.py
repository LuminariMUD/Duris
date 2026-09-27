#!/usr/bin/env python3
"""Flying ships fly high, and the cargo markets stay inside their bands.

Two settings did nothing:

- ShipData::z was never set, so a flying ship was no farther from surface guns
  than one on the water, although range() is three-dimensional and fly_ship()
  already raised its hull object to z 4.  fly_ship() now puts the ship at
  SHIP_FLYING_ALTITUDE and land_ship() brings it back to 0, so every range to a
  flying ship includes the altitude, and a surface weapon whose reach is no
  more than that cannot hit it at all.
- ship.cargo/contraband.minPriceMod and maxPriceMod were read nowhere: the clamp
  in read_cargo() was commented out, with defaults that would have zeroed the
  market.  bound_market_mod() now keeps every modifier inside its band on load,
  after each trade and after each drift, and an unset bound does not clamp.
  The shipped cargo band is scaled to the 0.60 neutral point.  (The sails half,
  warship.sails.damage.reduction, is run in test_ship_damage_control.py.)

This runs the real range(), fly_ship(), land_ship(), bound_market_mod() and
adjust_ship_market().
"""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function, source
from contract_text import contains

FUNCTIONS = "\n\n".join(
    [
        extract_function("ship_utils.c", "float range(float x1, float y1, float z1, float x2,"),
        extract_function("ship_base.c", "void fly_ship(P_ship ship)"),
        extract_function("ship_base.c", "void land_ship(P_ship ship)"),
        extract_function("ship_cargo.c", "static float bound_market_mod(bool contraband, float modifier)"),
        extract_function("ship_cargo.c", "void adjust_ship_market(int transaction, int location,"),
    ]
)

HARNESS = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "ships/ships.h"

#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <map>
#include <string>

static room_data rooms[2] = {};
P_room world = rooms;
float ship_cargo_market_mod[NUM_PORTS][NUM_PORTS];
float ship_contra_market_mod[NUM_PORTS][NUM_PORTS];
static std::map<std::string, double> properties;
static int market_writes = 0;

float get_property(const char *name, double fallback)
{
	auto found = properties.find(name);
	return found == properties.end() ? fallback : found->second;
}
float BOUNDEDF(float low, float value, float high)
{
	return value < low ? low : value > high ? high : value;
}
int write_cargo()
{
	++market_writes;
	return TRUE;
}
void logit(const char *, const char *, ...) {}
int eq_levistone_slot(const ShipData *) { return 0; }
char *ShipSlot::get_description() { return const_cast<char *>("a levistone"); }
void act_to_all_in_ship(P_ship, const char *) {}
void act_to_all_in_ship_f(P_ship, const char *, ...) {}
void act_to_outside(P_ship, int, const char *, ...) {}
void act_to_outside_ships(P_ship, P_ship, int, const char *, ...) {}
void update_ship_status(P_ship, P_ship) {}

''' + FUNCTIONS + r'''

int main()
{
	// A ship takes off to SHIP_FLYING_ALTITUDE and lands back at 0.
	obj_data hull = {};
	ShipData ship = {};
	ship.shipobj = &hull;
	rooms[1].sector_type = SECT_OCEAN;
	ship.location = 1;
	fly_ship(&ship);
	assert(IS_SET(ship.flags, FLYING) && ship.z == SHIP_FLYING_ALTITUDE);
	land_ship(&ship);
	assert(!IS_SET(ship.flags, FLYING) && ship.z == 0);

	// Surface guns reach a flying ship over the altitude too: three squares
	// away is five, and nothing is closer than the altitude itself.
	assert(std::fabs(range(0, 0, 0, 3, 0, SHIP_FLYING_ALTITUDE) - 5.0f) < 1e-5f);
	assert(range(0, 0, 0, 0, 0, SHIP_FLYING_ALTITUDE) >= SHIP_FLYING_ALTITUDE);
	assert(range(0, 0, SHIP_FLYING_ALTITUDE, 3, 0, SHIP_FLYING_ALTITUDE) == 3.0f);

	// Unset bounds do not clamp, so an unconfigured market is left alone.
	assert(bound_market_mod(false, 0.2f) == 0.2f && bound_market_mod(true, 7.0f) == 7.0f);

	// Configured bands hold after trades in either direction.
	properties = { { "ship.cargo.minPriceMod", 0.9 },	  { "ship.cargo.maxPriceMod", 1.15 },
		       { "ship.contraband.minPriceMod", 0.85 }, { "ship.contraband.maxPriceMod", 1.3 },
		       { "ship.cargo.sellAdjustMod", 0.002 },  { "ship.cargo.buyAdjustMod", 0.001 },
		       { "ship.contraband.sellAdjustMod", 0.01 }, { "ship.contraband.buyAdjustMod", 0.003 } };
	ship_cargo_market_mod[1][2] = ship_contra_market_mod[1][2] = 1.0f;
	adjust_ship_market(SOLD_CARGO, 1, 2, 400); // 1.0 x 0.2 would be 0.2
	assert(ship_cargo_market_mod[1][2] == 0.9f);
	adjust_ship_market(BOUGHT_CARGO, 1, 2, 1000); // 0.9 x 2 would be 1.8
	assert(ship_cargo_market_mod[1][2] == 1.15f);
	adjust_ship_market(SOLD_CONTRA, 1, 2, 50);
	assert(ship_contra_market_mod[1][2] == 0.85f);
	adjust_ship_market(BOUGHT_CONTRA, 1, 2, 500);
	assert(ship_contra_market_mod[1][2] == 1.3f);
	// A small trade still moves the price inside the band.
	ship_cargo_market_mod[1][2] = 1.0f;
	adjust_ship_market(BOUGHT_CARGO, 1, 2, 10);
	assert(ship_cargo_market_mod[1][2] > 1.0f && ship_cargo_market_mod[1][2] < 1.15f);
	assert(market_writes == 5);

	puts("flying ships are at altitude, and cargo markets stay inside their bands");
	return 0;
}
'''

# Both load paths clamp too: SQL read_cargo() and the flat-file install.
cargo = source("ship_cargo.c").read_text(encoding="utf-8")
assert contains(cargo, "ship_cargo_market_mod[port_id][cargo_type] = bound_market_mod(false, modifier);")
assert contains(cargo, "ship_contra_market_mod[port_id][cargo_type] = bound_market_mod(true, modifier);")
assert contains(cargo, "bound_market_mod(false, record.cargo[index])")
assert contains(cargo, "bound_market_mod(true, record.contraband[index])")
drift = extract_function("ship_cargo.c", "static void adjust_cargo_market()")
assert contains(drift, "bound_market_mod(false, ship_cargo_market_mod[i][j])")
assert contains(drift, "bound_market_mod(true, ship_contra_market_mod[i][j])")
properties_text = (ROOT / "lib/duris.properties").read_text(encoding="utf-8")
# The cargo band is scaled to the 0.60 neutral point the cargo market drifts to,
# so enabling it does not reprice a settled market.
for line in ("ship.cargo.minPriceMod=0.540", "ship.cargo.maxPriceMod=0.690",
             "ship.cargo.sellPriceMod=0.600", "ship.cargo.buyPriceMod=0.600",
             "ship.contraband.minPriceMod=0.850", "ship.contraband.maxPriceMod=1.300",
             "warship.sails.damage.reduction=0.850"):
    assert f"\n{line}\n" in properties_text, line

with tempfile.TemporaryDirectory(prefix="duris-ship-altitude-") as directory:
    path = Path(directory)
    (path / "test.cpp").write_text(HARNESS, encoding="utf-8")
    subprocess.run(
        ["g++", "-std=c++20", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
         "-Isrc", "-Itests/async", "-I/usr/include/mysql",
         str(path / "test.cpp"), "-o", str(path / "test")],
        cwd=ROOT, check=True)
    subprocess.run([str(path / "test")], check=True)
