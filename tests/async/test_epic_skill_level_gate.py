#!/usr/bin/env python3
"""Contracts for the epic skill level gate.

epic.skills.minLevel (default 30): no epic skills learned below it.
Epic points have no level gate.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, source


PROPERTIES = (ROOT / "lib" / "duris.properties").read_text()


def _flat(text: str) -> str:
    return "".join(text.split())


def _body(name: str, signature: str) -> str:
    """A function definition: its signature to the closing brace in column 0."""
    text = source(name).read_text()
    at = text.find(signature)
    while at >= 0:
        brace, semicolon = text.find("{", at), text.find(";", at)
        if brace >= 0 and (semicolon < 0 or brace < semicolon):
            return text[at:text.index("\n}\n", brace) + 2]
        at = text.find(signature, at + 1)
    raise AssertionError(f"{name}: no definition for {signature}")


def test_helper_reads_the_skill_level_and_clamps_it() -> None:
    helper = _body("world/epic.c", "int epic_skills_min_level()")
    harness = r'''
#include <map>
#include <string>
#define MAXLVL 62
#define BOUNDED(low, value, high) ((value) < (low) ? (low) : (value) > (high) ? (high) : (value))
static std::map<std::string, float> props;
float get_property(const char *key, double fallback) {
    const auto found = props.find(key);
    return found == props.end() ? static_cast<float>(fallback) : found->second;
}
''' + helper + r'''
int main() {
    if (epic_skills_min_level() != 30) return 1;
    props["epic.skills.minLevel"] = 40;
    if (epic_skills_min_level() != 40) return 2;
    props["epic.skills.minLevel"] = 500;
    if (epic_skills_min_level() != 62) return 3;
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix="duris-epic-skill-gate-") as directory:
        root = Path(directory)
        source_path, binary = root / "harness.cpp", root / "harness"
        source_path.write_text(harness)
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
                        str(source_path), "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], cwd=ROOT, check=True)


def test_epic_teachers_refuse_below_the_skill_level() -> None:
    teacher = _flat(_body("classes/epic_skills.c", "int epic_teacher(P_char ch, P_char pl, int cmd, char *arg)"))
    gate = teacher.index(_flat("if (GET_LEVEL(pl) < epic_skills_min_level())"))
    assert gate < teacher.index(_flat("epics_cost = 3 *"))
    assert gate < teacher.index("epic_transaction_submit(")


def test_epic_points_have_no_level_gate() -> None:
    epic = source("world/epic.c").read_text()
    assert "epic_level_can_gain" not in epic
    assert "epic_gain_min_level" not in epic
    assert "epic.gain.minLevel" not in PROPERTIES


def test_properties_ship_the_skill_default() -> None:
    section = PROPERTIES[PROPERTIES.index("[epic]"):]
    section = section[: section.index("\n[", 1)].splitlines()
    assert "epic.skills.minLevel=30.000" in section


if __name__ == "__main__":
    tests = [
        test_helper_reads_the_skill_level_and_clamps_it,
        test_epic_teachers_refuse_below_the_skill_level,
        test_epic_points_have_no_level_gate,
        test_properties_ship_the_skill_default,
    ]
    for test in tests:
        test()
    print("epic skill level gate contracts passed")
