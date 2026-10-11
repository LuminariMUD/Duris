#!/usr/bin/env python3
"""Contracts for the creation-race rebalance (issue #33).

The stat multipliers it set, the troll's lost groundfighting, and the reflection innate
gnomes and kobolds gain at level 31. Spell pulse is pinned by test_racial_pulse.py.
"""

from __future__ import annotations

import re

from _paths import ROOT, source


PROPERTIES = set((ROOT / "lib" / "duris.properties").read_text().splitlines())

STATS = {"MountainDwarf": {"dex": 100, "agi": 95},
         "DuergarDwarf": {"dex": 100, "agi": 95, "con": 125, "int": 85, "wis": 125},
         "Troll": {"agi": 90, "int": 70, "wis": 95},
         "Centaur": {"wis": 110},
         "Tiefling": {"str": 100, "luc": 95},
         "Drider": {"str": 120, "con": 120, "pow": 90, "int": 110}}


def _racial_innates() -> set[tuple[str, str, int]]:
    """Every (innate, race, level) assign_innates() grants, comments left out."""
    text = source("classes/innates.c").read_text()
    start = text.index("void assign_innates()")
    body = text[start:text.index("\n}\n", start)]
    body = re.sub(r"//[^\n]*|/\*.*?\*/", "", body, flags=re.S)
    return {(innate, race, int(level)) for innate, race, level in
            re.findall(r"ADD_RACIAL_INNATE\((\w+),\s*(\w+),\s*(\d+)\)", body)}


def test_stats_ship_the_rebalanced_values() -> None:
    for race, stats in STATS.items():
        for stat, value in stats.items():
            assert f"stats.{stat}.{race}={value:.3f}" in PROPERTIES, (race, stat)


def test_trolls_lose_groundfighting() -> None:
    granted = {(race, level) for innate, race, level in _racial_innates()
               if innate == "INNATE_GROUNDFIGHTING"}
    assert not any(race == "RACE_TROLL" for race, _ in granted), granted
    assert ("RACE_BARBARIAN", 21) in granted and ("RACE_DRIDER", 21) in granted, granted


def test_gnomes_and_kobolds_gain_reflection_at_31() -> None:
    granted = {(race, level) for innate, race, level in _racial_innates()
               if innate == "INNATE_REFLECTION"}
    assert granted == {("RACE_GNOME", 31), ("RACE_KOBOLD", 31)}, granted

    structs = source("core/structs.h").read_text()
    assert re.search(r"#define INNATE_REFLECTION \d+", structs)
    assert "#define LAST_INNATE INNATE_REFLECTION" in structs

    innates = source("classes/innates.c").read_text()
    assert '{ "reflection", do_innate_reflection },\n};' in innates
    start = innates.index("void do_innate_reflection(P_char ch")
    body = innates[start:innates.index("\n}\n", start)]
    # The cooldown comes from innate.timer.secs.reflection, and the spell always lands on the user.
    assert "check_innate_time(ch, INNATE_REFLECTION))" in body
    assert "spell_reflection(GET_LEVEL(ch), ch, 0, 0, ch, 0);" in body
    assert "innate.timer.secs.reflection=300.000" in PROPERTIES


if __name__ == "__main__":
    for test in (test_stats_ship_the_rebalanced_values, test_trolls_lose_groundfighting,
                 test_gnomes_and_kobolds_gain_reflection_at_31):
        test()
    print("race rebalance contracts passed")
