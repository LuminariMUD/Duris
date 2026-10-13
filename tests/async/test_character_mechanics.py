#!/usr/bin/env python3
"""Execute identity and Bulwark connections; broader site migration remains open."""

import hashlib
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, source, extract_function
from _source_contract import strip_comments, function_bodies


def production_function(file, signature):
    path = source(file)
    text = path.read_text()
    line = text[:text.index(signature)].count("\n") + 1
    return f'\n#line {line} "{path.relative_to(ROOT)}"\n' + extract_function(file, signature) + "\n"


def check_bulwark_sites(sources, bindings):
    """Migrated Bulwark sites only; no baseline exception for a new use/alias.

    This bounded tripwire accepts the three actual statement forms. It rejects
    unsupported reshaping for review; executable assertions own the arithmetic.
    The remainder of the option-site migration is still explicitly outstanding.
    """
    obligations = {
        "guardian_bulwark_grant": ("classes/innates.c", r"ADD_CLASS_INNATE\(\s*INNATE_GUARDIANS_BULWARK\s*,\s*CLASS_WARRIOR\s*,\s*[^,;{}]+,\s*SPEC_GUARDIAN\s*\)\s*;"),
        "guardian_bulwark_factor": ("combat/fight.c", r'dam_factor\[DF_GUARDIANS_BULWARK\]\s*=\s*get_property\(\s*"damage\.reduction\.guardians\.bulwark"\s*,\s*[^;{}]+\)\s*;'),
        "guardian_bulwark_effect": ("combat/fight.c", r"if\s*\(\s*has_innate\(victim,\s*INNATE_GUARDIANS_BULWARK\)\s*&&\s*victim->equipment\[WEAR_SHIELD\]\s*\)\s*dam\s*\*=\s*dam_factor\[DF_GUARDIANS_BULWARK\]\s*;"),
    }
    seen = set()
    errors = []
    symbols = re.compile(r"\b(?:INNATE_GUARDIANS_BULWARK|DF_GUARDIANS_BULWARK)\b")
    # Macro stringification makes these names the same native bindings the
    # executable used, rather than a second editable table of function names.
    for mechanic, symbol in bindings.items():
        if re.fullmatch(r"[a-zA-Z_]\w*", symbol):
            definitions = sum(len(function_bodies(text, rf"\b(?:int|bool)\s+{symbol}\s*\("))
                              for text in sources.values())
            if definitions != 1:
                errors.append(f"{mechanic}: native definition missing/conflicting: {symbol}")
    for path, text in sources.items():
        code = strip_comments(text)
        covered = []
        # Only typed descriptor initializers are metadata. A new branch in a
        # provider is not swallowed by a whole-function exclusion.
        for metadata in re.finditer(r"static const MechanicConnection connections\[\]\s*=\s*\{.*?\n\s*\};", code, re.S):
            strings_removed = re.sub(r'"(?:\\.|[^"\\])*"', '""', metadata.group())
            if re.search(r"\b(?:if|for|while|switch)\s*\(|\[\s*[=&]\s*\]", strings_removed):
                errors.append(f"{path}: unsupported executable descriptor initializer")
            covered.append(metadata.span())
        for marker in re.finditer(r"CHARACTER_MECHANIC_SITE\(\s*(\w+)\s*\)\s*;", code):
            site = marker[1]
            if site not in obligations:
                errors.append(f"{path}:{code.count(chr(10), 0, marker.start()) + 1}: unknown site {site}")
                continue
            owner, statement = obligations[site]
            match = re.match(r"\s*(" + statement + r")", code[marker.end():])
            if path != owner or not match:
                errors.append(f"{path}:{code.count(chr(10), 0, marker.start()) + 1}: missing/unsupported binding for {site}")
                continue
            if site in seen:
                errors.append(f"{path}: duplicate site {site}")
            seen.add(site)
            covered.append((marker.end(), marker.end() + match.end()))
        for token in symbols.finditer(code):
            if any(start <= token.start() < end for start, end in covered):
                continue
            line_start = code.rfind("\n", 0, token.start()) + 1
            # Exact existing numeric definitions are vocabulary, not effects.
            line = code[line_start:code.find("\n", token.end())]
            if ((path == "core/structs.h" and re.fullmatch(r"#define INNATE_GUARDIANS_BULWARK\s+\d+\s*", line)) or
                (path == "combat/damage.h" and re.fullmatch(r"#define DF_GUARDIANS_BULWARK\s+\d+\s*", line))):
                continue
            errors.append(f"{path}:{code.count(chr(10), 0, token.start()) + 1}: unregistered site/alias {token.group()}")
    for site in obligations.keys() - seen:
        errors.append(f"{site}: missing implementation site")
    for site in obligations:
        if site.replace("_", ".") not in bindings:
            errors.append(f"{site}: missing compiled connection")
    return errors


build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
inputs = [
    ROOT / "tests/async/character_mechanics_harness.cpp",
    source("character_mechanics.c"), source("common.c"), source("constant.c"),
    source("creation_availability_config.c"), source("specializations.c"), source("utility.c"),
    HARNESS_STUBS,
]

# Compile these production bodies without unrelated world/combat services. The
# fixture observes the value delivered by melee_damage to raw_damage; it does
# not claim to exercise the latter's HP, death, ward or persistence machinery.
innates = source("innates.c").read_text()
properties = source("properties.c").read_text()
combat_prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "combat/damage.h"
#include "magic/spells.h"
#include "classes/necromancy.h"
#include "player/character_mechanics.h"
#include <cassert>
#include <cctype>
#include <cmath>
#include <cstring>
#define PROPERTIES_FILE "lib/duris.properties"
#define MAX_PROPERTIES 3000
int properties_count;
float dam_factor[LAST_DF + 1];
static double delivered_damage;
static int damage_calls;
P_desc descriptor_list = nullptr;
void *__malloc(size_t size, const char *, const char *, int) { return malloc(size); }
void __free(void *p, const char *, int) { free(p); }
affected_type *get_spell_from_char(P_char ch, int spell, void *, int) {
    for (auto *af = ch->affected; af; af = af->next)
        if (af->type == spell) return af;
    return nullptr;
}
bool collector_presence_is_npc(P_char) { return false; }
int calculate_ac(P_char) { return 0; }
int number(int, int high) { return high; }
bool rapier_dirk_check(P_char) { return false; }
bool opposite_racewar(P_char, P_char) { assert(false && "fixture has no soulshield"); return false; }
int check_damage_ward(P_char, P_char, int) { return 0; }
bool decrease_skin_counter(P_char, unsigned int) { return false; }
void set_fighting(P_char, P_char) { assert(false && "fixture uses PHSDAM_NOENGAGE"); }
void DamageStuff(P_char, int) { assert(false && "fixture RNG suppresses equipment damage"); }
int attack_back(P_char, P_char, int) { assert(false && "fixture uses PHSDAM_NOENGAGE"); return 0; }
int check_shields(P_char, P_char, int, int) { assert(false && "fixture uses PHSDAM_NOSHIELDS"); return 0; }
int spell_damage(P_char, P_char, double, int, unsigned int, damage_messages *, int *) {
    assert(false && "fixture has no spell affects"); return 0;
}
int raw_damage(P_char, P_char, double amount, unsigned int, damage_messages *, int *) {
    delivered_damage = amount; ++damage_calls; return DAM_NONEDEAD;
}
'''
combat_bodies = (
    properties[properties.index("struct property\n{"):properties.index("int key_property_comp(")]
    + innates[innates.index("#define ADD_RACIAL_INNATE"):innates.index("float regen_factor")]
    + innates[innates.index("char racial_innates["):innates.index("extern const struct race_names")]
    + "\n".join(production_function(file, signature) for file, signature in [
        ("properties.c", "int key_property_comp("),
        ("properties.c", "int property_comp("),
        ("properties.c", "int parse_property("),
        ("properties.c", "int load_properties("),
        ("properties.c", "float get_property(const char *key, double default_value, bool"),
        ("properties.c", "float get_property(const char *key, double default_value)"),
        ("properties.c", "int get_property(const char *key, int default_value, bool"),
        ("properties.c", "int get_property(const char *key, int default_value)"),
        ("innates.c", "static int innate_char_race("),
        ("innates.c", "static int innate_unlock_level("),
        ("innates.c", "bool has_innate("),
        ("innates.c", "void assign_innates("),
        ("innates.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::innate_connections("),
        ("fight.c", "void update_dam_factors("),
        ("fight.c", "int melee_damage("),
        ("fight.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::melee_connections("),
    ])
)
combat_driver = r'''
void load_character_properties() {
    properties_count = load_properties(duris_properties);
    assert(properties_count > 0);
    qsort(duris_properties, properties_count, sizeof(property), property_comp);
    update_dam_factors();
}
void set_bulwark_property(float value) {
    auto *p = static_cast<property *>(bsearch("damage.reduction.guardians.bulwark",
        duris_properties, properties_count, sizeof(property), key_property_comp));
    assert(p); p->value = value; update_dam_factors();
}
void clear_character_properties() {
    for (int i = 0; i < properties_count; ++i) free(duris_properties[i].key);
    properties_count = 0;
}
double bulwark_melee(P_char attacker, P_char victim, bool bypass) {
    damage_calls = 0; delivered_damage = -1;
    int flags = PHSDAM_NOPOSITION | PHSDAM_NOENGAGE | PHSDAM_NOSHIELDS;
    if (bypass) flags |= PHSDAM_NOREDUCE;
    assert(melee_damage(attacker, victim, 1000, flags, nullptr, nullptr) == DAM_NONEDEAD);
    assert(damage_calls == 1);
    return delivered_damage;
}
'''
with tempfile.TemporaryDirectory(prefix="character-mechanics-", dir=build) as directory:
    work = Path(directory)
    (work / "lib").mkdir()
    shutil.copyfile(ROOT / "lib/creation_availability.cfg", work / "lib/creation_availability.cfg")
    shutil.copyfile(ROOT / "lib/duris.properties", work / "lib/duris.properties")
    combat = work / "combat.cpp"
    combat.write_text(combat_prelude + combat_bodies + combat_driver)
    binary = work / "harness"
    compile_command = [
        "g++", "-std=c++20", "-g", "-D__NO_MYSQL__", "-ffunction-sections", "-fdata-sections",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        "-I" + str(ROOT / "src"), "-I" + str(ROOT / "src/no_mysql"),
        *map(str, inputs), str(combat), "-Wl,--gc-sections", "-lbsd",
        "-o", str(binary),
    ]
    subprocess.run(compile_command, check=True)
    # Deliberately replace inherited overrides. No .env or running game is used.
    env = dict(os.environ, CHAOS_MUD="FALSE", CREATION_ALL_RACES="FALSE",
               CREATION_ALL_CLASSES="FALSE")
    result = subprocess.run([str(binary)], cwd=work, env=env, text=True, capture_output=True)
    print(result.stdout, end="")
    if result.returncode:
        print(result.stderr, end="")
    result.check_returncode()
    bindings = {row.split("\t")[1]: row.split("\t")[2]
                for row in result.stdout.splitlines() if row.startswith("CONNECTION\t")}
    for row in result.stdout.splitlines():
        if row.startswith("CONNECTION\t"):
            _, mechanic, _, path, line = row.split("\t")
            assert path in ("src/classes/innates.c", "src/combat/fight.c"), (mechanic, path)
            assert 0 < int(line) <= len((ROOT / path).read_text().splitlines()), (mechanic, line)
    sources = {str(path.relative_to(ROOT / "src")): path.read_text(errors="replace")
               for path in sorted((ROOT / "src").rglob("*"))
               if path.suffix in (".c", ".h", ".cpp", ".hpp", ".cc", ".hh", ".cxx", ".hxx")}
    errors = check_bulwark_sites(sources, bindings)
    assert not errors, "\n".join(errors)
    fight = sources["combat/fight.c"]
    effect = re.search(r"\t\tif \(has_innate\(victim, INNATE_GUARDIANS_BULWARK\).*?;", fight, re.S).group()
    mutations = [
        ("consumer_removed", "combat/fight.c", fight.replace(effect, "\t\t;", 1), "guardian_bulwark_effect"),
        ("marker_removed", "combat/fight.c", fight.replace("CHARACTER_MECHANIC_SITE(guardian_bulwark_effect);", "", 1), "unregistered site"),
        ("new_branch", "player/unregistered.c", "bool missed(P_char ch) { return has_innate(ch, INNATE_GUARDIANS_BULWARK); }\n", "unregistered site"),
        ("new_alias", "player/unregistered.h", "#define MY_INNATE INNATE_GUARDIANS_BULWARK\nbool missed(P_char ch) { return has_innate(ch, MY_INNATE); }\n", "unregistered site/alias"),
        ("nested_branch", "combat/fight.c", fight.replace(effect, effect.replace("\n\t\t\tdam", " { if (GET_RACE(victim) == RACE_HUMAN) return 0;\n\t\t\tdam") + " }", 1), "unsupported binding"),
    ]
    for name, path, changed, diagnostic in mutations:
        fixture = work / "mutations" / name / path
        fixture.parent.mkdir(parents=True, exist_ok=True)
        fixture.write_text(changed)
        mutated = dict(sources, **{path: fixture.read_text()})
        errors = check_bulwark_sites(mutated, bindings)
        assert any(diagnostic in error for error in errors), (name, errors)
    print("guardian.bulwark.reverse: PASS (missing consumer/marker, new file/alias, nested branch mutations)")
    print("Native executable SHA256:", hashlib.sha256(binary.read_bytes()).hexdigest())
    # The behavioral oracle must fail too when outcomes change. Build variants
    # under bin/; never edit/revert production files under a running test.
    for name, old, new in [
        ("effect_stubbed", "dam *= dam_factor[DF_GUARDIANS_BULWARK];", "dam *= 1.0;"),
        ("fallback_changed", 'get_property("damage.reduction.guardians.bulwark", 0.850)',
         'get_property("damage.reduction.guardians.bulwark", 0.250)'),
    ]:
        assert combat_bodies.count(old) == 1, name
        variant = work / "mutations" / name
        variant.mkdir(parents=True, exist_ok=True)
        variant_source, variant_binary = variant / "combat.cpp", variant / "harness"
        variant_source.write_text(combat_prelude + combat_bodies.replace(old, new) + combat_driver)
        command = [str(variant_source) if arg == str(combat) else
                   str(variant_binary) if arg == str(binary) else arg for arg in compile_command]
        subprocess.run(command, check=True)
        rejected = subprocess.run([str(variant_binary)], cwd=work, env=env, text=True, capture_output=True)
        assert rejected.returncode != 0 and "bulwark_melee(&attacker, &victim) == 850" in rejected.stderr, (name, rejected.stderr)
    print("guardian.bulwark.mutations: PASS (stubbed effect and changed fallback fail the native damage assertion)")
