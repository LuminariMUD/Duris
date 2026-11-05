#!/usr/bin/env python3
"""Every registered ability is converted, has no numbers to show, or is still pending.

Converted abilities are the cases of the facts tables in src/abilities/abilities.c.
The two lists live in tests/fixtures. The pending list may only shrink: an ability that
loses its facts function fails this test until it is deliberately listed again.
"""
import re
from collections import Counter

from _paths import ROOT, source
from _source_contract import strip_comments

FIXTURES = ROOT / "tests/fixtures"
REGISTRATION = re.compile(
    r'\b(?:SPELL_CREATE(?:_MSG|2)?|SKILL_CREATE(?:_WITH_MESSAGES)?)\s*\(\s*"(?:[^"\\]|\\.)*"\s*,\s*(\w+)')


def registered():
    """Spells, skills, songs and instruments by constant, then innates by constant."""
    abilities = []
    for name in ("classes/skills.c", "epic_skills.c"):
        abilities += REGISTRATION.findall(strip_comments(source(name).read_text()))
    structs = source("structs.h").read_text()
    innates = structs[structs.index("#define INNATE_HORSE_BODY 0"):structs.index("#define LAST_INNATE")]
    abilities += re.findall(r"^#define\s+(\w+)\s+\d+\b", innates, re.M)
    return abilities


def listed(name):
    lines = (FIXTURES / name).read_text().splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def main():
    abilities = registered()
    converted = re.findall(r"^\s*case\s+(\w+):", strip_comments(source("abilities.c").read_text()), re.M)
    no_numbers = listed("ability_coverage_no_numbers.txt")
    pending = listed("ability_coverage_pending.txt")
    known = set(abilities)
    assert len(known) == len(abilities), [a for a, n in Counter(abilities).items() if n > 1]
    seen = Counter(converted + no_numbers + pending)
    unknown = sorted(set(seen) - known)
    assert not unknown, f"not registered abilities: {unknown}"
    twice = sorted(a for a, n in seen.items() if n > 1)
    assert not twice, f"listed more than once: {twice}"
    missing = sorted(known - set(seen))
    assert not missing, f"neither converted nor listed (did a facts function go missing?): {missing}"
    print(f"PASS: {len(known)} abilities: {len(converted)} converted, "
          f"{len(no_numbers)} with no numbers, {len(pending)} pending")


if __name__ == "__main__":
    main()
