#!/usr/bin/env python3
"""Source-level regression contracts for Swashbuckler rebalance issue #48.

These tests pin the skill unlocks and combat rules, not measured gameplay DPS.
A combat integration test is still needed to validate outcomes on staging.
"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def skill_block(name: str) -> str:
    text = source("src/classes/skills.c")
    start = text.index(f'SKILL_CREATE("{name}"')
    match = re.search(r'\n\s*(?:SKILL_CREATE|SPELL_CREATE)', text[start + 1:])
    assert match, name
    return text[start:start + 1 + match.start()]


def test_attack_progression() -> None:
    triple = skill_block("triple attack")
    assert "SPEC_SKILL_ADD(CLASS_WARRIOR, 41, 90, SPEC_SWASHBUCKLER);" in triple
    assert "SPEC_SKILL_ADD(CLASS_WARRIOR, 41, 100, SPEC_SWORDSMAN);" in triple

    vicious = skill_block("vicious attack")
    assert "SPEC_SKILL_ADD(CLASS_WARRIOR, 56, 100, SPEC_SWASHBUCKLER);" in vicious

    dual = skill_block("dual wield")
    # Players cannot choose Swashbuckler before level 30; retain its existing unlock.
    assert "SPEC_SKILL_ADD(CLASS_WARRIOR, 30, 100, SPEC_SWASHBUCKLER);" in dual
    assert "SPEC_SKILL_ADD(CLASS_WARRIOR, 0, 0, SPEC_GUARDIAN);" in dual


def test_parry_modifier_is_advantage_not_penalty() -> None:
    fight = source("src/combat/fight.c")
    start = fight.index("// Harder to parry a swashbuckler.")
    block = fight[start:fight.index("// Random 5% change", start)]
    assert "GET_SPEC(attacker, CLASS_WARRIOR, SPEC_SWASHBUCKLER)" in block
    assert "learnedattacker = (int)(learnedattacker * 1.10);" in block
    assert "learnedattacker = (int)(learnedattacker * 0.80);" not in block
    assert "if (attroll > defroll)" in fight


def test_legsweep_adjacent_size_penalty() -> None:
    code = source("src/cmd/actoff.c")
    start = code.index("void do_legsweep(")
    end = code.find("\nvoid ", start + 1)
    body = code[start:end if end >= 0 else None]

    assert "const int size_difference = get_takedown_size(vict) - get_takedown_size(ch);" in body
    assert "if (size_difference < -1)" in body
    assert "if (size_difference > 1)" in body
    assert re.search(r"if \(size_difference != 0\)\s*percent_chance \*= 0\.75;", body)
    assert body.index("percent_chance *= 0.75;") < body.index("percent_chance = takedown_check(")
    for difference in range(-3, 4):
        auto_fail = difference < -1 or difference > 1
        expected = abs(difference) >= 2
        assert auto_fail == expected
        multiplier = 0.75 if difference != 0 and not auto_fail else 1.0
        if not auto_fail:
            assert multiplier == (1.0 if difference == 0 else 0.75)


def test_sword_dirk_factors_unchanged() -> None:
    props = source("lib/duris.properties").splitlines()
    assert "damage.increase.swashbuckler=1.100" in props
    assert "damage.reduction.swashbuckler=0.900" in props
    innates = source("src/classes/innates.c")
    assert "ADD_CLASS_INNATE(INNATE_RAPIER_DIRK, CLASS_MERCENARY, 1, 0);" in innates
    assert "ADD_CLASS_INNATE(INNATE_RAPIER_DIRK, CLASS_ROGUE, 1, SPEC_THIEF);" in innates


if __name__ == "__main__":
    test_attack_progression()
    test_parry_modifier_is_advantage_not_penalty()
    test_legsweep_adjacent_size_penalty()
    test_sword_dirk_factors_unchanged()
    print("Swashbuckler rebalance source contracts passed")
