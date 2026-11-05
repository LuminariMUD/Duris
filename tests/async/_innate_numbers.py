"""Give a native harness the shared innate numbers its extracted handlers now call.

The passive innates moved their numbers into small functions beside the handlers. A harness
that extracts one of those handlers needs the function as well, so with_innate_numbers()
extracts the real ones it finds called in the harness text and places each ahead of its first
use. Nothing is stubbed, so a harness still tests the production arithmetic.
"""
import re

from _paths import extract_function, source

# Helper to its file, callees first where one helper calls another.
HELPERS = {
    "hasted_bard_pulse": "classes/bard.c",
    "echo_song_level": "classes/bard.c",
    "echo_chance": "classes/bard.c",
    "echo_roll": "classes/bard.c",
    "echo_delay": "classes/bard.c",
    "intercept_luck_roll": "classes/drannak.c",
    "intercept_attack_roll": "classes/drannak.c",
    "intercept_duration": "classes/drannak.c",
    "resurrection_roll": "classes/innates.c",
    "resurrection_hit_points": "classes/innates.c",
    "resurrection_lag": "classes/innates.c",
    "embrace_death_first_share": "classes/innates.c",
    "embrace_death_second_share": "classes/innates.c",
    "embrace_death_third_share": "classes/innates.c",
    "embrace_death_first_bonus": "classes/innates.c",
    "embrace_death_second_bonus": "classes/innates.c",
    "embrace_death_third_bonus": "classes/innates.c",
    "embrace_death_check_interval": "classes/innates.c",
    "anti_evil_alignment": "classes/innates.c",
    "anti_evil_hit_points": "classes/innates.c",
    "anti_evil_fade": "classes/innates.c",
    "anti_evil_fade_interval": "classes/innates.c",
    "decrepify_curse": "classes/innates.c",
    "troll_burned_regeneration": "classes/innates.c",
    "rrakkma_max_steps": "classes/innates.c",
    "rrakkma_step_percent": "classes/innates.c",
    "hatred_check_delay": "classes/innates.c",
    "hatred_pulse_modifier": "classes/innates.c",
    "holy_crusade_healing": "classes/innates.c",
    "holy_crusade_cap": "classes/innates.c",
    "unholy_alliance_charm_duration": "classes/necromancy.c",
    "improved_wormhole_decay": "classes/psionics.c",
    "improved_wormhole_bonus": "classes/psionics.c",
    "ophidian_farsee_level": "cmd/actinf.c",
    "ophidian_invisible_level": "cmd/actinf.c",
    "flee_vitality_cost": "cmd/actoff.c",
    "flee_mount_vitality_cost": "cmd/actoff.c",
    "dragonmind_roll": "cmd/actoff.c",
    "dragonmind_steal_divisor": "cmd/actoff.c",
    "trample_knight_multiplier": "cmd/actoff.c",
    "perception_track_bonus": "cmd/track.c",
    "farsee_track_bonus": "cmd/track.c",
    "ophidian_track_penalty": "cmd/track.c",
    "track_sense_chance": "cmd/track.c",
    "elemental_power_level": "combat/dam_mods.c",
    "magical_reduction_mod": "combat/dam_mods.c",
    "magic_vulnerability_mod": "combat/dam_mods.c",
    "troll_burn_duration": "combat/dam_mods.c",
    "fire_race_cold_mod": "combat/dam_mods.c",
    "sacrilegious_holy_factor": "combat/dam_mods.c",
    "vuln_cold_slow_save": "combat/dam_mods.c",
    "vuln_cold_slow_duration": "combat/dam_mods.c",
    "warcallers_fury_bonus": "combat/dam_mods.c",
    "warcallers_fury_max_steps": "combat/dam_mods.c",
    "warcallers_fury_step": "combat/dam_mods.c",
    "intercept_attack_share": "combat/fight.c",
    "rapier_dirk_chance": "combat/fight.c",
    "rapier_dirk_more_hits_roll": "combat/fight.c",
    "rapier_dirk_more_hits": "combat/fight.c",
    "two_daggers_riposte_roll": "combat/fight.c",
    "spell_absorb_threshold": "combat/fight.c",
    "spell_absorb_damage_roll": "combat/fight.c",
    "spell_absorb_damage_divisor": "combat/fight.c",
    "aura_absorb_healing": "combat/fight.c",
    "aura_absorb_cap": "combat/fight.c",
    "acid_blood_min_hit": "combat/fight.c",
    "acid_blood_dodge_base": "combat/fight.c",
    "acid_blood_dodge_divisor": "combat/fight.c",
    "acid_blood_roll": "combat/fight.c",
    "acid_blood_damage": "combat/fight.c",
    "infernal_fury_shield": "combat/fight.c",
    "touch_vamp_share": "combat/fight.c",
    "rrakkma_ac_step": "combat/fight.c",
    "frightening_presence_chance": "combat/fight.c",
    "battle_frenzy_roll": "combat/fight.c",
    "battle_frenzy_damage": "combat/fight.c",
    "weapon_immunity_damage": "combat/fight.c",
    "weapon_immunity_unarmed_level": "combat/fight.c",
    "leap_chance_floor": "combat/fight.c",
    "leap_chance_top": "combat/fight.c",
    "leap_chance": "combat/fight.c",
    "giant_avoidance_factor": "combat/fight.c",
    "groundfighting_dodge_share": "combat/fight.c",
    "entrapment_chance": "combat/grapple.c",
    "entrapment_lag": "combat/grapple.c",
    "archery_haste_speed": "combat/range.c",
    "archery_blur_speed": "combat/range.c",
    "undead_fealty_gap": "core/utility.c",
    "quick_thinking_percent": "core/utility.c",
    "quick_thinking_roll": "core/utility.c",
    "haste_stat_save_bonus": "core/utility.c",
    "two_handed_sword_mastery_rating": "core/utility.c",
    "evasion_remove_chance": "core/utility.c",
    "evasion_snake_roll": "core/utility.c",
    "evasion_dragon_roll": "core/utility.c",
    "dual_wielding_master_hitroll": "magic/affects.c",
    "weapon_master_hitroll": "magic/affects.c",
    "hammer_master_damroll": "magic/affects.c",
    "blade_master_damroll": "magic/affects.c",
    "gamblers_luck_bonus": "magic/affects.c",
    "two_daggers_pulse": "magic/affects.c",
    "command_aura_hit_dam": "magic/affects.c",
    "command_aura_avenger_regen": "magic/affects.c",
    "command_aura_stat_max": "magic/affects.c",
    "command_aura_lightbringer_armor": "magic/affects.c",
    "command_aura_fear_save": "magic/affects.c",
    "restoration_other_share": "magic/smagic.c",
    "elemental_power_save_change": "magic/smagic.c",
    "elemental_power_area_factor": "magic/smagic.c",
    "wellness_improved_bonus": "magic/smagic.c",
    "lesser_mending_improved_bonus": "magic/smagic.c",
    "mending_improved_bonus": "magic/smagic.c",
    "greater_mending_cure_level": "magic/smagic.c",
    "wildmagic_roll": "net/sparser.c",
    "wildmagic_control_roll": "net/sparser.c",
    "wildmagic_health_roll": "net/sparser.c",
    "wildmagic_health_change": "net/sparser.c",
    "wildmagic_bystander_roll": "net/sparser.c",
    "haste_cast_time_share": "net/sparser.c",
    "seadog_speed_bonus": "ships/ship_utils.c",
    "seadog_sale_multiplier": "ships/ship_utils.c",
    "calming_delay": "world/handler.c",
    "calming_level_gap": "world/handler.c",
    "calming_gap_roll": "world/handler.c",
    "calming_notarget_percent": "world/handler.c",
    "calming_notarget_roll": "world/handler.c",
    "calming_command_roll": "world/handler.c",
    "calming_chance_bonus": "world/handler.c",
    "calming_switch_threshold": "world/handler.c",
    "calming_switch_penalty": "world/handler.c",
    "vuln_sun_damage": "world/handler.c",
    "regeneration_sleeping_multiple": "world/limits.c",
    "regeneration_resting_multiple": "world/limits.c",
    "eyeless_map_range": "world/map.c",
    "forest_map_cap": "world/map.c",
    "perception_map_bonus": "world/map.c",
    "dayblind_infravision_bonus": "world/map.c",
    "dayblind_underdark_range": "world/map.c",
}


def _definition(name):
    text = source(HELPERS[name]).read_text(errors="replace")
    head = re.search(rf"^(?:static )?[\w:]+ {name}\([^;\n]*\)\n{{", text, re.M).group(0)
    return extract_function(HELPERS[name], head)


def _insert_before_use(text, name, definition):
    """Above the top-level declaration holding the first call of `name`."""
    first = re.search(rf"\b{name}\(", text).start()
    heads = [m.start() for m in re.finditer(r"^[^\s{}#/]", text[:first], re.M)]
    at = heads[-1] if heads else 0
    return text[:at] + definition + "\n" + text[at:]


def with_innate_numbers(text, define_rolls=True):
    called = True
    while called:
        called = False
        for name in HELPERS:
            if re.search(rf"\b{name}\(", text) and not re.search(
                    rf"^(?:static |extern )?[\w:]+ {name}\([^;\n]*\)\s*(?:\{{|$)", text, re.M):
                text = _insert_before_use(text, name, _definition(name))
                called = True
    if "Rolls" in text and "abilities/abilities.h" not in text:
        text = '#include "abilities/abilities.h"\n' + text
    if define_rolls and "live_rolls" in text and "const Rolls live_rolls" not in text:
        rolls = "const Rolls live_rolls = { dice, number };\n"
        if not re.search(r"^int dice\(int \w+, int \w+\)\s*\{", text, re.M):
            rolls = extract_function("utility.c", "int dice(int num, int size)") + "\n" + rolls
        first = text.index("live_rolls")
        heads = [m.start() for m in re.finditer(r"^[^\s{}#/]", text[:first], re.M)]
        text = text[:heads[-1]] + rolls + text[heads[-1]:]
    return text
