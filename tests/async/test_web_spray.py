#!/usr/bin/env python3
"""Source-contract checks for the drider Web Spray innate."""
import re
import sys

from _paths import SRC
from contract_text import contains


def check(name, ok):
	if not ok:
		print(f"FAIL: {name}")
	return bool(ok)


structs = (SRC / "structs.h").read_text()
spells = (SRC / "spells.h").read_text()
skills = (SRC / "skills.c").read_text()
innates = (SRC / "innates.c").read_text()

body = re.search(r"void do_web_spray\(P_char ch.*?\n}\n", innates, re.S)
body = body.group(0) if body else ""
event = re.search(r"void event_web_spray\(.*?\n}\n", innates, re.S)
event = event.group(0) if event else ""

all_ok = True
all_ok &= check("INNATE_WEB_SPRAY is the last innate",
	contains(structs, "#define INNATE_WEB_SPRAY 178") and
	contains(structs, "#define LAST_INNATE INNATE_WEB_SPRAY"))
all_ok &= check("web spray tag defined and named",
	contains(spells, "#define TAG_WEB_SPRAY 2127") and
	contains(skills, 'TAG_CREATE_WITH_MESSAGES("web spray", TAG_WEB_SPRAY,'))
all_ok &= check("innates_data entry is the last one",
	contains(innates, '{ "web spray", do_web_spray },\n};'))
all_ok &= check("driders get it at level 31",
	contains(innates, "ADD_RACIAL_INNATE(INNATE_WEB_SPRAY, RACE_DRIDER, 31);"))

all_ok &= check("target validated before the cooldown is spent",
	0 < body.find("CanDoFightMove(ch, victim)") < body.find("check_innate_time("))
all_ok &= check("5 minute cooldown",
	contains(body, "check_innate_time(ch, INNATE_WEB_SPRAY, 300)"))
all_ok &= check("freedom of movement and evade block it",
	contains(body, "check_freedom_of_movement(victim,") and
	contains(body, "GET_CHAR_SKILL(victim, SKILL_EVADE)"))
all_ok &= check("tackle-style roll with level * 1.5 base",
	contains(body, "chance = GET_LEVEL(ch) * 1.5;") and
	contains(body, "chance = .70 * chance +") and
	contains(body, "chance = BOUNDED(5, chance, 90);"))
all_ok &= check("lasts 30 seconds",
	body.count("30 * WAIT_SEC") == 2)
all_ok &= check("drain is level / 8 per combat round",
	contains(body, "moves = GET_LEVEL(ch) / 8;") and
	contains(event, "add_event(event_web_spray, PULSE_VIOLENCE, ch,"))
all_ok &= check("drain stops when the webbing wears off",
	contains(event, "!affected_by_spell(ch, TAG_WEB_SPRAY)"))
all_ok &= check("re-spray replaces the running drain",
	body.find("disarm_char_nevents(victim, event_web_spray);") <
	body.find("add_event(event_web_spray"))
all_ok &= check("caster lag and fight engagement",
	contains(body, "CharWait(ch, PULSE_VIOLENCE);") and body.count("engage(ch, victim);") == 4)

actmove = (SRC / "actmove.c").read_text()
move_check = re.search(r"void web_spray_move_check\(P_char ch\).*?\n}\n", innates, re.S)
move_check = move_check.group(0) if move_check else ""
all_ok &= check("room moves run the break check",
	contains(actmove, "telemetry_gameplay_movement(ch);\n\tweb_spray_move_check(ch);"))
all_ok &= check("10% break chance ends the webbing and the drain",
	contains(move_check, "number(1, 100) > 10") and
	contains(move_check, "affect_from_char(ch, TAG_WEB_SPRAY);") and
	contains(move_check, "disarm_char_nevents(ch, event_web_spray);"))

if not all_ok:
	sys.exit(1)
print("All web spray checks passed.")
