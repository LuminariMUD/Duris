#!/usr/bin/env python3
"""Regression checks for Gith Monk creation without changing random NPC classes."""

from pathlib import Path
import re
import subprocess
import tempfile

from _paths import ROOT, source


MONK = 7
table = source("constant.c").read_text(encoding="utf-8")
start = table.index("const int class_table[LAST_RACE + 1][CLASS_COUNT + 1] = {")
rows = table[start : table.index("\n};", start)]
matches = re.findall(
    r"\{([^{}]+)\}\s*,?\s*/\*\s*(Githyanki|Githzerai)\s*\*/", rows
)
assert len(matches) == 2, "Expected exactly two Gith race/class rows"
for values, race in matches:
    entries = [int(value.strip()) for value in values.split(",") if value.strip()]
    assert len(entries) == 31, (race, len(entries))
    assert entries[MONK] == {"Githyanki": -1, "Githzerai": 1}[race], race

config = (ROOT / "lib/creation_availability.cfg").read_text(encoding="utf-8")
specs = source("specializations.c").read_text(encoding="utf-8")
kits = source("newbie_kit_plan.c").read_text(encoding="utf-8")
for race in ("githyanki", "githzerai"):
    assert f"creation.race.{race}.enabled=true" in config
    symbol = "RACE_" + race.upper()
    assert re.search(
        rf"\{{\s*{symbol}\s*,\s*CLASS_MONK\s*,\s*SPEC_ALL\s*\}}", specs
    ), symbol
    assert re.search(
        rf"CREATE_KIT\(\s*{symbol}\s*,\s*CLASS_MONK\s*,", kits
    ), symbol
assert "creation.class.monk.enabled=true" in config

# Both client transports already use the same alignment policy. Fixed G/E
# codes match Githzerai/Githyanki faction admission.
for name in ("nanny.c", "ws_handlers.c"):
    assert "creation_class_align(" in source(name).read_text(encoding="utf-8")

help_text = (ROOT / "help/duris_help_parsed.hlp").read_text(encoding="utf-8")
monk_help = help_text.split("\nMonk - Last Edited:", 1)[1].split("\n#0", 1)[0]
for display in ("&+GGith&+Wyanki&n", "&+WGith&+Gzerai&n"):
    assert display in monk_help.split("==Allowed races==", 1)[1].split(
        "These are normal-roster", 1
    )[0]
docs = (ROOT / "docs/reference/CLASSES.md").read_text(encoding="utf-8")
assert "| Monk | G: Human, Githzerai. E: Orc, Githyanki. A: Tiefling. |" in docs

mob = source("random.mob.c").read_text(encoding="utf-8")
signature = "static bool random_mob_class_allowed(int race, int class_idx)"
predicate = mob.split(signature, 1)[1].split("\n}", 1)[0]
for required in (
    "class_idx == flag2idx(CLASS_MONK)",
    "race == RACE_GITHYANKI || race == RACE_GITHZERAI",
    "return false;",
    "return class_table[race][class_idx] != 5;",
):
    assert required in predicate, required
assert "while (!random_mob_class_allowed(race, class_idx))" in mob

# Compile and execute the production predicate, not a Python rewrite of it.
# Its real caller remains checked above, with ordinary class-table selection
# preserved for all combinations other than the two new player-only Gith Monks.
harness = r"""
#include <cassert>
constexpr int LAST_RACE = 40;
constexpr int CLASS_COUNT = 30;
constexpr int RACE_HUMAN = 1;
constexpr int RACE_ORC = 12;
constexpr int RACE_GITHYANKI = 15;
constexpr int RACE_GITHZERAI = 30;
constexpr unsigned CLASS_MONK = 1u << 6;
int class_table[LAST_RACE + 1][CLASS_COUNT + 1] = {};
int flag2idx(unsigned bit) { assert(bit == CLASS_MONK); return 7; }
""" + signature + predicate + "\n}\n" + r"""
int main() {
    for (auto &row : class_table)
        for (auto &cell : row)
            cell = 5;
    class_table[RACE_GITHYANKI][7] = -1;
    class_table[RACE_GITHZERAI][7] = 1;
    class_table[RACE_GITHYANKI][1] = -1;
    class_table[RACE_GITHZERAI][1] = 2;
    class_table[RACE_HUMAN][7] = 1;
    class_table[RACE_ORC][7] = -1;

    assert(!random_mob_class_allowed(RACE_GITHYANKI, 7));
    assert(!random_mob_class_allowed(RACE_GITHZERAI, 7));
    assert(random_mob_class_allowed(RACE_GITHYANKI, 1));
    assert(random_mob_class_allowed(RACE_GITHZERAI, 1));
    assert(random_mob_class_allowed(RACE_HUMAN, 7));
    assert(random_mob_class_allowed(RACE_ORC, 7));
    assert(!random_mob_class_allowed(RACE_HUMAN, 2));
}
"""
with tempfile.TemporaryDirectory(prefix="duris-gith-monk-") as temp_dir:
    cpp = Path(temp_dir) / "mob_class_test.cpp"
    binary = Path(temp_dir) / "mob_class_test"
    cpp.write_text(harness, encoding="utf-8")
    subprocess.run(
        [
            "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
            "-o", str(binary), str(cpp),
        ],
        check=True,
    )
    subprocess.run([str(binary)], check=True)

print("Gith Monk creation and random-mobile eligibility contracts passed")
