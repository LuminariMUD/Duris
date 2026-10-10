#!/usr/bin/env python3
"""In CHAOS mode, update_skills() fills the epic skills only when the curated grant is off.

Runs the production update_skills() from src/guild/guild.c. With CHAOS_STARTER_EPIC_SKILLS
on, a CHAOS character's epic skills come from the curated grant at entry, so the guild
leaves them as they are; with it off, the legacy path sets every epic skill to 100. Outside
CHAOS mode the guild never touches them.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import HARNESS_STUBS, ROOT, extract_function

HARNESS = r'''
#include "core/structs.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "combat/chaos_config.h"
#include "magic/spells.h"
#include <cassert>
#include <cstdio>

Skill skills[MAX_AFFECT_TYPES + 1];
static bool chaos = false, curated = false;
bool chaos_mud_enabled(void) { return chaos; }
bool chaos_starter_epic_skills_enabled(void) { return curated; }
int GET_LVL_FOR_SKILL(P_char, int) { return 0; }
ClassSkillInfo SKILL_DATA_ALL(P_char, int) { return {}; }

// PRODUCTION

static int epic_after(bool chaos_mode, bool curated_grant)
{
	chaos = chaos_mode;
	curated = curated_grant;
	pc_only_data pc{};
	char_data ch{};
	ch.only.pc = &pc;
	ch.player.level = 30;
	pc.skills[SKILL_ANATOMY].learned = pc.skills[SKILL_ANATOMY].taught = 25;
	update_skills(&ch);
	assert(pc.skills[SKILL_ANATOMY].taught == pc.skills[SKILL_ANATOMY].learned);
	return pc.skills[SKILL_ANATOMY].learned;
}

int main()
{
	skills[SKILL_ANATOMY].targets = TAR_EPIC;
	assert(epic_after(true, false) == 100);
	assert(epic_after(true, true) == 25);
	assert(epic_after(false, false) == 25);
	std::puts("CHAOS epic skills: the guild fills them only when the curated grant is off");
}
'''

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="guild-chaos-epic-", dir=ROOT / "bin/tests") as build:
    source = Path(build) / "harness.cpp"
    binary = Path(build) / "harness"
    source.write_text(HARNESS.replace(
        "// PRODUCTION", extract_function("guild.c", "void update_skills(P_char ch)")))
    subprocess.run(["g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-Isrc", str(source), str(HARNESS_STUBS),
                    "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
