#!/usr/bin/env python3
"""Prismatic and color spray stop once a ray kills their caster.

A ray's spell_damage() can be deflected or arcane-riposted back onto the caster
and kill them. Prismatic spray then fired its next ray, whose resists_spell()
read GET_CHAR_SKILL(caster) through the only.pc that free_char() had already
released, and color spray asked should_area_hit() about the next target with
the dead caster's in_room at NOWHERE. should_area_hit() also read the victim's
room before rejecting a dead victim, so an extracted victim indexed world[-1].

Compiles the production spell_prismatic_spray(), spell_color_spray() and
should_area_hit() under ASan/UBSan with a world array allocated as db.c does
and a ray that kills the caster the way extract_char() does.
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import HARNESS_STUBS, ROOT, extract_function, source

HARNESS = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "abilities/abilities.h"
#include "net/comm.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>

P_room world;
int number(int, int to) { return to; }
int dice(int, int) { return 0; }
const Rolls live_rolls = { dice, number };
int is_char_in_room(const P_char ch, int room) { return ch->in_room == room; }
void zone_spellmessage(int, bool, const char *, const char *) {}
// The fixture's targets are all fighting the caster, so should_area_hit() returns early.
bool AdjacentInRoom(P_char, P_char) { std::abort(); }
struct affected_type *get_spell_from_char(P_char, int, void *, int) { std::abort(); }
void affect_remove(P_char, struct affected_type *) { std::abort(); }
bool grouped(P_char, P_char) { std::abort(); }
P_char get_linking_char(P_char, int) { std::abort(); }
int IS_MORPH(P_char) { std::abort(); }

static int rays, skill_reads;
// extract_char() -> free_char(): out of the room, only.pc released, marked dead.
static void extract(P_char ch)
{
	world[ch->in_room].people = ch->next_in_room;
	ch->next_in_room = nullptr;
	ch->in_room = NOWHERE;
	ch->only.pc = nullptr;
	ch->specials.position = POS_STANDING + STAT_DEAD;
}
// Each ray resists through GET_CHAR_SKILL(caster); the first is deflected and kills the caster.
void spell_single_prismatic_ray(int, P_char ch, char *, int, P_char, P_obj)
{
	rays++;
	skill_reads += ch->only.pc->skills[SKILL_SPELL_PENETRATION].learned;
	if (rays == 1)
		extract(ch);
}

// FUNCTIONS

typedef void spell_fn(int, P_char, char *, int, P_char, P_obj);

static void cast_until_caster_dies(spell_fn *spell)
{
	static pc_only_data caster_pc;
	char_data caster{}, first{}, second{};
	for (P_char ch : { &caster, &first, &second })
	{
		ch->in_room = 1;
		ch->specials.position = POS_STANDING + STAT_NORMAL;
		ch->specials.fighting = &caster;
	}
	caster.specials.fighting = &first;
	caster.only.pc = &caster_pc;
	world[1].people = &caster;
	caster.next_in_room = &first;
	first.next_in_room = &second;

	rays = 0;
	spell(50, &caster, nullptr, 0, nullptr, nullptr);
	assert(rays == 1);
}

int main()
{
	world = new room_data[2]{}; // a heap array, as db.c allocates it
	cast_until_caster_dies(spell_prismatic_spray);
	cast_until_caster_dies(spell_color_spray);

	char_data caster{}, corpse{};
	caster.in_room = 1;
	caster.specials.position = POS_STANDING + STAT_NORMAL;
	corpse.in_room = NOWHERE;
	corpse.specials.position = POS_STANDING + STAT_DEAD;
	assert(!should_area_hit(&caster, &corpse));

	delete[] world;
	std::puts("area sprays stop when their caster dies; dead victims are rejected first");
}
'''

magic = source("magic/magic.c").read_text()
functions = "\n".join((
    re.search(r"^#define RAY_COUNT .*$", magic, re.M).group(0),
    extract_function("magic/magic.c", "static int prismatic_spray_rays(const Rolls &rolls)"),
    extract_function("magic/magic.c", "void spell_color_spray(int level, P_char ch,"),
    extract_function("magic/magic.c", "void spell_prismatic_spray(int level, P_char ch,"),
    extract_function("core/utility.c", "static bool should_area_hit_with_position("),
    extract_function("core/utility.c", "bool should_area_hit(P_char ch, P_char victim)"),
))
(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="caster-death-", dir=ROOT / "bin/tests") as tmp:
    harness = Path(tmp) / "caster_death.cpp"
    harness.write_text(HARNESS.replace("// FUNCTIONS", functions))
    binary = harness.with_suffix("")
    subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-fsanitize=address,undefined",
                    "-fno-sanitize-recover=undefined", "-fno-omit-frame-pointer",
                    "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections", "-Isrc",
                    "-I/usr/include/mysql", str(harness), str(HARNESS_STUBS), "-o", str(binary)],
                   cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, env=dict(os.environ,
        ASAN_OPTIONS="detect_leaks=1:halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1"))
