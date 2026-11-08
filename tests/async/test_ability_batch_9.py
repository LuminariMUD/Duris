#!/usr/bin/env python3
"""Shared ability numbers, batch 9: illusionist and necromancy spells.

Builds src/abilities/abilities.c and the real RNG with every shared and facts function of
sillusionist.c and necromancy.c, under sanitizers. Each converted roll keeps its
pre-conversion expression below as the oracle: under the same seeds it must give the same
value, leave the RNG at the same draw and fall inside the range its page shows. Every page is
built at every level for several casters: it must never roll, and every line must fit 79
columns.
"""
import re
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT, extract_function, source
from contract_text import contains
from _source_contract import function_bodies, strip_comments

ILLUSION = "classes/sillusionist.c"
NECRO = "classes/necromancy.c"

SPELLS = [line.split() for line in """
SPELL_ASPHYXIATE asphyxiate classes/sillusionist.c
SPELL_BOULDER boulder classes/sillusionist.c
SPELL_CLONE_FORM clone_form classes/sillusionist.c
SPELL_DELIRIUM delirium classes/sillusionist.c
SPELL_DETECT_ILLUSION detect_illusion classes/sillusionist.c
SPELL_DRAGON dragon classes/sillusionist.c
SPELL_DREAM_TRAVEL dream_travel classes/sillusionist.c
SPELL_FLICKER flicker classes/sillusionist.c
SPELL_HAMMER hammer classes/sillusionist.c
SPELL_ILLUSIONARY_WALL illusionary_wall classes/sillusionist.c
SPELL_IMPRISON imprison classes/sillusionist.c
SPELL_INSECTS insects classes/sillusionist.c
SPELL_MASK mask classes/sillusionist.c
SPELL_NONEXISTENCE nonexistence classes/sillusionist.c
SPELL_OBSCURING_MIST obscuring_mist classes/sillusionist.c
SPELL_PHANTOM_ARMOR phantom_armor classes/sillusionist.c
SPELL_REFLECTION reflection classes/sillusionist.c
SPELL_SHADOW_MERGE shadow_merge classes/sillusionist.c
SPELL_SHADOW_MONSTER shadow_monster classes/sillusionist.c
SPELL_SHADOW_SHIELD shadow_shield classes/sillusionist.c
SPELL_SHADOW_SPAWN shadow_spawn classes/sillusionist.c
SPELL_SHADOW_TRAVEL shadow_travel classes/sillusionist.c
SPELL_SHDW_GATE_ARDGRAL shdw_gate_ardgral classes/sillusionist.c
SPELL_STUNNING_VISIONS stunning_visions classes/sillusionist.c
SPELL_SUPPRESSION suppress_sound classes/sillusionist.c
SPELL_TITAN titan classes/sillusionist.c
SPELL_VANISH vanish classes/sillusionist.c
SPELL_WATCHING_WALL watching_wall classes/sillusionist.c
SPELL_ANIMATE_DEAD animate_dead classes/necromancy.c
SPELL_CALL_ARCHON call_archon classes/necromancy.c
SPELL_CALL_ASURA call_asura classes/necromancy.c
SPELL_CALL_AVATAR call_avatar classes/necromancy.c
SPELL_CALL_BRALANI call_bralani classes/necromancy.c
SPELL_CALL_DEVA call_deva classes/necromancy.c
SPELL_CALL_KNIGHT call_knight classes/necromancy.c
SPELL_CALL_LIBERATOR call_liberator classes/necromancy.c
SPELL_CALL_TITAN call_titan classes/necromancy.c
SPELL_CREATE_DRACOLICH create_dracolich classes/necromancy.c
SPELL_CREATE_GOLEM create_golem classes/necromancy.c
SPELL_CREATE_GREATER_DRACOLICH create_greater_dracolich classes/necromancy.c
SPELL_RAISE_LICH raise_lich classes/necromancy.c
SPELL_RAISE_SHADOW raise_shadow classes/necromancy.c
SPELL_RAISE_SPECTRE raise_spectre classes/necromancy.c
SPELL_RAISE_VAMPIRE raise_vampire classes/necromancy.c
SPELL_RAISE_WRAITH raise_wraith classes/necromancy.c
SPELL_SLASHING_DARKNESS slashing_darkness classes/necromancy.c
SPELL_TAINT taint classes/necromancy.c
SPELL_UNDEAD_TO_DEATH undead_to_death classes/necromancy.c
""".split("\n") if line.strip()]

NO_NUMBERS = ("SPELL_COMPACT_CORPSE", "SPELL_CORPSEFORM", "SPELL_GREATER_FLICKER", "SPELL_NIGHTMARE",
              "SPELL_SPAWN", "SPELL_WALL_OF_BONES")

# The batch's helpers, by file; other functions in these files are not this batch's.
PREFIXES = {
    ILLUSION: ("illusion_", "phantom_armor_", "shadow_monster_", "insects_", "boulder_", "shadow_travel_",
               "stunning_visions_", "reflection_", "mask_size", "watching_wall_", "illusionary_wall_",
               "shadow_shield_", "vanish_", "hammer_", "detect_illusion_", "dream_travel_", "imprison_",
               "dragon_", "titan_", "delirium_", "flicker_", "obscuring_mist_", "sound_suppression_",
               "shadow_merge_", "ardgral_", "shadow_spawn_", "asphyxiate_"),
    NECRO: ("draco_", "raised_", "corpse_pet_", "greater_corpse_", "call_titan_", "create_dracolich_", "golem_",
            "call_avatar_", "greater_dracolich_", "slashing_darkness_", "undead_to_death_", "taint_"),
}

# What each handler must call.
HANDLER_CALLS = {
    ILLUSION: {
        "spell_phantom_armor": ["af.duration = phantom_armor_duration()", "af.modifier = phantom_armor_ac(level)",
                                "af1->duration = phantom_armor_duration()"],
        "spell_shadow_monster": ["summoned >= illusion_pet_limit(ch)", "shadow_monster_level(live_rolls, level)",
                                 "shadow_monster_hit_points(live_rolls, GET_LEVEL(mob))",
                                 "setup_pet(mob, ch, illusion_pet_control(), PET_NOORDER | PET_NOCASH)",
                                 "mob->points.hitroll = shadow_monster_hitroll(ch)",
                                 "mob->points.damroll = shadow_monster_damroll(ch)",
                                 "mob->points.damnodice = shadow_monster_dice_count(ch)",
                                 "mob->points.damsizedice = shadow_monster_dice_size(ch)"],
        "spell_insects": ["for (i = illusion_pet_limit(ch); i > summoned; i--)", "insects_level(live_rolls, level)",
                          "GET_LEVEL(ch) > insects_blur_above()", "GET_LEVEL(ch) > insects_flurry_above()",
                          "insects_hit_points(live_rolls, GET_LEVEL(mob), GET_LEVEL(ch))",
                          "mob->points.hitroll = insects_hitroll(ch)", "mob->points.damroll = insects_damroll(ch)",
                          "mob->points.damnodice = insects_dice_count(ch)",
                          "mob->points.damsizedice = insects_dice_size(ch)",
                          "setup_pet(mob, ch, illusion_pet_control(), PET_NOORDER | PET_NOCASH)"],
        "spell_boulder": ["dam = boulder_damage(live_rolls, level)",
                          "if (NewSaves(victim, SAVING_SPELL, mod)) dam = boulder_saved(dam)",
                          "SPLDAM_GENERIC, SPLDAM_GLOBE, &messages",
                          "if (!boulder_knockdown_roll(live_rolls))", "CharWait(victim, boulder_knockdown_lag())"],
        "spell_shadow_travel": ["CharWait(ch, shadow_travel_dreamer_lag()); else if (IS_PC(ch)) "
                                "CharWait(ch, shadow_travel_pc_lag())",
                                "distance = shadow_travel_distance(level)",
                                "distance += shadow_travel_dreamer_distance()"],
        "spell_stunning_visions": ["int percent = stunning_visions_percent(live_rolls, level)",
                                   "percent += stunning_visions_power_bonus(GET_C_POW(ch) - GET_C_POW(victim))",
                                   "percent > stunning_visions_deep_above()",
                                   "Stun(victim, ch, stunning_visions_deep_stun(), FALSE)",
                                   "percent > stunning_visions_trance_above()",
                                   "Stun(victim, ch, stunning_visions_trance_stun(), FALSE)",
                                   "percent > stunning_visions_mesmerize_above()",
                                   "Stun(victim, ch, stunning_visions_mesmerize_stun(), FALSE)",
                                   "percent >= stunning_visions_slight_from()",
                                   "Stun(victim, ch, stunning_visions_slight_stun(), FALSE)"],
        "spell_reflection": ["numb = reflection_images(level)", "reflection_image_hit_points(live_rolls, level)",
                             "setup_pet(image, ch, reflection_image_control(), PET_NOCASH)"],
        "mask_as": ["CharWait(ch, illusion_fade_lag())", "GET_LEVEL(target) > illusion_copy_highest_level()",
                    "CharWait(ch, mask_size_lag())", "ch->disguise.hit = illusion_disguise_hits(ch)"],
        "spell_watching_wall": ["WATCHING_WALL, watching_wall_strength(level), illusion_wall_decay()"],
        "spell_illusionary_wall": ["ILLUSIONARY_WALL, level, illusion_wall_decay()"],
        "spell_shadow_shield": ["int absorb = shadow_shield_absorb(live_rolls, level)",
                                "af.duration = shadow_shield_duration()"],
        "spell_vanish": ["af.duration = vanish_duration(level)", "af1->duration = vanish_duration(level)"],
        "spell_hammer": ["level = hammer_level(level, ch)", "dam = hammer_damage(live_rolls, level)",
                         "dam = hammer_saved(dam)", "if (!hammer_stun_roll(live_rolls))",
                         "Stun(ch, ch, hammer_stun(), FALSE)", "Stun(victim, ch, hammer_stun(), TRUE)",
                         "SPLDAM_GENERIC, SPLDAM_NOSHRUG, &messages"],
        "spell_detect_illusion": ["af1->duration = detect_illusion_duration(level)",
                                  "af.duration = detect_illusion_duration(level)"],
        "spell_dream_travel": ["CharWait(ch, dream_travel_dreamer_lag(live_rolls))",
                               "CharWait(ch, dream_travel_pc_lag())",
                               "CharWait(targ, dream_travel_dreamer_member_lag()); else "
                               "CharWait(targ, dream_travel_member_lag())"],
        "spell_clone_form": ["GET_LEVEL(victim) > illusion_copy_highest_level()", "CharWait(ch, illusion_fade_lag())",
                             "ch->disguise.hit = illusion_disguise_hits(ch)"],
        "spell_imprison": ["if (imprison_first_save_roll(live_rolls))",
                           "NewSaves(victim, SAVING_FEAR, imprison_first_save_mod())",
                           "shell_hps = imprison_shell_hit_points(level)",
                           "NewSaves(victim, SAVING_FEAR, imprison_second_save_mod())",
                           "shell_hps = imprison_saved_hit_points(shell_hps)"],
        "spell_dragon": ["summoned >= illusion_pet_limit(ch)", "dragon_level(live_rolls, level)",
                         "dragon_hit_points(live_rolls, GET_LEVEL(mob))",
                         "setup_pet(mob, ch, illusion_pet_control(), PET_NOORDER | PET_NOCASH)"],
        "spell_titan": ["titan_level(live_rolls, level)", "mob->points.base_hit = titan_hit_points(ch)",
                        "mob->points.hitroll = titan_hitroll(GET_LEVEL(mob))",
                        "mob->points.damroll = titan_damroll(GET_LEVEL(mob))",
                        "mob->points.damnodice = titan_dice_count(ch)",
                        "mob->points.damsizedice = titan_dice_size(ch)",
                        "setup_pet(mob, ch, illusion_pet_control(), PET_NOORDER | PET_NOCASH)"],
        "spell_delirium": ["percent > delirium_works_above()", "af.duration = delirium_duration()"],
        "spell_flicker": ["spell_shadow_shield(flicker_shield_level(level), ch, 0, 0, gl->ch, 0)"],
        "spell_obscuring_mist": ["af.duration = obscuring_mist_duration(level)"],
        "spell_sound_suppression": ["af.duration = sound_suppression_duration()",
                                    "sound_suppression_sneak_roll(live_rolls) > "
                                    "sound_suppression_sneak_fails_up_to(counter)"],
        "spell_shadow_merge": ["af.duration = shadow_merge_duration()"],
        "cast_ardgral": ["to_room = real_room0(ardgral_room_roll(live_rolls))", "set.throughput = ardgral_throughput()",
                         "set.init_timeout = ardgral_init_timeout()",
                         "set.post_enter_timeout = ardgral_post_enter_timeout()",
                         "set.post_enter_lag = ardgral_post_enter_lag()", "set.decay_timer = ardgral_decay()"],
        "spell_shadow_burst": ["sbbdata.waves = shadow_spawn_waves()",
                               "add_event(event_shadow_spawn, shadow_spawn_wave_delay()",
                               "CharWait(ch, shadow_spawn_lag())"],
        "event_shadow_spawn": ["cast_as_damage_area(ch, spell_shadow_spawn, GET_LEVEL(ch), NULL",
                               "splat = shadow_spawn_player_splat()",
                               "!shadow_spawn_wave_roll(live_rolls, splat)",
                               "add_event(event_shadow_spawn, shadow_spawn_wave_delay()"],
        "spell_shadow_spawn": ["dam = shadow_spawn_damage(live_rolls, level)", "savemod = shadow_spawn_save_mod(ch)",
                               "affmod = shadow_spawn_affect_odds(ch)", "dam = shadow_spawn_player_damage(dam)",
                               "dam = shadow_spawn_undead_damage(dam)", "SPLDAM_SPIRIT, 0, &messages",
                               "NewSaves(victim, SAVING_FEAR, savemod)",
                               "blind(ch, victim, shadow_spawn_blind_duration())"],
        "event_asphyxiate": ["dam = asphyxiate_saved_damage(live_rolls, ch)",
                             "dam = asphyxiate_failed_damage(live_rolls, ch)",
                             "add_event(event_asphyxiate, asphyxiate_delay()", "SPLDAM_GENERIC, SPLDAM_NODEFLECT"],
        "spell_asphyxiate": ["int rounds = asphyxiate_rounds()"],
    },
    NECRO: {
        "can_raise_draco": ["int necro_power = draco_power(level, ch)", "int cost = draco_cost(bGreater)"],
        "raise_undead": ["life = raised_undead_spec_life(ch, life)",
                         "clevel > (level + raised_undead_corpse_margin())",
                         "(level < raised_undead_strict_below())", "clevel < raised_undead_weakest_corpse()",
                         "life = raised_undead_globe_life(live_rolls, life)",
                         "typ = raised_undead_type_roll(live_rolls, ch, level)",
                         "int necro_power = raised_undead_power(level, ch)", "cap = raised_undead_cap(level, typ)",
                         "undead->base_stats.Str = raised_spectre_strength()",
                         "undead->base_stats.Agi = raised_spectre_agility()",
                         "undead->base_stats.Dex = raised_spectre_dexterity()",
                         "raised_undead_hit_points(live_rolls, GET_LEVEL(undead), GET_LEVEL(ch), typ, life)",
                         "raised_undead_armor(GET_LEVEL(undead), typ)", "raised_undead_hitroll(GET_LEVEL(undead))",
                         "raised_undead_damroll(live_rolls, GET_LEVEL(undead))",
                         "raised_undead_dice_size(level)", "raised_undead_control(timeToDecay)",
                         "raised_undead_late_death_roll(live_rolls)",
                         "raised_undead_death_delay( duration, raised_undead_late_death_roll(live_rolls))"],
        "spell_call_titan": ["obj->value[CORPSE_LEVEL] < corpse_pet_corpse_level()",
                             "life += corpse_pet_globe_life(ch)", "call_titan_hit_points(live_rolls, life)",
                             "(!corpse_pet_rebel_roll(live_rolls))", "corpse_pet_rebel_death(live_rolls)",
                             "GET_AC(mob) -= call_titan_ac()", "raised_undead_late_death_roll(live_rolls)",
                             "raised_undead_death_delay( duration, raised_undead_late_death_roll(live_rolls))"],
        "spell_create_dracolich": ["obj->value[CORPSE_LEVEL] < corpse_pet_corpse_level()",
                                   "life += corpse_pet_globe_life(ch)", "create_dracolich_hit_points(live_rolls, life)",
                                   "mob->points.damnodice = create_dracolich_dice_count(level)",
                                   "mob->points.damsizedice = create_dracolich_dice_size(level)",
                                   "create_dracolich_damroll(live_rolls, level)",
                                   "IS_PC(ch) && !corpse_pet_rebel_roll(live_rolls) && !globe",
                                   "corpse_pet_rebel_death(live_rolls)", "GET_AC(mob) -= create_dracolich_ac(ch)",
                                   "corpse_pet_death_delay(duration)"],
        "spell_create_golem": ["level < golem_flesh_level()", "level >= golem_blood_level() && clevel >= "
                               "golem_blood_level()", "level >= golem_bone_level() && clevel >= golem_bone_level()"],
        "create_golem": ["sum + golem_data[which_type].cost > golem_power(ch)",
                         "clevel > (level + raised_undead_corpse_margin())", "life = corpse_pet_globe_life(ch)",
                         "cap = golem_cap(level, which_type)", "golem_armor(GET_LEVEL(mob))",
                         "percent = golem_form_roll(live_rolls)", "percent > golem_form_above()",
                         "golem_hit_points(live_rolls, GET_LEVEL(mob), GET_LEVEL(ch), which_type, life)",
                         "golem_hitroll(GET_LEVEL(mob))", "golem_damroll(GET_LEVEL(mob))",
                         "raised_undead_late_death_roll(live_rolls)",
                         "raised_undead_death_delay( duration, raised_undead_late_death_roll(live_rolls))"],
        "spell_call_avatar": ["obj->value[CORPSE_LEVEL] < greater_corpse_pet_corpse_level()",
                              "life += corpse_pet_globe_life(ch)", "call_avatar_hit_points(live_rolls, life)",
                              "GET_C_STR(mob) < corpse_pet_stat_floor()", "mob->base_stats.Str = corpse_pet_stat()",
                              "(!corpse_pet_rebel_roll(live_rolls))", "corpse_pet_rebel_death(live_rolls)",
                              "raised_undead_late_death_roll(live_rolls)",
                              "raised_undead_death_delay( duration, raised_undead_late_death_roll(live_rolls))"],
        "spell_create_greater_dracolich": ["level = greater_dracolich_level(level, ch)",
                                           "obj->value[CORPSE_LEVEL] < greater_corpse_pet_corpse_level()",
                                           "life += corpse_pet_globe_life(ch)",
                                           "greater_dracolich_hit_points(live_rolls, life)",
                                           "mob->points.damnodice = greater_dracolich_dice_count(level)",
                                           "mob->points.damsizedice = greater_dracolich_dice_size(level)",
                                           "greater_dracolich_damroll(live_rolls, level)",
                                           "GET_C_STR(mob) < corpse_pet_stat_floor()",
                                           "IS_PC(ch) && !greater_dracolich_rebel_roll(live_rolls) && !globe",
                                           "corpse_pet_rebel_death(live_rolls)",
                                           "GET_AC(mob) -= greater_dracolich_ac(level)",
                                           "corpse_pet_death_delay(duration)"],
        "spell_slashing_darkness": ["int num_missiles = slashing_darkness_missiles(level)",
                                    "dam = slashing_darkness_damage(live_rolls, level, num_missiles)",
                                    "slashing_darkness_half(dam), SPLDAM_GENERIC, SPLDAM_ALLGLOBES | RAWDAM_NOKILL | "
                                    "SPLDAM_NOSHRUG", "slashing_darkness_half(dam), SPLDAM_NEGATIVE, SPLDAM_ALLGLOBES | "
                                    "SPLDAM_NOSHRUG"],
        "spell_undead_to_death": ["save = undead_to_death_fixed_save()",
                                  "save = undead_to_death_save(GET_LEVEL(ch) - GET_LEVEL(victim))",
                                  "level = undead_to_death_level(level)",
                                  "dam = undead_to_death_damage(live_rolls, level)",
                                  "dam = undead_to_death_soulshield_damage(dam)",
                                  "save -= undead_to_death_soulshield_save()",
                                  "else if (!undead_to_death_lucky_roll(live_rolls))",
                                  "undead_to_death_lucky_damage(dam), SPLDAM_HOLY",
                                  "af.duration = undead_to_death_weak_duration(live_rolls)",
                                  "(int)(-1 * undead_to_death_strength_loss(live_rolls))",
                                  "(int)(-1 * undead_to_death_constitution_loss(live_rolls))",
                                  "(int)(-1 * undead_to_death_agility_loss(live_rolls))",
                                  "(int)(-1 * undead_to_death_dexterity_loss(live_rolls))",
                                  "undead_to_death_other_damage(dam), SPLDAM_HOLY"],
        "spell_taint": ["dam = taint_damage(live_rolls, level)", "dam = taint_saved(dam)",
                        "SPLDAM_NEGATIVE, 0, &messages"],
    },
}

HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "abilities/abilities.h"
#include "classes/necromancy.h"
#include "combat/damage.h"
#include "world/db.h"
#include <algorithm>
#include <cassert>
#include <climits>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <string>

void randomize(uint64_t seed);

static int infuse_life;
int GET_CHAR_SKILL_P(P_char, int) { return infuse_life; }
// lib/duris.properties values where they differ from the code's fallbacks.
float get_property(const char *key, double fallback) {
    if (!strcmp(key, "spell.area.damage.to.pc")) return 1.15f;
    if (!strcmp(key, "spell.dim.perlevel.modifier")) return 1.25f;
    if (!strcmp(key, "damage.reduction.shadowShield")) return 0.70f;
    return (float)fallback;
}
int get_property(const char *, int fallback) { return fallback; }
P_char get_linked_char(P_char, ush_int) { return nullptr; }
std::string invisibility_facts(P_char) { return "  Duration: invisibility's own page\n"; }
extern const struct undead_description undead_data[NECROPET_LAST + 1];

FUNCTIONS

// The next draw after a roll; equal fingerprints after equal seeds mean equal draw counts.
static int fingerprint() { return number(0, INT_MAX); }

static void same(const char *name, const std::function<int()> &original,
                 const std::function<int(const Rolls &)> &shared) {
    const int a = shared(lowest_rolls), b = shared(highest_rolls);
    for (uint64_t seed = 1; seed <= 40; ++seed) {
        randomize(seed);
        const int expected = original(), expected_next = fingerprint();
        randomize(seed);
        const int actual = shared(live_rolls), actual_next = fingerprint();
        if (actual != expected || actual_next != expected_next ||
            actual < std::min(a, b) || actual > std::max(a, b)) {
            std::fprintf(stderr, "%s: seed %d gave %d, expected %d in %d..%d\n", name,
                         (int)seed, actual, expected, a, b);
            std::abort();
        }
    }
}
#define SAME(original, shared) \
    same(#shared, [&] { return original; }, [&](const Rolls &rolls) { return shared; })

// The text holds these whole lines.
static bool contains(const std::string &text, const char *lines) {
    const size_t length = std::strlen(lines);
    assert(length && lines[length - 1] == '\n');
    for (size_t at = text.find(lines); at != std::string::npos; at = text.find(lines, at + 1))
        if (at == 0 || text[at - 1] == '\n')
            return true;
    std::fprintf(stderr, "missing \"%s\" in:\n%s", lines, text.c_str());
    return false;
}

struct Viewer { const char *name; uint m_class; int spec; int life; };
static const Viewer viewers[] = {
    { "warrior", CLASS_WARRIOR, 0, 0 },
    { "illusionist", CLASS_ILLUSIONIST, 0, 0 },
    { "dark dreamer", CLASS_ILLUSIONIST, SPEC_DARK_DREAMER, 0 },
    { "deceiver", CLASS_ILLUSIONIST, SPEC_DECEIVER, 0 },
    { "necromancer", CLASS_NECROMANCER, 0, 30 },
    { "necrolyte", CLASS_NECROMANCER, SPEC_NECROLYTE, 0 },
    { "reaper", CLASS_NECROMANCER, SPEC_REAPER, 30 },
    { "diabolis", CLASS_NECROMANCER, SPEC_DIABOLIS, 0 },
    { "blighter", CLASS_BLIGHTER, 0, 0 },
    { "theurgist", CLASS_THEURGIST, 0, 30 },
    { "thaumaturge", CLASS_THEURGIST, SPEC_THAUMATURGE, 30 },
    { "templar", CLASS_THEURGIST, SPEC_TEMPLAR, 0 },
    { "medium", CLASS_THEURGIST, SPEC_MEDIUM, 0 },
};

static char_data viewer(const Viewer &v, int level) {
    char_data ch{};
    ch.player.m_class = v.m_class;
    ch.player.spec = v.spec;
    ch.player.race = RACE_HUMAN;
    ch.player.level = level;
    ch.points.max_hit = 1000;
    infuse_life = v.life;
    return ch;
}

struct Page { const char *name; AbilityFacts facts; };
static const Page pages[] = {
PAGES
};

static void rolls_match() {
    for (int level : { 1, 10, 30, 50, 56, 60 }) {
        SAME(BOUNDED(1, number(level - 5, level + 1), 55), shadow_monster_level(rolls, level));
        SAME(dice(level, 3) + (level * 2), shadow_monster_hit_points(rolls, level));
        SAME(MIN(30, MAX(1, number(level - 7, level - 2))), insects_level(rolls, level));
        SAME(dice(level, 3) + (level), insects_hit_points(rolls, level, level));
        SAME(dice(2 * level, 8), boulder_damage(rolls, level));
        SAME(level + number(-10, 10), stunning_visions_percent(rolls, level));
        SAME(level * 4 + number(0, 50), reflection_image_hit_points(rolls, level));
        SAME((level / 6) + number(1, 4), shadow_shield_absorb(rolls, level));
        SAME(9 * level + number(-25, 25), hammer_damage(rolls, level));
        SAME(BOUNDED(1, number(level - 5, level + 1), 55), dragon_level(rolls, level));
        SAME(dice(level, 5) + (level * 4), dragon_hit_points(rolls, level));
        SAME(BOUNDED(1, number(level - 5, level), 55), titan_level(rolls, level));
        SAME(level * 4 + number(-20, 40), shadow_spawn_damage(rolls, level));
        char_data ch = viewer(viewers[1], level);
        P_char caster = &ch;
        SAME((5 * GET_LEVEL(caster) + 65) / 2 + number(0, 40), asphyxiate_saved_damage(rolls, caster));
        SAME(5 * GET_LEVEL(caster) + number(5, 45), asphyxiate_failed_damage(rolls, caster));
        for (const int odds : { 1, 2, 3, 4, 5 })
            SAME(number(0, odds), shadow_spawn_affect_roll(rolls, odds));
        for (int life : { 0, 40, 100 }) {
            for (int typ = 0; typ <= NECROPET_LAST; ++typ)
                SAME((int)(dice(level, 12) + level * undead_data[typ].hps + (life * 3)),
                     raised_undead_hit_points(rolls, level, level, typ, life));
            for (int type = 0; type <= NECROGOLEM_LAST; ++type)
                SAME((int)(dice(level, 11) + level * golem_data[type].hps + (life * 3)),
                     golem_hit_points(rolls, level, level, type, life));
            SAME((life + number(50, 100)), raised_undead_globe_life(rolls, life));
            SAME(dice(125, 15) + (life * 3), call_titan_hit_points(rolls, life));
            SAME(dice(125, 15) + (life * 5), create_dracolich_hit_points(rolls, life));
            SAME(2500 + number(-10, 50) + (life * 5), call_avatar_hit_points(rolls, life));
            SAME(2500 + number(-10, 50) + (life * 5), greater_dracolich_hit_points(rolls, life));
        }
        SAME((int)(0.55 * level) + number(-6, 2), raised_undead_damroll(rolls, level));
        SAME(level + number(4, 24), create_dracolich_damroll(rolls, level));
        SAME(level + number(24, 44), greater_dracolich_damroll(rolls, level));
        SAME((dice(1, 4) * 4 + number(1, level)) * BOUNDED(1, (level / 3), 5),
             slashing_darkness_damage(rolls, level, slashing_darkness_missiles(level)));
        SAME((16 * level) + number(-40, 40), undead_to_death_damage(rolls, level));
        SAME(9 * MIN(level, 56) + number(-40, 40), taint_damage(rolls, level));
        SAME((int)(number(0, MIN(level + 5, 45)) / 10) + ((NECROPET_LAST + 1) / 2),
             [&] { char_data t = viewer(viewers[9], level); return raised_undead_type_roll(rolls, &t, level); }());
        SAME(number(0, 1),
             [&] { char_data t = viewer(viewers[8], level); return raised_undead_type_roll(rolls, &t, level); }());
        SAME((int)(number(0, MIN(level + 5, 45)) / 10),
             [&] { char_data t = viewer(viewers[4], level); return raised_undead_type_roll(rolls, &t, level); }());
    }
    SAME(number(0, 9), boulder_knockdown_roll(rolls));
    SAME(number(0, 5), shadow_travel_unseen_roll(rolls));
    SAME(number(0, 19), hammer_stun_roll(rolls));
    SAME(number(4 * WAIT_SEC, 6 * WAIT_SEC), dream_travel_dreamer_lag(rolls));
    SAME(number(0, 1), imprison_first_save_roll(rolls));
    SAME(number(0, 2), delirium_wander_roll(rolls));
    SAME(number(1, 100), sound_suppression_sneak_roll(rolls));
    SAME(number(30401, 30464), ardgral_room_roll(rolls));
    SAME(number(0, 2), shadow_spawn_wave_roll(rolls, 2));
    SAME(number(0, 2), watching_wall_vision_roll(rolls));
    SAME(number(0, 5), illusionary_wall_block_roll(rolls));
    SAME(number(1, 100), wall_climb_roll(rolls));
    SAME(number(1, 10), raised_undead_late_death_roll(rolls));
    SAME(number(0, 12), corpse_pet_rebel_roll(rolls));
    SAME(number(0, 9), greater_dracolich_rebel_roll(rolls));
    SAME((4 + number(1, 6)) * WAIT_SEC, corpse_pet_rebel_death(rolls));
    SAME(number(0, 100), golem_form_roll(rolls));
    SAME(number(0, 3), undead_to_death_lucky_roll(rolls));
    SAME(number(1, 2), undead_to_death_weak_duration(rolls));
    SAME(dice(3, 10), undead_to_death_strength_loss(rolls));
    SAME(dice(3, 20), undead_to_death_constitution_loss(rolls));
    SAME(dice(3, 10), undead_to_death_agility_loss(rolls));
    SAME(dice(3, 10), undead_to_death_dexterity_loss(rolls));
}

int main() {
    rolls_match();
    // Every page at every level for every kind of caster: no rolls, short lines, sane numbers.
    randomize(9);
    const int untouched = fingerprint();
    for (const Viewer &v : viewers)
        for (int level = 1; level <= 62; ++level)
            for (const Page &page : pages) {
                char_data ch = viewer(v, level);
                randomize(9);
                const std::string text = page.facts(&ch);
                assert(fingerprint() == untouched);
                assert(!text.empty() && text.back() == '\n');
                size_t start = 0;
                while (start < text.size()) {
                    const size_t end = text.find('\n', start);
                    if (end - start > 79 || text.compare(start, 2, "  ") != 0) {
                        std::fprintf(stderr, "%s, %s, level %d: \"%s\"\n", page.name, v.name, level,
                                     text.substr(start, end - start).c_str());
                        std::abort();
                    }
                    start = end + 1;
                }
                assert(text.find("--") == std::string::npos);
            }

EXACT
    puts("PASS: batch 9 shared rolls match the old code and stay in range, facts never roll");
}
'''

EXACT = r'''
    char_data ch{};
    ch = viewer(viewers[1], 56); // illusionist
    assert(asphyxiate_facts(&ch) ==
        "  Hits: 3, 0.25 seconds apart\n"
        "  Damage per hit if the target fails its save: 285-325 at your level, 56\n"
        "  If it saves: 172-212\n"
        "  Each hit makes its own save. It stops if either of you dies.\n"
        "  Damage scales with your level without a level-51 cap.\n"
        "  It does nothing to a target with no lungs. It cannot be deflected.\n"
        "  Globes and spirit wards do not stop it.\n"
        "  Spell damage modifiers and the target's defenses apply after.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(boulder_facts(&ch) ==
        "  Damage: 112-896 at your level, 56\n"
        "  If the target saves: 56-448\n"
        "  A major globe stops it; minor globes and spirit wards do not.\n"
        "  Spell damage modifiers and the target's defenses apply after.\n"
        "  Chance it knocks down a standing survivor: 1 in 10\n"
        "  Lag on the target knocked down: 2 seconds\n"
        "  Elites and greater races do not fall.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(clone_form_facts(&ch) ==
        "  Disguise strength: 112, worn down by damage and time\n"
        "  Your lag fading back with \"me\" or \"self\": 12 seconds\n"
        "  Highest level you can copy: 56\n"
        "  You cannot copy anything over one size smaller than you.\n"
        "  You cannot copy a reflection image, the training dummy, or yourself.\n"
        "  You must be disguised to fade back.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(delirium_facts(&ch) ==
        "  Duration: 10 seconds\n"
        "  Chance each step goes a random way: 1 in 3\n"
        "  It works if this is over 10: your power minus the target's\n"
        "    intelligence, plus its spell save modifier, plus your level advantage.\n"
        "  Recasting it on a confused target does nothing. You cannot target yourself.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(detect_illusion_facts(&ch) ==
        "  Duration: 56-57 game hours (70-71.25 minutes) at your level, 56\n"
        "  It also detects invisibility. Recasting it only renews the duration.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(dragon_facts(&ch) ==
        "  Dragons at once: 4 at your level, 56\n"
        "  Dragon's level: 51-55\n"
        "  Its hit points: 255-495\n"
        "  It serves you for: 1-2 game hours (1.25-2.5 minutes)\n"
        "  A globe of shadows or unholy alliance makes that permanent.\n"
        "  It attacks your target at once. Safe rooms block it.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(dream_travel_facts(&ch) ==
        "  Your lag: 12 seconds, even if it fails\n"
        "  Cast on another player, it takes you there, asleep.\n"
        "  Cast on yourself, it brings your group to you, asleep: NPCs and players\n"
        "  who consent and whom you can see, unless they are fighting.\n"
        "  Group members in no-teleport rooms or hometowns stay.\n"
        "  Each one's lag: 12 seconds\n"
        "  It cannot reach an NPC, the other racewar side or an immortal,\n"
        "  and single-file rooms block it.\n"
        "  Non-detection, and no-locate players you do not know, hide a target.\n"
        "  No-teleport rooms, hometowns and rooms you cannot enter block it, as do\n"
        "  ocean around the target, and flying or swimming. Both must be raidable.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(flicker_facts(&ch) ==
        "  You need a group. It leaves the room in permanent twilight.\n"
        "  Casts: shadow shield on your group here, at level 36\n"
        "  Hits absorbed: 7-10\n"
        "  Each melee hit on them: 46 less\n"
        "  Then, if over 10 is left: 70% of that\n"
        "  It applies before the raw damage modifiers.\n"
        "  Hits that ignore reductions go through it and use up nothing.\n"
        "  An attacker's fist of dragon can do the same.\n"
        "  Duration: 4-5 game hours (5-6.25 minutes)\n"
        "  It does nothing to a target with any skin spell.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(hammer_facts(&ch) ==
        "  Damage: 479-529 at your level, 56\n"
        "  If the target saves: 319-352\n"
        "  Magic resistance can shrug it first; damage cannot then be shrugged.\n"
        "  Globes and spirit wards do not stop it.\n"
        "  Spell damage modifiers and the target's defenses apply after.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(illusionary_wall_facts(&ch) ==
        "  Wall lasts: 7 minutes 30 seconds\n"
        "  Chance a walker into it finds it out and passes: 1 in 6\n"
        "  It hides the exit. Once found, the next walker blows it away.\n"
        "  Doors, blocked, secret, one-way and walled exits cannot take a wall, and\n"
        "  some rooms disperse the magic. You cannot cast it disguised in a town.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(imprison_facts(&ch) ==
        "  Chance of a first fear save that stops it: 1 in 2, at +10, harder\n"
        "  Shell's strength: 680 at your level, 56\n"
        "  If it makes a fear save at +3, harder: 442\n"
        "  The shell takes the damage meant for the target until a hit exceeds it.\n"
        "  It stops the target's fights. It only takes a player not in a fight, not\n"
        "  already imprisoned, and not you.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(insects_facts(&ch) ==
        "  Swarms at once: 4 at your level, 56\n"
        "  A cast summons until you have that many.\n"
        "  Swarm's level: 30\n"
        "  Its hit points: 86-146\n"
        "  Its hitroll: 56\n"
        "  Its damroll: 18\n"
        "  Its damage dice: 7d6\n"
        "  It is hasted.\n"
        "  It has blur: if you are above level 31\n"
        "  It has flurry: if you are above level 50\n"
        "  It serves you for: 1-2 game hours (1.25-2.5 minutes)\n"
        "  A globe of shadows or unholy alliance makes that permanent.\n"
        "  It attacks your target at once. Safe rooms block it.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(mask_facts(&ch) ==
        "  Disguise strength: 112, worn down by damage and time\n"
        "  Your lag fading back with \"me\" or \"self\": 12 seconds\n"
        "  Your lag if over one size off the target: 4 seconds\n"
        "  Highest level you can copy: 56\n"
        "  It only copies players, by name. You must be disguised to fade back.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(nonexistence_facts(&ch) ==
        "  Casts: invisibility on everyone in the room, at your level\n"
        "  Duration: invisibility's own page\n"
        "  It also hides them, except in water or on the ocean.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(obscuring_mist_facts(&ch) ==
        "  Duration: 15-16 game hours (18.75-20 minutes) at your level, 56\n"
        "  No mortal can look into, or scan, a room holding someone in the mist.\n"
        "  Recasting it on someone in the mist does nothing.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(phantom_armor_facts(&ch) ==
        "  Armor class: -56 at your level, 56\n"
        "  Duration: 15-16 game hours (18.75-20 minutes)\n"
        "  Recasting it only renews the duration.\n"
        "  It does nothing to a target with another armor-type spell.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(reflection_facts(&ch) ==
        "  Images: 4 at your level, 56\n"
        "  Each image's hit points: 224-274\n"
        "  They serve you for: 3-4 game hours (3.75-5 minutes)\n"
        "  A globe of shadows or unholy alliance makes that permanent.\n"
        "  Those fighting the target turn on one image.\n"
        "  Recasting replaces your images and the target's.\n"
        "  It cannot target an NPC, and not while you have a titan illusion.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(shadow_merge_facts(&ch) ==
        "  Duration: 4-5 game hours (5-6.25 minutes)\n"
        "  It hides you, and you stay hidden moving with whoever you follow.\n"
        "  Any other command or move takes you out of the shadows.\n"
        "  Recasting it while merged does nothing.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(shadow_monster_facts(&ch) ==
        "  Shadows at once: 4 at your level, 56\n"
        "  Shadow's level: 51-55\n"
        "  Its hit points: 153-275\n"
        "  Its hitroll: 56\n"
        "  Its damroll: 28\n"
        "  Its damage dice: 11d9\n"
        "  It serves you for: 1-2 game hours (1.25-2.5 minutes)\n"
        "  A globe of shadows or unholy alliance makes that permanent.\n"
        "  It attacks your target at once. Safe rooms block it.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(shadow_shield_facts(&ch) ==
        "  Hits absorbed: 10-13 at your level, 56\n"
        "  Each melee hit on you: 46 less\n"
        "  Then, if over 10 is left: 70% of that\n"
        "  It applies before the raw damage modifiers.\n"
        "  Hits that ignore reductions go through it and use up nothing.\n"
        "  An attacker's fist of dragon can do the same.\n"
        "  Duration: 4-5 game hours (5-6.25 minutes)\n"
        "  It does nothing to a target with any skin spell.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(shadow_spawn_facts(&ch) ==
        "  Your lag: 4 seconds\n"
        "  First wave after: 8 seconds\n"
        "  Waves: at most 2\n"
        "  Chance of the next wave, after as long: 1 in 3\n"
        "  Leaving the room collapses the vortex. Safe rooms stop it.\n"
        "  Spirit damage per wave: 204-264 at your level, 56\n"
        "  To another player: 234-303\n"
        "  To an undead NPC: 40-52\n"
        "  To an undead player: 46-60\n"
        "  Globes and spirit wards do not stop it.\n"
        "  Spell damage modifiers and the target's defenses apply after.\n"
        "  If a survivor fails a fear save: at +5, harder\n"
        "  Chance it is blinded: 1 in 3, for 4 seconds\n"
        "  Chance it flees: 1 in 3\n"
        "  Undead, elites and greater races ignore both, and magic resistance can\n"
        "  shrug each. The blind and those who cannot be blinded stay as they are.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(shadow_travel_facts(&ch) ==
        "  Range: 70 rooms by exits, either way, at your level, 56\n"
        "  Your lag: 9 seconds, even if it fails\n"
        "  Chance each onlooker misses you going or coming: 1 in 6\n"
        "  Non-detection, and no-locate players you do not know, hide a target.\n"
        "  So does a mount with a rider.\n"
        "  A follower cannot reach a player.\n"
        "  No-teleport rooms, hometowns and castles block it, as does ocean around\n"
        "  you and the other racewar side. You, and a player target, must be raidable.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(shdw_gate_ardgral_facts(&ch) ==
        "  Opens to: one of 64 rooms of Ardgral, one way\n"
        "  Can pass: no limit\n"
        "  Portal lasts: up to 1 minute\n"
        "  No-gate rooms, hometowns and castles block it, and you must be raidable.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(stunning_visions_facts(&ch) ==
        "  Score: 46-66 at your level, 56\n"
        "  It halves if you make your own spell save, and doubles on a player's pet.\n"
        "  Your level minus the target's adds to it.\n"
        "  Every 10 power you have over the target adds: 8\n"
        "  Stun at a score over 90: 8 seconds\n"
        "  Over 60: 4 seconds\n"
        "  Over 40: 2 seconds\n"
        "  At 25 or more: 1 second\n"
        "  A lower score does nothing. Fear saves do not apply.\n"
        "  A stun stops your fight and the target's.\n"
        "  Zombies, golems, plants, greater races and immortals are immune.\n"
        "  Elites cannot be stunned, and the target's magic resistance can shrug it.\n"
        "  It does nothing to a target already stunned, or down and lagged, unless\n"
        "  it is bashed or you sprang at it.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(suppress_sound_facts(&ch) ==
        "  You need a group. It covers everyone in it here.\n"
        "  Duration: 2-3 game hours (2.5-3.75 minutes)\n"
        "  Chance each member gets no sneak: 2 in 100 per group member\n"
        "  On the world map, no noise moving with allies up to: 13, give or take 1\n"
        "  Those under it cannot speak unless illithid, or use group chat or some\n"
        "  other voice commands. It cannot be dispelled, and recasting does nothing.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(titan_facts(&ch) ==
        "  Titan's level: 51-55 at your level, 56\n"
        "  Its hit points: 700 with your maximum hit points\n"
        "  Its hitroll: 25-27\n"
        "  Its damroll: 17-18\n"
        "  Its damage dice: 9d7\n"
        "  It serves you for: 1-2 game hours (1.25-2.5 minutes)\n"
        "  A globe of shadows or unholy alliance makes that permanent.\n"
        "  It attacks your target at once. You can have only one, and none while\n"
        "  your reflection images follow you. Safe rooms block it.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(vanish_facts(&ch) ==
        "  Invisibility: 28-29 game hours (35-36.25 minutes) at your level, 56\n"
        "  Recasting it, or invisibility, only renews the duration.\n"
        "  It also hides you, except in water or on the ocean.\n");
    ch = viewer(viewers[1], 56); // illusionist
    assert(watching_wall_facts(&ch) ==
        "  Wall lasts: 7 minutes 30 seconds\n"
        "  Strength: 56 at your level, 56\n"
        "  Chance someone acting by it shows you the room: 1 in 3\n"
        "  Seconds between those chances: more than 10\n"
        "  You must be elsewhere and in the game. Immortals show you nothing.\n"
        "  Hits wear it down by the hitter's damroll and level, and hurt the hitter.\n"
        "  Your own hit breaks it.\n"
        "  A hitter's lag: 16 seconds\n"
        "  Wall climbers get over it: 40%\n"
        "  Doors, blocked, secret, one-way and walled exits cannot take a wall, and\n"
        "  some rooms disperse the magic. You cannot cast it disguised in a town.\n");
    ch = viewer(viewers[4], 56); // necromancer
    assert(animate_dead_facts(&ch) ==
        "  Raises at random: skeleton, zombie, spectre, wraith, vampire\n"
        "  A corpse too weak for the type it rolls rolls again.\n"
        "  Lowest corpse level: 4\n"
        "  Its top level: 21-50 at your level, 56, lower on a weak corpse\n"
        "  At that level, its hit points: 178-1362 with your infuse life\n"
        "  Power it costs: 10-28 of your 112\n"
        "  Control lasts at least: 4-5 game hours (5-6.25 minutes)\n"
        "  It lasts longer on a fresher corpse.\n"
        "  It dies after its charm ends, plus: 2 minutes to 11 minutes\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  A globe of shadows also adds to infuse life: 50-100\n"
        "  Safe rooms block it, and the corpse must be on the ground here.\n"
        "  In vampire form you need necroplasm on. A good necromancer or an evil\n"
        "  theurgist is refused.\n");
    ch = viewer(viewers[9], 56); // theurgist
    assert(call_archon_facts(&ch) ==
        "  Raises at random: hound, lantern, asura, bralani, knight-errant\n"
        "  A corpse too weak for the type it rolls rolls again.\n"
        "  Lowest corpse level: 4\n"
        "  Its top level: 21-50 at your level, 56, lower on a weak corpse\n"
        "  At that level, its hit points: 178-1362 with your infuse life\n"
        "  Power it costs: 10-28 of your 112\n"
        "  Control lasts at least: 4-5 game hours (5-6.25 minutes)\n"
        "  It lasts longer on a fresher corpse.\n"
        "  It dies after its charm ends, plus: 2 minutes to 11 minutes\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  A globe of shadows also adds to infuse life: 50-100\n"
        "  Safe rooms block it, and the corpse must be on the ground here.\n"
        "  In vampire form you need necroplasm on. A good necromancer or an evil\n"
        "  theurgist is refused.\n");
    ch = viewer(viewers[9], 56); // theurgist
    assert(call_asura_facts(&ch) ==
        "  Corpse level needed: 20\n"
        "  Its top level: 31 at your level, 56, lower on a weak corpse\n"
        "  At that level, its hit points: 233-574 with your infuse life\n"
        "  Its base armor class: -66\n"
        "  Its hitroll: 21\n"
        "  Its damroll: 11-19\n"
        "  Its damage die size: 5\n"
        "  Power it costs: 10 of your 112\n"
        "  Control lasts at least: 4-5 game hours (5-6.25 minutes)\n"
        "  It lasts longer on a fresher corpse.\n"
        "  It dies after its charm ends, plus: 2 minutes to 11 minutes\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  A globe of shadows also adds to infuse life: 50-100\n"
        "  Safe rooms block it, and the corpse must be on the ground here.\n"
        "  In vampire form you need necroplasm on. A good necromancer or an evil\n"
        "  theurgist is refused.\n");
    ch = viewer(viewers[9], 56); // theurgist
    assert(call_avatar_facts(&ch) ==
        "  Corpse level needed: 51\n"
        "  Its hit points: 2640-2700 with your infuse life\n"
        "  Its strength and dexterity: 100 if either is below 95\n"
        "  Power it costs: 75 of your 112\n"
        "  Chance it turns on you: 1 in 13\n"
        "  It then attacks you and dies in: 5 seconds to 10 seconds\n"
        "  Its control lasts longer on a fresher corpse and with a duller pet.\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  A globe of shadows also adds to infuse life: 112\n"
        "  Safe rooms block it, and the corpse must be here. You must be able to move.\n"
        "  In vampire form you need necroplasm on.\n"
        "  It dies after its charm ends, plus: 2 minutes to 11 minutes\n");
    ch = viewer(viewers[9], 56); // theurgist
    assert(call_bralani_facts(&ch) ==
        "  Corpse level needed: 30\n"
        "  Its top level: 36 at your level, 56, lower on a weak corpse\n"
        "  At that level, its hit points: 305-701 with your infuse life\n"
        "  Its base armor class: -86\n"
        "  Its hitroll: 25\n"
        "  Its damroll: 13-21\n"
        "  Its damage die size: 5\n"
        "  Power it costs: 22 of your 112\n"
        "  Control lasts at least: 4-5 game hours (5-6.25 minutes)\n"
        "  It lasts longer on a fresher corpse.\n"
        "  It dies after its charm ends, plus: 2 minutes to 11 minutes\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  A globe of shadows also adds to infuse life: 50-100\n"
        "  Safe rooms block it, and the corpse must be on the ground here.\n"
        "  In vampire form you need necroplasm on. A good necromancer or an evil\n"
        "  theurgist is refused.\n");
    ch = viewer(viewers[9], 56); // theurgist
    assert(call_deva_facts(&ch) ==
        "  Corpse level needed: 40\n"
        "  Its top level: 50 at your level, 56, lower on a weak corpse\n"
        "  At that level, its hit points: 420-970 with your infuse life\n"
        "  Its base armor class: -145\n"
        "  Its hitroll: 35\n"
        "  Its damroll: 21-29\n"
        "  Its damage die size: 5\n"
        "  Power it costs: 65 of your 112\n"
        "  Control lasts at least: 4-5 game hours (5-6.25 minutes)\n"
        "  It lasts longer on a fresher corpse.\n"
        "  It dies after its charm ends, plus: 2 minutes to 11 minutes\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  A globe of shadows also adds to infuse life: 50-100\n"
        "  Safe rooms block it, and the corpse must be on the ground here.\n"
        "  In vampire form you need necroplasm on. A good necromancer or an evil\n"
        "  theurgist is refused.\n");
    ch = viewer(viewers[9], 56); // theurgist
    assert(call_knight_facts(&ch) ==
        "  Corpse level needed: 40\n"
        "  Its top level: 50 at your level, 56, lower on a weak corpse\n"
        "  At that level, its hit points: 812-1362 with your infuse life\n"
        "  Its base armor class: -115\n"
        "  Its hitroll: 35\n"
        "  Its damroll: 21-29\n"
        "  Its damage die size: 5\n"
        "  Power it costs: 28 of your 112\n"
        "  Control lasts at least: 4-5 game hours (5-6.25 minutes)\n"
        "  It lasts longer on a fresher corpse.\n"
        "  It dies after its charm ends, plus: 2 minutes to 11 minutes\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  A globe of shadows also adds to infuse life: 50-100\n"
        "  Safe rooms block it, and the corpse must be on the ground here.\n"
        "  In vampire form you need necroplasm on. A good necromancer or an evil\n"
        "  theurgist is refused.\n");
    ch = viewer(viewers[9], 56); // theurgist
    assert(call_liberator_facts(&ch) ==
        "  Corpse level needed: 45\n"
        "  Its top level: 46 at your level, 56, lower on a weak corpse\n"
        "  At that level, its hit points: 416-922 with your infuse life\n"
        "  Its base armor class: -126\n"
        "  Its hitroll: 32\n"
        "  Its damroll: 19-27\n"
        "  Its damage die size: 5\n"
        "  Power it costs: 28 of your 112\n"
        "  Control lasts at least: 4-5 game hours (5-6.25 minutes)\n"
        "  It lasts longer on a fresher corpse.\n"
        "  It dies after its charm ends, plus: 2 minutes to 11 minutes\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  A globe of shadows also adds to infuse life: 50-100\n"
        "  Safe rooms block it, and the corpse must be on the ground here.\n"
        "  In vampire form you need necroplasm on. A good necromancer or an evil\n"
        "  theurgist is refused.\n");
    ch = viewer(viewers[9], 56); // theurgist
    assert(call_titan_facts(&ch) ==
        "  Corpse level needed: 46\n"
        "  Its hit points: 215-1965 with your infuse life\n"
        "  If it serves, its armor class improves by: 50\n"
        "  Power it costs: 37 of your 112\n"
        "  Chance it turns on you: 1 in 13\n"
        "  It then attacks you and dies in: 5 seconds to 10 seconds\n"
        "  Its control lasts longer on a fresher corpse and with a duller pet.\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  A globe of shadows also adds to infuse life: 112\n"
        "  Safe rooms block it, and the corpse must be here. You must be able to move.\n"
        "  In vampire form you need necroplasm on.\n"
        "  It dies after its charm ends, plus: 2 minutes to 11 minutes\n");
    ch = viewer(viewers[4], 56); // necromancer
    assert(create_dracolich_facts(&ch) ==
        "  Corpse level needed: 46\n"
        "  Its hit points: 275-2025 with your infuse life\n"
        "  Its damage dice: 5d6 at your level, 56\n"
        "  Its damroll: 60-80\n"
        "  If it serves, its armor class improves by: 392\n"
        "  Power it costs: 37 of your 112\n"
        "  Chance it turns on you: 1 in 13\n"
        "  It then attacks you and dies in: 5 seconds to 10 seconds\n"
        "  It never turns on you while you hold a globe of shadows.\n"
        "  Its control lasts longer on a fresher corpse and with a duller pet.\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  A globe of shadows also adds to infuse life: 112\n"
        "  Safe rooms block it, and the corpse must be here. You must be able to move.\n"
        "  In vampire form you need necroplasm on.\n"
        "  It dies after its charm ends, plus: 1 minute\n");
    ch = viewer(viewers[4], 56); // necromancer
    assert(create_golem_facts(&ch) ==
        "  Flesh golem, corpse level needed: 41\n"
        "  Its top level: 50, lower on a weak corpse\n"
        "  At that level, its hit points: 980-1480 with your infuse life\n"
        "  Its armor class: -50\n"
        "  Its hitroll: 45\n"
        "  Its damroll: 35\n"
        "  Power it costs: 6 of your 18\n"
        "  Blood golem, corpse level needed: 46\n"
        "  Its top level: 50, lower on a weak corpse\n"
        "  At that level, its hit points: 1260-1760 with your infuse life\n"
        "  Its armor class: -50\n"
        "  Its hitroll: 45\n"
        "  Its damroll: 35\n"
        "  Power it costs: 6 of your 18\n"
        "  Bone golem, corpse level needed: 51\n"
        "  Its top level: 51, lower on a weak corpse\n"
        "  At that level, its hit points: 1541-2051 with your infuse life\n"
        "  Its armor class: -51\n"
        "  Its hitroll: 45\n"
        "  Its damroll: 35\n"
        "  Power it costs: 6 of your 18\n"
        "  Chance of vampire form: 35 in 101\n"
        "  Its control lasts longer on a fresher corpse and with a duller pet.\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  It dies after its charm ends, plus: 2 minutes to 11 minutes\n"
        "  A globe of shadows replaces infuse life with: 112\n"
        "  Safe rooms block it, and the corpse must be here. You must be able to move.\n"
        "  In vampire form you need necroplasm on.\n");
    ch = viewer(viewers[4], 56); // necromancer
    assert(create_greater_dracolich_facts(&ch) ==
        "  Corpse level needed: 51\n"
        "  Its hit points: 2640-2700 with your infuse life\n"
        "  Its damage dice: 6d7 at your level, 56\n"
        "  Its damroll: 80-100\n"
        "  Its strength and dexterity: 100 if either is below 95\n"
        "  If it serves, its armor class improves by: 224\n"
        "  Power it costs: 75 of your 112\n"
        "  Chance it turns on you: 1 in 10\n"
        "  It then attacks you and dies in: 5 seconds to 10 seconds\n"
        "  It never turns on you while you hold a globe of shadows.\n"
        "  Its control lasts longer on a fresher corpse and with a duller pet.\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  A globe of shadows also adds to infuse life: 112\n"
        "  Safe rooms block it, and the corpse must be here. You must be able to move.\n"
        "  In vampire form you need necroplasm on.\n"
        "  It dies after its charm ends, plus: 1 minute\n");
    ch = viewer(viewers[4], 56); // necromancer
    assert(raise_lich_facts(&ch) ==
        "  Corpse level needed: 45\n"
        "  Its top level: 46 at your level, 56, lower on a weak corpse\n"
        "  At that level, its hit points: 416-922 with your infuse life\n"
        "  Its base armor class: -21\n"
        "  Its hitroll: 32\n"
        "  Its damroll: 19-27\n"
        "  Its damage die size: 5\n"
        "  Power it costs: 28 of your 112\n"
        "  Control lasts at least: 4-5 game hours (5-6.25 minutes)\n"
        "  It lasts longer on a fresher corpse.\n"
        "  It dies after its charm ends, plus: 2 minutes to 11 minutes\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  A globe of shadows also adds to infuse life: 50-100\n"
        "  Safe rooms block it, and the corpse must be on the ground here.\n"
        "  In vampire form you need necroplasm on. A good necromancer or an evil\n"
        "  theurgist is refused.\n");
    ch = viewer(viewers[4], 56); // necromancer
    assert(raise_shadow_facts(&ch) ==
        "  Corpse level needed: 40\n"
        "  Its top level: 50 at your level, 56, lower on a weak corpse\n"
        "  At that level, its hit points: 420-970 with your infuse life\n"
        "  Its base armor class: -40\n"
        "  Its hitroll: 35\n"
        "  Its damroll: 21-29\n"
        "  Its damage die size: 5\n"
        "  Power it costs: 65 of your 112\n"
        "  Control lasts at least: 4-5 game hours (5-6.25 minutes)\n"
        "  It lasts longer on a fresher corpse.\n"
        "  It dies after its charm ends, plus: 2 minutes to 11 minutes\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  A globe of shadows also adds to infuse life: 50-100\n"
        "  Safe rooms block it, and the corpse must be on the ground here.\n"
        "  In vampire form you need necroplasm on. A good necromancer or an evil\n"
        "  theurgist is refused.\n");
    ch = viewer(viewers[4], 56); // necromancer
    assert(raise_spectre_facts(&ch) ==
        "  Corpse level needed: 20\n"
        "  Its top level: 31 at your level, 56, lower on a weak corpse\n"
        "  At that level, its hit points: 233-574 with your infuse life\n"
        "  Its base armor class: 39\n"
        "  Its hitroll: 21\n"
        "  Its damroll: 11-19\n"
        "  Its damage die size: 5\n"
        "  Its strength, agility and dexterity: 90, 100, 100\n"
        "  Power it costs: 10 of your 112\n"
        "  Control lasts at least: 4-5 game hours (5-6.25 minutes)\n"
        "  It lasts longer on a fresher corpse.\n"
        "  It dies after its charm ends, plus: 2 minutes to 11 minutes\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  A globe of shadows also adds to infuse life: 50-100\n"
        "  Safe rooms block it, and the corpse must be on the ground here.\n"
        "  In vampire form you need necroplasm on. A good necromancer or an evil\n"
        "  theurgist is refused.\n");
    ch = viewer(viewers[4], 56); // necromancer
    assert(raise_vampire_facts(&ch) ==
        "  Corpse level needed: 40\n"
        "  Its top level: 50 at your level, 56, lower on a weak corpse\n"
        "  At that level, its hit points: 812-1362 with your infuse life\n"
        "  Its base armor class: -10\n"
        "  Its hitroll: 35\n"
        "  Its damroll: 21-29\n"
        "  Its damage die size: 5\n"
        "  Power it costs: 28 of your 112\n"
        "  Control lasts at least: 4-5 game hours (5-6.25 minutes)\n"
        "  It lasts longer on a fresher corpse.\n"
        "  It dies after its charm ends, plus: 2 minutes to 11 minutes\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  A globe of shadows also adds to infuse life: 50-100\n"
        "  Safe rooms block it, and the corpse must be on the ground here.\n"
        "  In vampire form you need necroplasm on. A good necromancer or an evil\n"
        "  theurgist is refused.\n");
    ch = viewer(viewers[4], 56); // necromancer
    assert(raise_wraith_facts(&ch) ==
        "  Corpse level needed: 30\n"
        "  Its top level: 36 at your level, 56, lower on a weak corpse\n"
        "  At that level, its hit points: 305-701 with your infuse life\n"
        "  Its base armor class: 19\n"
        "  Its hitroll: 25\n"
        "  Its damroll: 13-21\n"
        "  Its damage die size: 5\n"
        "  Power it costs: 22 of your 112\n"
        "  Control lasts at least: 4-5 game hours (5-6.25 minutes)\n"
        "  It lasts longer on a fresher corpse.\n"
        "  It dies after its charm ends, plus: 2 minutes to 11 minutes\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  A globe of shadows also adds to infuse life: 50-100\n"
        "  Safe rooms block it, and the corpse must be on the ground here.\n"
        "  In vampire form you need necroplasm on. A good necromancer or an evil\n"
        "  theurgist is refused.\n");
    ch = viewer(viewers[4], 56); // necromancer
    assert(slashing_darkness_facts(&ch) ==
        "  Generic, then negative damage, each: 12-180 at your level, 56\n"
        "  The first part cannot kill. Magic resistance can shrug the spell first;\n"
        "  the damage cannot then be shrugged.\n"
        "  Any globe or spirit ward stops it.\n"
        "  Spell damage modifiers and the target's defenses apply after.\n");
    ch = viewer(viewers[4], 56); // necromancer
    assert(taint_facts(&ch) ==
        "  It only works on angels.\n"
        "  Negative damage: 464-544 at your level, 56\n"
        "  If the target saves: 232-272\n"
        "  Globes and spirit wards do not stop it.\n"
        "  Spell damage modifiers and the target's defenses apply after.\n");
    ch = viewer(viewers[4], 56); // necromancer
    assert(undead_to_death_facts(&ch) ==
        "  It only works on undead.\n"
        "  Holy damage if its save fails: 856-936 at your level, 56\n"
        "  Its save modifier: your level minus its, within 10; more is harder\n"
        "  Against a player's pet: +5, harder\n"
        "  If it makes the save, chance of less damage: 1 in 4\n"
        "  That damage: 642-702\n"
        "  Otherwise, hit points over its maximum are lost and that is all.\n"
        "  Otherwise, if it fails a paralysis save and is not weakened yet:\n"
        "  Strength lost: 3-30\n"
        "  Constitution lost: 3-60\n"
        "  Agility lost: 3-30\n"
        "  Dexterity lost: 3-30\n"
        "  For: 1-3 game hours (1.25-3.75 minutes)\n"
        "  Otherwise, damage: 573-627\n"
        "  A soulshield halves the damage to: 428-468\n"
        "  And eases its saves by: 2\n"
        "  It cannot be shrugged. Globes and spirit wards do not stop it.\n"
        "  Spell damage modifiers and the target's defenses apply after.\n");
    ch = viewer(viewers[3], 56); // deceiver
    assert(hammer_facts(&ch) ==
        "  Damage: 479-529 at your level, 56\n"
        "  If the target saves: 319-352\n"
        "  Magic resistance can shrug it first; damage cannot then be shrugged.\n"
        "  Globes and spirit wards do not stop it.\n"
        "  Spell damage modifiers and the target's defenses apply after.\n"
        "  Chance to stun if the target survives: 1 in 20\n"
        "  Stun: 4 seconds; fear saves shorten or stop it\n"
        "  A target with deflect stuns you instead, with no fear save.\n"
        "  Elites cannot be stunned. Greater races, plants, golems and constructs\n"
        "  may resist.\n");
    ch = viewer(viewers[1], 1); // illusionist
    assert(hammer_facts(&ch) ==
        "  Damage: 0-34 (none below 1 lands) at your level, 1\n"
        "  If the target saves: 0-22 (none below 1 lands)\n"
        "  Magic resistance can shrug it first; damage cannot then be shrugged.\n"
        "  Globes and spirit wards do not stop it.\n"
        "  Spell damage modifiers and the target's defenses apply after.\n");
    ch = viewer(viewers[2], 56); // dark dreamer
    assert(shadow_travel_facts(&ch) ==
        "  Range: 85 rooms by exits, either way, at your level, 56\n"
        "  Your lag: 1 second, even if it fails\n"
        "  Chance each onlooker misses you going or coming: 1 in 6\n"
        "  Non-detection, and no-locate players you do not know, hide a target.\n"
        "  So does a mount with a rider.\n"
        "  A follower cannot reach a player.\n"
        "  No-teleport rooms, hometowns and castles block it, as does ocean around\n"
        "  you and the other racewar side. You, and a player target, must be raidable.\n");
    ch = viewer(viewers[1], 60); // illusionist
    assert(shadow_travel_facts(&ch) ==
        "  Range: any, as an immortal\n"
        "  Your lag: 9 seconds, even if it fails\n"
        "  Chance each onlooker misses you going or coming: 1 in 6\n"
        "  Non-detection, and no-locate players you do not know, hide a target.\n"
        "  A follower cannot reach a player.\n"
        "  No-teleport rooms, hometowns and castles block it, as does ocean around\n"
        "  you and the other racewar side. You, and a player target, must be raidable.\n");
    ch = viewer(viewers[2], 56); // dark dreamer
    assert(dream_travel_facts(&ch) ==
        "  Your lag: 4 seconds to 6 seconds, even if it fails\n"
        "  Cast on another player, it takes you there, asleep.\n"
        "  Cast on yourself, it brings your group to you, asleep: NPCs and players\n"
        "  who consent and whom you can see, unless they are fighting.\n"
        "  Group members in no-teleport rooms or hometowns stay.\n"
        "  Each one's lag: 6 seconds\n"
        "  It cannot reach an NPC, the other racewar side or an immortal,\n"
        "  and single-file rooms block it.\n"
        "  Non-detection, and no-locate players you do not know, hide a target.\n"
        "  No-teleport rooms, hometowns and rooms you cannot enter block it, as do\n"
        "  ocean around the target, and flying or swimming. Both must be raidable.\n");
    ch = viewer(viewers[1], 60); // illusionist
    assert(dream_travel_facts(&ch) ==
        "  Your lag: 12 seconds, even if it fails\n"
        "  Cast on another player, it takes you there, asleep.\n"
        "  Cast on yourself, it brings your group to you, asleep: NPCs and players\n"
        "  who consent and whom you can see, unless they are fighting.\n"
        "  Each one's lag: 12 seconds\n"
        "  Non-detection, and no-locate players you do not know, hide a target.\n"
        "  No-teleport rooms, hometowns and rooms you cannot enter block it, as do\n"
        "  ocean around the target, and flying or swimming. Both must be raidable.\n");
    ch = viewer(viewers[1], 60); // illusionist
    assert(mask_facts(&ch) ==
        "  Disguise strength: 120, worn down by damage and time\n"
        "  Your lag fading back with \"me\" or \"self\": 12 seconds\n"
        "  Highest level you can copy: your own, as an immortal\n"
        "  It only copies players, by name. You must be disguised to fade back.\n");
    ch = viewer(viewers[1], 60); // illusionist
    assert(clone_form_facts(&ch) ==
        "  Disguise strength: 120, worn down by damage and time\n"
        "  Your lag fading back with \"me\" or \"self\": 12 seconds\n"
        "  Highest level you can copy: your own, as an immortal\n"
        "  You cannot copy a reflection image, the training dummy, or yourself.\n"
        "  You must be disguised to fade back.\n");
    ch = viewer(viewers[0], 56); // warrior
    assert(insects_facts(&ch) ==
        "  Swarms at once: 4 at your level, 56\n"
        "  A cast summons one, as you are no illusionist.\n"
        "  Swarm's level: 30\n"
        "  Its hit points: 86-146\n"
        "  Its hitroll: 56\n"
        "  Its damroll: 18\n"
        "  Its damage dice: 7d6\n"
        "  It is hasted.\n"
        "  It has blur: if you are above level 31\n"
        "  It has flurry: if you are above level 50\n"
        "  It serves you for: 1-2 game hours (1.25-2.5 minutes)\n"
        "  A globe of shadows or unholy alliance makes that permanent.\n"
        "  It attacks your target at once. Safe rooms block it.\n");
    ch = viewer(viewers[0], 56); // warrior
    assert(shadow_monster_facts(&ch) ==
        "  Shadows at once: 1 at your level, 56\n"
        "  Shadow's level: 51-55\n"
        "  Its hit points: 153-275\n"
        "  Its hitroll: 56\n"
        "  Its damroll: 28\n"
        "  Its damage dice: 11d9\n"
        "  It serves you for: 1-2 game hours (1.25-2.5 minutes)\n"
        "  A globe of shadows or unholy alliance makes that permanent.\n"
        "  It attacks your target at once. Safe rooms block it.\n");
    ch = viewer(viewers[4], 1); // necromancer
    assert(create_golem_facts(&ch) ==
        "  Level needed: 41\n");
    ch = viewer(viewers[4], 45); // necromancer
    assert(create_golem_facts(&ch) ==
        "  Flesh golem, corpse level needed: 41\n"
        "  Its top level: 48, lower on a weak corpse\n"
        "  At that level, its hit points: 813-1293 with your infuse life\n"
        "  Its armor class: -48\n"
        "  Its hitroll: 43\n"
        "  Its damroll: 33\n"
        "  Power it costs: 6 of your 15\n"
        "  Highest corpse level you can raise: 49\n"
        "  Chance of vampire form: 35 in 101\n"
        "  Its control lasts longer on a fresher corpse and with a duller pet.\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  It dies after its charm ends, plus: 2 minutes to 11 minutes\n"
        "  A globe of shadows replaces infuse life with: 90\n"
        "  Safe rooms block it, and the corpse must be here. You must be able to move.\n"
        "  In vampire form you need necroplasm on.\n");
    ch = viewer(viewers[9], 45); // theurgist
    assert(create_golem_facts(&ch) ==
        "  Valorhammer golem, corpse level needed: 41\n"
        "  Its top level: 49, lower on a weak corpse\n"
        "  At that level, its hit points: 1264-1754 with your infuse life\n"
        "  Its armor class: -49\n"
        "  Its hitroll: 44\n"
        "  Its damroll: 34\n"
        "  Power it costs: 6 of your 15\n"
        "  Highest corpse level you can raise: 49\n"
        "  Chance of vampire form: 35 in 101\n"
        "  Its control lasts longer on a fresher corpse and with a duller pet.\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  It dies after its charm ends, plus: 2 minutes to 11 minutes\n"
        "  A globe of shadows replaces infuse life with: 90\n"
        "  Safe rooms block it, and the corpse must be here. You must be able to move.\n"
        "  In vampire form you need necroplasm on.\n");
    ch = viewer(viewers[8], 45); // blighter
    assert(animate_dead_facts(&ch) ==
        "  Raises at random: skeleton, zombie\n"
        "  A corpse too weak for the type it rolls rolls again.\n"
        "  Lowest corpse level: 4\n"
        "  Its top level: 20-25 at your level, 45, lower on a weak corpse\n"
        "  At that level, its hit points: 74-381 with your infuse life\n"
        "  Power it costs: 10 of your 30\n"
        "  Control lasts at least: 4-5 game hours (5-6.25 minutes)\n"
        "  It lasts longer on a fresher corpse.\n"
        "  It dies after its charm ends, plus: 2 minutes to 11 minutes\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  A globe of shadows also adds to infuse life: 50-100\n"
        "  Highest corpse level you can raise: 49\n"
        "  Safe rooms block it, and the corpse must be on the ground here.\n"
        "  In vampire form you need necroplasm on. A good necromancer or an evil\n"
        "  theurgist is refused.\n");
    ch = viewer(viewers[4], 1); // necromancer
    assert(animate_dead_facts(&ch) ==
        "  Raises at random: skeleton\n"
        "  A corpse too weak for the type it rolls rolls again.\n"
        "  Lowest corpse level: 4\n"
        "  Its top level: 15 at your level, 1, lower on a weak corpse\n"
        "  At that level, its hit points: 106-271 with your infuse life\n"
        "  Power it costs: 10 of your 2\n"
        "  Control lasts at least: 4-5 game hours (5-6.25 minutes)\n"
        "  It lasts longer on a fresher corpse.\n"
        "  It dies after its charm ends, plus: 2 minutes to 11 minutes\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  A globe of shadows also adds to infuse life: 50-100\n"
        "  Highest corpse level you can raise: 5\n"
        "  Safe rooms block it, and the corpse must be on the ground here.\n"
        "  In vampire form you need necroplasm on. A good necromancer or an evil\n"
        "  theurgist is refused.\n");
    ch = viewer(viewers[6], 45); // reaper
    assert(raise_spectre_facts(&ch) ==
        "  Corpse level needed: 20\n"
        "  Its top level: 30 at your level, 45, lower on a weak corpse\n"
        "  At that level, its hit points: 240-570 with your infuse life\n"
        "  Its base armor class: 40\n"
        "  Its hitroll: 21\n"
        "  Its damroll: 10-18\n"
        "  Its damage die size: 4\n"
        "  Its strength, agility and dexterity: 90, 100, 100\n"
        "  Power it costs: 10 of your 90\n"
        "  Control lasts at least: 4-5 game hours (5-6.25 minutes)\n"
        "  It lasts longer on a fresher corpse.\n"
        "  It dies after its charm ends, plus: 2 minutes to 11 minutes\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  A globe of shadows also adds to infuse life: 50-100\n"
        "  Highest corpse level you can raise: 49\n"
        "  Safe rooms block it, and the corpse must be on the ground here.\n"
        "  In vampire form you need necroplasm on. A good necromancer or an evil\n"
        "  theurgist is refused.\n");
    ch = viewer(viewers[5], 45); // necrolyte
    assert(raise_wraith_facts(&ch) ==
        "  Corpse level needed: 30\n"
        "  Its top level: 35 at your level, 45, lower on a weak corpse\n"
        "  At that level, its hit points: 179-564 with your infuse life\n"
        "  Its base armor class: 20\n"
        "  Its hitroll: 24\n"
        "  Its damroll: 13-21\n"
        "  Its damage die size: 4\n"
        "  Power it costs: 22 of your 100\n"
        "  Control lasts at least: 4-5 game hours (5-6.25 minutes)\n"
        "  It lasts longer on a fresher corpse.\n"
        "  It dies after its charm ends, plus: 2 minutes to 11 minutes\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  A globe of shadows also adds to infuse life: 50-100\n"
        "  Highest corpse level you can raise: 49\n"
        "  Safe rooms block it, and the corpse must be on the ground here.\n"
        "  In vampire form you need necroplasm on. A good necromancer or an evil\n"
        "  theurgist is refused.\n");
    ch = viewer(viewers[4], 1); // necromancer
    assert(taint_facts(&ch) ==
        "  It only works on angels.\n"
        "  Negative damage: 0-49 (none below 1 lands) at your level, 1\n"
        "  If the target saves: 0-24 (none below 1 lands)\n"
        "  Globes and spirit wards do not stop it.\n"
        "  Spell damage modifiers and the target's defenses apply after.\n");
    ch = viewer(viewers[4], 1); // necromancer
    assert(undead_to_death_facts(&ch) ==
        "  It only works on undead.\n"
        "  Holy damage if its save fails: 0-56 (none below 1 lands) at your level, 1\n"
        "  Its save modifier: your level minus its, within 10; more is harder\n"
        "  Against a player's pet: +5, harder\n"
        "  If it makes the save, chance of less damage: 1 in 4\n"
        "  That damage: 0-42 (none below 1 lands)\n"
        "  Otherwise, hit points over its maximum are lost and that is all.\n"
        "  Otherwise, if it fails a paralysis save and is not weakened yet:\n"
        "  Strength lost: 3-30\n"
        "  Constitution lost: 3-60\n"
        "  Agility lost: 3-30\n"
        "  Dexterity lost: 3-30\n"
        "  For: 1-3 game hours (1.25-3.75 minutes)\n"
        "  Otherwise, damage: 0-37 (none below 1 lands)\n"
        "  A soulshield halves the damage to: 0-28 (none below 1 lands)\n"
        "  And eases its saves by: 2\n"
        "  It cannot be shrugged. Globes and spirit wards do not stop it.\n"
        "  Spell damage modifiers and the target's defenses apply after.\n");
    ch = viewer(viewers[2], 1); // dark dreamer
    assert(shadow_spawn_facts(&ch) ==
        "  Your lag: 4 seconds\n"
        "  First wave after: 8 seconds\n"
        "  Waves: at most 2\n"
        "  Chance of the next wave, after as long: 1 in 3\n"
        "  Leaving the room collapses the vortex. Safe rooms stop it.\n"
        "  Spirit damage per wave: 0-44 (none below 1 lands) at your level, 1\n"
        "  To another player: 0-50 (none below 1 lands)\n"
        "  To an undead NPC: 0-8 (none below 1 lands)\n"
        "  To an undead player: 0-10 (none below 1 lands)\n"
        "  Globes and spirit wards do not stop it.\n"
        "  Spell damage modifiers and the target's defenses apply after.\n"
        "  If a survivor fails a fear save: unmodified\n"
        "  Chance it is blinded: 1 in 6, for 4 seconds\n"
        "  Chance it flees: 1 in 6\n"
        "  Undead, elites and greater races ignore both, and magic resistance can\n"
        "  shrug each. The blind and those who cannot be blinded stay as they are.\n");
    ch = viewer(viewers[4], 1); // necromancer
    assert(create_dracolich_facts(&ch) ==
        "  Corpse level needed: 46\n"
        "  Its hit points: 275-2025 with your infuse life\n"
        "  Its damage dice: 1d1 at your level, 1\n"
        "  Its damroll: 5-25\n"
        "  If it serves, its armor class improves by: 7\n"
        "  Power it costs: 37 of your 2\n"
        "  Chance it turns on you: 1 in 13\n"
        "  It then attacks you and dies in: 5 seconds to 10 seconds\n"
        "  It never turns on you while you hold a globe of shadows.\n"
        "  Its control lasts longer on a fresher corpse and with a duller pet.\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  A globe of shadows also adds to infuse life: 2\n"
        "  Safe rooms block it, and the corpse must be here. You must be able to move.\n"
        "  In vampire form you need necroplasm on.\n"
        "  It dies after its charm ends, plus: 1 minute\n");
    ch = viewer(viewers[1], 1); // illusionist
    assert(boulder_facts(&ch) ==
        "  Damage: 2-16 at your level, 1\n"
        "  If the target saves: 1-8\n"
        "  A major globe stops it; minor globes and spirit wards do not.\n"
        "  Spell damage modifiers and the target's defenses apply after.\n"
        "  Chance it knocks down a standing survivor: 1 in 10\n"
        "  Lag on the target knocked down: 2 seconds\n"
        "  Elites and greater races do not fall.\n");
    ch = viewer(viewers[1], 1); // illusionist
    assert(flicker_facts(&ch) ==
        "  You need a group. It leaves the room in permanent twilight.\n"
        "  Casts: shadow shield on your group here, at level 0\n"
        "  Hits absorbed: 1-4\n"
        "  Each melee hit on them: 46 less\n"
        "  Then, if over 10 is left: 70% of that\n"
        "  It applies before the raw damage modifiers.\n"
        "  Hits that ignore reductions go through it and use up nothing.\n"
        "  An attacker's fist of dragon can do the same.\n"
        "  Duration: 4-5 game hours (5-6.25 minutes)\n"
        "  It does nothing to a target with any skin spell.\n");
    ch = viewer(viewers[1], 1); // illusionist
    assert(reflection_facts(&ch) ==
        "  Images: 1 at your level, 1\n"
        "  Each image's hit points: 4-54\n"
        "  They serve you for: 3-4 game hours (3.75-5 minutes)\n"
        "  A globe of shadows or unholy alliance makes that permanent.\n"
        "  Those fighting the target turn on one image.\n"
        "  Recasting replaces your images and the target's.\n"
        "  It cannot target an NPC, and not while you have a titan illusion.\n");
    ch = viewer(viewers[1], 1); // illusionist
    assert(vanish_facts(&ch) ==
        "  Invisibility: up to 1 game hour (up to 1.25 minutes) at your level, 1\n"
        "  Recasting it, or invisibility, only renews the duration.\n"
        "  It also hides you, except in water or on the ocean.\n");
    ch = viewer(viewers[4], 60); // necromancer
    assert(create_greater_dracolich_facts(&ch) ==
        "  Corpse level needed: 51\n"
        "  Its hit points: 2640-2700 with your infuse life\n"
        "  Its damage dice: 6d7 at your level, 60\n"
        "  Its damroll: 80-100\n"
        "  Its strength and dexterity: 100 if either is below 95\n"
        "  If it serves, its armor class improves by: 224\n"
        "  Power it costs: no limit, as an immortal\n"
        "  Chance it turns on you: 1 in 10\n"
        "  It then attacks you and dies in: 5 seconds to 10 seconds\n"
        "  It never turns on you while you hold a globe of shadows.\n"
        "  Its control lasts longer on a fresher corpse and with a duller pet.\n"
        "  A globe of shadows or unholy alliance makes the charm permanent,\n"
        "  and then it does not die.\n"
        "  A globe of shadows also adds to infuse life: 120\n"
        "  Safe rooms block it, and the corpse must be here. You must be able to move.\n"
        "  In vampire form you need necroplasm on.\n"
        "  It dies after its charm ends, plus: 1 minute\n");
    ch = viewer(viewers[1], 60); // illusionist
    assert(hammer_facts(&ch) ==
        "  Damage: 479-529 at your level, 60\n"
        "  If the target saves: 319-352\n"
        "  Magic resistance can shrug it first; damage cannot then be shrugged.\n"
        "  Globes and spirit wards do not stop it.\n"
        "  Spell damage modifiers and the target's defenses apply after.\n");

    // Level boundaries.
    const auto at = [](int v, int level) { return viewer(viewers[v], level); };
    ch = at(1, 49); assert(contains(shadow_spawn_facts(&ch), "  Chance it is blinded: 1 in 6, for 4 seconds\n"));
    ch = at(1, 50); assert(contains(shadow_spawn_facts(&ch), "  Chance it is blinded: 1 in 5, for 4 seconds\n"));
    ch = at(1, 54); assert(contains(shadow_spawn_facts(&ch), "  Chance it flees: 1 in 4\n"));
    ch = at(1, 10); assert(contains(shadow_spawn_facts(&ch), "  If a survivor fails a fear save: at +1, harder\n"));
    ch = at(1, 30); assert(contains(reflection_facts(&ch), "  Images: 1 at your level, 30\n"));
    ch = at(1, 36); assert(contains(reflection_facts(&ch), "  Images: 2 at your level, 36\n"));
    ch = at(1, 46); assert(contains(reflection_facts(&ch), "  Images: 4 at your level, 46\n"));
    ch = at(1, 47); assert(contains(imprison_facts(&ch), "  Shell's strength: 440 at your level, 47\n"));
    ch = at(1, 46); assert(contains(imprison_facts(&ch), "  Shell's strength: 400 at your level, 46\n"));
    ch = at(1, 53); assert(contains(imprison_facts(&ch), "  Shell's strength: 680 at your level, 53\n"));
    ch = at(1, 13); assert(contains(dragon_facts(&ch), "  Dragons at once: 1 at your level, 13\n"));
    ch = at(1, 14); assert(contains(dragon_facts(&ch), "  Dragons at once: 1 at your level, 14\n"));
    ch = at(1, 28); assert(contains(dragon_facts(&ch), "  Dragons at once: 2 at your level, 28\n"));
    ch = at(4, 48); assert(contains(raise_wraith_facts(&ch), "  Highest corpse level you can raise: 52\n"));
    ch = at(4, 49); assert(raise_wraith_facts(&ch).find("Highest corpse") == std::string::npos);
    ch = at(4, 40); assert(create_golem_facts(&ch) == "  Level needed: 41\n");
    ch = at(4, 41); assert(create_golem_facts(&ch).find("Blood golem") == std::string::npos);
    ch = at(4, 46); assert(contains(create_golem_facts(&ch), "  Blood golem, corpse level needed: 46\n"));
    assert(create_golem_facts(&ch).find("Bone golem") == std::string::npos);
    ch = at(4, 51); assert(contains(create_golem_facts(&ch), "  Bone golem, corpse level needed: 51\n"));
    ch = at(5, 56); // necrolyte
    assert(contains(raise_lich_facts(&ch), "  Power it costs: 28 of your 122\n"));
    assert(contains(create_dracolich_facts(&ch), "  Power it costs: 37 of your 122\n"));
    ch = at(8, 56); // blighter
    assert(contains(animate_dead_facts(&ch), "  Power it costs: 10 of your 37\n"));
    ch = at(6, 56); infuse_life = 30; // reaper: a third more infuse life
    assert(contains(raise_spectre_facts(&ch), "  At that level, its hit points: 263-604 with your infuse life\n"));
    ch = at(1, 56); assert(hammer_level(60, &ch) == 56 && greater_dracolich_level(60, &ch) == 56);
    assert(undead_to_death_level(60) == 56 && undead_to_death_save(-20) == -10 && undead_to_death_save(3) == 3);
'''


def helpers_of(file):
    """Each helper and facts function of the batch in one file, in source order."""
    text = source(file).read_text(encoding="utf-8", errors="replace")
    facts = {name for _, name, spell_file in SPELLS if spell_file == file}
    found = []
    for match in re.finditer(r"^((?:static )?[\w:]+ (\w+)\()", text, re.M):
        signature, name = match.groups()
        if name.startswith(PREFIXES[file]) or (name.endswith("_facts") and name[:-6] in facts):
            found.append(signature)
    return found


def table(file, start):
    """A const table's definition, whole."""
    text = source(file).read_text(encoding="utf-8", errors="replace")
    at = text.index(start)
    return text[at:text.index("};", at) + 2]


def check_sources():
    for file, handlers in HANDLER_CALLS.items():
        code = strip_comments(source(file).read_text(encoding="utf-8", errors="replace"))
        for handler, calls in handlers.items():
            bodies = function_bodies(code, rf"\b(void|bool|int)\s+{handler}\s*\(")
            assert len(bodies) == 1, handler
            body = re.sub(r"\s+", " ", bodies[0])
            for call in calls:
                assert contains(body, call), f"{handler} does not call {call}"
    illusion = strip_comments(source(ILLUSION).read_text(encoding="utf-8", errors="replace"))
    # The handler's rolls stay where they were.
    travel = re.sub(r"\s+", " ", function_bodies(illusion, r"\bvoid\s+spell_shadow_travel\s*\(")[0])
    assert travel.count("!shadow_travel_unseen_roll(live_rolls)") == 2
    assert travel.index("CharWait(ch, shadow_travel_dreamer_lag())") < travel.index("if (!victim)")
    dream = re.sub(r"\s+", " ", function_bodies(illusion, r"\bvoid\s+spell_dream_travel\s*\(")[0])
    assert dream.index("CharWait(ch, dream_travel_pc_lag())") < dream.index("can_relocate_to(ch, victim)")
    # Hammer's stun stays gated on the deceiver, and on surviving the damage.
    hammer = re.sub(r"\s+", " ", function_bodies(illusion, r"\bvoid\s+spell_hammer\s*\(")[0])
    assert hammer.index("spell_damage(") < hammer.index("GET_SPEC(ch, CLASS_ILLUSIONIST, SPEC_DECEIVER)") < \
        hammer.index("hammer_stun_roll(live_rolls)")
    spawn = re.sub(r"\s+", " ", function_bodies(illusion, r"\bvoid\s+spell_shadow_spawn\s*\(")[0])
    assert spawn.count("!shadow_spawn_affect_roll(live_rolls, affmod)") == 2
    assert spawn.index("IS_PC(ch) && IS_PC(victim)") < spawn.index("shadow_spawn_player_damage") < \
        spawn.index("IS_UNDEAD(victim)") < spawn.index("shadow_spawn_undead_damage")
    # Each property reads its own key.
    for function, key in (("shadow_travel_distance", "spell.dim.perlevel.modifier"),
                          ("ardgral_throughput", "portals.gate.maxToPass"),
                          ("ardgral_init_timeout", "portals.gate.initTimeout"),
                          ("ardgral_post_enter_timeout", "portals.gate.postEnterTimeout"),
                          ("ardgral_post_enter_lag", "portals.gate.postEnterLag"),
                          ("ardgral_decay", "portals.gate.decayTimeout"),
                          ("shadow_spawn_player_damage", "spell.area.damage.to.pc")):
        assert f'"{key}"' in function_bodies(illusion, rf"\bstatic\s+\w+\s+{function}\s*\(")[0], function
    # Shadow shield is in melee_damage's skin chain, and reads its own configured share.
    fight = strip_comments(source("fight.c").read_text(encoding="utf-8", errors="replace"))
    melee = re.sub(r"\s+", " ", function_bodies(fight, r"\bint\s+melee_damage\s*\(")[0])
    assert ("affected_by_spell(victim, SPELL_SHADOW_SHIELD) && !(flags & PHSDAM_NOREDUCE)) "
            "{ reduction = 1. - shadow_shield_melee_share(); skin = SPELL_SHADOW_SHIELD;") in melee
    # The object procs and movement read the numbers on the pages.
    procs = strip_comments(source("specs.object.c").read_text(encoding="utf-8", errors="replace"))
    wall = function_bodies(procs, r"\bint\s+wall_generic\s*\(")[0]
    assert "!watching_wall_vision_roll(live_rolls)" in wall
    assert "(time(NULL) - obj->value[6]) > watching_wall_vision_gap()" in wall
    assert "if (illusionary_wall_block_roll(live_rolls))" in wall
    moves = strip_comments(source("actmove.c").read_text(encoding="utf-8", errors="replace"))
    assert len(re.findall(r"SPELL_DELIRIUM\) &&\s*!delirium_wander_roll\(live_rolls\)", moves)) == 2
    assert re.search(r"SPELL_SUPPRESSION\) &&\s*noise_var <= sound_suppression_noise_limit\(\)", moves)
    # Dispatching spells pass the caster's level on.
    necro = strip_comments(source(NECRO).read_text(encoding="utf-8", errors="replace"))
    for handler, typ in (("spell_raise_spectre", "NECROPET_SPECTRE"), ("spell_raise_wraith", "NECROPET_WRAITH"),
                         ("spell_raise_shadow", "NECROPET_SHADOW"), ("spell_raise_vampire", "NECROPET_VAMPIRE"),
                         ("spell_raise_lich", "NECROPET_LICH"), ("spell_animate_dead", "-1"),
                         ("spell_call_asura", "THEURPET_SPECTRE"), ("spell_call_bralani", "THEURPET_WRAITH"),
                         ("spell_call_deva", "THEURPET_SHADOW"), ("spell_call_knight", "THEURPET_VAMPIRE"),
                         ("spell_call_liberator", "THEURPET_LICH"), ("spell_call_archon", "-1")):
        body = function_bodies(necro, rf"\bvoid\s+{handler}\s*\(")[0]
        assert f"raise_undead(level, ch, victim, obj, {typ})" in body, handler
    for page, typ in (("raise_spectre", "NECROPET_SPECTRE"), ("raise_wraith", "NECROPET_WRAITH"),
                      ("raise_shadow", "NECROPET_SHADOW"), ("raise_vampire", "NECROPET_VAMPIRE"),
                      ("raise_lich", "NECROPET_LICH"), ("call_asura", "THEURPET_SPECTRE"),
                      ("call_bralani", "THEURPET_WRAITH"), ("call_deva", "THEURPET_SHADOW"),
                      ("call_knight", "THEURPET_VAMPIRE"), ("call_liberator", "THEURPET_LICH")):
        assert f"raised_undead_facts(ch, {typ})" in function_bodies(necro, rf"\b{page}_facts\s*\(")[0], page
    golem = function_bodies(necro, r"\bvoid\s+spell_create_golem\s*\(")[0]
    assert "pet_type = THEURGOLEM_VALOR" in golem
    # Registration, and the disabled or number-free spells on the no-numbers list.
    registered = strip_comments(source("abilities.c").read_text())
    header = source("abilities.h").read_text()
    for constant, name, _ in SPELLS:
        assert re.search(rf"case {constant}:\s*return {name}_facts;", registered), constant
        assert f"std::string {name}_facts(char_data *ch);" in header, name
    no_numbers = (ROOT / "tests/fixtures/ability_coverage_no_numbers.txt").read_text().split()
    for constant in NO_NUMBERS:
        assert constant in no_numbers, constant
        assert not re.search(rf"case {constant}:", registered), constant
    assert 'send_to_char("Temporarily disabled.\\n", ch);' in \
        source(NECRO).read_text(encoding="utf-8", errors="replace")


def main():
    check_sources()
    functions = [extract_function("utility.c", "int dice(int num, int size)"),
                 extract_function("utility.c", "int BOUNDED(int a, int b, int c)"),
                 extract_function("utility.c", "int GET_CLASS(P_char ch, uint m_class)"),
                 extract_function("magic/spells.c", "int wall_climb_roll("),
                 extract_function("magic/spells.c", "int wall_climb_above("),
                 extract_function("magic/spells.c", "int wall_hit_lag("),
                 extract_function("fight.c", "int skin_spell_deduct("),
                 extract_function("fight.c", "float shadow_shield_melee_share("),
                 table(NECRO, "const struct golem_description golem_data[4]"),
                 table(NECRO, "const struct undead_description undead_data[NECROPET_LAST + 1] =")]
    for file in PREFIXES:
        functions += [extract_function(file, signature) for signature in helpers_of(file)]
    pages = ",\n".join(f'    {{ "{name}", {name}_facts }}' for _, name, _ in SPELLS)
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ability-batch-9-", dir=build) as temporary:
        directory = Path(temporary)
        harness = directory / "batch9.cpp"
        harness.write_text(HARNESS.replace("PAGES", pages).replace("FUNCTIONS", "\n".join(functions))
                           .replace("EXACT", EXACT))
        binary = directory / "batch9"
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
                        "-Isrc", "-I/usr/include/mysql", "-I/usr/include/libxml2",
                        str(harness), "src/abilities/abilities.c", "src/core/random.c",
                        "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], cwd=directory, check=True)


if __name__ == "__main__":
    main()
