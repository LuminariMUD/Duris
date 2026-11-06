#!/usr/bin/env python3
"""Preserve the old sets/spawn pool and execute real catalog/report entry points."""
import hashlib
import collections
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, HARNESS_STUBS, extract_function, source


def aggregate_rows(text, declaration):
    text = re.sub(r"//[^\n]*", "", text)
    start = text.index("{", text.index(declaration))
    depth = 0
    rows = []
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
            if depth == 2:
                row_start = i
        elif text[i] == "}":
            if depth == 2:
                rows.append(re.sub(r"\s+", "", text[row_start:i + 1]))
            depth -= 1
            if not depth:
                return rows
    raise AssertionError("unterminated aggregate")


def digest(rows):
    return hashlib.sha256("\n".join(rows).encode()).hexdigest()


catalog_source = source("named_sets.c").read_text()
spawn_source = source("random.mob.c").read_text()
set_rows = aggregate_rows(catalog_source, "named_sets[] =")
spawn_rows = aggregate_rows(spawn_source, "zones_random_data[] =")
# Frozen from 878c3a85b, before separating sets from roaming spawns. New sets may
# be added without changing any old zone/effect/threshold or spawn sampling row.
BASELINE_IDS = "14 18 20 21 23 24 26 27 35 37 38 40 53 60 67 68 73 87 90 91 93 94 103 106 112 113 124 130 133 140 143 151 152 159 160 162 165 170 183 191 196 197 200 202 213 215 220 222 224 226 229 230 232 238 244 254 257 260 261 262 264 266 270 285 289 294 306 308 311 313 315 318 320 324 328 333 335 342 345 360 367 368 370 371 377 381 383 386 387 391 400 402 412 419 441 448 450 583 662 671 676 700 710 756 758 800 824 857 936 955 960 964 975 987 1325"
old_ids = set(map(int, BASELINE_IDS.split()))
assert digest([row for row in set_rows if int(row[1:row.index(',')]) in old_ids]) == "ea4af79fa4b514f3fe4e85a2b099a6e7bde3a8d3cc3906b6de0509adafcec217"
assert digest(spawn_rows) == "d6651121125ccc52834725a969e5c5d9625396b05cd4aba7c3957b528f9313ed"
assert len(spawn_rows) == 118
assert "named_sets" not in extract_function("random.mob.c", "P_char create_random_mob(")

# The reviewed assignment document is the data manifest. Keep every old row and
# require one exact tier for each addition, with no unclassified active record.
assignments = (ROOT / "docs/ongoing-projects/named-zone-set-first-pass-assignments.md").read_text()
sections = [
    assignments.split("## The 42 proposed assignments")[1].split("## Effect homes after both passes")[0],
    assignments.split("### The 79 wider-review additions")[1].split("### Excluded active records")[0],
]
expected = {}
for section in sections:
    for line in section.splitlines():
        if not re.match(r"^\| \d+ \|", line):
            continue
        cells = line.split("|")
        zone, pieces = int(cells[1]), int(cells[4])
        effect = int(re.search(r"\(#(\d+)\)", cells[3])[1])
        assert zone not in expected
        expected[zone] = (pieces, effect)
assert len(expected) == 183 and not old_ids & expected.keys()
defines = {name: int(number) for name, number in re.findall(
    r"^#define\s+(\w+)\s+(\d+)\s*(?://[^\n]*)?$", source("spells.h").read_text(), re.M)}
actual_ids = {int(row[1:row.index(',')]) for row in set_rows}
assert len(set_rows) == len(actual_ids) == 298
assert actual_ids == old_ids | expected.keys()
for row in set_rows:
    zone = int(row[1:row.index(',')])
    if zone in old_ids:
        continue
    match = re.fullmatch(r"\{\d+,\{\{(\d+),(\w+)\}\}\}", row)
    assert match and (int(match[1]), defines[match[2]]) == expected[zone], row
excluded = {int(value) for value in re.findall(r"^\| (-?\d+) \|",
    assignments.split("### Excluded active records")[1].split("## Implementation handoff")[0], re.M)}
assert len(excluded) == 56 and not excluded & actual_ids
loaded = set()
for line in (ROOT / "areas/AREA").read_text().splitlines():
    if not line.strip() or line.lstrip().startswith("*"):
        continue
    area = line.split()[0]
    path = ROOT / "areas/zon" / (area + ".zon")
    if path.exists():
        number = int(re.search(r"^#(-?\d+)", path.read_text(encoding="latin-1"), re.M)[1])
        loaded.add(number - 2**32 if number > 2**31 - 1 else number)
assert loaded == actual_ids | excluded, (loaded ^ (actual_ids | excluded))
assert len(loaded) == 354
homes = collections.defaultdict(set)
for row in set_rows:
    zone = int(row[1:row.index(',')])
    for pieces, token in re.findall(r"\{(\d+),(\w+)\}", row):
        if int(pieces) and token in defines:
            homes[defines[token]].add(zone)
for line in assignments.split("## Effect homes after both passes")[1].split("
## ", 1)[0].splitlines():
    if not re.search(r"\(#\d+\)", line):
        continue
    cells = line.split("|")
    effect = int(re.search(r"\(#(\d+)\)", cells[1])[1])
    assert int(cells[-2]) == len(homes[effect]), (effect, cells[-2], homes[effect])

# Use the real registration list for handler availability and names. The callback
# body is irrelevant to catalog validation; actual effects belong to wear tests.
registrations = source("skills.c").read_text() + source("epic_skills.c").read_text()
registrations = re.sub(r"/\*.*?\*/|//[^\n]*", "", registrations, flags=re.S)
initializers = []
for kind, name, effect in re.findall(
        r'\b(SPELL_CREATE(?:_MSG|2)?|SKILL_CREATE(?:_WITH_MESSAGES)?)\(\s*"([^"\n]+)"\s*,\s*(\w+)',
        registrations):
    initializers.append(f'skills[{effect}].name = "{name}";')
    if kind.startswith("SPELL_"):
        initializers.append(f'skills[{effect}].spell_pointer = fixture_spell;')

harness = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "world/db.h"
#include "item/named_sets.h"
#include "redis/redis_report_cache.h"
#include "magic/spells.h"
#include <cassert>
#include <cstdarg>
#include <string>
#include <set>
#include <vector>

Skill skills[MAX_AFFECT_TYPES + 1];
static std::vector<zone_data> zones;
zone_data *zone_table;
static std::string title;
static int missing_zone = -1;
static bool cache_enabled, cached;
static int cache_generations, pages;
static std::string cache, displayed;
static void fixture_spell(int, P_char, char *, int, P_char, P_obj) {}
void logit(const char *, const char *format, ...) {
    va_list args;
    va_start(args, format);
    vfprintf(stderr, format, args);
    fputc('\n', stderr);
    va_end(args);
}
int real_zone(int zone) {
    if (zone == missing_zone) return -1;
    for (size_t i = 0; i < named_set_count; ++i)
        if (named_sets[i].zone == zone) return i;
    return -1;
}
char *redis_get_named_report() { return cached ? strdup(cache.c_str()) : nullptr; }
void redis_cache_named_report() {
    ++cache_generations;
    if (cache_enabled) {
        char *text = generate_named_report();
        cache = text;
        free(text);
        cached = true;
    }
}
void page_string(P_desc, char *text, int copy) {
    assert(copy == 1);
    displayed = text;
    ++pages;
}
''' + extract_function("utility.c", "string strip_ansi(") + \
    extract_function("utility.c", "string pad_ansi(") + \
    extract_function("redis_report_cache.c", "char *generate_named_report(") + \
    extract_function("random.mob.c", "void do_namedreport(") + r'''
int main() {
''' + "\n".join(initializers) + r'''
    title = "&+rA zone &+Wwith a very long title&n " + std::string(MAX_STRING_LENGTH, 'x');
    zones.resize(named_set_count);
    zone_table = zones.data();
    int tiers = 0;
    std::set<int> effects;
    for (size_t i = 0; i < named_set_count; ++i) {
        zones[i].number = named_sets[i].zone;
        zones[i].name = title.data();
        for (const auto &tier : named_sets[i].proc_spells)
            if (tier[0]) { ++tiers; effects.insert(tier[1]); }
    }
    assert(named_set_count == 298 && tiers == 389 && effects.size() == 106);
    assert(validate_named_sets());
    char *notes = generate_named_report();
    assert(strstr(notes,"Guardian Spirits requires a Shaman wearer"));
    assert(strstr(notes,"neutral wearers gain no bonus"));
    assert(strstr(notes,"Globe of Darkness excludes Holy Light and Mage Flame"));
    free(notes);
    assert(real_zone(30) == -1 && real_zone(250) == -1);
    assert(!named_set_effect_supported(-1));
    assert(!named_set_effect_supported(0));
    assert(!named_set_effect_supported(MAX_AFFECT_TYPES + 1));
    assert(!named_set_effect_supported(SKILL_KICK));
    assert(!named_set_effect_supported(SONG_HEALING));
    assert(named_set_effect_supported(SKILL_EPIC_STRENGTH));
    assert(named_set_effect_supported(SONG_DRAGONS));
    missing_zone = named_sets[0].zone;
    assert(!validate_named_sets());
    missing_zone = -1;
    auto callback = skills[SPELL_ARMOR].spell_pointer;
    skills[SPELL_ARMOR].spell_pointer = nullptr;
    assert(!validate_named_sets());
    skills[SPELL_ARMOR].spell_pointer = callback;

    char_data ch{};
    do_namedreport(&ch, nullptr, 0);
    const std::string expected = displayed;
    assert(pages == 1 && cache_generations == 1);
    assert(expected.size() > MAX_STRING_LENGTH * 4);
    assert(expected.find(" #14 ") != std::string::npos); // zone at table index zero
    assert(expected.find(" #1325 ") != std::string::npos); // beyond old staff cutoff
    assert(expected.find(" #30 ") == std::string::npos);
    size_t rows = 0;
    for (size_t pos = 0; (pos = expected.find("\n #", pos)) != std::string::npos; ++pos)
        ++rows;
    assert(rows == named_set_count);
    cache_enabled = true;
    do_namedreport(&ch, nullptr, 0); // cold cache
    assert(displayed == expected && pages == 2 && cache_generations == 2);
    do_namedreport(&ch, nullptr, 0); // warm cache
    assert(displayed == expected && pages == 3 && cache_generations == 2);
    cached = false; // expiry or staff invalidation
    do_namedreport(&ch, nullptr, 0);
    assert(displayed == expected && cache_generations == 3);
}
'''

validator = extract_function("named_sets.c", "bool validate_named_sets(")
invalid_harness = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "item/named_sets.h"
#include "world/db.h"
#include <cassert>
static named_set_definition invalid_sets[2];
static size_t invalid_count = 1;
#define named_sets invalid_sets
#define named_set_count invalid_count
bool named_set_effect_supported(int effect) { return effect == 1; }
int real_zone(int) { return 0; }
''' + validator + r'''
int main() {
    invalid_sets[0] = {1, {{3, 1}}};
    assert(validate_named_sets());
    for (const named_set_definition &bad : {
            named_set_definition{0, {{3, 1}}},
            named_set_definition{1, {{0, 1}}},
            named_set_definition{1, {{-1, 1}}},
            named_set_definition{1, {{MAX_WEAR, 1}}},
            named_set_definition{1, {{3, -1}}},
            named_set_definition{1, {{3, MAX_AFFECT_TYPES + 1}}},
            named_set_definition{1, {{0, 0}}}}) {
        invalid_sets[0] = bad;
        assert(!validate_named_sets());
    }
    invalid_sets[0] = invalid_sets[1] = {1, {{3, 1}}};
    invalid_count = 2;
    assert(!validate_named_sets());
}
'''

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="named-set-catalog-", dir=build) as directory:
    for name, cpp_source, linked in (
            ("catalog-report", harness, ["src/item/named_sets.c"]),
            ("invalid-catalog", invalid_harness, [])):
        cpp = Path(directory) / f"{name}.cpp"
        binary = Path(directory) / name
        cpp.write_text(cpp_source)
        subprocess.run([
            "g++", "-std=c++20", "-g", "-O1", "-D__NO_REDIS__",
            "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
            "-ffunction-sections", "-fdata-sections", "-Isrc", "-I/usr/include/mysql", str(cpp),
            *linked, str(HARNESS_STUBS), "-Wl,--gc-sections", "-o", str(binary),
        ], cwd=ROOT, check=True)
        subprocess.run([str(binary)], cwd=ROOT, check=True)
print("named-set baseline, validation, and cached/uncached command output: passed")
