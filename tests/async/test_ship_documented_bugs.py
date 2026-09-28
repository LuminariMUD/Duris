#!/usr/bin/env python3
"""The ship bugs SHIPS.md listed as known issues are fixed.

Writing the ship documentation turned up a list of discrepancies.  These are
the code bugs among them, and how each is now pinned:

- The volley roll is 2d50 >= 100 - N, but players were shown N%.  They now see
  the roll's real chance, volley_hit_percent() (run here); combat is unchanged.
- find_ship_setup() with "any hull" could pick the disabled zone ship (run here).
- The coastline crash chance read ship->speed after zeroing it, so speed never
  mattered.
- The disembark "edge of the ship" test took the room slot from vnum % 10,
  which is meaningless for rooms handed out first-free from the pool.
- A ship sunk by a fleet lost only one ship's share of the frags.
- buy contraband never stacked onto the port's contraband already aboard.
- The contraband alignment gate compared > 1000, which alignment never reaches.
- The shipwright quoted twice the summon fee it charges.
- Ship.Info reported people as 0, maxSail as a constant, and status with
  colour codes.
- A ram target's own ram was sized from the rammer's hull.
- Stale comments: the diplomat, set_chief()'s command, and flying range.
- In-game help: arc widths, turning, the maneuver speed, repair weapon, the
  pasted prompts in "Ship cargo", and the missing "Ship npcs", "Ship Weapons"
  and "Toggle Shipmap" entries.
"""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function, source

HARNESS = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "ships/ships.h"
#include "ships/ship_npc.h"

#include <cassert>
#include <cstdio>

static int roll = 0;
int number(int, int) { return roll; }
const ShipTypeData ship_type_data[MAXSHIPCLASS] = {};
static NPCShipSetup npcShipSetup[] = {
	{ SH_DREADNOUGHT, 4, 25, nullptr },
	{ SH_ZONE_SHIP, 4, 25, nullptr },
	{ SH_DREADNOUGHT, 4, 25, nullptr },
};

''' + extract_function("ship_combat.c", "int volley_hit_percent(int hit_chance)") + "\n\n" + \
    extract_function("ship_npc.c", "NPCShipSetup *find_ship_setup(int level, int m_class, int speed)") + r'''

int main()
{
	// The shown chance is the 2d50 roll's: low chances hit less often, high
	// ones more often, than the raw figure.
	const int expected[][2] = { { 0, 0 },	{ 10, 3 },  { 20, 9 },	{ 30, 20 },
				    { 40, 34 }, { 50, 53 }, { 60, 70 }, { 70, 84 },
				    { 80, 93 }, { 90, 99 }, { 100, 100 } };
	for (const auto &pair : expected)
		assert(volley_hit_percent(pair[0]) == pair[1]);

	// "Any hull" never draws the zone ship, whatever the roll; asking for it
	// by class still finds it.
	for (roll = 0; roll < 3; roll++)
		assert(find_ship_setup(4, -1, -1)->m_class == SH_DREADNOUGHT);
	roll = 0;
	assert(find_ship_setup(4, SH_ZONE_SHIP, -1)->m_class == SH_ZONE_SHIP);

	puts("volley chances are shown truly and any-hull pirates are never the zone ship");
	return 0;
}
'''

base = source("ship_base.c").read_text(encoding="utf-8")
combat = source("ship_combat.c").read_text(encoding="utf-8")
shop = source("ship_shop.c").read_text(encoding="utf-8")
control = source("ship_control.c").read_text(encoding="utf-8")
utils = source("ship_utils.c").read_text(encoding="utf-8")
json_utils = source("json_utils.c").read_text(encoding="utf-8")

# The crash chance uses the speed the ship hit the coast at.
assert "const int impact_speed = ship->speed;" in base
crash = base[base.index("const int impact_speed = ship->speed;") :]
crash = crash[: crash.index("crash_land(ship);")]
assert crash.index("impact_speed = ship->speed") < crash.index("ship->speed = 0;")
assert "(float)(impact_speed +" in crash and "(float)(ship->speed +" not in crash

# Disembarking finds the room's slot by vnum.
room_proc = extract_function("ship_base.c", "int ship_room_proc(")
assert "i / 10" not in room_proc
assert "SHIP_ROOM_NUM(ship, j) != i" in room_proc

# The sunk ship loses the whole frag value, not one fleet member's share.
assert "frag_gain = frag_loss = calc_frag_gain(ship);" in combat
assert "ship_loss_on_sink(ship, attacker, frag_loss);" in combat
assert "frag_gain = frag_gain / fleet_size_total;" in combat

# A counter-ram is sized from the target's own ram.
assert "int counter_eram_dam = eq_ram_damage(target);" in combat

# Contraband stacks onto the port's contraband already aboard, then takes an
# empty slot; the alignment gate is reachable at the alignment cap.
buy_contra = extract_function("ship_shop.c", "int buy_contra(")
assert buy_contra.index("ship->slot[slot].type == SLOT_CONTRABAND && ship->slot[slot].index == rroom") < \
    buy_contra.index("ship->slot[slot].type == SLOT_EMPTY")
assert "GET_ALIGNMENT(ch) >= MINCONTRAALIGN" in buy_contra
assert "GET_ALIGNMENT(ch) < MINCONTRAALIGN" in shop

# The summons is quoted at what it costs.
assert shop.count("summon_ship_cost(ship)") == 2
assert "SHIPTYPE_HULL_WEIGHT(ship->m_class) * 100" not in shop

# Players are shown the true volley chance.
assert "volley_hit_percent(weaponsight(ship, slot, j, ch))" in control
assert "volley_hit_percent(hit_chance));" in combat

# Ship.Info fields.
assert 'cJSON_AddNumberToObject(root, "people", num_people_in_ship(ship));' in json_utils
assert 'cJSON_AddNumberToObject(root, "maxSail", SHIP_MAX_SAIL(ship));' in json_utils
assert 'strip_ansi(get_ship_status(ship)).c_str()' in json_utils

# Comments that described code that does not exist.
assert "legitimises" not in utils
assert '"setbit ship <owner> chief <n>"' in utils
assert "stay out of" not in utils

# In-game help.
helpships = (ROOT / "lib/information/helpships").read_text(encoding="utf-8")
assert "80 degree arcs" in helpships and "100 degree arcs" in helpships
assert "45 degree" not in helpships and "120 degree" not in helpships
assert "faster it turns" in helpships and "the slower they turn" not in helpships
assert "speed 20 or below to" in helpships
parsed = (ROOT / "help/duris_help_parsed.hlp").read_text(encoding="utf-8")
assert "Pos: standing" not in parsed
assert "Repair weapon <weapon number/all>" not in parsed
titles = [entry.strip().split("\n")[1].split(" - Last Edited:")[0].strip()
          for entry in parsed.split("\n#0\n") if len(entry.strip().split("\n")) > 1]
for title in ("Ship npcs", "Ship Weapons", "Toggle Shipmap"):
    assert titles.count(title) == 1, title

with tempfile.TemporaryDirectory(prefix="duris-ship-bugs-") as directory:
    path = Path(directory)
    (path / "test.cpp").write_text(HARNESS, encoding="utf-8")
    subprocess.run(
        ["g++", "-std=c++20", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
         "-Isrc", "-Itests/async", "-I/usr/include/mysql",
         str(path / "test.cpp"), "-o", str(path / "test")],
        cwd=ROOT, check=True)
    subprocess.run([str(path / "test")], check=True)
