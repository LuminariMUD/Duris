#!/usr/bin/env python3
"""Execute identity, specialization and Bulwark links; wider migration remains open."""

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
    signature = re.search(re.escape(signature).replace(r"\ ", r"\s+"), text).group()
    line = text[:text.index(signature)].count("\n") + 1
    return f'\n#line {line} "{path.relative_to(ROOT)}"\n' + extract_function(file, signature) + "\n"


def check_mechanic_sites(sources, bindings):
    """Migrated statements plus Bulwark/altar reverse checks, without baseline exemptions.

    This bounded tripwire accepts the actual marked statement forms. It rejects
    unsupported reshaping for review; executable assertions own the arithmetic.
    The remainder of the option-site migration is still explicitly outstanding.
    """
    obligations = {
        "guardian_bulwark_grant": ("classes/innates.c", r"ADD_CLASS_INNATE\(\s*INNATE_GUARDIANS_BULWARK\s*,\s*CLASS_WARRIOR\s*,\s*[^,;{}]+,\s*SPEC_GUARDIAN\s*\)\s*;"),
        "guardian_bulwark_factor": ("combat/fight.c", r'dam_factor\[DF_GUARDIANS_BULWARK\]\s*=\s*get_property\(\s*"damage\.reduction\.guardians\.bulwark"\s*,\s*[^;{}]+\)\s*;'),
        "guardian_bulwark_effect": ("combat/fight.c", r"if\s*\(\s*has_innate\(victim,\s*INNATE_GUARDIANS_BULWARK\)\s*&&\s*victim->equipment\[WEAR_SHIELD\]\s*\)\s*dam\s*\*=\s*dam_factor\[DF_GUARDIANS_BULWARK\]\s*;"),
        "specialization_entry": ("cmd/interp.c", r"CMD_N\(\s*CMD_SPECIALIZE\s*,\s*STAT_SLEEPING\s*\+\s*POS_PRONE\s*,\s*do_specialize\s*,\s*0\s*,\s*FALSE\s*\)\s*;"),
        "specialization_select": ("classes/specializations.c", r"ch->player\.spec\s*=\s*i\s*\+\s*1\s*;"),
        "specialization_refresh": ("classes/specializations.c", r"update_skills\(ch\)\s*;"),
        "specialization_capture": ("player/player_snapshot_capture.c", r"ADD_STATUS\(specialization,\s*ch->player\.spec\)\s*;"),
        "specialization_load": ("player/player_load_materialize.c", r"ch->player\.spec\s*=\s*loaded\s*;"),
        "innate_entry": ("cmd/interp.c", r"CMD_Y\(\s*CMD_INNATE\s*,\s*STAT_NORMAL\s*\+\s*POS_STANDING\s*,\s*do_innate\s*,\s*0\s*,\s*TRUE\s*\)\s*;"),
        "innate_dispatch": ("classes/innates.c", r'if\s*\(innates_data\[i\]\.func\)\s*\{\s*\(innates_data\[i\]\.func\)\(ch,\s*innate_args,\s*CMD_INNATE\);\s*\}\s*else\s*\{\s*send_to_char\("This innate is always active\.\\n",\s*ch\);\s*\}'),
        "unspecialization_entry_coral": ("specs/specs.assign.c", r"obj_index\[real_object0\(2203\)\]\.func\.obj\s*=\s*unspec_altar;"),
        "unspecialization_entry_blood": ("specs/specs.assign.c", r"obj_index\[real_object0\(12016\)\]\.func\.obj\s*=\s*unspec_altar;"),
        "unspecialization_altar": ("specs/specs.object.c", r"unspecialize\(ch,\s*obj\);"),
        "unspecialization_value": ("economy/tradeskill.c", r"if\s*\(proc\s*==\s*unspec_altar\)\s*return\s*-100000;"),
        "unspecialization_purchase": ("classes/specializations.c", r'if\s*\(!epic_transaction_submit\(ch,\s*-10,\s*epic_reason_type::specialization_purchase,\s*0,\s*EPIC_COMMAND_REQUIRE_FUNDS,\s*critical_source_site::command,\s*critical_deadline_class::interactive,\s*unspecialize_committed,\s*nullptr,\s*0\)\)\s*send_to_char\("The epic transaction service is busy\. Please try again\.\\n",\s*ch\);'),
        "unspecialization_commit": ("classes/specializations.c", r"ch->player\.spec\s*=\s*0;"),
        "unspecialization_refresh": ("classes/specializations.c", r"update_skills\(ch\);"),
        "unspecialization_forget": ("classes/specializations.c", r"forget_spells\(ch,\s*-1\);"),
        "epics_capture": ("player/player_snapshot_capture.c", r"ADD_STATUS\(epics,\s*ch->only\.pc->epics\);"),
        "epics_load": ("player/player_load_materialize.c", r"ch->only\.pc->epics\s*=\s*result\.domains\.epics;"),
        "epics_transaction": ("world/epic_transaction.c", r"balance\s*\+=\s*delta;"),
    }
    seen = set()
    errors = []
    symbols = re.compile(r"\b(?:INNATE_GUARDIANS_BULWARK|DF_GUARDIANS_BULWARK|unspec_altar|2203|12016)\b")
    # Macro stringification makes these names the same native bindings the
    # executable used, rather than a second editable table of function names.
    for mechanic, symbol in bindings.items():
        if re.fullmatch(r"[a-zA-Z_]\w*", symbol):
            definitions = 0
            for path, text in sources.items():
                if symbol not in text:
                    continue
                for body in function_bodies(text, rf"\b(?:int|bool|void)\s+{symbol}\s*\("):
                    # The offline pfile executable deliberately has no skill
                    # refresh. Exclude only its exact empty stub, not the file.
                    if (path == "account/pfile-stubs.c" and symbol == "update_skills"
                            and re.fullmatch(r"\{\s*\}", body)):
                        continue
                    definitions += 1
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
            if site == "specialization_load" and not re.search(
                    r"case player_status_field::specialization:\s*$", code[:marker.start()]):
                errors.append(f"{path}: specialization load mapped from wrong field")
        for token in symbols.finditer(code):
            if any(start <= token.start() < end for start, end in covered):
                continue
            line_start = code.rfind("\n", 0, token.start()) + 1
            # Exact existing numeric definitions are vocabulary, not effects.
            line = code[line_start:code.find("\n", token.end())]
            if ((path == "core/structs.h" and re.fullmatch(r"#define INNATE_GUARDIANS_BULWARK\s+\d+\s*", line)) or
                (path == "combat/damage.h" and re.fullmatch(r"#define DF_GUARDIANS_BULWARK\s+\d+\s*", line))):
                continue
            # Only the exact native definition/prototype header is vocabulary;
            # the function body remains subject to the same use-site scan.
            if (token.group() == "unspec_altar" and path in ("specs/specs.object.c", "world/specs.prototypes.h")
                    and re.fullmatch(r"int unspec_altar\(P_obj obj, P_char ch, int cmd, char \*(?:arg|argument)\);?\s*", line)):
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
    source("chaos_config.c"),
    source("safe_format.c"),
    source("epic_transaction.c"), source("epic_command.c"), source("critical_command.c"),
    HARNESS_STUBS,
]

# Compile these production bodies without unrelated world/combat services. The
# fixture observes the value delivered by melee_damage to raw_damage; it does
# not claim to exercise the latter's HP, death, ward or persistence machinery.
innates = source("innates.c").read_text()
properties = source("properties.c").read_text()
# Preserve every production name/callback slot. Active effects are outside this
# passive fixture; any attempt to invoke one fails instead of simulating success.
innate_table = re.search(r"const struct innate_data innates_data\[LAST_INNATE \+ 1\] = .*?\n};", innates, re.S).group()
active_callbacks = sorted(set(re.findall(r'\{ "[^"]+", (\w+) \}', innate_table)) - {"NULL"})
innate_stubs = "\n".join(f'void {name}(P_char, char *, int) {{ assert(false && "unexpected active innate callback"); }}'
                         for name in active_callbacks)
valuation_body = production_function("tradeskill.c", "int get_ival_from_proc(obj_proc_type proc)")
valued_callbacks = sorted(set(re.findall(r"\bproc\s*==\s*(\w+)", strip_comments(valuation_body))) - {"unspec_altar"})
valuation_stubs = "\n".join(f'int {name}(P_obj, P_char, int, char *) {{ assert(false && "valuation does not invoke object callbacks"); return 0; }}'
                            for name in valued_callbacks)
combat_prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "combat/damage.h"
#include "magic/spells.h"
#include "classes/necromancy.h"
#include "combat/chaos_config.h"
#include "classes/specializations.h"
#include "cmd/interp.h"
#include "player/character_mechanics.h"
#include "persistence/persistence_checkpoint.h"
#include <cassert>
#include <cctype>
#include <cmath>
#include <cstring>
#include <string>
#define PROPERTIES_FILE "lib/duris.properties"
#define MAX_PROPERTIES 3000
int properties_count;
Skill skills[MAX_SKILLS];
int GET_LVL_FOR_SKILL(P_char, int);
command_info cmd_info[MAX_CMD_LIST];
P_room world;
index_data object_prototypes[3]{};
P_index obj_index = object_prototypes;
int top_of_objt = 2;
int unspec_altar(P_obj, P_char, int, char *);
int mechanic_removed_affects, mechanic_stop_memorizing, mechanic_ledger_calls;
void mark_player_dirty_components(int, player_component_mask_t) {}
critical_submit_result critical_command_coordinator_submit(critical_command command) {
    epic_command_payload payload{};
    assert(epic_command_decode_payload(command, &payload));
    assert(payload.delta == -10 && payload.reason == epic_reason_type::specialization_purchase);
    ++mechanic_ledger_calls;
    return critical_submit_result::accepted;
}
void affect_remove(P_char ch, affected_type *removed) {
    auto **link = &ch->affected;
    while (*link && *link != removed) link = &(*link)->next;
    assert(*link && removed->type == TAG_MEMORIZE);
    *link = removed->next; delete removed; ++mechanic_removed_affects;
}
void stop_memorizing(P_char, memorization_stop_reason) { ++mechanic_stop_memorizing; }
extern const innate_data innates_data[];
std::string mechanic_output;
void send_to_char(const char *text, P_char) { mechanic_output += text; }
bool epic_summon(P_char, char *) { assert(false && "not a summon fixture"); return false; }
void do_list_innates(P_char, char *) { assert(false && "not a catalog fixture"); }
void mobsay(P_char, const char *) {} // Dialogue/quest side effects belong to the full-world journey.
bool is_linked_to(P_char, P_char, ush_int) { return false; } // No staff-consent teacher in this fixture.
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
    innate_stubs + "\n" + innate_table + "\n" + valuation_stubs + "\n" + valuation_body
    + properties[properties.index("struct property\n{"):properties.index("int key_property_comp(")]
    + innates[innates.index("#define ADD_RACIAL_INNATE"):innates.index("float regen_factor")]
    + innates[innates.index("char racial_innates["):innates.index("extern const struct race_names")]
    + production_function("interp.c", "const char *fill_words[]") + ";\n"
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
        ("innates.c", "bool can_use_innate("),
        ("innates.c", "void do_innate(P_char ch, char *arg, int cmd)"),
        ("innates.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::innate_connections("),
        ("fight.c", "void update_dam_factors("),
        ("fight.c", "int melee_damage("),
        ("fight.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::melee_connections("),
        ("interp.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::command_connections("),
        ("interp.c", "bool is_abbrev("),
        ("interp.c", "int search_block("),
        ("interp.c", "int fill_word("),
        ("interp.c", "void argument_interpreter("),
        ("guild.c", "void update_skills("),
        ("guild.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::training_connections("),
        ("memorize.c", "int forget_spells("),
        ("memorize.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::memorization_connections("),
        ("db.c", "int real_object0("), ("db.c", "int real_object(const int"),
        ("specs.object.c", "int unspec_altar("),
        ("specs.object.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::object_action_connections("),
        ("specs.assign.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::object_registration_connections("),
        ("tradeskill.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::object_value_connections("),
        ("player_snapshot_capture.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::status_capture_connections("),
        ("player_load_materialize.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::status_load_connections("),
    ])
)
interpreter = source("interp.c").read_text()
registration = re.search(r"CHARACTER_MECHANIC_SITE\(specialization_entry\);\s*CMD_N\([^;]+;", interpreter).group()
innate_registration = re.search(r"CHARACTER_MECHANIC_SITE\(innate_entry\);\s*CMD_Y\([^;]+;", interpreter).group()
combat_bodies += "\n" + interpreter[interpreter.index("#define CMD_N("):interpreter.index("#define CMD_CNF_Y(")]
combat_bodies += "\nvoid initialize_mechanic_commands() {\n" + registration + "\n" + innate_registration + "\n}\n"
assignments = source("specs.assign.c").read_text()
altar_registrations = [re.search(r"CHARACTER_MECHANIC_SITE\(unspecialization_entry_" + name +
                                r"\);\s*obj_index\[[^;]+;", assignments).group()
                       for name in ("coral", "blood")]
combat_bodies += '\nvoid initialize_mechanic_objects() {\nobject_prototypes[1].virtual_number = 2203;\nobject_prototypes[2].virtual_number = 12016;\n' + "\n".join(altar_registrations) + "\n}\n"
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
    compiler = [
        "g++", "-std=c++20", "-g", "-D__NO_MYSQL__", "-ffunction-sections", "-fdata-sections",
        "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        "-I" + str(ROOT / "src"), "-I" + str(ROOT / "src/no_mysql"),
    ]
    # The mutation suite changes one translation unit at a time. Compile the
    # unchanged units once within this private run, with the same sanitizer
    # flags; there is no cross-run cache or modification of the worktree.
    units = [*inputs, combat]
    objects = [work / f"unit-{index}.o" for index in range(len(units))]
    for unit, obj in zip(units, objects):
        subprocess.run([*compiler, "-c", str(unit), "-o", str(obj)], check=True)

    def link_harness(output, linked_objects):
        subprocess.run([*compiler, *map(str, linked_objects), "-Wl,--gc-sections",
                        "-lbsd", "-lcrypto", "-o", str(output)], check=True)

    def build_variant(original, replacement, output):
        obj = output.with_suffix(".o")
        subprocess.run([*compiler, "-c", str(replacement), "-o", str(obj)], check=True)
        linked = list(objects)
        linked[units.index(original)] = obj
        link_harness(output, linked)

    link_harness(binary, objects)
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
            path = str(Path(path).relative_to(ROOT)) if Path(path).is_absolute() else path
            assert path in ("src/classes/innates.c", "src/combat/fight.c", "src/cmd/interp.c",
                            "src/classes/specializations.c", "src/guild/guild.c",
                            "src/specs/specs.assign.c", "src/specs/specs.object.c", "src/classes/memorize.c",
                            "src/world/epic_transaction.c",
                            "src/economy/tradeskill.c",
                            "src/player/player_snapshot_capture.c", "src/player/player_load_materialize.c"), (mechanic, path)
            assert 0 < int(line) <= len((ROOT / path).read_text().splitlines()), (mechanic, line)
    sources = {str(path.relative_to(ROOT / "src")): path.read_text(errors="replace")
               for path in sorted((ROOT / "src").rglob("*"))
               if path.suffix in (".c", ".h", ".cpp", ".hpp", ".cc", ".hh", ".cxx", ".hxx")}
    errors = check_mechanic_sites(sources, bindings)
    assert not errors, "\n".join(errors)
    fight = sources["combat/fight.c"]
    effect = re.search(r"\t\tif \(has_innate\(victim, INNATE_GUARDIANS_BULWARK\).*?;", fight, re.S).group()
    mutations = [
        ("consumer_removed", "combat/fight.c", fight.replace(effect, "\t\t;", 1), "guardian_bulwark_effect"),
        ("marker_removed", "combat/fight.c", fight.replace("CHARACTER_MECHANIC_SITE(guardian_bulwark_effect);", "", 1), "unregistered site"),
        ("new_branch", "player/unregistered.c", "bool missed(P_char ch) { return has_innate(ch, INNATE_GUARDIANS_BULWARK); }\n", "unregistered site"),
        ("new_alias", "player/unregistered.h", "#define MY_INNATE INNATE_GUARDIANS_BULWARK\nbool missed(P_char ch) { return has_innate(ch, MY_INNATE); }\n", "unregistered site/alias"),
        ("nested_branch", "combat/fight.c", fight.replace(effect, effect.replace("\n\t\t\tdam", " { if (GET_RACE(victim) == RACE_HUMAN) return 0;\n\t\t\tdam") + " }", 1), "unsupported binding"),
        ("altar_overwrite", "specs/unregistered.c", "void overwrite() { obj_index[real_object0(2203)].func.obj = different_altar; }\n", "unregistered site/alias"),
        ("altar_alias", "specs/unregistered.h", "#define MY_ALTAR 12016\n", "unregistered site/alias"),
        ("altar_new_caller", "specs/unregistered.c", "int invoke(P_obj obj, P_char ch, int cmd, char *arg) { return unspec_altar(obj, ch, cmd, arg); }\n", "unregistered site/alias"),
    ]
    for name, path, changed, diagnostic in mutations:
        fixture = work / "mutations" / name / path
        fixture.parent.mkdir(parents=True, exist_ok=True)
        fixture.write_text(changed)
        mutated = dict(sources, **{path: fixture.read_text()})
        errors = check_mechanic_sites(mutated, bindings)
        assert any(diagnostic in error for error in errors), (name, errors)
    print("guardian.bulwark.reverse: PASS (missing consumer/marker, new file/alias, nested branch mutations)")
    print("unspecialization.reverse: PASS (new overwrite, numeric alias and caller rejected)")
    for name, path, old, new, diagnostic in [
        ("registration_removed", "cmd/interp.c",
         "CMD_N(CMD_SPECIALIZE, STAT_SLEEPING + POS_PRONE, do_specialize, 0, FALSE);", ";", "specialization_entry"),
        ("assignment_removed", "classes/specializations.c", "ch->player.spec = i + 1;", ";", "specialization_select"),
        ("refresh_removed", "classes/specializations.c", "update_skills(ch);", ";", "specialization_refresh"),
        ("capture_removed", "player/player_snapshot_capture.c", "ADD_STATUS(specialization, ch->player.spec);", ";", "specialization_capture"),
        ("load_removed", "player/player_load_materialize.c", "ch->player.spec = loaded;", ";", "specialization_load"),
        ("load_wrong_field", "player/player_load_materialize.c", "case player_status_field::specialization:",
         "case player_status_field::class_primary:", "load mapped from wrong field"),
        ("pfile_exclusion_changed", "account/pfile-stubs.c", "void update_skills(P_char) {}",
         "void update_skills(P_char ch) { ch->player.spec = 0; }", "native definition missing/conflicting"),
        ("altar_registration_removed", "specs/specs.assign.c", "obj_index[real_object0(2203)].func.obj = unspec_altar;",
         ";", "unspecialization_entry_coral"),
        ("altar_call_removed", "specs/specs.object.c", "unspecialize(ch, obj);", ";", "unspecialization_altar"),
        ("purchase_callback_removed", "classes/specializations.c", "unspecialize_committed, nullptr, 0)",
         "nullptr, nullptr, 0)", "unspecialization_purchase"),
        ("forget_removed", "classes/specializations.c", "forget_spells(ch, -1);", ";", "unspecialization_forget"),
        ("epics_materialize_removed", "player/player_load_materialize.c", "ch->only.pc->epics = result.domains.epics;",
         ";", "epics_load"),
    ]:
        assert old in sources[path], name
        changed = sources[path].replace(old, new, 1)
        fixture = work / "mutations" / name / path
        fixture.parent.mkdir(parents=True, exist_ok=True)
        fixture.write_text(changed)
        errors = check_mechanic_sites(dict(sources, **{path: fixture.read_text()}), bindings)
        assert any(diagnostic in error for error in errors), (name, errors)
    print("specialization.sites: PASS (removed registration/assignment/refresh/capture/load, wrong loaded field and changed exact exclusion rejected)")
    print("Native executable SHA256:", hashlib.sha256(binary.read_bytes()).hexdigest())
    # The behavioral oracle must fail too when outcomes change. Build variants
    # under bin/; never edit/revert production files under a running test.
    for name, old, new, diagnostic in [
        ("effect_stubbed", "dam *= dam_factor[DF_GUARDIANS_BULWARK];", "dam *= 1.0;",
         "bulwark_melee(&attacker, &victim) == 850"),
        ("fallback_changed", 'get_property("damage.reduction.guardians.bulwark", 0.850)',
         'get_property("damage.reduction.guardians.bulwark", 0.250)',
         "bulwark_melee(&attacker, &victim) == 850"),
        ("registration_unset", registration, "", "command registration missing or different handler"),
        ("innate_registration_unset", innate_registration, "", "innate.entry: command registration missing or different handler"),
        ("passive_changed_to_active", '{ "bulwark", NULL }', '{ "bulwark", do_innate_reflection }',
         "passive has an active callback"),
        ("passive_dispatch_stubbed", 'send_to_char("This innate is always active.\\n", ch);',
         'send_to_char("Nothing happened.\\n", ch);', 'mechanic_output == "This innate is always active.\\n"'),
        ("altar_registration_unset", altar_registrations[0], "", "object registration missing or different handler"),
        ("altar_valuation_changed", "if (proc == unspec_altar)\n\t\treturn -100000;",
         "if (proc == unspec_altar)\n\t\treturn 0;", "value(obj_index[slot].func.obj) == -100000"),
    ]:
        assert combat_bodies.count(old) == 1, name
        variant = work / "mutations" / name
        variant.mkdir(parents=True, exist_ok=True)
        variant_source, variant_binary = variant / "combat.cpp", variant / "harness"
        variant_source.write_text(combat_prelude + combat_bodies.replace(old, new) + combat_driver)
        build_variant(combat, variant_source, variant_binary)
        rejected = subprocess.run([str(variant_binary)], cwd=work, env=env, text=True, capture_output=True)
        assert rejected.returncode != 0 and diagnostic in rejected.stderr, (name, rejected.stderr)
    print("guardian.bulwark.mutations: PASS (stubbed effect and changed fallback fail the native damage assertion)")
    print("innate.dispatch.mutations: PASS (removed registration, active passive callback and stubbed dispatch rejected)")
    # Removing the actual refresh call must fail the learned/taught assertion,
    # even though the refresh function and connection still exist.
    for name, file, old, new, diagnostic in [
        ("refresh_not_called", "specializations.c", "update_skills(ch);", ";", "pc.skills[SKILL_GUARD].learned == 40"),
        ("purchase_callback_not_called", "specializations.c", "unspecialize_committed, nullptr, 0)", "nullptr, nullptr, 0)",
         "student.player.spec == 0 && pc.epics == 2"),
        ("forget_not_called", "specializations.c", "forget_spells(ch, -1);", ";", "mechanic_removed_affects == 2"),
        ("debit_not_applied", "epic_transaction.c", "balance += delta;", ";", "student.player.spec == 0 && pc.epics == 2"),
    ]:
        variant = work / "mutations" / name
        variant.mkdir(parents=True, exist_ok=True)
        variant_source, variant_binary = variant / (file + ".cpp"), variant / "harness"
        assert old in source(file).read_text(), name
        variant_source.write_text(source(file).read_text().replace(old, new, 1))
        build_variant(source(file), variant_source, variant_binary)
        rejected = subprocess.run([str(variant_binary)], cwd=work, env=env, text=True, capture_output=True)
        assert rejected.returncode != 0 and diagnostic in rejected.stderr, (name, rejected.stderr)
    print("specialization.mutations: PASS (removed registration and refresh call fail native assertions)")
    print("unspecialization.mutations: PASS (removed altar registration, purchase callback, debit and forgetting call fail native assertions)")
