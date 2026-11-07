#!/usr/bin/env python3
"""Item procs must not parse a combat payload as command text.

A melee hit carries a P_char and CMD_GOTHIT carries a proc_data *. Before the
fix, ring_of_regeneration ran one_argument() over any payload, and
deathseeker_mace resolved its melee target through ParseTarget(), reading the
payload's bytes as a name. Run both with binary payloads under ASan.

gauntlets_legend's periodic procs read no payload: periodic events carry no
actor, so they act on the wearer, and its heal casts stoneskin on that wearer.
"""

from pathlib import Path
import os
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function

SPELLS = ("biofeedback cannibalize clairvoyance combat_mind curse dispel_magic "
          "energy_drain fear full_harm greater_soul_disturbance invigorate lifelust "
          "prot_from_undead shadow_shield vitality wither nonexistence accel_healing dispel_evil "
          "dispel_good endurance group_heal soulshield").split()

PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "cmd/interp.h"
#include "magic/spells.h"
#include "net/comm.h"
#include "world/specs.prototypes.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>

static room_data rooms[1]{};
P_room world = rooms;
static int roll = 1;
static P_char stoneskinned;
void spell_stone_skin(int, P_char, char *, int, P_char victim, P_obj) { stoneskinned = victim; }
static P_char healed;
void spell_heal(int, P_char, char *, int, P_char victim, P_obj) { healed = victim; }
void spell_cure_critic(int, P_char, char *, int, P_char victim, P_obj) { healed = victim; }
bool has_skin_spell(P_char) { return false; }
void cast_as_area(P_char, int, int, char *) {}
int number(int low, int) { return roll >= low ? roll : low; }
void act(const char *, int, P_char, P_obj, void *, int) {}
int fill_word(char *) { return 0; }
P_char ParseTarget(P_char, char *) { std::abort(); }
P_char get_char_vis(P_char, const char *) { return nullptr; }
void half_chop(char *, char *first, char *second) { *first = *second = '\0'; }
bool isname(const char *, const char *) { return false; }
void hummer(P_obj) {}
bool damage(P_char, P_char, double, int) { return false; }
int get_property(const char *, int fallback) { return fallback; }
void set_obj_extra_flags(P_obj obj, unsigned int flags) { obj->extra_flags = flags; }
''' + "".join(f"void spell_{name}(int, P_char, char *, int, P_char, P_obj) {{}}\n" for name in SPELLS)

DRIVER = r'''
int main()
{
	static char_data wearer, victim;
	static obj_data ring, mace;
	for (P_char ch : {&wearer, &victim})
		SET_POS(ch, POS_STANDING + STAT_NORMAL);
	ring.loc_p = mace.loc_p = LOC_WORN;
	ring.loc.wearing = mace.loc.wearing = &wearer;
	wearer.equipment[WEAR_FINGER_R] = &ring;
	wearer.equipment[WIELD] = &mace;

	// A proc_data with no zero byte: parsing it as text overruns the allocation.
	auto *data = static_cast<proc_data *>(malloc(sizeof(proc_data)));
	memset(static_cast<void *>(data), 'A', sizeof(proc_data));
	char *gothit = reinterpret_cast<char *>(data);
	char *hit = reinterpret_cast<char *>(&victim);

	assert(!ring_of_regeneration(&ring, &wearer, CMD_GOTHIT, gothit));
	assert(!ring_of_regeneration(&ring, &wearer, CMD_MELEE_HIT, hit));
	assert(!deathseeker_mace(&mace, &wearer, CMD_GOTHIT, gothit));
	assert(!deathseeker_mace(&mace, &wearer, CMD_MELEE_HIT, hit));

	// The rub command still works.
	ring.extra_flags = ITEM_GLOW;
	char rub[] = "ring";
	assert(ring_of_regeneration(&ring, &wearer, CMD_RUB, rub) && !(ring.extra_flags & ITEM_GLOW));
	free(data);

	// Periodic ticks act on the wearer: the 1-in-10 combat proc while fighting,
	// otherwise the 3-minute stoneskin, cast on the wearer.
	static obj_data gauntlets;
	gauntlets.loc_p = LOC_WORN;
	gauntlets.loc.wearing = &wearer;
	wearer.equipment[WEAR_HANDS] = &gauntlets;
	GET_MAX_HIT(&wearer) = GET_MAX_HIT(&victim) = 100;
	GET_HIT(&wearer) = 10;
	GET_HIT(&victim) = 20;
	wearer.specials.fighting = &victim;
	roll = 0;
	assert(gauntlets_legend(&gauntlets, nullptr, CMD_PERIODIC, nullptr));
	assert(GET_HIT(&wearer) == 22 && GET_HIT(&victim) == 16 && !stoneskinned);
	wearer.specials.fighting = nullptr;
	assert(gauntlets_legend(&gauntlets, nullptr, CMD_PERIODIC, nullptr));
	assert(stoneskinned == &wearer);

	// The same periodic rule revives deathseeker_mace's and buckler_saints' heals.
	healed = nullptr;
	assert(deathseeker_mace(&mace, nullptr, CMD_PERIODIC, nullptr) && healed == &wearer);
	static obj_data buckler;
	buckler.loc_p = LOC_WORN;
	buckler.loc.wearing = &wearer;
	wearer.equipment[WEAR_SHIELD] = &buckler;
	healed = nullptr;
	assert(buckler_saints(&buckler, nullptr, CMD_PERIODIC, nullptr) && healed == &wearer);
	puts("item proc payloads: combat payloads are not parsed as text");
}
'''


def main():
    production = "\n".join([
        extract_function("interp.c", "char *one_argument("),
        extract_function("comm.c", "void act_trio("),
        extract_function("specs.object.c", "P_char melee_proc_target("),
        extract_function("specs.object.c", "struct proc_data *defense_proc_data("),
        extract_function("specs.object.c", "int ring_of_regeneration("),
        extract_function("specs.winterhaven.c", "int deathseeker_mace("),
        extract_function("specs.winterhaven.c", "int gauntlets_legend("),
        extract_function("specs.winterhaven.c", "int buckler_saints("),
    ])
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="item-proc-payloads-", dir=build) as directory:
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
