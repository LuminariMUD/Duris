#!/usr/bin/env python3
"""Execute the shared item-proc event guards and one converted callback each.

melee_proc_target() and defense_proc_data() are compiled from specs.object.c with
mace_of_sea (melee) and generic_parry_proc (CMD_GOTHIT), so the test covers both
the guard contracts and their wiring into real callbacks.
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
#include "world/specs.prototypes.h"
#include <cassert>
#include <cstdio>

static int roll, acts, spells;
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
	roll = acts = spells = 0;
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

	puts("item proc guards: melee and defensive contracts and wiring passed");
}
'''


def main():
    production = "\n".join(extract_function("specs.object.c", signature) for signature in (
        "P_char melee_proc_target(",
        "struct proc_data *defense_proc_data(",
        "int mace_of_sea(",
        "int generic_parry_proc(",
    ))
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
