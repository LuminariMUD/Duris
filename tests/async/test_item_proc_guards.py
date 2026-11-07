#!/usr/bin/env python3
"""Execute the shared item-proc helpers and one converted callback each.

The event guards, act_trio, periodic_stoneskin and the spell deflection selector
are compiled from source with mace_of_sea (melee), generic_parry_proc (CMD_GOTHIT)
and elvenkind_cloak (CMD_GOTNUKED), so the test covers the helper contracts and
their wiring into real callbacks.
"""

from pathlib import Path
import os
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "cmd/interp.h"
#include "magic/spells.h"
#include "net/comm.h"
#include "combat/damage.h"
#include "world/specs.prototypes.h"
#include <cassert>
#include <cstdio>

static room_data rooms[1]{};
P_room world = rooms;
static int roll, acts, spells, skins;
static bool skinned;
static P_char damaged;
bool has_skin_spell(P_char) { return skinned; }
void spell_stone_skin(int, P_char, char *, int, P_char, P_obj) { ++skins; }
int spell_damage(P_char, P_char vict, double, int, uint, struct damage_messages *, int *)
{
	damaged = vict;
	return 0;
}
int number(int low, int) { return roll >= low ? roll : low; }
void act(const char *, int, P_char, P_obj, void *, int) { ++acts; }
void spell_dread_wave(int, P_char, char *, int, P_char, P_obj) { ++spells; }
'''

DRIVER = r'''
static char_data wearer, victim, other;
static obj_data item;

static void reset()
{
	wearer = char_data{}; victim = char_data{}; other = char_data{}; item = obj_data{};
	for (P_char ch : {&wearer, &victim, &other})
		SET_POS(ch, POS_STANDING + STAT_NORMAL);
	item.loc_p = LOC_WORN;
	item.loc.wearing = &wearer;
	roll = acts = spells = skins = 0;
	skinned = false;
	damaged = nullptr;
}

static char *payload(void *p) { return static_cast<char *>(p); }

int main()
{
	reset();
	assert(melee_proc_target(&item, &wearer, CMD_MELEE_HIT, payload(&victim)) == &victim);
	assert(!melee_proc_target(&item, &wearer, CMD_GOTHIT, payload(&victim)));
	assert(!melee_proc_target(&item, &wearer, CMD_SET_PERIODIC, nullptr));
	assert(!melee_proc_target(&item, &wearer, CMD_MELEE_HIT, nullptr));
	assert(!melee_proc_target(&item, &other, CMD_MELEE_HIT, payload(&victim)));
	SET_POS(&victim, POS_PRONE + STAT_DEAD);
	assert(!melee_proc_target(&item, &wearer, CMD_MELEE_HIT, payload(&victim)));
	reset();
	SET_POS(&wearer, POS_PRONE + STAT_DEAD);
	assert(!melee_proc_target(&item, &wearer, CMD_MELEE_HIT, payload(&victim)));
	reset();
	item.loc_p = LOC_CARRIED;
	assert(!melee_proc_target(&item, &wearer, CMD_MELEE_HIT, payload(&victim)));

	reset();
	proc_data data{};
	data.victim = &other;
	assert(defense_proc_data(&item, &wearer, CMD_GOTHIT, CMD_GOTHIT, payload(&data)) == &data);
	assert(defense_proc_data(&item, &wearer, CMD_GOTNUKED, CMD_GOTNUKED, payload(&data)) == &data);
	assert(!defense_proc_data(&item, &wearer, CMD_GOTNUKED, CMD_GOTHIT, payload(&data)));
	assert(!defense_proc_data(&item, &wearer, CMD_GOTHIT, CMD_GOTHIT, nullptr));
	assert(!defense_proc_data(&item, &other, CMD_GOTHIT, CMD_GOTHIT, payload(&data)));

	// mace_of_sea: 1/30 on a melee hit, nothing on other events.
	reset();
	assert(mace_of_sea(&item, &wearer, CMD_MELEE_HIT, payload(&victim)) && spells == 1);
	reset();
	roll = 1;
	assert(!mace_of_sea(&item, &wearer, CMD_MELEE_HIT, payload(&victim)) && !spells);
	reset();
	assert(!mace_of_sea(&item, &wearer, CMD_SET_PERIODIC, nullptr) && !spells);

	// generic_parry_proc: 1/20 on CMD_GOTHIT stops the attack; melee hits are ignored.
	reset();
	assert(generic_parry_proc(&item, &wearer, CMD_GOTHIT, payload(&data)) && acts == 3);
	reset();
	roll = 1;
	assert(!generic_parry_proc(&item, &wearer, CMD_GOTHIT, payload(&data)) && !acts);
	reset();
	assert(!generic_parry_proc(&item, &wearer, CMD_MELEE_HIT, payload(&victim)) && !acts);

	// periodic_stoneskin: casts once per interval, never over another skin spell.
	reset();
	assert(periodic_stoneskin(&item, &wearer, 30, 60) && skins == 1 && item.timer[0]);
	assert(!periodic_stoneskin(&item, &wearer, 30, 60) && skins == 1);
	item.timer[0] = 0;
	skinned = true;
	assert(!periodic_stoneskin(&item, &wearer, 30, 60) && skins == 1);

	// elvenkind_cloak: 1/4 on CMD_GOTNUKED redirects to a uniformly chosen mortal
	// bystander, skipping the wearer and staff; nothing without a bystander.
	static char_data staff, second;
	reset();
	staff = char_data{};
	second = char_data{};
	for (P_char p : {&staff, &second})
		SET_POS(p, POS_STANDING + STAT_NORMAL);
	staff.player.level = MAXLVLMORTAL + 1;
	rooms[0].people = &wearer;
	wearer.next_in_room = &staff;
	staff.next_in_room = &other;
	other.next_in_room = &second;
	data.victim = &victim;
	roll = 0;
	assert(elvenkind_cloak(&item, &wearer, CMD_GOTNUKED, payload(&data)) && damaged == &other);
	damaged = nullptr;
	roll = 1;
	assert(!elvenkind_cloak(&item, &wearer, CMD_GOTNUKED, payload(&data)) && !damaged);
	other.next_in_room = nullptr;
	staff.next_in_room = &second;
	second.next_in_room = &other;
	roll = 0;
	assert(elvenkind_cloak(&item, &wearer, CMD_GOTNUKED, payload(&data)) && damaged == &second);
	wearer.next_in_room = &staff;
	staff.next_in_room = nullptr;
	damaged = nullptr;
	assert(!elvenkind_cloak(&item, &wearer, CMD_GOTNUKED, payload(&data)) && !damaged);

	puts("item proc helpers: guards, stoneskin and deflection contracts and wiring passed");
}
'''


def main():
    production = extract_function("comm.c", "void act_trio(") + "\n".join(extract_function("specs.object.c", signature) for signature in (
        "P_char melee_proc_target(",
        "struct proc_data *defense_proc_data(",
        "int mace_of_sea(",
        "int generic_parry_proc(",
        "bool periodic_stoneskin(",
    )) + extract_function("specs.underworld.c", "static bool deflect_spell(") \
        + extract_function("specs.underworld.c", "int elvenkind_cloak(")
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="item-proc-guards-", dir=build) as directory:
        cpp, binary = Path(directory) / "harness.cpp", Path(directory) / "harness"
        cpp.write_text(PRELUDE + production + DRIVER)
        subprocess.run([
            "g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
            "-Wno-unused-parameter", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
            "-fno-pie", "-no-pie", "-ffunction-sections", "-fdata-sections",
            "-I" + str(ROOT / "src"), str(cpp), str(HARNESS_STUBS), "-Wl,--gc-sections",
            "-o", str(binary),
        ], check=True)
        subprocess.run([str(binary)], check=True, env={**os.environ,
            "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1",
            "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1"})


if __name__ == "__main__":
    main()
