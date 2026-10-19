#!/usr/bin/env python3
"""Check class-point documentation against source tables and its stated arithmetic.

Grades are design judgments. This audit does not validate gameplay balance.
"""

from decimal import Decimal
from pathlib import Path
import re
from statistics import median
import unittest


ROOT = Path(__file__).resolve().parents[2]
AXES = "DBTHCSU"
WEIGHTS = tuple(map(Decimal, (6, 4, 5, 5, 4, 4, 2)))
NORMALIZER = Decimal(84)  # Frozen calibration, not the current roster median.


def table(markdown, first_column):
    match = re.search(
        rf"^\| {re.escape(first_column)} \|[^\n]*\n\|[-: |]+\n((?:\|[^\n]+\n)+)",
        markdown, re.M,
    )
    if not match:
        raise AssertionError(f"Missing table: {first_column}")
    return [[cell.strip() for cell in line.strip().strip("|").split("|")]
            for line in match[1].splitlines()]


def source_array(text, name):
    match = re.search(rf"\b{name}\s*(?:\[[^]]*\])+\s*=\s*\{{(.*?)\n\}};", text, re.S)
    if not match:
        raise AssertionError(f"Missing source array: {name}")
    # These initializers have no comment delimiters inside string literals.
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", match[1], flags=re.S)


def raw_score(grades):
    return sum(weight * grade for weight, grade in zip(WEIGHTS, grades))


def cp(raw):
    return 100 * raw / NORMALIZER


class ClassPointsContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = (ROOT / "docs/reference/CLASS-POINTS.md").read_text()
        cls.prose = " ".join(cls.doc.split())
        cls.rows = table(cls.doc, "Class / specialization")
        cls.cards = {row[0]: tuple(map(Decimal, row[1:8])) for row in cls.rows}
        cls.basis = table(cls.doc, "Reference build")
        cls.properties = dict(re.findall(
            r"(?m)^([^#\s=]+)\s*=\s*([^\n]+)",
            (ROOT / "lib/duris.properties").read_text(),
        ))

    def test_shared_scale_and_prices(self):
        formula = re.search(r"(?m)^raw = (.+)$", self.doc)[1]
        self.assertEqual(re.sub(r"\s+", "", formula),
                         "+".join(f"{weight}{axis}" for weight, axis in zip(WEIGHTS, AXES)))
        formula = re.search(r"(?m)^CP\s*= (.+)$", self.doc)[1]
        self.assertEqual(re.sub(r"\s+", "", formula), "100×raw/M")
        self.assertEqual(Decimal(re.search(r"(?m)^M = (\d+) for", self.doc)[1]), NORMALIZER)
        prices = table(self.doc, "Axis")
        self.assertEqual(len(prices), len(AXES))
        for row, axis, weight in zip(prices, AXES, WEIGHTS):
            with self.subTest(axis=axis):
                self.assertTrue(row[0].startswith(f"**{axis} — "))
                units, price = row[1].split("; ")
                self.assertEqual(Decimal(units), weight)
                self.assertEqual(price, f"{cp(weight):.2f} CP")

    def test_scorecard_arithmetic_and_sensitivity(self):
        self.assertEqual(len(self.rows), len(self.cards), "Duplicate reference build")
        raw_totals = []
        for row in self.rows:
            with self.subTest(build=row[0]):
                self.assertEqual(len(row), 12)
                grades = self.cards[row[0]]
                self.assertTrue(all(g.is_finite() and g >= 0 and g * 2 % 1 == 0
                                    for g in grades))
                raw = raw_score(grades)
                low = cp(raw_score([max(0, g - 1) for g in grades]))
                high = cp(raw_score([g + 1 for g in grades]))
                self.assertEqual(Decimal(row[8]), raw)
                self.assertEqual(row[9:], [f"{cp(raw):.1f}", f"{low:.1f}", f"{high:.1f}"])
                # This is an explicit observation about this revision, not a balance gate.
                self.assertLess(low, 90)
                self.assertGreater(high, 110)
                raw_totals.append(raw)

        current_median, minimum, maximum, cp_min, cp_max = re.search(
            r"The raw median is \*\*([\d.]+)\*\*, range \*\*([\d.]+)–([\d.]+)\*\*, "
            r"producing \*\*([\d.]+)–([\d.]+) CP\*\*", self.prose,
        ).groups()
        self.assertEqual(Decimal(current_median), median(raw_totals))
        self.assertEqual((Decimal(minimum), Decimal(maximum)), (min(raw_totals), max(raw_totals)))
        self.assertEqual((cp_min, cp_max), (f"{cp(min(raw_totals)):.1f}", f"{cp(max(raw_totals)):.1f}"))

    def test_source_roster_race_spec_and_hp_inputs(self):
        constant = (ROOT / "src/core/constant.c").read_text()
        common = (ROOT / "src/core/common.c").read_text()
        defines = (ROOT / "src/core/defines.h").read_text()
        structs = (ROOT / "src/core/structs.h").read_text()
        availability = (ROOT / "src/account/creation_availability_config.c").read_text()
        specs = (ROOT / "src/classes/specializations.c").read_text()
        config = dict(re.findall(
            r"(?m)^creation\.(\S+)\s*=\s*(true|false)\s*$",
            (ROOT / "lib/creation_availability.cfg").read_text(),
        ))
        race_ids = {name: int(value) for name, value in re.findall(
            r"(?m)^#define (RACE_\w+)\s+(\d+)\b", defines)}
        class_ids = {name: int(value) for name, value in re.findall(
            r"(?m)^#define (CLASS_\w+)\s+BIT_(\d+)\b", defines)}
        spec_ids = {name: int(value) for name, value in re.findall(
            r"(?m)^#define (SPEC_\w+)\s+(\d+)\b", structs)}
        spec_ids["SPEC_ALL"] = 0
        names = re.findall(r'\{\s*"([^"]+)"', source_array(common, "class_names_table"))
        policy_classes = {name: int(value) for name, value in re.findall(
            r'\{\s*"([^"]+)"\s*,\s*(\d+)\s*\}', source_array(availability, "class_names"))}
        policy_races = dict(re.findall(
            r'\{\s*"([^"]+)"\s*,\s*(RACE_\w+)\s*\}', source_array(availability, "race_names")))
        playable = set(re.findall(r"\{\s*(RACE_\w+)\s*,", source_array(constant, "playable_races")))
        enabled_races = {race for key, race in policy_races.items()
                         if race in playable and config.get(f"race.{key}.enabled", "true") == "true"}
        matrix = [list(map(int, re.findall(r"-?\d+", row)))
                  for row in re.findall(r"\{([^{}]+)\}", source_array(constant, "class_table"))]
        for row in matrix:
            self.assertLessEqual(len(row), len(names))
            row.extend([0] * (len(names) - len(row)))  # C zero-initializes omitted cells.
        eligible = {names[index] for key, index in policy_classes.items()
                    if config.get(f"class.{key}.enabled", "true") == "true"
                    and any(matrix[race_ids[race]][index] != 5 for race in enabled_races)}
        classes = [row[0].split(" / ")[0] for row in self.rows]
        self.assertEqual(len(classes), len(set(classes)), "Duplicate class in calibration")
        self.assertEqual(set(classes), eligible)
        self.assertEqual(len(classes), int(re.search(r"produces \*\*(\d+) classes\*\*", self.doc)[1]))
        self.assertEqual(len(self.basis), len(self.cards))
        self.assertEqual({row[0] for row in self.basis}, set(self.cards))

        spec_names = [[re.sub(r"&(?:\+.|.)", "", value).casefold()
                       for value in re.findall(r'"([^"]*)"', row)]
                      for row in re.findall(r"\{([^{}]+)\}", source_array(common, "specdata"))]
        allowed = {(race, class_ids[klass], spec_ids[spec]) for race, klass, spec in re.findall(
            r"\{\s*(RACE_\w+)\s*,\s*(CLASS_\w+)\s*,\s*(SPEC_\w+)\s*\}",
            source_array(specs, "allowed_race_specs"),
        )}
        for row in self.basis:
            with self.subTest(build=row[0]):
                self.assertEqual(len(row), 4)
                klass, spec = row[0].split(" / ")
                class_id = names.index(klass)
                race = policy_races[row[1].lower().replace(" ", "-")]
                self.assertIn(race, enabled_races)
                self.assertNotEqual(matrix[race_ids[race]][class_id], 5)
                spec_id = spec_names[class_id].index(spec.casefold()) + 1
                self.assertTrue((race, class_id, 0) in allowed or (race, class_id, spec_id) in allowed)
                self.assertEqual(Decimal(row[2]), Decimal(self.properties[f"hitpoints.class.{klass}"]))

    def test_estimated_dominance_pairs(self):
        expected = set()
        for higher, a in self.cards.items():
            for lower, b in self.cards.items():
                if all(x >= y for x, y in zip(a, b)) and any(x > y for x, y in zip(a, b)):
                    axes = ", ".join(axis for axis, x, y in zip(AXES, a, b) if x > y)
                    expected.add((higher, lower, axes))
        documented = table(self.doc, "Higher estimated vector")
        self.assertEqual(len(documented), len(expected))
        self.assertEqual({tuple(row) for row in documented}, expected)

    def test_scenario_weights(self):
        scenarios = table(self.doc, "Scenario")
        self.assertEqual(len(scenarios), len({row[0] for row in scenarios}))
        weights = [Decimal(row[1].removesuffix("%")) for row in scenarios]
        self.assertTrue(weights and all(0 < weight <= 100 for weight in weights))
        self.assertEqual(sum(weights), 100)

    def test_worked_changes(self):
        grades = list(self.cards["Mercenary / Brigand"])
        before = raw_score(grades)
        old_c, new_c = map(Decimal, re.search(r"net C grade from ([\d.]+) to ([\d.]+)", self.prose).groups())
        self.assertEqual(old_c, grades[AXES.index("C")])
        grades[AXES.index("C")] = new_c
        after = raw_score(grades)
        self.assertIn(f"starts at raw {before}, or {cp(before):.1f} CP", self.prose)
        self.assertIn(f"New raw is `{before} + 4 × {new_c - old_c} = {after.normalize():f}`", self.prose)
        self.assertIn(f"**{cp(after):.1f} CP**, a **+{cp(after - before):.1f} CP** change", self.prose)

        vectors = re.findall(r"`([DBTHCSU][\d.]+(?: [DBTHCSU][\d.]+){6})`", self.doc)
        self.assertEqual(len(vectors), 2)
        totals = []
        for vector in vectors:
            values = re.findall(r"([DBTHCSU])([\d.]+)", vector)
            self.assertEqual("".join(axis for axis, _ in values), AXES)
            totals.append(raw_score([Decimal(value) for _, value in values]))
        for word, raw in zip(("is", "becomes"), totals):
            self.assertIn(f"Raw {word} **{raw}**, or **{cp(raw):.1f} CP**", self.prose)
        self.assertIn(f"The **{cp(totals[0] - totals[1]):.1f} CP** reduction", self.prose)

        # The delta range applies only to C; unchanged uncertain grades cancel.
        delta_low, delta_high, midpoint = map(Decimal, re.search(
            r"C increase is estimated as `([\d.]+) to ([\d.]+)` with midpoint `([\d.]+)`", self.prose,
        ).groups())
        c_price = cp(WEIGHTS[AXES.index("C")])
        self.assertEqual(midpoint, (delta_low + delta_high) / 2)
        self.assertIn(f"**{c_price * delta_low:.1f}–{c_price * delta_high:.1f} CP**", self.prose)
        self.assertIn(f"midpoint **+{c_price * midpoint:.1f} CP**", self.prose)

    def test_passive_and_repricing_examples(self):
        factor = Decimal(self.properties["damage.reduction.guardians.bulwark"])
        self.assertIn(f"configured `{factor:.3f}` damage factor", self.prose)
        self.assertIn(f"`1 / {factor:.2f} = {1 / factor:.4f}`", self.prose)
        before, after = map(Decimal, re.search(r"moving T from ([\d.]+) to ([\d.]+),", self.prose).groups())
        price = cp(WEIGHTS[AXES.index("T")] * (after - before))
        self.assertIn(f"= {price:.2f} CP`", self.prose)
        old_u, new_u = map(Decimal, re.search(r"U's weight from (\d+) to (\d+)", self.prose).groups())
        self.assertEqual(old_u, WEIGHTS[AXES.index("U")])
        self.assertIn(f"+{cp((new_u - old_u) * 5):.2f} for U5 and +{cp(new_u - old_u):.2f} for U1", self.prose)

    def test_burst_accounting_example(self):
        t, b, total, opening, rate, excess, sustained = map(Decimal, re.search(
            r"`t=(\d+)`, `b=(\d+)`, `Q=(\d+)`, and `Qb=(\d+)` give `r=([\d.]+)`, "
            r"`burst_excess=([\d.]+)`, and `sustained_damage=([\d.]+)`", self.prose,
        ).groups())
        self.assertTrue(0 < b < t and 0 <= opening <= total)
        self.assertEqual(rate, (total - opening) / (t - b))
        self.assertEqual(excess, max(0, opening - rate * b))
        self.assertEqual(sustained + excess, total)
        self.assertIn(f"D uses **{sustained / t:g} damage/second**", self.prose)
        self.assertIn(f"B uses **{excess:g} excess damage**", self.prose)
        self.assertIn(f"full {total / t:.1f} DPS", self.prose)


if __name__ == "__main__":
    unittest.main()
