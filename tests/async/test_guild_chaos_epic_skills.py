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
#include "classes/paladins.h"
#include <cassert>
#include <cstdio>
#include <initializer_list>

Skill skills[MAX_AFFECT_TYPES + 1];
static bool chaos = false, curated = false;
int get_property(const char *, int fallback) { return fallback; }
bool chaos_mud_enabled(void) { return chaos; }
bool chaos_starter_epic_skills_enabled(void) { return curated; }
int GET_CLASS(P_char ch, uint cls) { return (ch->player.m_class & cls) != 0; }
int GET_LVL_FOR_SKILL(P_char ch, int skill) {
    if (skill == SKILL_RIFF) return ch->player.spec ? 30 : 0;
    return skill == SKILL_SMITE_EVIL ? 30 : 0;
}
int GET_CHAR_SKILL_P(P_char ch, int skill) { return ch->only.pc->skills[skill].learned; }
static bool smite_scheduled;
static int smite_starts;
void event_smite_evil(P_char, P_char, P_obj, void *) {}
P_nevent get_scheduled(P_char, event_func_type) { return smite_scheduled ? reinterpret_cast<P_nevent>(1) : nullptr; }
nevent_schedule_result add_event(event_func func, int, P_char, P_char, P_obj, int, const void *, int) {
    assert(func == event_smite_evil); smite_scheduled = true; ++smite_starts; return {};
}
ClassSkillInfo SKILL_DATA_ALL(P_char, int skill) {
    ClassSkillInfo result{};
    if (skill == SKILL_SMITE_EVIL) result.maxlearn[0] = 100;
    if (skill == SKILL_RIFF) result.maxlearn[1] = result.maxlearn[2] = result.maxlearn[3] = 100;
    return result;
}

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
    chaos = false; smite_scheduled = false; smite_starts = 0;
    pc_only_data pc{}; char_data ch{}; ch.only.pc = &pc; ch.in_room = 1;
    ch.player.level = 29; update_skills(&ch);
    assert(!smite_scheduled);
    ch.player.level = 30; update_skills(&ch);
    assert(smite_scheduled && smite_starts == 1);
    assert(GET_CHAR_SKILL(&ch, SKILL_SMITE_EVIL) > 0);
    update_skills(&ch); assert(smite_starts == 1);
    // Riff is retained while unspecialized, including repeated login updates.
    ch.player.m_class = CLASS_BARD; ch.player.level = 56; ch.player.spec = 1;
    pc.skills[SKILL_RIFF].learned = 87; pc.skills[SKILL_RIFF].taught = 100;
    update_skills(&ch);
    ch.player.spec = 0; update_skills(&ch); update_skills(&ch);
    assert(pc.skills[SKILL_RIFF].learned == 87 && pc.skills[SKILL_RIFF].taught == 100);
    for (int spec : {1, 2, 3}) {
        ch.player.spec = spec; update_skills(&ch);
        assert(pc.skills[SKILL_RIFF].learned == 87 && pc.skills[SKILL_RIFF].taught == 100);
    }
    ch.player.spec = 0; pc.skills[SKILL_RIFF] = {}; update_skills(&ch);
    assert(pc.skills[SKILL_RIFF].learned == 0 && pc.skills[SKILL_RIFF].taught == 0);
    ch.player.secondary_class = CLASS_ROGUE; update_skills(&ch);
    assert(pc.skills[SKILL_RIFF].learned == 0 && pc.skills[SKILL_RIFF].taught == 0);
	std::puts("CHAOS epic skills: the guild fills them only when the curated grant is off");
}
'''

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="guild-chaos-epic-", dir=ROOT / "bin/tests") as build:
    source = Path(build) / "harness.cpp"
    binary = Path(build) / "harness"
    source.write_text(HARNESS.replace(
        "// PRODUCTION", extract_function("paladins.c", "int smite_evil_interval()") + extract_function("guild.c", "void update_skills(P_char ch)")))
    subprocess.run(["g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-Isrc", str(source), str(HARNESS_STUBS),
                    "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
