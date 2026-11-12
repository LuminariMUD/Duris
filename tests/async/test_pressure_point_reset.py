#!/usr/bin/env python3
"""The Elaphidist pressure-point combo resets on its victim at stack six (#214).

Compiles the production monk_critic() under ASan/UBSan with affect storage,
damage and output controlled by the fixture. The tag lives on the victim, so the
sixth strike must remove it there, and the seventh strike starts a new combo.
"""

import os
import subprocess
import tempfile
from pathlib import Path

from _paths import HARNESS_STUBS, ROOT, extract_function, source

HARNESS = r'''
// INCLUDES
#include <cassert>
#include <cstdio>

static int damage_calls;

struct affected_type *get_spell_from_char(P_char ch, int spell, void *, int)
{
	for (affected_type *af = ch->affected; af; af = af->next)
		if (af->type == spell)
			return af;
	return nullptr;
}
struct affected_type *affect_to_char(P_char ch, struct affected_type *af)
{
	affected_type *copy = new affected_type(*af);
	copy->next = ch->affected;
	ch->affected = copy;
	return copy;
}
void affect_from_char(P_char ch, int spell)
{
	for (affected_type **link = &ch->affected; *link;)
	{
		if ((*link)->type == spell)
		{
			affected_type *gone = *link;
			*link = gone->next;
			delete gone;
		}
		else
			link = &(*link)->next;
	}
}
int melee_damage(P_char, P_char, double, int, struct damage_messages *, int *)
{
	damage_calls++;
	return DAM_NONEDEAD;
}
bool blind(P_char, P_char, int) { return true; }
void CharWait(P_char, int) {}
int dice(int, int) { return 0; }

// FUNCTIONS

static int stack(P_char victim)
{
	affected_type *af = get_spell_from_char(victim, TAG_PRESSURE_POINTS, nullptr, 0);
	return af ? af->modifier : 0;
}

int main()
{
	char_data monk{}, victim{};
	monk.specials.position = victim.specials.position = STAT_NORMAL | POS_STANDING;
	monk.player.m_class = CLASS_MONK;
	monk.player.spec = SPEC_WAYOFSNAKE;
	monk.player.name = victim.player.name = const_cast<char *>("fixture");
	victim.player.race = RACE_HUMAN;

	for (int strike = 1; strike <= 5; strike++)
	{
		monk_critic(&monk, &victim, nullptr);
		assert(stack(&victim) == strike);
	}
	assert(damage_calls == 1);

	monk_critic(&monk, &victim, nullptr);
	assert(stack(&victim) == 0);

	monk_critic(&monk, &victim, nullptr);
	assert(stack(&victim) == 1);

	affect_from_char(&victim, TAG_PRESSURE_POINTS);
	affect_from_char(&victim, SPELL_SLOW);
	std::puts("pressure points reset on the victim at stack six");
}
'''

fight = "combat/fight.c"
includes = "\n".join(line for line in source(fight).read_text().splitlines()
                     if line.startswith("#include"))
functions = "\n".join((extract_function("core/utility.c", "int GET_CLASS(P_char ch, uint m_class)"),
                       extract_function(fight, "bool monk_critic(P_char ch, P_char victim, int *damAccumulator)")))
(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="pressure-points-", dir=ROOT / "bin/tests") as tmp:
    harness = Path(tmp) / "pressure.cpp"
    harness.write_text(HARNESS.replace("// INCLUDES", includes).replace("// FUNCTIONS", functions))
    binary = harness.with_suffix("")
    subprocess.run(["g++", "-std=c++20", "-g", "-O1", "-fsanitize=address,undefined",
                    "-fno-omit-frame-pointer", "-ffunction-sections", "-fdata-sections",
                    "-Wl,--gc-sections", "-Isrc", "-I/usr/include/mysql", str(harness),
                    str(HARNESS_STUBS), "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, env=dict(os.environ,
        ASAN_OPTIONS="detect_leaks=1:halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1"))
