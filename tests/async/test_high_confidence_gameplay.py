#!/usr/bin/env python3
"""Execute #715 spell handlers with distinct casters/targets and boundary resources."""
import re
import subprocess

from _paths import ROOT, extract_function, source


PRELUDE = r'''
#include "abilities/abilities.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "world/events.h"
#include "world/weather.h"
#include "combat/damage.h"
#include "classes/paladins.h"
#include "magic/spells.h"
#include "net/comm.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <vector>
#include <type_traits>

static room_data rooms[3]{};
P_room world = rooms;
static std::vector<int> rolls;
static size_t draw;
int number(int low, int high) {
    int result = draw < rolls.size() ? rolls[draw++] : low;
    assert(result >= low && result <= high);
    return result;
}
int dice(int count, int size) { return count * size; }
const Rolls live_rolls = {dice, number};
float get_property(const char *key, double fallback) {
    if (!std::strcmp(key, "spell.lifebolt.selfdam.lvl")) return 1;
    if (!std::strcmp(key, "spell.lendHealth.healRatio")) return 0.5;
    return fallback;
}
int get_property(const char *, int fallback) { return fallback; }
int GET_CLASS(P_char ch, uint cls) { return ch->player.m_class & cls; }
int GET_PRIME_CLASS(P_char ch, uint cls) { return ch->player.m_class & cls; }
float BOUNDEDF(float low, float value, float high) { return value < low ? low : value > high ? high : value; }
int GET_CHAR_SKILL_P(P_char ch, int skill) { return ch->only.pc->skills[skill].learned; }
int STAT_INDEX(int stat) { return stat; }
int BOUNDED(int low, int value, int high) { return value < low ? low : value > high ? high : value; }
bool ac_can_see(P_char, P_char, bool) { return true; }
bool SanityCheck(P_char ch, const char *) { return ch != nullptr; }
static bool saved;
static P_char save_target, message_target;
static std::vector<std::pair<P_char, int>> save_mods;
static int last_damage, scheduled;
static int event_counter;
static P_char damaged;
void act(const char *, int, P_char, P_obj, void *, int) {}
void send_to_char(const char *, P_char ch) { message_target = ch; }
void send_to_room(const char *, int) {}
void logit(const char *, const char *, ...) {}
void debug(const char *, ...) {}
void do_point(P_char, P_char) {}
void appear(P_char, bool) {}
void update_pos(P_char) {}
void StartRegen(P_char, regen_resource) {}
bool resists_spell(P_char, P_char) { return false; }
bool NewSaves(P_char ch, int, int mod) { save_target = ch; save_mods.emplace_back(ch, mod); return saved; }
bool saves_spell(P_char ch, int) { save_target = ch; return saved; }
bool StatSave(P_char ch, int, int) { save_target = ch; return saved; }
bool fear_check(P_char, bool) { return false; }
bool is_linked_to(P_char, P_char, ush_int) { return true; }
P_char get_linked_char(P_char, ush_int) { return nullptr; }
bool should_area_hit(P_char ch, P_char victim) { return ch != victim; }
bool grouped(P_char a, P_char b) { return a == b || (a->group && a->group == b->group); }
void engage(P_char, P_char) {}
void stop_memorizing(P_char, memorization_stop_reason) {}
void remember(P_char, P_char) {}
void MobStartFight(P_char, P_char) {}
void CharWait(P_char, int) {}
void do_flee(P_char, char *, int) {}
void die(P_char, P_char) { ++event_counter; }
bool notch_skill(P_char, int, float) { return true; }
void stop_fighting(P_char) {}
void set_fighting(P_char, P_char) {}
void StopAllAttackers(P_char) {}
void do_action(P_char, char *, int) {}
void do_say(P_char, char *, int) {}
static int stun_duration;
void Stun(P_char, P_char, int duration, bool) { stun_duration = duration; }
void KnockOut(P_char, int) {}
void event_psionic_wave_blast(P_char, P_char, P_obj, void *) {}
static int attacks;
void attack(P_char, P_char) { ++attacks; }
void event_holy_dharma(P_char, P_char, P_obj, void *) {}
int CheckMindflayerPresence(P_char) { return 0; }
void spell_silence(int, P_char, char *, int, P_char, P_obj) {}
void poison_lifeleak(int, P_char, char *, int, P_char, affected_type *) {}
void spell_malison(int, P_char, char *, int, P_char, P_obj) {}
void spell_cure_blind(int, P_char, char *, int, P_char ch, P_obj) { REMOVE_BIT(ch->specials.affected_by, AFF_BLIND); }
void spell_cure_disease(int, P_char, char *, int, P_char, P_obj) {}
int poison_common_remove(P_char ch) { REMOVE_BIT(ch->specials.affected_by2, AFF2_POISONED); return 1; }
bool affected_by_spell(P_char ch, int type) {
    for (auto *af = ch->affected; af; af = af->next) if (af->type == type) return true;
    return false;
}
affected_type *get_spell_from_char(P_char ch, int type, void *, int) {
    for (auto *af = ch->affected; af; af = af->next) if (af->type == type) return af;
    return nullptr;
}
affected_type *affect_to_char(P_char ch, affected_type *af) {
    auto *copy = new affected_type(*af);
    copy->next = ch->affected;
    ch->affected = copy;
    return copy;
}
void affect_to_char_with_messages(P_char ch, affected_type *af, const char *, const char *) {
    affect_to_char(ch, af);
}
void affect_join(P_char ch, affected_type *af, bool, bool) { affect_to_char(ch, af); }
void affect_from_char(P_char ch, int type) {
    for (auto **p = &ch->affected; *p;) {
        if ((*p)->type == type) { auto *old = *p; *p = old->next; delete old; }
        else p = &(*p)->next;
    }
}
static void clear(P_char ch) {
    while (ch->affected) affect_from_char(ch, ch->affected->type);
    ch->specials.affected_by = ch->specials.affected_by2 = ch->specials.affected_by5 = 0;
}
static int modifier(P_char ch, int type, int location) {
    for (auto *af = ch->affected; af; af = af->next)
        if (af->type == type && af->location == location) return af->modifier;
    assert(false); return 0;
}
int get_default_save_mod(P_char, P_char, int, int) { return 0; }
int spell_damage(P_char, P_char victim, double dam, int, uint, damage_messages *, int *) {
    last_damage = dam; damaged = victim; return DAM_NONEDEAD;
}
void wear_off_message(P_char, affected_type *) {}
void affect_remove(P_char ch, affected_type *af) {
    for (auto **p = &ch->affected; *p; p = &(*p)->next)
        if (*p == af) { *p = af->next; delete af; return; }
    assert(false);
}
void update_group_vitals(P_char) {}
void gmcp_char_vitals(P_char) {}
bool has_aura(P_char, int) { return false; }
int aura_mod(P_char, int) { return 0; }
bool affected_by_skill(P_char ch, int type) { return affected_by_spell(ch, type); }
affected_type *get_first_affect_with_flag(P_char ch, uint flags) {
    for (auto *af = ch->affected; af; af = af->next) if (af->flags & flags) return af;
    return nullptr;
}
void heal(P_char ch, P_char, int hp, int) { GET_HIT(ch) += hp; }
nevent_schedule_result add_event(event_func, int, P_char, P_char, P_obj, int, const void *data, int size) {
    ++scheduled;
    if (data && size == sizeof(int)) event_counter = *static_cast<const int *>(data);
    return {};
}
static room_affect room_effect{};
room_affect *get_spell_from_room(P_room, int) { return room_effect.type ? &room_effect : nullptr; }
room_affect *affect_to_room(int, room_affect *af) { room_effect = *af; return &room_effect; }
int sunlight = SUN_DARK;
static void reset_rolls(std::initializer_list<int> values = {}) { rolls = values; draw = 0; }
static char_data alive() {
    char_data ch{}; ch.specials.position = POS_STANDING + STAT_NORMAL;
    ch.player.level = 50; ch.in_room = 1;
    ch.points.hit = ch.points.max_hit = 500; ch.points.vitality = 100;
    return ch;
}
'''


FUNCTIONS = {
    "fight.c": ["get_ward_from_char", "check_damage_ward", "plague_heal_block_percent",
                "aura_healing_mod", "vamp", "soul_trap_hit_points", "soul_trap_threshold",
                "soul_trap_group_threshold", "soul_trap_cap", "soul_trap"],
    "smagic.c": [
        "animalist_level_bonus", "elephantstrength_duration", "elephantstrength_str_max",
        "elephantstrength_con_max", "elephantstrength_stat_penalty", "elephantstrength_damroll",
        "lionrage_duration", "lionrage_agi", "lionrage_str", "lionrage_damroll",
        "spirit_armor_duration", "spirit_armor_ac", "spirit_armor_save",
        "spell_spirit_armor", "spell_elephantstrength", "spell_lionrage",
        "torment_spirits_interval", "torment_spirits_damage", "event_torment_spirits",
        "corrosive_blast_damage", "corrosive_blast_ac", "corrosive_blast_duration", "spell_corrosive_blast",
    ],
    "magic.c": [
        "cyclone_damage", "cyclone_stun_roll", "cyclone_stun_chance", "cyclone_stun", "cyclone_halved", "spell_cyclone", "KludgeDuration", "lodestone_vision_duration", "spell_lodestone_vision", "curse_duration", "curse_hitroll", "curse_saves", "spell_curse",
        "devitalize_movement", "devitalize_floor", "spell_devitalize",
        "true_seeing_duration", "spell_true_seeing", "animal_vision_duration", "spell_animal_vision",
        "natures_blessing_duration", "spell_natures_blessing", "shadow_vision_duration", "spell_shadow_vision",
        "prot_from_undead_duration", "spell_prot_from_undead", "starshell_duration", "spell_starshell",
        "rope_trick_duration", "spell_rope_trick",
        "enlarge_duration", "enlarge_refresh_duration", "enlarge_str_max", "enlarge_con_max", "enlarge_agi", "enlarge_dex", "spell_enlarge",
        "reduce_duration", "reduce_refresh_duration", "reduce_str", "reduce_con", "reduce_agi_max", "reduce_dex_max", "spell_reduce",
        "edictum_cineris_berserk_lag", "edictum_cineris_penalty", "edictum_cineris_duration", "spell_edictum_cineris",
        "life_bolt_damage", "life_bolt_unopposed", "spell_life_bolt",
        "mielikki_vitality_duration", "mielikki_vitality_hit", "mielikki_vitality_moves", "mielikki_vitality_regen", "spell_mielikki_vitality",
        "restore_spirit_damage", "restore_spirit_untrained", "restore_spirit_untrained_damage",
        "restore_spirit_saved", "restore_spirit_level_bonus", "restore_spirit_vamp", "spell_restore_spirit",
        "acidimmolate_burn_damage", "event_acidimmolate",
        "vitalize_mana_amount", "spell_vitalize_mana", "turn_undead_fear_levels", "spell_turn_undead",
    ],
    "psionics.c": [
        "lend_health_most", "lend_health_ratio", "lend_health_healing", "lend_health_cost",
        "lend_health_short_roll", "lend_health_lowest_health", "spell_lend_health",
        "spinal_corruption_effect_roll", "spinal_corruption_lag", "spinal_corruption_slow_duration", "spell_spinal_corruption",
        "confuse_target_levels", "confuse_effect_roll", "confuse_stun", "confuse_turn_roll",
        "confuse_turn_limit", "confuse_githyanki_mana", "spell_confuse",
        "psionic_wave_blast_damage", "psionic_wave_blast_shrug_roll", "psionic_wave_blast_waves", "spell_psionic_wave_blast",
    ],
    "ethermancer.c": ["ethereal_discharge_damage", "ethereal_discharge_save_mod", "ethereal_discharge_strip_roll", "spell_ethereal_discharge"],
    "paladins.c": ["righteous_aura_interval", "righteous_aura_pc_blessing_duration", "righteous_aura_npc_blessing_duration", "righteous_aura_soulshield_alignment", "righteous_aura_dharma_delay", "righteous_aura_taunt_alignment", "event_righteous_aura_check"],
    "sillusionist.c": ["stunning_visions_percent", "stunning_visions_power_bonus", "stunning_visions_deep_above", "stunning_visions_deep_stun", "stunning_visions_trance_above", "stunning_visions_trance_stun", "stunning_visions_mesmerize_above", "stunning_visions_mesmerize_stun", "stunning_visions_slight_from", "stunning_visions_slight_stun", "spell_stunning_visions"],
    "actnew.c": ["advanced_meditation_cure_threshold", "advanced_meditation_poison_rating", "advanced_meditation_poison_roll", "advanced_meditation_disease_rating", "advanced_meditation_cure_level", "advanced_meditation_interval", "event_meditation"],
    "blispells.c": ["sap_nature_amount", "sap_nature_scourge", "spell_sap_nature"],
    "innates.c": ["god_call_blessing_duration", "event_lathander"],
}

DRIVER = r'''
int main() {
    char_data caster = alive(), target = alive(), other = alive();
    std::remove_pointer_t<decltype(caster.only.pc)> caster_pc{}, target_pc{}, other_pc{};
    caster.only.pc = &caster_pc; target.only.pc = &target_pc; other.only.pc = &other_pc;
    for (auto spell : {spell_true_seeing, spell_animal_vision, spell_natures_blessing, spell_shadow_vision}) {
        spell(50, &caster, nullptr, 0, &target, nullptr);
        assert(target.affected && !caster.affected);
        int type = target.affected->type;
        assert(message_target == &target);
        spell(50, &caster, nullptr, 0, &caster, nullptr);
        target.affected->duration = 1;
        spell(50, &caster, nullptr, 0, &target, nullptr);
        assert(target.affected->duration > 1 && !target.affected->next);
        clear(&target); // An already-buffed caster must still bless a fresh ally.
        spell(50, &caster, nullptr, 0, &target, nullptr);
        assert(affected_by_spell(&target, type));
        clear(&caster); clear(&target);
    }
    caster.player.m_class = CLASS_SHAMAN; caster.player.spec = SPEC_SPIRITUALIST;
    spell_spirit_armor(50, &caster, nullptr, 0, &target, nullptr);
    assert(modifier(&target, SPELL_SPIRIT_ARMOR, APPLY_AC) == -100);
    clear(&target);
    spell_lionrage(50, &caster, nullptr, 0, &target, nullptr);
    assert(modifier(&target, SPELL_LIONRAGE, APPLY_STR) == 11);
    assert(modifier(&target, SPELL_LIONRAGE, APPLY_DAMROLL) == 6);
    clear(&target);
    spell_elephantstrength(50, &caster, nullptr, 0, &target, nullptr);
    assert(modifier(&target, SPELL_ELEPHANTSTRENGTH, APPLY_AGI) == -10);
    assert(modifier(&target, SPELL_ELEPHANTSTRENGTH, APPLY_DAMROLL) == 6);
    clear(&target);
    // Elite targets receive the curse on a failed save, never on a successful one.
    target.specials.act = ACT_ISNPC | ACT_ELITE;
    spell_curse(50, &caster, nullptr, 0, &target, nullptr);
    assert(affected_by_spell(&target, SPELL_CURSE)); clear(&target);
    saved = true; spell_curse(50, &caster, nullptr, 0, &target, nullptr);
    assert(!target.affected); saved = false; target.specials.act = 0;
    for (int vitality : {0, 5, 20, 30, 200}) {
        target.points.vitality = vitality;
        spell_devitalize(50, &caster, nullptr, 0, &target, nullptr);
        assert(target.points.vitality <= vitality);
        if (vitality >= 20) assert(target.points.vitality >= 20);
    }
    // Corrosion stops at AC zero rather than discarding the remaining penalty.
    target.points.curr_armor = -10;
    spell_corrosive_blast(50, &caster, nullptr, 0, &target, nullptr);
    assert(modifier(&target, SPELL_CORROSIVE_BLAST, APPLY_AC) == 10); clear(&target);
    target.points.curr_armor = 10;
    spell_corrosive_blast(50, &caster, nullptr, 0, &target, nullptr);
    assert(modifier(&target, SPELL_CORROSIVE_BLAST, APPLY_AC) == 0); clear(&target);
    spell_prot_from_undead(50, &caster, nullptr, 0, &target, nullptr);
    assert(affected_by_spell(&target, SPELL_PROT_FROM_UNDEAD) && !caster.affected); clear(&target);
    // Fear rolls the target's save; negative scores cannot become positive bonuses.
    target.points.hitroll = target.points.damroll = -10;
    spell_edictum_cineris(50, &caster, nullptr, 0, &target, nullptr);
    assert(save_target == &target);
    assert(modifier(&target, SPELL_FEAR, APPLY_HITROLL) == 0);
    assert(modifier(&target, SPELL_FEAR, APPLY_DAMROLL) == 0); clear(&target);
    rooms[1].sector_type = SECT_FIELD;
    spell_starshell(50, &caster, nullptr, 0, nullptr, nullptr);
    room_effect.duration = 1;
    spell_starshell(50, &caster, nullptr, 0, nullptr, nullptr);
    assert(room_effect.duration == starshell_duration(50));
    // Once the torment limit is reached, even all-zero stop rolls cannot reschedule.
    int counter = 10; scheduled = 0;
    event_torment_spirits(&caster, &target, nullptr, &counter);
    assert(scheduled == 0);
    counter = 6; reset_rolls({0, 1});
    event_torment_spirits(&caster, &target, nullptr, &counter);
    assert(scheduled == 1 && event_counter == 7);
    // The templar bonus is paid in HP and cannot be gained at/below its cost.
    caster.player.m_class = CLASS_THEURGIST; caster.player.spec = SPEC_TEMPLAR;
    int base = life_bolt_damage(live_rolls, 50), cost = base / 4;
    caster.points.hit = 500;
    spell_life_bolt(50, &caster, nullptr, 0, &target, nullptr);
    assert(caster.points.hit == 500 - cost);
    assert(last_damage == life_bolt_unopposed(base) + cost);
    for (int hp : {cost - 1, cost}) {
        caster.points.hit = hp;
        spell_life_bolt(50, &caster, nullptr, 0, &target, nullptr);
        assert(caster.points.hit == hp && last_damage == life_bolt_unopposed(base));
    }
    // A fractional lending ratio still heals, and the original 50-HP ceiling survives.
    caster.points.hit = 500; target.points.hit = 1;
    spell_lend_health(50, &caster, nullptr, 0, &target, nullptr);
    assert(target.points.hit == 26 && caster.points.hit == 400);
    // A room target immune to turning does not prevent later undead being turned.
    target.player.race = other.player.race = RACE_SKELETON;
    target.player.level = 60; other.player.level = 1;
    rooms[1].people = &target; target.next_in_room = &other;
    event_counter = 0; reset_rolls({0});
    spell_turn_undead(50, &caster, nullptr, 0, nullptr, nullptr);
    assert(event_counter == 1);
    // The caster can sleep, but the victim's state decides the sleep branch.
    target.player.race = RACE_HUMAN; target.player.level = 50;
    caster.specials.position = POS_STANDING + STAT_SLEEPING;
    target.specials.position = POS_STANDING + STAT_NORMAL;
    reset_rolls({2});
    spell_spinal_corruption(50, &caster, nullptr, 0, &target, nullptr);
    assert(GET_STAT(&target) == STAT_SLEEPING);
    caster.specials.position = POS_STANDING + STAT_NORMAL;
    // Reaching the total-level limit still charges a githyanki's mana.
    caster.player.race = RACE_GITHYANKI; caster.points.mana = 100;
    target.player.level = 200; target.next_in_room = &other;
    saved = true;
    spell_confuse(50, &caster, nullptr, 0, &target, nullptr);
    assert(caster.points.mana == 100 - confuse_githyanki_mana()); saved = false;
    // A blessed group member at the front must not skip later members.
    group_list group{&caster, nullptr};
    caster.group = target.group = other.group = &group;
    target.specials.affected_by3 = AFF3_ENHANCE_HEALING;
    rooms[1].people = &target; target.next_in_room = &other; other.next_in_room = &caster;
    event_lathander(&caster, nullptr, nullptr, nullptr);
    assert(affected_by_spell(&other, TAG_ENHANCE_HEALING));
    assert(affected_by_spell(&caster, TAG_ENHANCE_HEALING));
    clear(&caster); clear(&target); clear(&other);
    // Mielikki's exclusions and renewals belong to the recipient, not the caster.
    affected_type blessing{}; blessing.type = SPELL_MIELIKKI_VITALITY;
    blessing.duration = 1; affect_to_char(&target, &blessing);
    spell_mielikki_vitality(50, &caster, nullptr, 0, &target, nullptr);
    assert(target.affected->duration == mielikki_vitality_duration()); clear(&target);
    affect_to_char(&caster, &blessing);
    spell_mielikki_vitality(50, &caster, nullptr, 0, &target, nullptr);
    assert(affected_by_spell(&target, SPELL_MIELIKKI_VITALITY));
    clear(&caster); clear(&target);
    // The restore-spirit lingering drain reaches a new recipient.
    target.points.vitality = 100; reset_rolls();
    spell_restore_spirit(50, &caster, nullptr, 0, &target, nullptr);
    assert(affected_by_spell(&target, SPELL_RESTORE_SPIRIT)); clear(&target);
    // Acid immolate also stops at its upper event limit with all-zero stop rolls.
    counter = 7; scheduled = 0;
    event_acidimmolate(&caster, &target, nullptr, &counter);
    assert(scheduled == 0);
    // The psionic health gate accepts injuries down to exactly 20%, not just full HP.
    for (int hp : {19, 20, 50, 99, 100}) {
        clear(&target); target.points.hit = hp; target.points.max_hit = 100;
        scheduled = 0;
        spell_psionic_wave_blast(50, &caster, nullptr, 0, &target, nullptr);
        assert(affected_by_spell(&target, SPELL_PSIONIC_WAVE_BLAST) == (hp >= 20));
        assert(scheduled == (hp >= 20));
    }
    clear(&target);
    // Righteous aura must never mistake the owner for an opposing aura holder.
    caster.specials.affected_by2 = 0;
    blessing.type = SPELL_RIGHTEOUS_AURA; affect_to_char(&caster, &blessing);
    blessing.type = SPELL_BLEAK_FOEMAN; affect_to_char(&caster, &blessing);
    rooms[1].people = &caster; caster.next_in_room = nullptr; attacks = 0;
    event_righteous_aura_check(&caster, nullptr, nullptr, nullptr);
    assert(attacks == 0); clear(&caster);
    // Each discharge target rolls its own level-dependent save modifier.
    caster.group = target.group = other.group = nullptr;
    target.player.level = 10; other.player.level = 50;
    rooms[1].people = &target; target.next_in_room = &other; other.next_in_room = nullptr;
    blessing.type = SPELL_ETHEREAL_FORM; affect_to_char(&caster, &blessing);
    blessing.type = SPELL_ARMOR; affect_to_char(&target, &blessing); affect_to_char(&other, &blessing);
    save_mods.clear();
    spell_ethereal_discharge(50, &caster, nullptr, 0, &target, nullptr);
    assert(save_mods.size() == 2);
    assert(save_mods[0].first == &target && save_mods[1].first == &other);
    assert(save_mods[0].second != save_mods[1].second);
    clear(&caster); clear(&target); clear(&other);
    target.specials.position = POS_STANDING + STAT_NORMAL;
    target.points.hit = 100; target.player.race = RACE_HUMAN;
    reset_rolls(); save_target = nullptr;
    spell_stunning_visions(50, &caster, nullptr, 0, &target, nullptr);
    assert(save_target == &target);
    // Curing an ailment must preserve the meditation event chain.
    caster.specials.affected_by = AFF_MEDITATE | AFF_BLIND;
    caster_pc.skills[SKILL_ADVANCED_MEDITATION].learned = 100;
    scheduled = 0; reset_rolls();
    event_meditation(&caster, nullptr, nullptr, nullptr);
    assert(scheduled == 1 && !IS_AFFECTED(&caster, AFF_BLIND));
    caster.specials.affected_by2 = AFF2_POISONED;
    event_meditation(&caster, nullptr, nullptr, nullptr);
    assert(scheduled == 2 && !IS_AFFECTED2(&caster, AFF2_POISONED));
    clear(&caster);
    // Three hidden rope users fill the room's cap, including a recast on one of them.
    affected_type rope{}; rope.type = SPELL_ROPE_TRICK;
    for (auto *ch : {&caster, &target, &other}) {
        affect_to_char(ch, &rope); ch->specials.affected_by = AFF_HIDE;
    }
    rooms[1].people = &caster; caster.next_in_room = &target;
    target.next_in_room = &other; other.next_in_room = nullptr;
    spell_rope_trick(50, &caster, nullptr, 0, &target, nullptr);
    assert(!target.affected->next);
    clear(&caster); clear(&target); clear(&other);
    // Recasts cannot replace three game hours with the cast level.
    target.player.size = SIZE_MEDIUM;
    for (auto spell : {spell_enlarge, spell_reduce}) {
        spell(50, &caster, nullptr, 0, &target, nullptr);
        assert(target.affected);
        target.affected->duration = 1;
        spell(50, &caster, nullptr, 0, &target, nullptr);
        for (auto *af = target.affected; af; af = af->next) assert(af->duration == 3);
        clear(&target);
    }
    // Item casts above the caster's level retain a proportional duration.
    caster.player.level = 50;
    assert(KludgeDuration(&caster, 60, 60) == 50);
    assert(KludgeDuration(&caster, 25, 10) == 20);
    caster.specials.affected_by5 = AFF5_MINE;
    spell_lodestone_vision(50, &caster, nullptr, 0, &target, nullptr);
    assert(affected_by_spell(&target, SPELL_LODESTONE));
    clear(&caster); clear(&target);
    affected_type sap{}; sap.type = SPELL_SAP_NATURE; sap.duration = 1;
    affect_to_char(&caster, &sap);
    spell_sap_nature(50, &caster, nullptr, 0, &target, nullptr);
    assert(affected_by_spell(&target, SPELL_SAP_NATURE));
    assert(caster.affected->duration == 1);
    target.affected->duration = 1;
    spell_sap_nature(50, &caster, nullptr, 0, &target, nullptr);
    assert(target.affected->duration > 1);
    clear(&caster); clear(&target);
    // The rare cyclone outcome is reachable without losing the ordinary stun tier.
    target.specials.affected_by = AFF_FLY;
    for (int roll : {1, 5, 6, 50, 51}) {
        stun_duration = 0; reset_rolls({roll, 0});
        spell_cyclone(50, &caster, nullptr, 0, &target, nullptr);
        assert(stun_duration == (roll <= 5 ? PULSE_VIOLENCE : roll <= 50 ? cyclone_stun() : 0));
    }
    target.specials.affected_by = 0;
    reset_rolls();
    // Nonpositive damage cannot add to innate or spell wards.
    caster.points.ward = 50;
    affected_type ward{}; ward.type = SPELL_LESSER_GUARDIAN_WARD;
    ward.flags = AFFTYPE_DAM_WARD; ward.modifier = 40;
    auto *ward_af = affect_to_char(&caster, &ward);
    for (int damage : {-100, -1, 0}) {
        assert(check_damage_ward(&target, &caster, damage) == 0);
        assert(caster.points.ward == 50 && ward_af->modifier == 40);
    }
    clear(&caster);
    // Mortal healing drains both shared absorb pools, including pool exhaustion.
    caster.player.level = 50;
    for (int type : {SPELL_BMANTLE, SPELL_FLAMESTRIKE}) {
        affected_type mantle{}; mantle.type = type; mantle.modifier = 60;
        affect_to_char(&caster, &mantle); caster.points.hit = 100;
        assert(vamp(&caster, 100, 500, false) == 50);
        assert(get_spell_from_char(&caster, type)->modifier == 10);
        assert(vamp(&caster, 100, 500, false) == 90);
        assert(!affected_by_spell(&caster, type));
    }
    // A killer without soul trap heals the skilled group trapper.
    caster_pc.skills[SKILL_SOUL_TRAP].learned = 0;
    target_pc.skills[SKILL_SOUL_TRAP].learned = 100;
    group_list trapper{&target, nullptr}; caster.group = &trapper;
    target.points.hit = 100; target.points.max_hit = 500; other.player.level = 50;
    assert(soul_trap(&caster, &other));
    assert(target.points.hit == 200);
    clear(&caster); clear(&target); clear(&other);
    std::puts("PASS high-confidence gameplay: targets, refreshes, stats, costs, room loops and event limits");
}
'''


functions = []
for file, names in FUNCTIONS.items():
    text = source(file).read_text()
    for name in names:
        match = re.search(r"^(?:static )?[\w:* ]+\b" + name + r"\([^;]*?\)\n\{", text, re.M)
        assert match, (file, name)
        functions.append(extract_function(file, match.group()[:-2]))

out = ROOT / "bin/tests/high-confidence-gameplay"
out.mkdir(parents=True, exist_ok=True)
cpp, binary = out / "harness.cpp", out / "harness"
cpp.write_text(PRELUDE + "\n".join(functions) + DRIVER)
subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                "-fno-pie", "-no-pie", "-Isrc", str(cpp), "-o", str(binary)], cwd=ROOT, check=True)
subprocess.run([str(binary)], check=True, timeout=30)
