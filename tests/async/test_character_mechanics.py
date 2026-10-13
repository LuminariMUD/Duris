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
        "multiclass_command": ("cmd/interp.c", r"CMD_N\(CMD_MULTICLASS,\s*STAT_NORMAL\s*\+\s*POS_PRONE,\s*do_multiclass,\s*0,\s*FALSE\);"),
        "multiclass_room_test": ("specs/specs.assign.c", r"world\[real_room0\(17\)\]\.funct\s*=\s*multiclass_proc;"),
        "multiclass_room_temple": ("specs/specs.assign.c", r"world\[real_room0\(52904\)\]\.funct\s*=\s*multiclass_proc;"),
        "multiclass_select": ("specs/specs.room.c", r"ch->player\.secondary_class\s*=\s*1\s*<<\s*\(i\s*-\s*1\);"),
        "multiclass_reset": ("specs/specs.room.c", r"do_start\(ch,\s*cmd\);"),
        "multiclass_restore": ("specs/specs.room.c", r"do_restore\(ch,\s*GET_NAME\(ch\),\s*0\);"),
        "multiclass_forget": ("specs/specs.room.c", r"forget_spells\(ch,\s*-1\);"),
        "multiclass_refund": ("specs/specs.room.c", r"refund_epic_skills\(ch\);"),
        "multiclass_trophies": ("specs/specs.room.c", r"clear_zone_trophy\(ch\);"),
        "multiclass_newbie_skills": ("cmd/actwiz.c", r"NewbySkillSet\(ch,\s*\(nomsg\s*!=\s*CMD_MULTICLASS\)\s*\?\s*TRUE\s*:\s*FALSE\);"),
        "multiclass_refund_commit": ("world/epic.c", r'if\s*\(!epic_transaction_submit\(ch,\s*point_refund,\s*epic_reason_type::epic_skill_refund,\s*0,\s*0,\s*critical_source_site::command,\s*critical_deadline_class::interactive,\s*epic_skill_refund_committed,\s*&context,\s*sizeof\(context\)\)\)\s*send_to_char\("The epic transaction service is busy\. Please try again\.\\n",\s*ch\);'),
        "multiclass_wallet_refund": ("world/epic.c", r'if\s*\(!currency_transaction_submit_wallet_value\(\s*ch,\s*context\.coins,\s*currency_reason_type::refund,\s*context\.points,\s*critical_source_site::recovery,\s*critical_deadline_class::recovery,\s*epic_coin_refund_committed,\s*nullptr,\s*0\)\)\s*send_to_char\(\s*"Your coin refund could not be queued\. Please contact staff\.\\n",\s*ch\);'),
        "multiclass_primary_cap": ("core/utility.c", r'float pri_mod\s*=\s*get_property\("skill\.cap\.multi\.mod\.primarySkill",\s*100\.0\);'),
        "multiclass_secondary_cap": ("core/utility.c", r'float sec_mod\s*=\s*get_property\("skill\.cap\.multi\.mod\.secondarySkill",\s*95\.0\);'),
        "multiclass_skill_data": ("core/utility.c", r"if\s*\(IS_PC\(ch\)\s*&&\s*\(sec_class\s*>=\s*0\)\)"),
        "multiclass_hitpoints": ("magic/affects.c", r"class_mod\s*=\s*MAX\(class_mod,\s*class_hitpoints\[flag2idx\(ch->player\.secondary_class\)\]\);"),
        "class_hitpoint_factors": ("magic/affects.c", r"class_hitpoints\[i\]\s*=\s*get_property\(buf,\s*1\.0\);"),
        "racial_constitution": ("world/db.c", r"stat_factor\[i\]\.Con\s*=\s*\(sh_int\)get_property\(buf,\s*100\.\);"),
        "skills_capture": ("player/player_snapshot_capture.c", r"snapshot\.skills\.push_back\(\{\s*index,\s*static_cast<uint8_t>\(skill\.learned\),\s*static_cast<uint8_t>\(skill\.taught\)\s*\}\);"),
        "affects_capture": ("player/player_snapshot_capture.c", r"snapshot\.affects\.push_back\(std::move\(row\)\);"),
        "trophies_capture": ("player/player_snapshot_capture.c", r"snapshot\.trophies\.push_back\(\{\s*trophy\.zone_number,\s*trophy\.exp\s*\}\);"),
        "skills_load": ("player/player_load_materialize.c", r"for\s*\(const player_skill_snapshot &entry\s*:\s*result\.snapshot\.skills\)"),
        "affects_load": ("player/player_load_materialize.c", r"for\s*\(const player_affect_snapshot &entry\s*:\s*result\.snapshot\.affects\)"),
        "trophies_load": ("player/player_load_materialize.c", r"for\s*\(const player_trophy_snapshot &entry\s*:\s*result\.snapshot\.trophies\)"),
        "status_capture": ("player/player_snapshot_capture.c", r"if\s*\(\(components & PLAYER_COMPONENT_STATUS\)\s*&&\s*!capture_status\(ch,\s*snapshot,\s*budget,\s*save_intent\)\)\s*return player_snapshot_capture_result::limit_exceeded;"),
        "status_load": ("player/player_load_materialize.c", (
            r"for\s*\(const player_snapshot_string &entry\s*:\s*result\.snapshot\.status_strings\)\s*if\s*\(!apply_string\(ch,\s*entry\)\)\s*return false;",
            r"for\s*\(const player_snapshot_integer &entry\s*:\s*result\.snapshot\.status_integers\)\s*apply_integer\(ch,\s*entry,\s*&hit_difference\);",
            r"for\s*\(size_t index = 0; index < result\.snapshot\.conditions\.size\(\); \+\+index\)\s*ch->specials\.conditions\[index\] = result\.snapshot\.conditions\[index\];",
            r"for\s*\(size_t index = 0; index < result\.snapshot\.quest_values\.size\(\); \+\+index\)\s*\*quest\[index\] = result\.snapshot\.quest_values\[index\];",
        )),
    }
    state_fields = {
        "class_secondary": "ch->player.secondary_class", "level": "GET_LEVEL(ch)",
        "base_mana": "ch->points.base_mana", "base_hit": "ch->points.base_hit",
        "base_vitality": "ch->points.base_vitality", "experience": "GET_EXP(ch)",
        "prestige": "ch->only.pc->prestige", "guild_status": "ch->specials.guild_status",
        "copper": "GET_COPPER(ch)", "silver": "GET_SILVER(ch)",
        "gold": "GET_GOLD(ch)", "platinum": "GET_PLATINUM(ch)",
    }
    wallet_fields = ("copper", "silver", "gold", "platinum")
    obligations["multiclass_status_capture"] = ("player/player_snapshot_capture.c", tuple(
        rf"ADD_STATUS\({field},\s*{re.escape(value)}\);" for field, value in state_fields.items()))
    obligations["multiclass_status_load"] = ("player/player_load_materialize.c", tuple(
        re.escape("ch->player.level" if field == "level" else value) + r"\s*=\s*" +
        (rf"result\.domains\.wallet\[{wallet_fields.index(field)}\];" if field in wallet_fields else "loaded;")
        for field, value in state_fields.items()))
    obligations = {key: (owner, (patterns,) if isinstance(patterns, str) else patterns)
                   for key, (owner, patterns) in obligations.items()}
    seen = set()
    errors = []
    symbols = re.compile(r"\b(?:INNATE_GUARDIANS_BULWARK|DF_GUARDIANS_BULWARK|unspec_altar|multiclass_proc|2203|12016|52904)\b|\bworld\s*\[\s*real_room0\(\s*17\s*\)\s*\]\.funct")
    # Macro stringification makes these names the same native bindings the
    # executable used, rather than a second editable table of function names.
    for mechanic, (symbol, kind) in bindings.items():
        if kind == "callable" and re.fullmatch(r"[a-zA-Z_]\w*", symbol):
            definitions = 0
            for path, text in sources.items():
                if symbol not in text:
                    continue
                for body in function_bodies(text, rf"\b(?:int|bool|void|ClassSkillInfo)\s+{symbol}\s*\("):
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
            owner, statements = obligations[site]
            matches = [(i, match) for i, statement in enumerate(statements)
                       if (match := re.match(r"\s*(" + statement + r")", code[marker.end():]))]
            if path != owner or len(matches) != 1:
                errors.append(f"{path}:{code.count(chr(10), 0, marker.start()) + 1}: missing/unsupported binding for {site}")
                continue
            index, match = matches[0]
            if (site, index) in seen:
                errors.append(f"{path}: duplicate site {site}")
            seen.add((site, index))
            covered.append((marker.end(), marker.end() + match.end()))
            if site == "specialization_load" and not re.search(
                    r"case player_status_field::specialization:\s*$", code[:marker.start()]):
                errors.append(f"{path}: specialization load mapped from wrong field")
            if site == "multiclass_status_load" and tuple(state_fields)[index] not in wallet_fields and not re.search(
                    rf"case player_status_field::{tuple(state_fields)[index]}:\s*$", code[:marker.start()]):
                errors.append(f"{path}: multiclass status load mapped from wrong field")
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
            if (token.group() == "multiclass_proc" and path in ("specs/specs.room.c", "world/specs.prototypes.h")
                    and re.fullmatch(r"int multiclass_proc\(int\s*(?:room)?, P_char(?: ch)?, int cmd, char \*arg\);?\s*", line)):
                continue
            errors.append(f"{path}:{code.count(chr(10), 0, token.start()) + 1}: unregistered site/alias {token.group()}")
    for site, (_, statements) in obligations.items():
        for index in range(len(statements)):
            if (site, index) not in seen:
                errors.append(f"{site}[{index}]: missing implementation site")
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
    source("hardcore_config.c"),
    source("currency_transaction.c"), source("currency_command.c"),
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
#include "account/creation_availability_config.h"
#include "cmd/interp.h"
#include "player/character_mechanics.h"
#include "persistence/persistence_checkpoint.h"
#include "guild/assocs.h"
#include "item/trophy.h"
#include "classes/epic_skills.h"
#include "world/epic.h"
#include "world/hardcore_config.h"
#include "economy/currency_transaction.h"
#include "persistence/persistence_mode.h"
#include "player/player_save_pipeline.h"
#include "player/player_snapshot_repository.h"
#include "flatfile/flatfile_player_repository.h"
#include "sql/sql_player.h"
#include <cassert>
#include <cctype>
#include <cstdarg>
#include <cmath>
#include <cstring>
#include <string>
#define PROPERTIES_FILE "lib/duris.properties"
#define MAX_PROPERTIES 3000
int properties_count;
Skill skills[MAX_SKILLS];
int GET_LVL_FOR_SKILL(P_char, int);
command_info cmd_info[MAX_CMD_LIST];
room_data mechanic_rooms[3]{};
P_room world = mechanic_rooms;
extern const int top_of_world = 2;
extern const class_names class_names_table[];
extern const race_names race_names_table[];
extern const racial_data_type racial_data[];
extern stat_data stat_factor[LAST_RACE + 1];
float class_hitpoints[CLASS_COUNT + 1], combat_by_class[CLASS_COUNT + 1][2];
float combat_by_race[LAST_RACE + 1][3], pulse_all, shield_combat_mult, shield_combat_tank_mult;
// Guild storage, kit delivery, restore presentation and refund persistence are
// boundaries. Reset/skill/refund calculations below are production functions.
Guild::Guild() = default;
Guild::~Guild() = default;
int mechanic_kit_requests, mechanic_restores, mechanic_coin_refund, mechanic_saves;
void load_obj_to_newbies(P_char ch) {
    assert(ch->player.level == 1 && ch->player.secondary_class == 0);
    ++mechanic_kit_requests;
}
void do_restore(P_char ch, char *, int) {
    assert(ch->player.level == 1 && ch->player.secondary_class == CLASS_CLERIC && ch->player.spec == 0);
    ++mechanic_restores;
}
bool mechanic_stage_coin_refund = true;
bool insert_money_pickup(int pid, int value) { assert(pid == 42); mechanic_coin_refund += value; return mechanic_stage_coin_refund; }
bool do_save_silent(P_char ch, int) {
    assert(ch->player.secondary_class == CLASS_CLERIC && ch->only.pc->skills[SKILL_EPIC_STRENGTH].learned == 0);
    ++mechanic_saves; return true;
}
void gmcp_char_vitals(P_char) {}
bool persistence_log_submit(const char *) { return true; }
const char *get_account_name_safe(P_char) { return "mechanics_account"; }
persistence_mode persistence_mode_get() { std::abort(); }
const char *persistence_mode_flatfile_root() { std::abort(); }
player_save_apply_result flatfile_bank_delta_apply(const std::string &, const std::string &,
        int8_t, const std::array<int64_t, 4> &, flatfile_authority_operation *, std::string *) { std::abort(); }
player_save_apply_result bank_delta_repository_apply_from_pool(const bank_delta_snapshot &) { std::abort(); }
player_save_submit_result persistence_writer_submit(persistence_job_kind, uint64_t, size_t, persistence_job_write_fn) { std::abort(); }
player_save_pipeline_result player_save_pipeline_request(P_char, player_component_mask_t, int, int) { std::abort(); }
index_data object_prototypes[3]{};
P_index obj_index = object_prototypes;
int top_of_objt = 2;
int unspec_altar(P_obj, P_char, int, char *);
int mechanic_removed_affects, mechanic_stop_memorizing, mechanic_ledger_calls;
void mark_player_dirty_components(int, player_component_mask_t) {}
critical_submit_result critical_command_coordinator_submit(critical_command command) {
    epic_command_payload payload{};
    assert(epic_command_decode_payload(command, &payload));
    assert((payload.delta == -10 && payload.reason == epic_reason_type::specialization_purchase) ||
           (payload.delta == 300 && payload.reason == epic_reason_type::epic_skill_refund));
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
void send_to_char_f(P_char, const char *format, ...) {
    char message[MAX_STRING_LENGTH]; va_list args;
    va_start(args, format); vsnprintf(message, sizeof(message), format, args); va_end(args);
    mechanic_output += message;
}
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
    + production_function("epic_skills.c", "epic_reward epic_rewards[] =") + ";\n"
    + production_function("epic.c", "struct epic_skill_refund_context") + ";\n"
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
        ("handler.c", "bool isname(const char *str, const char *namelist)"),
        ("limits.c", "void clear_title("),
        ("limits.c", "int vitality_limit("),
        ("memorize.c", "bool praying_class("),
        ("actwiz.c", "void NewbySkillSet("),
        ("actwiz.c", "static void do_start_impl("),
        ("actwiz.c", "void do_start(P_char ch, int nomsg)"),
        ("epic.c", "void epic_coin_refund_committed("),
        ("epic.c", "void epic_skill_refund_committed("),
        ("epic.c", "void refund_epic_skills("),
        ("trophy.c", "void clear_zone_trophy("),
        ("db.c", "void update_stat_data("),
        ("affects.c", "void update_damage_data("),
        ("affects.c", "int calculate_hitpoints2("),
        ("actoth.c", "void do_multiclass("),
        ("specs.room.c", "int multiclass_proc("),
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
        ("specs.assign.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::room_registration_connections("),
        ("actoth.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::multiclass_command_connections("),
        ("specs.room.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::multiclass_connections("),
        ("specs.room.c", "std::span<const character_mechanics::TransitionConnection> character_mechanics::multiclass_transitions("),
        ("actwiz.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::reset_connections("),
        ("affects.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::hitpoint_connections("),
        ("db.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::racial_stat_connections("),
        ("epic.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::epic_refund_connections("),
        ("trophy.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::trophy_connections("),
        ("db.c", "int real_room0("), ("db.c", "int real_room("),
    ])
)
interpreter = source("interp.c").read_text()
registration = re.search(r"CHARACTER_MECHANIC_SITE\(specialization_entry\);\s*CMD_N\([^;]+;", interpreter).group()
innate_registration = re.search(r"CHARACTER_MECHANIC_SITE\(innate_entry\);\s*CMD_Y\([^;]+;", interpreter).group()
multiclass_registration = re.search(r"CHARACTER_MECHANIC_SITE\(multiclass_command\);\s*CMD_N\([^;]+;", interpreter).group()
combat_bodies += "\n" + interpreter[interpreter.index("#define CMD_N("):interpreter.index("#define CMD_CNF_Y(")]
combat_bodies += "\nvoid initialize_mechanic_commands() {\n" + registration + "\n" + innate_registration + "\n" + multiclass_registration + "\n}\n"
assignments = source("specs.assign.c").read_text()
altar_registrations = [re.search(r"CHARACTER_MECHANIC_SITE\(unspecialization_entry_" + name +
                                r"\);\s*obj_index\[[^;]+;", assignments).group()
                       for name in ("coral", "blood")]
combat_bodies += '\nvoid initialize_mechanic_objects() {\nobject_prototypes[1].virtual_number = 2203;\nobject_prototypes[2].virtual_number = 12016;\n' + "\n".join(altar_registrations) + "\n}\n"
room_registrations = [re.search(r"CHARACTER_MECHANIC_SITE\(multiclass_room_" + name + r"\);\s*world\[[^;]+;", assignments).group()
                      for name in ("test", "temple")]
combat_bodies += '\nvoid initialize_mechanic_rooms() {\nmechanic_rooms[1].number = 17;\nmechanic_rooms[2].number = 52904;\n' + "\n".join(room_registrations) + "\n}\n"
combat_driver = r'''
void load_character_properties() {
    properties_count = load_properties(duris_properties);
    assert(properties_count > 0);
    qsort(duris_properties, properties_count, sizeof(property), property_comp);
    update_dam_factors();
}
void set_character_property(const char *key, float value) {
    auto *p = static_cast<property *>(bsearch(key,
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
    bindings = {row.split("\t")[1]: tuple(row.split("\t")[2:4])
                for row in result.stdout.splitlines() if row.startswith("CONNECTION\t")}
    for row in result.stdout.splitlines():
        if row.startswith("CONNECTION\t"):
            _, mechanic, _, kind, path, line = row.split("\t")
            assert kind in ("callable", "value"), (mechanic, kind)
            path = str(Path(path).relative_to(ROOT)) if Path(path).is_absolute() else path
            assert path in ("src/classes/innates.c", "src/combat/fight.c", "src/cmd/interp.c",
                            "src/classes/specializations.c", "src/guild/guild.c",
                            "src/specs/specs.assign.c", "src/specs/specs.object.c", "src/classes/memorize.c",
                            "src/world/epic_transaction.c",
                            "src/economy/tradeskill.c",
                            "src/cmd/actoth.c", "src/cmd/actwiz.c", "src/specs/specs.room.c",
                            "src/magic/affects.c", "src/world/db.c", "src/world/epic.c",
                            "src/core/utility.c", "src/item/trophy.c",
                            "src/economy/currency_transaction.c",
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
        ("multiclass_overwrite", "specs/unregistered.c", "void overwrite() { world[real_room0(17)].funct = different_room; }\n", "unregistered site/alias"),
        ("multiclass_alias", "specs/unregistered.h", "#define MY_MULTIROOM 52904\n", "unregistered site/alias"),
        ("multiclass_new_caller", "specs/unregistered.c", "int invoke(int room, P_char ch, int cmd, char *arg) { return multiclass_proc(room, ch, cmd, arg); }\n", "unregistered site/alias"),
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
    print("multiclass.reverse: PASS (new room overwrite, temple alias and caller rejected)")
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
        ("secondary_capture_removed", "player/player_snapshot_capture.c", "ADD_STATUS(class_secondary, ch->player.secondary_class);",
         ";", "multiclass_status_capture"),
        ("secondary_load_wrong_field", "player/player_load_materialize.c", "case player_status_field::class_secondary:",
         "case player_status_field::class_primary:", "multiclass status load mapped from wrong field"),
        ("skills_load_removed", "player/player_load_materialize.c", "CHARACTER_MECHANIC_SITE(skills_load);\n\tfor (const player_skill_snapshot &entry : result.snapshot.skills)",
         "CHARACTER_MECHANIC_SITE(skills_load);\n\tfor (const player_skill_snapshot &entry : std::vector<player_skill_snapshot>{})", "skills_load"),
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
        ("multiclass_start_omitted", "do_start(ch, cmd);", ";",
         "ch->player.level == 1 && ch->player.secondary_class == CLASS_CLERIC"),
        ("multiclass_refund_omitted", "refund_epic_skills(ch);", ";",
         "pc.skills[SKILL_EPIC_STRENGTH].learned == 0"),
        ("multiclass_clock_not_restored", "ch->player.time.logon = logon;", ";",
         "student.player.time.played == 12345 && student.player.time.logon == logon"),
        ("multiclass_hp_ignores_secondary",
         "class_mod = MAX(class_mod, class_hitpoints[flag2idx(ch->player.secondary_class)]);", ";",
         "calculate_hitpoints2(&student) == warrior_hp"),
        ("multiclass_room_unregistered", room_registrations[1], "", "room registration missing or different handler"),
        ("multiclass_command_unregistered", multiclass_registration, "", "multiclass.command: command registration missing or different handler"),
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
        ("secondary_skill_delay_removed", "utility.c", "required_level = sec_rlevel + 5;", "required_level = sec_rlevel;",
         "SKILL_DATA_ALL(&student, SKILL_MEDITATE).rlevel[0] == 6"),
        ("wallet_refund_credit_missing", "currency_transaction.c",
         "GET_PLATINUM(character) = static_cast<int>(result.wallet.amount[3]);", ";",
         "GET_PLATINUM(&student) == scenario.expected_platinum"),
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
    print("multiclass.mutations: PASS (removed reset/refund/wallet credit/clock retention, secondary skill delay and secondary HP contribution rejected)")
