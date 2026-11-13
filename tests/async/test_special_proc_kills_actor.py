#!/usr/bin/env python3
"""special() stops when a proc kills the character whose command it is handling.

Some procs kill or extract the actor and still return FALSE: Charon (mob 60008)
die()s its opponent, exit traps (trap_razor_hooks, shabo_trap_up_two,
huntsman_ward) damage the mover. special() then kept offering the command to
the remaining procs and indexed world[ch->in_room] with in_room == NOWHERE, and
command_interpreter() went on to run the command for the dead character.

Compiles the production special() under ASan/UBSan with a world array allocated
as db.c does and a mob proc that extracts the actor the way die() does.
"""

import os
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function

HARNESS = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "world/outposts.h"
#include <cassert>
#include <cstdio>

P_room world;
P_index obj_index, mob_index;
int top_of_world = 1;
bool training_dummy_is(P_char) { return false; }
bool affected_by_spell(P_char, int) { return false; }
int panic_corruption_int(const char *, const char *, ...) { __builtin_trap(); }

static int later_procs;
// Like Charon: kills the actor (die() -> extract_char -> char_from_room), returns FALSE.
static int killer(P_char, P_char actor, int, char *)
{
	actor->specials.position = POS_STANDING + STAT_DEAD;
	world[1].people = actor->next_in_room;
	actor->next_in_room = nullptr;
	actor->in_room = NOWHERE;
	return FALSE;
}
static int bystander(P_char, P_char, int, char *)
{
	later_procs++;
	return FALSE;
}

// FUNCTIONS

int main()
{
	world = new room_data[2]{}; // a heap array, as db.c allocates it
	mob_index = new index_data[2]{};
	mob_index[0].func.mob = killer;
	mob_index[1].func.mob = bystander;
	static npc_only_data killer_npc{}, bystander_npc{};
	killer_npc.R_num = 0;
	bystander_npc.R_num = 1;

	char_data actor{}, mob{}, other{};
	for (P_char ch : { &actor, &mob, &other })
	{
		ch->in_room = 1;
		ch->specials.position = POS_STANDING + STAT_NORMAL;
	}
	mob.specials.act = other.specials.act = ACT_ISNPC;
	mob.only.npc = &killer_npc;
	other.only.npc = &bystander_npc;
	world[1].people = &actor;
	actor.next_in_room = &mob;
	mob.next_in_room = &other;

	char arg[] = "";
	assert(special(&actor, 1, arg)); // handled: the command must not run for the dead actor
	assert(later_procs == 0);
	delete[] world;
	delete[] mob_index;
	std::puts("special() stops when a proc kills the actor");
}
'''

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="special-proc-death-", dir=ROOT / "bin/tests") as tmp:
    source = Path(tmp) / "special.cpp"
    source.write_text(HARNESS.replace(
        "// FUNCTIONS", extract_function("cmd/interp.c", "bool special(P_char ch, int cmd, char *arg)")))
    binary = source.with_suffix("")
    subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-fsanitize=address,undefined",
                    "-fno-sanitize-recover=undefined", "-fno-omit-frame-pointer",
                    "-Isrc", "-I/usr/include/mysql", str(source), "-o", str(binary)],
                   cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, env=dict(os.environ,
        ASAN_OPTIONS="detect_leaks=1:halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1"))
