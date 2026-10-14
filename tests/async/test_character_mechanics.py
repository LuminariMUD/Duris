#!/usr/bin/env python3
"""Execute migrated identity, specialization, multiclass and Revenant connections."""

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


def check_registration_sites(sources, observed):
    """Every initializer call must have native write provenance; new aliases fail.

    Registration declarations/macros and the three existing forwarding functions
    are machinery. All remaining uses must be actual observed initializer calls.
    This does not replace the wider selector/effect ownership migration.
    """
    names = (r"ADD_RACIAL_INNATE|ADD_CLASS_INNATE|SPELL_CREATE(?:_MSG|2)?|"
             r"SKILL_CREATE(?:_WITH_MESSAGES)?|SPEC_(?:SPELL|SKILL)_ADD|SPELL_ADD|"
             r"SKILL_ADD|TAG_CREATE(?:_WITH_MESSAGES)?|POISON_CREATE|"
             r"CMD_(?:N|Y|CNF_N|CNF_Y|GRT|SOC|TRIG)")
    token = re.compile(r"\b(?:" + names + r")\b")
    initializers = {
        "classes/skills.c": ("initialize_skills", "create_poisons", "create_tags"),
        "classes/epic_skills.c": ("create_epic_skills",),
        "classes/innates.c": ("assign_innates",),
        "cmd/interp.c": ("assign_command_pointers",),
    }
    forwards = {
        "SPELL_CREATE": "SPELL_CREATE_MSG(Name,Index,Beats,Targets,Spell_pointer,NULL,site);",
        "SKILL_CREATE_WITH_MESSAGES": "SKILL_CREATE(Name,Index,Type,site);",
        "SPELL_CREATE2": "SPELL_CREATE_MSG(Name,Index,Beats,Targets,Spell_pointer,Wear_off,site);",
    }
    delegates = {
        "SPELL_CREATE": "SPELL_CREATE_MSG", "SKILL_CREATE_WITH_MESSAGES": "SKILL_CREATE",
        "SPELL_CREATE2": "SPELL_CREATE_MSG", "TAG_CREATE": "SKILL_CREATE",
        "TAG_CREATE_WITH_MESSAGES": "SKILL_CREATE_WITH_MESSAGES", "POISON_CREATE": "SPELL_CREATE",
    }
    errors, accounted = [], set()
    for path, source_text in sources.items():
        code = strip_comments(source_text)
        code = re.sub(r'"(?:\\.|[^"\\])*"',
                      lambda match: re.sub(r"[^\n]", " ", match.group()), code)
        machinery, bodies = [], []
        for name in initializers.get(path, ()):
            matches = list(function_bodies(code, rf"\bvoid\s+{name}\s*\("))
            if len(matches) != 1:
                errors.append(f"{path}: missing/conflicting initializer {name}")
                continue
            begin = code.index(matches[0])
            bodies.append((begin, begin + len(matches[0])))
        if path in ("classes/skills.c", "classes/skills.h", "classes/innates.c"):
            for declaration in re.finditer(r"\bvoid\s+(?:" + names + r")\s*\([^;{}]*\)\s*(?:;|\{)", code):
                machinery.append(declaration.span())
        if path in ("classes/skills.c", "classes/innates.c", "cmd/interp.c"):
            for macro in re.finditer(r"^#define\s+(\w+)\((?:[^\n]*\\\n)*[^\n]*", code, re.M):
                if not token.fullmatch(macro[1]):
                    continue
                expected = [macro[1]] + ([delegates[macro[1]]] if macro[1] in delegates else [])
                actual = token.findall(macro.group())
                bare_tool_macro = macro[1] in ("SPELL_CREATE", "TAG_CREATE", "TAG_CREATE_WITH_MESSAGES", "POISON_CREATE")
                if actual != expected and not (bare_tool_macro and actual == [macro[1]]):
                    errors.append(f"{path}: unsupported registration macro {macro[1]}")
                machinery.append(macro.span())
        if path == "cmd/interp.c":
            machinery.extend(match.span() for match in re.finditer(
                r"^#undef\s+CMD_(?:N|Y|CNF_N|CNF_Y|GRT|SOC|TRIG)\s*$", code, re.M))
        for write in re.finditer(r"\bcmd_info\s*\[[^\]]+\]\s*\.\s*\w+\s*(?:=(?!=)|\+\+|--|\+=|-=)", code):
            if any(begin <= write.start() < end for begin, end in machinery):
                continue
            reset = re.match(r"cmd_info\[position\]\.command_pointer\s*=\s*NULL;", code[write.start():])
            if path == "cmd/interp.c" and reset and any(begin <= write.start() < end for begin, end in bodies):
                continue
            errors.append(f"{path}:{code.count(chr(10), 0, write.start())+1}: unobserved command write")
        if path == "classes/skills.c":
            # Exact existing disabled comprehension grants. A changed/removed
            # block needs review; no blanket preprocessor exclusion is used.
            disabled = list(re.finditer(r"^#if 0\n(.*?)^#endif", code, re.M | re.S))
            expected_disabled = ("SPELL_ADD(CLASS_SORCERER,5);SPELL_ADD(CLASS_CLERIC,4);"
                                 "SPELL_ADD(CLASS_DRUID,4);SPELL_ADD(CLASS_BARD,6);")
            if len(disabled) != 1 or re.sub(r"\s+", "", disabled[0][1]) != expected_disabled:
                errors.append(f"{path}: disabled comprehension grant exclusion changed")
            else:
                machinery.append(disabled[0].span())
            for name, expected in forwards.items():
                matches = list(function_bodies(code, rf"\bvoid\s+{name}\s*\("))
                if len(matches) != 1:
                    errors.append(f"{path}: missing/conflicting registration forwarder {name}")
                    continue
                body = matches[0]
                uses = list(token.finditer(body))
                if len(uses) != 1 or re.sub(r"\s+", "", body[uses[0].start():body.index(';', uses[0].start())+1]) != expected:
                    errors.append(f"{path}: changed registration forwarder {name}")
                begin = code.index(body)
                machinery.append((begin, begin + len(body)))
        offsets = [0] + [match.end() for match in re.finditer("\n", code)]
        lines = code.splitlines()
        points = {site: offsets[site[1]-1] + site[2]-1
                  for site in observed if site[0] == "src/" + path
                  and 0 < site[1] <= len(lines) and 0 < site[2] <= len(lines[site[1]-1])}
        for use in token.finditer(code):
            if any(begin <= use.start() < end for begin, end in machinery):
                continue
            end = code.find(';', use.end()) + 1
            sites = {site for site, position in points.items() if use.start() <= position < end}
            if (not any(begin <= use.start() < limit for begin, limit in bodies) or not sites
                    or not re.match(r"\s*\(", code[use.end():])):
                errors.append(f"{path}:{code.count(chr(10), 0, use.start())+1}: unobserved registration/alias {use.group()}")
            else:
                accounted.update(sites)
    for path, line, column in sorted(observed - accounted):
        errors.append(f"{path}:{line}:{column}: stale registration provenance")
    return errors


def native_definition_count(sources, symbol):
    count = 0
    for path, text in sources.items():
        if symbol not in text:
            continue
        text = text.replace("[[maybe_unused]]", "")
        for body in function_bodies(text, rf"\b(?:int|bool|void|ClassSkillInfo|account_racewar_admission)\s+{symbol}\s*\("):
            # This exact offline stub deliberately has no gameplay refresh.
            if (path == "account/pfile-stubs.c" and symbol == "update_skills"
                    and re.fullmatch(r"\{\s*\}", body)):
                continue
            count += 1
    return count


def command_definition_count(sources, symbol, no_mysql):
    """Resolve native command signatures, including ACMD and three backend arms."""
    count = 0
    for path, text in sources.items():
        if symbol not in text:
            continue
        text = text.replace("[[maybe_unused]]", "")
        if path in ("sql/sql.c", "combat/ctf.c", "economy/auction_houses.c"):
            # These existing owners select alternative implementations with the
            # same outer __NO_MYSQL__ guard. Resolve both builds independently.
            start = text.index("#ifdef __NO_MYSQL__\n")
            alternate = text.index("\n#else\n", start)
            finish = text.rindex("\n#endif")
            text = text[:start] + (text[start:alternate] if no_mysql else text[alternate:finish])
        signature = (rf"\bvoid\s+{symbol}\s*\(\s*(?:P_char|(?:struct\s+)?char_data\s*\*)[^,()]*,\s*char\s*\*[^,()]*,\s*int[^,()]*\)"
                     rf"|\bACMD\s*\(\s*{symbol}\s*\)")
        count += len(function_bodies(text, signature))
    return count


def check_mechanic_sites(sources, bindings):
    """Migrated statements and bounded Bulwark/altar/multiclass/crown reverse checks.

    This bounded tripwire accepts the actual marked statement forms. It rejects
    unsupported reshaping for review; executable assertions own the arithmetic.
    The remainder of the option-site migration is still explicitly outstanding.
    """
    obligations = {
        "ascend_attempt": ("cmd/actoth.c", r'if\s*\(!IS_NPC\(ch\)\)\s*\{\s*send_to_char\("&\+WThis is too powerful an enchantment for you to master\.\.\.&n\\n\\r",\s*ch\);\s*return;\s*\}'),
        "ascend_theurgist": ("cmd/actoth.c", r'if\s*\(IS_NPC\(ch\)\)\s*return;'),
        "descend_attempt": ("cmd/actoth.c", r'send_to_char\("This command has been disabled until further notice\.\\n", ch\);\s*return;'),
        "corpseform_attempt": ("classes/necromancy.c", r'send_to_char\("Temporarily disabled\.\\n", ch\);\s*return;'),
        "telnet_race_entry": ("account/nanny.c", r"select_race\(d, arg\);"),
        "telnet_class_entry": ("account/nanny.c", r"select_class\(d, arg\);"),
        "telnet_alignment_entry": ("account/nanny.c", r"select_alignment\(d, arg\);"),
        "race_affect_cleanup": ("magic/affects.c", (
            r"GET_RACE\(ch\) = af->modifier;",
            r"if\s*\(af->type == TAG_RACE_CHANGE && IS_SET\(af->flags, AFFTYPE_NOSAVE\) &&\s*af->modifier >= RACE_NONE && af->modifier <= LAST_RACE\)\s*ch->player\.time\.birth =\s*time\(NULL\) - racial_data\[af->modifier\]\.base_age \* SECS_PER_MUD_YEAR;",
        )),
        "death_affect_cleanup": ("combat/fight.c", (
            r"if\s*\(!\(af->flags & AFFTYPE_PERM\)\)\s*affect_remove\(ch, af\);\s*else if\s*\(af->type == TAG_MEMORIZE\)\s*af->flags &= ~MEMTYPE_FULL;",
            r"remove_death_affects\(ch\);",
        )),
        "revenant_entry": ("specs/specs.assign.c", r"obj_index\[real_object0\(22070\)\]\.func\.obj\s*=\s*revenant_helm;"),
        "revenant_value": ("economy/tradeskill.c", r"if\s*\(proc == revenant_helm\)\s*\{\s*return 225;\s*\}"),
        "object_periodic": ("world/db.c", (
            r"if\s*\(obj_index\[obj->R_num\]\.func\.obj\)\s*\(\*obj_index\[obj->R_num\]\.func\.obj\)\(obj, 0, CMD_PERIODIC, 0\);",
            r"add_event\(event_object_proc, PULSE_MOBILE \+ number\(-4, 4\), 0, 0, obj, 0, 0,\s*0\);",
        )),
        "revenant_apply": ("specs/specs.object.c", (
            r"af\.type = TAG_RACE_CHANGE;",
            r"af\.flags = AFFTYPE_NOSAVE \| AFFTYPE_NODISPEL \| AFFTYPE_NOAPPLY;",
            r"af\.modifier = GET_RACE\(ch\);",
            r"add_event\(event_revenant_crown, \(int\)\(0\.5 \* PULSE_VIOLENCE\), ch, 0, 0, 0, 0, 0\);",
            r"ch->player\.race = RACE_REVENANT;",
            r"ch->player\.time\.birth -= \(racial_data\[RACE_REVENANT\]\.base_age\) \* SECS_PER_MUD_YEAR;",
        )),
        "revenant_lifecycle": ("specs/specs.object.c", (
            r"add_event\(event_revenant_crown, \(int\)\(0\.5 \* PULSE_VIOLENCE\), ch, 0, 0, 0, 0, 0\);",
            r"ch->player\.race = af->modifier;",
            r"ch->player\.time\.birth -= \(racial_data\[GET_RACE\(ch\)\]\.base_age\) \* SECS_PER_MUD_YEAR;",
            r"affect_remove\(ch, af\);",
        )),
        "race_status_capture": ("player/player_snapshot_capture.c", (
            r"ADD_STATUS\(race, GET_RACE\(ch\)\);", r"ADD_STATUS\(birth_time, ch->player\.time\.birth\);",
        )),
        "race_status_load": ("player/player_load_materialize.c", (
            r"GET_RACE\(ch\) = loaded;", r"ch->player\.time\.birth = loaded;",
        )),
        "transient_race_capture": ("player/player_snapshot_capture.c", (
            r"if\s*\(affect->type == TAG_RACE_CHANGE &&\s*\(snapshot\.components & PLAYER_COMPONENT_STATUS\)\)",
            r"const auto birth =\s*time\(nullptr\) -\s*racial_data\[affect->modifier\]\.base_age \* SECS_PER_MUD_YEAR;",
            r"row\.unsigned_value = affect->modifier;",
            r"row\.signed_value = birth;",
            r"if\s*\(components & \(PLAYER_COMPONENT_STATUS \| PLAYER_COMPONENT_AFFECTS\)\)",
        )),
        "equipment_capture": ("player/player_snapshot_capture.c", r"const auto result = capture_items\(ch, snapshot\.items, budget,\s*components & PLAYER_COMPONENT_EQUIPMENT,\s*components & PLAYER_COMPONENT_INVENTORY,\s*true, true\);"),
        "inventory_capture": ("player/player_snapshot_capture.c", r"for\s*\(const obj_data \*object = owner->carrying; object;\s*object = object->next_content\)"),
        "equipment_load": ("player/player_load_items.c", r"character->equipment\[slot - 1\] = object;"),
        "inventory_load": ("player/player_load_items.c", r"object->loc\.carrying = character;"),
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
    symbols = re.compile(r"\b(?:INNATE_GUARDIANS_BULWARK|DF_GUARDIANS_BULWARK|unspec_altar|multiclass_proc|2203|12016|52904|revenant_helm|event_revenant_crown|REVENANT_CROWN_VNUM|22070|remove_death_affects)\b|\bworld\s*\[\s*real_room0\(\s*17\s*\)\s*\]\.funct")
    # Macro stringification makes these names the same native bindings the
    # executable used, rather than a second editable table of function names.
    for mechanic, (symbol, kind) in bindings.items():
        if kind == "callable" and re.fullmatch(r"[a-zA-Z_]\w*", symbol):
            definitions = native_definition_count(sources, symbol)
            if definitions != 1:
                errors.append(f"{mechanic}: native definition missing/conflicting: {symbol}")
    for path, text in sources.items():
        code = strip_comments(text)
        covered = []
        if path == "specs/specs.mobile.c":
            # Llyren's artifact locator hides this rareload object. It neither
            # changes identity nor admits a character to a transformation.
            # Exclude only this exact display filter; any policy change fails.
            locator = r"if\s*\(!IS_ARTIFACT\(t_obj\) \|\| obj_index\[t_obj->R_num\]\.virtual_number == 22070\)\s*\{\s*continue;\s*\}"
            matches = list(re.finditer(locator, code))
            bodies = list(function_bodies(code, r"\bint\s+llyren\s*\("))
            if len(matches) != 1 or len(bodies) != 1 or matches[0].group() not in bodies[0]:
                errors.append(f"{path}: crown locator exclusion changed")
            else:
                covered.append(matches[0].span())
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
            guard = None
            if site == "race_affect_cleanup" and index == 0:
                guard = r"if\s*\(af->type == TAG_RACE_CHANGE \|\| af->type == SPELL_DRACONIC_APOTHEOSIS\)\s*\{\s*$"
            if site == "revenant_lifecycle" and index == 0:
                guard = r"else if\s*\(armor != NULL && obj_index\[armor->R_num\]\.virtual_number == REVENANT_CROWN_VNUM\)\s*\{\s*$"
            if site == "object_periodic" and index == 1:
                guard = r"if\s*\(\(\*obj_index\[nr\]\.func\.obj\)\(obj, 0, CMD_SET_PERIODIC, 0\)\)\s*\{\s*$"
            if guard:
                prefix = re.search(guard, code[:marker.start()])
                if not prefix:
                    errors.append(f"{path}: {site} callback guard changed")
                else:
                    covered.append((prefix.start(), marker.start()))
            if site == "race_status_load" and not re.search(
                    rf"case player_status_field::{('race', 'birth_time')[index]}:\s*$", code[:marker.start()]):
                errors.append(f"{path}: race status load mapped from wrong field")
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
                (path == "combat/damage.h" and re.fullmatch(r"#define DF_GUARDIANS_BULWARK\s+\d+\s*", line)) or
                (path == "core/defines.h" and re.fullmatch(r"#define REVENANT_CROWN_VNUM\s+22070\s*", line))):
                continue
            # Only the exact native definition/prototype header is vocabulary;
            # the function body remains subject to the same use-site scan.
            if (token.group() == "unspec_altar" and path in ("specs/specs.object.c", "world/specs.prototypes.h")
                    and re.fullmatch(r"int unspec_altar\(P_obj obj, P_char ch, int cmd, char \*(?:arg|argument)\);?\s*", line)):
                continue
            if (token.group() == "multiclass_proc" and path in ("specs/specs.room.c", "world/specs.prototypes.h")
                    and re.fullmatch(r"int multiclass_proc\(int\s*(?:room)?, P_char(?: ch)?, int cmd, char \*arg\);?\s*", line)):
                continue
            if (token.group() == "revenant_helm" and path in ("specs/specs.object.c", "world/specs.prototypes.h")
                    and re.fullmatch(r"int revenant_helm\(P_obj(?: obj)?, P_char(?: ch)?, int(?: cmd)?, char \*\s*\);?\s*", line)):
                continue
            if (token.group() == "event_revenant_crown" and path == "specs/specs.object.c"
                    and re.fullmatch(r"void event_revenant_crown\(P_char ch, P_char\s*, P_obj obj, void \*\s*\)\s*", line)):
                continue
            if (token.group() == "remove_death_affects" and path == "combat/fight.c"
                    and re.fullmatch(r"static void remove_death_affects\(P_char ch\)\s*", line)):
                continue
            errors.append(f"{path}:{code.count(chr(10), 0, token.start()) + 1}: unregistered site/alias {token.group()}")
    for stem, state, handler in (("race", "CON_GET_RACE", "select_race"),
                                  ("class", "CON_GET_CLASS", "select_class"),
                                  ("alignment", "CON_ALIGN", "select_alignment")):
        code = strip_comments(sources["account/nanny.c"])
        pattern = (rf"case\s+{state}:\s*CHARACTER_MECHANIC_SITE\(telnet_{stem}_entry\);"
                   rf"\s*{handler}\(d, arg\);\s*break;")
        if len(re.findall(pattern, code)) != 1:
            errors.append(f"telnet.{stem}.entry: native login case changed")
    death = list(function_bodies(strip_comments(sources["combat/fight.c"]), r"\bvoid\s+die\s*\("))
    if len(death) != 1 or death[0].count("remove_death_affects(ch);") != 1:
        errors.append("death.affect.cleanup: missing death caller")
    else:
        body = death[0]
        cleanup = body.index("remove_death_affects(ch);")
        terminal = body.find("persistence_save_character_terminal(ch, RENT_DEATH);")
        if terminal < cleanup:
            errors.append("death.affect.cleanup: cleanup must precede terminal capture")
        # Keep the actual caller's existing arena/PC guards. A marker inside a
        # newly added conditional must not certify an unreachable cleanup call.
        lexical = re.sub(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'",
                         lambda match: " " * len(match.group()), body)
        scopes = []
        for position, character in enumerate(lexical[:cleanup]):
            if character == "{":
                scopes.append(position)
            elif character == "}":
                scopes.pop()
        guards = ("", "if(!CHAR_IN_ARENA(ch)||IS_NPC(ch))", "if(IS_PC(ch))")
        if len(scopes) != len(guards) or any(
                not re.sub(r"\s+", "", lexical[:position]).endswith(guard)
                for position, guard in zip(scopes, guards)):
            errors.append("death.affect.cleanup: death caller guards changed")
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
    source("hardcore_config.c"), source("racewar_admission.c"),
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
valued_callbacks = sorted(set(re.findall(r"\bproc\s*==\s*(\w+)", strip_comments(valuation_body))) - {"unspec_altar", "revenant_helm"})
valuation_stubs = "\n".join(f'int {name}(P_obj, P_char, int, char *) {{ assert(false && "valuation does not invoke object callbacks"); return 0; }}'
                            for name in valued_callbacks)
combat_prelude = r'''
#include "core/prototypes.h"
#include "core/mm.h"
#include "core/utils.h"
#include "net/comm.h"
#include "combat/damage.h"
#include "magic/spells.h"
#include "classes/necromancy.h"
#include "combat/chaos_config.h"
#include "classes/specializations.h"
#include "account/creation_availability_config.h"
#include "cmd/interp.h"
#include "net/ws_handlers.h"
#include "account/racewar_admission.h"
#include "player/character_mechanics.h"
#include "persistence/persistence_checkpoint.h"
#include "guild/assocs.h"
#include "item/trophy.h"
#include "classes/epic_skills.h"
#include "world/epic.h"
#include "world/events.h"
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
extern Skill skills[MAX_AFFECT_TYPES + 1];
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
index_data object_prototypes[4]{};
P_index obj_index = object_prototypes;
int top_of_objt = 3;
int unspec_altar(P_obj, P_char, int, char *);
int revenant_helm(P_obj, P_char, int, char *);
void event_revenant_crown(P_char, P_char, P_obj, void *);
void event_object_proc(P_char, P_char, P_obj, void *);
P_nevent current_nevent = nullptr;
int mechanic_crown_events, mechanic_object_events, mechanic_wait;
nevent_schedule_result add_event(event_func callback, int delay, P_char ch, P_char victim,
        P_obj obj, int flag, const void *data, int size) {
    assert(!victim && !flag && !data && !size);
    if (callback == event_revenant_crown) {
        assert(ch && !obj && delay == PULSE_VIOLENCE / 2);
        ++mechanic_crown_events;
    } else {
        assert(callback == event_object_proc && !ch && obj && delay == PULSE_MOBILE + 4);
        ++mechanic_object_events;
    }
    return {nevent_schedule_status::scheduled, {nullptr, 0}};
}
void CharWait(P_char, int delay) { mechanic_wait = delay; }
affected_type *affect_to_char(P_char ch, affected_type *affect) {
    assert(affect->type == TAG_RACE_CHANGE);
    auto *copy = new affected_type(*affect);
    copy->next = ch->affected;
    ch->affected = copy;
    return copy;
}
P_obj unequip_char(P_char ch, int slot, bool saving) {
    assert(!saving && ch->equipment[slot]);
    P_obj obj = ch->equipment[slot];
    ch->equipment[slot] = nullptr;
    obj->loc_p = 0;
    return obj;
}
void obj_to_char(P_obj obj, P_char ch) {
    obj->next_content = ch->carrying;
    ch->carrying = obj;
    obj->loc.carrying = ch;
    obj->loc_p = LOC_CARRIED;
}
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
mm_ds mechanic_affect_pool{};
mm_ds *dead_affect_pool = &mechanic_affect_pool;
void mm_release(mm_ds *pool, void *value) {
    assert(pool == dead_affect_pool);
    delete static_cast<affected_type *>(value);
    ++mechanic_removed_affects;
}
// The real removal algorithm owns unlinking and race/birth changes. These
// services bound derived stats, notifications, linked affects and the scheduler.
void all_affects(P_char, int) {}
void balance_affects(P_char) {}
int char_light(P_char) { return 0; }
int room_light(int, int) { return 0; }
void gmcp_char_affects(P_char) {}
void unlink_char_affect(P_char, affected_type *) { std::abort(); }
void unlink_char_obj_affect(P_char, affected_type *) { std::abort(); }
void event_short_affect(P_char, P_char, P_obj, void *) { std::abort(); }
void event_web_spray(P_char, P_char, P_obj, void *) { std::abort(); }
void disarm_char_nevents(P_char, event_func_type) { std::abort(); }
nevent_handle nevent_handle_from_event(P_nevent) { std::abort(); }
nevent_cancel_result nevent_cancel(nevent_handle) { std::abort(); }
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
        ("innates.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::innate_registration_connections("),
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
        ("affects.c", "void affect_remove("),
        ("affects.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::affect_cleanup_connections("),
        ("fight.c", "static void remove_death_affects("),
        ("fight.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::death_connections("),
        ("specs.object.c", "void event_revenant_crown("),
        ("specs.object.c", "int revenant_helm("),
        ("specs.object.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::revenant_connections("),
        ("specs.object.c", "std::span<const character_mechanics::TransitionConnection> character_mechanics::revenant_transitions("),
        ("affects.c", "bool affected_by_spell("),
        ("db.c", "void event_object_proc("),
        ("db.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::object_periodic_connections("),
        ("player_load_items.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::item_load_connections("),
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
combat_bodies += (
    production_function("actoth.c", "enum class ascend_kind : int") + ";\n"
    + production_function("actoth.c", "struct ascend_context") + ";\n"
    + "\nvoid ascend_committed(P_char, bool, const epic_command_result &, unsigned int, const uint8_t *, size_t) { std::abort(); }\n"
    + "P_char FindTeacher(P_char) { std::abort(); }\n"
    + "void do_old_descend(P_char, char *, int) { std::abort(); }\n"
    + "bool isCarved(P_obj);\n"
    + production_function("actoth.c", "void ascend_theurgist(")
    + production_function("actoth.c", "void do_ascend(")
    + production_function("actoth.c", "void do_descend(")
    + production_function("necromancy.c", "void spell_corpseform(")
    + production_function("necromancy.c", "void event_corpseform_wearoff(")
    + production_function("actoth.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::ascension_connections(")
    + production_function("necromancy.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::corpseform_connections(")
)
interpreter = source("interp.c").read_text()
command_initializer = production_function("interp.c", "void assign_command_pointers(void)")
command_callbacks = set(re.findall(
    r"\bCMD_(?:N|Y|CNF_N|CNF_Y|GRT)\([^,]+,[^,]+,\s*(\w+)",
    strip_comments(command_initializer))) | {"do_action", "do_not_here"}
command_machinery = (
    "\nstatic std::vector<character_mechanics::CommandWrite> command_registration_writes;\n"
    + production_function("interp.c", "const char *command[MAX_CMD] =") + ";\n"
    + production_function("interp.c", "static void record_command(")
    + interpreter[interpreter.index("#define CMD_N("):interpreter.index("void assign_command_pointers(void)")]
)
# All command IDs/guards and the real initializer run. Unexercised command bodies
# abort; the production definition check below separately resolves their owners.
existing_implementations = {str(path): path.read_text() for path in inputs}
existing_implementations["fixture"] = combat_prelude + combat_bodies
command_stubs = "\n".join(
    f'void {name}(P_char, char *, int) {{ std::abort(); }}'
    for name in sorted(command_callbacks)
    if native_definition_count(existing_implementations, name) == 0)
# Providers reference the journal before the initializer body appears.
combat_bodies = command_machinery + "\n" + command_stubs + "\n" + combat_bodies
combat_bodies += "\n" + command_initializer + "\nvoid initialize_mechanic_commands() { assign_command_pointers(); }\n"
assignments = source("specs.assign.c").read_text()
altar_registrations = [re.search(r"CHARACTER_MECHANIC_SITE\(unspecialization_entry_" + name +
                                r"\);\s*obj_index\[[^;]+;", assignments).group()
                       for name in ("coral", "blood")]
crown_registration = re.search(r"CHARACTER_MECHANIC_SITE\(revenant_entry\);\s*obj_index\[[^;]+;", assignments).group()
combat_bodies += '\nvoid initialize_mechanic_objects() {\nobject_prototypes[1].virtual_number = 2203;\nobject_prototypes[2].virtual_number = 12016;\nobject_prototypes[3].virtual_number = 22070;\n' + "\n".join([*altar_registrations, crown_registration]) + "\n}\n"
room_registrations = [re.search(r"CHARACTER_MECHANIC_SITE\(multiclass_room_" + name + r"\);\s*world\[[^;]+;", assignments).group()
                      for name in ("test", "temple")]
combat_bodies += '\nvoid initialize_mechanic_rooms() {\nmechanic_rooms[1].number = 17;\nmechanic_rooms[2].number = 52904;\n' + "\n".join(room_registrations) + "\n}\n"
# Only dispatch identity/fences are tested here. Actual Telnet selections and
# JSON creation bodies remain world/command behavior obligations.
nanny_source = source("nanny.c").read_text()
ws_source = source("ws_handlers.c").read_text()
login_cases = [re.search(r"case " + state + r":\s*CHARACTER_MECHANIC_SITE\(telnet_" + stem +
                        r"_entry\);\s*" + handler + r"\(d, arg\);\s*break;", nanny_source).group()
               for stem, state, handler in (("race", "CON_GET_RACE", "select_race"),
                                             ("class", "CON_GET_CLASS", "select_class"),
                                             ("alignment", "CON_ALIGN", "select_alignment"))]
ws_table = re.search(r'static const character_mechanics::JsonHandler websocket_handlers\[\] = \{.*?\n\};', ws_source, re.S).group()
ws_callbacks = sorted(set(re.findall(r'\{ "[^"\n]+", (ws_cmd_\w+) \}', ws_table)))
combat_bodies += "\nint mechanic_login_selection, mechanic_json_selection, mechanic_json_fallback;\n"
combat_bodies += 'account_racewar_admission account_check_racewar_admission(P_desc, int, bool, bool) { std::abort(); }\n'
combat_bodies += 'bool account_commit_character_admission(P_desc, P_char, bool, account_racewar_admission *) { std::abort(); }\n'
combat_bodies += 'void init_char(P_char) { std::abort(); }\n'
combat_bodies += production_function("account.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::admission_connections(")

for number, name in enumerate(("select_race", "select_class", "select_alignment"), 1):
    combat_bodies += f"void {name}(P_desc, char *) {{ mechanic_login_selection = {number}; }}\n"
for name in ws_callbacks:
    body = ("mechanic_json_selection = 1;" if name == "ws_cmd_chargen_options" else
            "mechanic_json_selection = 2;" if name == "ws_cmd_create_character" else "std::abort();")
    combat_bodies += f"void {name}(P_desc, cJSON *) {{ {body} }}\n"
combat_bodies += ("void write_to_q(const char *, struct txt_q *, const int) { ++mechanic_json_fallback; }\n"
                  "void nanny(P_desc d, char *arg) { switch (STATE(d)) {\n" +
                  "\n".join(login_cases) + "\ndefault: std::abort(); } }\n" + ws_table + "\n" +
                  production_function("ws_handlers.c", "static ws_cmd_handler find_websocket_handler(") +
                  production_function("ws_handlers.c", "void ws_handle_command(") +
                  production_function("nanny.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::telnet_creation_connections(") +
                  production_function("ws_handlers.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::websocket_creation_connections("))

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
# Execute the complete production skill initializer, retaining its callback
# addresses. These callback bodies abort if invoked: this case proves registration,
# grant provenance and native table contents, not every spell's behavior.
skill_source = source("skills.c").read_text()
skill_initializers = "\n".join(production_function(file, signature) for file, signature in [
    ("skills.c", "void initialize_skills()\n{"), ("skills.c", "void create_poisons()\n{"),
    ("skills.c", "void create_tags()\n{"), ("epic_skills.c", "void create_epic_skills()\n{"),
])
skill_callbacks = {}
for call in re.finditer(r'\b(SPELL_CREATE(?:_MSG|2)?|POISON_CREATE)\(\s*"[^"\n]*"(.*?)\);',
                        strip_comments(skill_initializers), re.S):
    args = call[2].lstrip(",").split(",")
    callback = args[1 if call[1] == "POISON_CREATE" else 3].strip()
    assert re.fullmatch(r"[A-Za-z_]\w*", callback), callback
    if callback != "NULL":
        skill_callbacks[callback] = "affected_type *" if call[1] == "POISON_CREATE" else "P_obj"
skill_callback_stubs = "\n".join(
    f'void {name}(int, P_char, char *, int, P_char, {last}) {{ std::abort(); }}'
    for name, last in sorted(skill_callbacks.items()) if name != "spell_corpseform")
skill_registration_source = (
    skill_source[skill_source.index('#include "core/defines.h"'):skill_source.index('int numSkills;')]
        .replace('#ifndef _DE_', '')
    + '\n#include "core/prototypes.h"\n#include "classes/skills.h"\n#include "player/character_mechanics.h"\n#include <cstdlib>\n'
    + 'Skill skills[MAX_AFFECT_TYPES + 1];\nint numSkills;\nint SortedSkills[MAX_AFFECT_TYPES + 1];\n'
    + skill_callback_stubs + '\n'
    + skill_source[skill_source.index('static std::vector<character_mechanics::GrantWrite> skill_registration_writes;'):
                   skill_source.index('\n#endif\n\nvoid create_poisons();')]
    + '\nvoid create_poisons();\nvoid create_tags();\nvoid create_epic_skills();\n'
    + skill_initializers
    + production_function("skills.c", "std::span<const character_mechanics::MechanicConnection> character_mechanics::skill_registration_connections(")
)

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
    registrations = work / "registrations.cpp"
    registrations.write_text(skill_registration_source)
    units = [*inputs, combat, registrations]
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
                            "src/classes/specializations.c", "src/classes/skills.c", "src/guild/guild.c",
                            "src/account/nanny.c", "src/net/ws_handlers.c", "src/account/creation_availability_config.c",
                            "src/account/account.c", "src/account/racewar_admission.c", "src/classes/necromancy.c",
                            "src/specs/specs.assign.c", "src/specs/specs.object.c", "src/classes/memorize.c",
                            "src/world/epic_transaction.c",
                            "src/economy/tradeskill.c",
                            "src/cmd/actoth.c", "src/cmd/actwiz.c", "src/specs/specs.room.c",
                            "src/magic/affects.c", "src/world/db.c", "src/world/epic.c",
                            "src/core/utility.c", "src/core/constant.c", "src/item/trophy.c",
                            "src/economy/currency_transaction.c",
                            "src/player/player_snapshot_capture.c", "src/player/player_load_materialize.c",
                            "src/player/player_load_items.c"), (mechanic, path)
            assert 0 < int(line) <= len((ROOT / path).read_text().splitlines()), (mechanic, line)
    sources = {str(path.relative_to(ROOT / "src")): path.read_text(errors="replace")
               for path in sorted((ROOT / "src").rglob("*"))
               if path.suffix in (".c", ".h", ".cpp", ".hpp", ".cc", ".hh", ".cxx", ".hxx")}
    observed = {tuple([row.split("\t")[1], *map(int, row.split("\t")[2:])])
                for row in result.stdout.splitlines() if row.startswith(("GRANT_SITE\t", "COMMAND_SITE\t"))}
    registration_errors = check_registration_sites(sources, observed)
    assert not registration_errors, "\n".join(registration_errors)
    for name, snippet in (
        ("alias", "#define HIDDEN_GRANT SKILL_ADD\n"),
        ("uninvoked", "void uninvoked() { SKILL_ADD(CLASS_WARRIOR, 1, 100); }\n"),
        ("command_alias", "#define HIDDEN_COMMAND CMD_N\n"),
        ("uninvoked_command", "void uninvoked() { CMD_N(CMD_KICK, 0, do_kick, 1, TRUE); }\n"),
    ):
        changed = dict(sources, **{"classes/unregistered.h": snippet})
        assert any("unobserved registration/alias" in error
                   for error in check_registration_sites(changed, observed)), name
    changed = dict(sources, **{"cmd/unregistered.c": "void overwrite() { cmd_info[CMD_KICK].minimum_level = 0; }\n"})
    assert any("unobserved command write" in error for error in check_registration_sites(changed, observed))
    removed = dict(sources)
    removed["classes/skills.c"] = removed["classes/skills.c"].replace(
        'SKILL_CREATE("flame mastery", SKILL_FLAME_MASTERY, TAR_MENTAL);', ';', 1)
    assert any("stale registration provenance" in error
               for error in check_registration_sites(removed, observed))
    print(f"ability.registration.reverse: PASS ({len(observed)} native caller sites; new alias/caller and stale call detected)")
    missing_callbacks = [name for name in skill_callbacks if native_definition_count(sources, name) != 1]
    assert not missing_callbacks, ("missing/conflicting registered callback implementations", missing_callbacks)
    for no_mysql in (False, True):
        missing = [name for name in sorted(command_callbacks) if command_definition_count(sources, name, no_mysql) != 1]
        assert not missing, ("missing/conflicting command implementations", no_mysql, missing)
    missing_callback = dict(sources)
    callback_owner = "magic/magic.c"
    original_callback = "void spell_draconic_apotheosis("
    assert original_callback in missing_callback[callback_owner]
    missing_callback[callback_owner] = missing_callback[callback_owner].replace(
        original_callback, "void unregistered_apotheosis(", 1)
    assert native_definition_count(missing_callback, "spell_draconic_apotheosis") == 0
    missing_command = dict(sources)
    missing_command["combat/training_dummy.c"] = missing_command["combat/training_dummy.c"].replace(
        "ACMD(do_training_dummy)", "ACMD(unregistered_training_dummy)", 1)
    assert command_definition_count(missing_command, "do_training_dummy", True) == 0
    print(f"ability.implementations: PASS ({len(skill_callbacks)} spell/poison and {len(command_callbacks)} command callback symbols resolve to production definitions; removed implementation rejected; effect behavior is separate)")
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
        ("crown_alias", "specs/unregistered.h", "#define MY_CROWN 22070\n", "unregistered site/alias"),
        ("crown_overwrite", "specs/unregistered.c", "void overwrite() { obj_index[real_object0(22070)].func.obj = other; }\n", "unregistered site/alias"),
        ("crown_new_caller", "specs/unregistered.c", "void invoke(P_char ch) { event_revenant_crown(ch, 0, 0, 0); }\n", "unregistered site/alias"),
        ("death_new_alias", "combat/unregistered.h", "#define MY_DEATH_CLEANUP remove_death_affects\n", "unregistered site/alias"),
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
    print("revenant.reverse: PASS (new crown alias, overwrite and lifecycle caller rejected)")
    for name, path, old, new, diagnostic in [
        ("login_case_changed", "account/nanny.c", "case CON_GET_RACE:", "case CON_GET_CLASS:", "native login case changed"),
        ("death_call_removed", "combat/fight.c", "remove_death_affects(ch);", ";", "missing death caller"),
        ("death_call_guarded", "combat/fight.c", "CHARACTER_MECHANIC_SITE(death_affect_cleanup);\n\t\t\tremove_death_affects(ch);",
         "if (false) { CHARACTER_MECHANIC_SITE(death_affect_cleanup);\n\t\t\tremove_death_affects(ch); }", "death caller guards changed"),
        ("death_capture_too_early", "combat/fight.c", "CHARACTER_MECHANIC_SITE(death_affect_cleanup);\n\t\t\tremove_death_affects(ch);",
         "persistence_save_character_terminal(ch, RENT_DEATH);\n\t\t\tCHARACTER_MECHANIC_SITE(death_affect_cleanup);\n\t\t\tremove_death_affects(ch);", "cleanup must precede terminal capture"),
        ("crown_direct_reversal_removed", "specs/specs.object.c", "ch->player.race = af->modifier;", ";", "revenant_lifecycle"),
        ("crown_direct_birth_removed", "specs/specs.object.c", "ch->player.time.birth -= (racial_data[GET_RACE(ch)].base_age) * SECS_PER_MUD_YEAR;", ";", "revenant_lifecycle"),
        ("crown_locator_changed", "specs/specs.mobile.c", "virtual_number == 22070",
         "virtual_number == 22071", "crown locator exclusion changed"),
        ("crown_retention_guard", "specs/specs.object.c", "virtual_number == REVENANT_CROWN_VNUM",
         "virtual_number != REVENANT_CROWN_VNUM", "callback guard changed"),
        ("race_load_wrong_field", "player/player_load_materialize.c", "case player_status_field::race:",
         "case player_status_field::racewar:", "race status load mapped from wrong field"),
        ("birth_capture_removed", "player/player_snapshot_capture.c", "ADD_STATUS(birth_time, ch->player.time.birth);",
         ";", "race_status_capture"),
        ("transient_race_projection_removed", "player/player_snapshot_capture.c", "row.unsigned_value = affect->modifier;",
         ";", "transient_race_capture"),
        ("equipment_attachment_removed", "player/player_load_items.c", "character->equipment[slot - 1] = object;",
         ";", "equipment_load"),
        ("inventory_attachment_removed", "player/player_load_items.c", "object->loc.carrying = character;",
         ";", "inventory_load"),
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
    # Keep one compiled negative case per distinct behavioral failure mechanism.
    # All positive lifecycle assertions and the fast source mutations above remain.
    # Native cases also directly remove command/object/room bindings, mutate cells,
    # omit provenance and introduce conflicts; those do not need extra compilations.
    # Build variants under bin/ without editing the live worktree.
    for name, old, new, diagnostic in [
        ("crown_original_race_lost", "af.modifier = GET_RACE(ch);", "af.modifier = RACE_REVENANT;",
         "wearer.affected && wearer.affected->modifier == RACE_ORC"),
        ("generic_birth_restore_omitted", "ch->player.time.birth =\n\t\t\t\ttime(NULL) - racial_data[af->modifier].base_age * SECS_PER_MUD_YEAR;",
         ";", "subject.player.time.birth >= now - 15 * SECS_PER_MUD_YEAR"),
        ("effect_stubbed", "dam *= dam_factor[DF_GUARDIANS_BULWARK];", "dam *= 1.0;",
         "bulwark_melee(&attacker, &victim) == 850"),
        ("fallback_changed", 'get_property("damage.reduction.guardians.bulwark", 0.850)',
         'get_property("damage.reduction.guardians.bulwark", 0.250)',
         "bulwark_melee(&attacker, &victim) == 850"),
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
    print("state/lifecycle.mutations: PASS (lost original form identity and omitted birth restoration rejected)")
    # Completion and debit are distinct from an effect or property failure.
    for name, file, old, new, diagnostic in [
        ("purchase_callback_not_called", "specializations.c", "unspecialize_committed, nullptr, 0)", "nullptr, nullptr, 0)",
         "student.player.spec == 0 && pc.epics == 2"),
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
    print("transaction.mutations: PASS (detached completion callback and omitted debit rejected)")
