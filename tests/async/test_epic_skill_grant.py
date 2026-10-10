#!/usr/bin/env python3
"""The epic skills a CHAOS starter gets without specializing, and the rules that pick them.

Runs the production grant_epic_skills_without_specialization() and its eligibility check
from src/classes/epic_skills.c over small reward and teacher tables: a specialized or
non-player character gets none; every epic skill is first cleared; a skill goes only to a
class (or secondary class) its reward names, never past a denying skill or below its
prerequisite's level, and never to a thri-kreen as devastating critical; and each granted
skill is learned and taught at its teacher's maximum, at most 100.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import HARNESS_STUBS, ROOT, SRC

source = (SRC / "epic_skills.c").read_text()
start = source.index("namespace\n{\nconst epic_teacher_skill *find_epic_teacher_for_skill")
end = source.index("void create_epic_skills()", start)
PRODUCTION = source[start:end]

HARNESS = r'''
#include "core/structs.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "classes/epic_skills.h"
#include "magic/spells.h"
#include "world/epic.h"
#include <cassert>
#include <cstdio>

Skill skills[MAX_AFFECT_TYPES + 1];
int GET_CHAR_SKILL_P(P_char ch, int skill)
{
	return ch->only.pc->skills[skill].learned;
}
int BOUNDED(int low, int value, int high)
{
	return value < low ? low : value > high ? high : value;
}

epic_reward epic_rewards[] = {
	{ EPIC_REWARD_SKILL, SKILL_ANATOMY, 0, 0, 0, CLASS_WARRIOR },
	{ EPIC_REWARD_SKILL, SKILL_CHANT_MASTERY, 0, 0, 0, CLASS_SORCERER },
	{ EPIC_REWARD_SKILL, SKILL_DEVASTATING_CRITICAL, 0, 0, 0, CLASS_WARRIOR },
	{ EPIC_REWARD_SKILL, SKILL_SUMMON_BLIZZARD, 0, 0, 0, 0 },
	{ EPIC_REWARD_SKILL, SKILL_SNEAKY_STRIKE, 0, 0, 0, 0 },
	{}
};
epic_teacher_skill epic_teachers[] = {
	{ 1, SKILL_ANATOMY, 0, 80, 0, 0, 0 },
	{ 2, SKILL_CHANT_MASTERY, 0, 100, 0, 0, 0 },
	{ 3, SKILL_DEVASTATING_CRITICAL, 0, 150, 0, 0, 0 },
	// Denied to whoever knows chant mastery.
	{ 4, SKILL_SUMMON_BLIZZARD, 0, 100, 0, SKILL_CHANT_MASTERY, 0 },
	// Needs anatomy at 50.
	{ 5, SKILL_SNEAKY_STRIKE, 0, 60, SKILL_ANATOMY, 0, 50 },
	{}
};

// PRODUCTION

static int learned(P_char ch, int skill)
{
	return ch->only.pc->skills[skill].learned;
}

int main()
{
	for (int skill : { SKILL_ANATOMY, SKILL_CHANT_MASTERY, SKILL_DEVASTATING_CRITICAL,
			   SKILL_SUMMON_BLIZZARD, SKILL_SNEAKY_STRIKE, SKILL_MINE })
		skills[skill].targets = TAR_EPIC;

	pc_only_data pc{};
	char_data ch{};
	ch.only.pc = &pc;
	ch.player.m_class = CLASS_WARRIOR;
	ch.player.race = RACE_HUMAN;
	pc.skills[SKILL_MINE].learned = pc.skills[SKILL_MINE].taught = 40;

	// A warrior: anatomy at its teacher's 80, devastating critical capped at 100, summon
	// blizzard (any class), and sneaky strike, whose anatomy prerequisite the grant met
	// just before; no chant mastery. Every other epic skill is cleared first.
	assert(grant_epic_skills_without_specialization(&ch) == 4);
	assert(learned(&ch, SKILL_ANATOMY) == 80 && pc.skills[SKILL_ANATOMY].taught == 80);
	assert(learned(&ch, SKILL_DEVASTATING_CRITICAL) == 100);
	assert(learned(&ch, SKILL_SUMMON_BLIZZARD) == 100 && learned(&ch, SKILL_SNEAKY_STRIKE) == 60);
	assert(learned(&ch, SKILL_CHANT_MASTERY) == 0);
	assert(learned(&ch, SKILL_MINE) == 0 && pc.skills[SKILL_MINE].taught == 0);

	// With a sorcerer's secondary class: chant mastery, which then denies summon blizzard.
	ch.player.secondary_class = CLASS_SORCERER;
	assert(grant_epic_skills_without_specialization(&ch) == 4);
	assert(learned(&ch, SKILL_CHANT_MASTERY) == 100 && learned(&ch, SKILL_SUMMON_BLIZZARD) == 0);

	// A sorcerer: chant mastery alone. No warrior skill, blizzard denied, and sneaky strike
	// below its prerequisite.
	ch.player.m_class = CLASS_SORCERER;
	ch.player.secondary_class = 0;
	assert(grant_epic_skills_without_specialization(&ch) == 1);
	assert(learned(&ch, SKILL_CHANT_MASTERY) == 100 && learned(&ch, SKILL_ANATOMY) == 0);
	assert(learned(&ch, SKILL_SNEAKY_STRIKE) == 0 && learned(&ch, SKILL_SUMMON_BLIZZARD) == 0);

	// A thri-kreen warrior gets no devastating critical.
	ch.player.m_class = CLASS_WARRIOR;
	ch.player.race = RACE_THRIKREEN;
	assert(grant_epic_skills_without_specialization(&ch) == 3);
	assert(learned(&ch, SKILL_DEVASTATING_CRITICAL) == 0);

	// A specialized character gets nothing, and keeps what it had.
	ch.player.spec = 1;
	assert(grant_epic_skills_without_specialization(&ch) == 0);
	assert(learned(&ch, SKILL_ANATOMY) == 80);
	std::puts("epic skills without specialization go by class, denial, prerequisite and cap");
}
'''

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="epic-skill-grant-", dir=ROOT / "bin/tests") as build:
    harness = Path(build) / "harness.cpp"
    binary = Path(build) / "harness"
    harness.write_text(HARNESS.replace("// PRODUCTION", PRODUCTION))
    subprocess.run(["g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-Isrc", str(harness), str(HARNESS_STUBS),
                    "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
