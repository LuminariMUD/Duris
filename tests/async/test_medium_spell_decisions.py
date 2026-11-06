#!/usr/bin/env python3
"""Execute #715 owner decisions at spell, resource, room and expiry boundaries."""
import re
import subprocess

from _paths import ROOT, source
from _source_contract import function_bodies, strip_comments


def functions(file, names):
    text = strip_comments(source(file).read_text())
    result = []
    for name in names.split():
        signature = rf"(?m)^(?:static )?[\w:* ]+\b{name}\s*\([^;]*?\)\s*\n(?=\{{)"
        match = re.search(signature, text)
        assert match, (file, name)
        result.append(match.group() + function_bodies(text, signature)[0])
    return "\n".join(result)


PRELUDE = r'''
#include "abilities/abilities.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "world/events.h"
#include "world/db.h"
#include "world/map.h"
#include "world/graph.h"
#include "item/objmisc.h"
#include "world/vnum.obj.h"
#include "combat/damage.h"
#include "magic/spells.h"
#include "net/comm.h"
#include <cassert>
#include <cstring>
#include <cstdio>
#include <algorithm>
#include <type_traits>
#include <vector>

static room_data rooms[4]{};
P_room world = rooms;
static zone_data zones[1]{};
zone_data *zone_table = zones;
static index_data mobs[1000]{};
P_index mob_index = mobs;
const int top_of_world = 3;
P_nevent ne_schedule[PULSES_IN_TICK]{};
P_char character_list;
const char *spells[MAX_SKILLS + 1]{};
static bool saved, shrug, consent, introduced, war, portal_allowed, necroplasm;
static int roll, roll_count, damage_done, damage_calls, damage_result, shrug_attempts, last_save_mod;
static double precise_damage;
static std::vector<int> draws;
static uint damage_flags;
static std::vector<P_char> recipients;
static P_char pet_master;
static int paralyzed, restored, waited, deaths, technique, refusals, extracted;
static std::vector<P_obj> objects;
static bool fail_object;
static bool kill_area_caster;
static int decay_duration;
struct Pending { P_char ch; event_func func; int delay; std::vector<char> payload; };
static std::vector<Pending> pending;
static int rescheduled;
bool has_innate(P_char, int) { return false; }
int CheckMindflayerPresence(P_char) { return 0; }
int number(int lo, int hi) {
    ++roll_count;
    int value = roll;
    if (!draws.empty()) { value = draws.front(); draws.erase(draws.begin()); }
    return std::clamp(value, lo, hi);
}
int dice(int count, int size) {
    if (count == 1 && size == 3 && technique) return technique;
    return std::max(1, count) * size;
}
const Rolls live_rolls = {dice, number};
int get_property(const char *, int fallback) { return fallback; }
float get_property(const char *, double fallback) { return fallback; }
int GET_CHAR_SKILL_P(P_char ch, int skill) { return ch->only.pc->skills[skill].learned; }
int STAT_INDEX(int stat) { return stat; }
int BOUNDED(int low, int value, int high) { return std::clamp(value, low, high); }
float BOUNDEDF(float low, float value, float high) { return std::clamp(value, low, high); }
int panic_corruption_int(const char *, const char *, ...) { std::abort(); }
bool SanityCheck(P_char ch, const char *) { return ch; }
bool require_char(P_char ch, const char *, const char *, ...) { return ch; }
void logit(const char *, const char *, ...) {}
void debug(const char *, ...) {}
void send_to_char(const char *text, P_char) { refusals += std::strstr(text, "plane") != nullptr; }
void send_to_room(const char *, int) {}
void zone_spellmessage(int, bool, const char *, const char *) {}
void make_dry(P_char) {}
void spell_single_firestorm(int, P_char, char *, int, P_char, P_obj) {}
int cast_as_damage_area(P_char ch, spell_func, int, P_char, float, float) {
    if (kill_area_caster) delete ch;
    return 0;
}
void act(const char *, int, P_char, P_obj, void *, int) {}
void appear(P_char, bool) {}
void do_point(P_char, P_char) {}
void update_pos(P_char) {}
void CharWait(P_char, int amount) { waited += amount; }
void die(P_char, P_char) { ++deaths; }
void extract_char(P_char) { ++extracted; }
const char *get_god_name(P_char) { return "test"; }
int attack_back(P_char, P_char, int) { return DAM_NONEDEAD; }
void remember(P_char, P_char) {}
void MobStartFight(P_char, P_char) {}
void StopMercifulAttackers(P_char) {}
void stop_fighting(P_char ch) { ch->specials.fighting = nullptr; }
void spell_minor_paralysis(int, P_char, char *, int, P_char, P_obj) { ++paralyzed; }
bool resists_spell(P_char, P_char) { ++shrug_attempts; return shrug; }
bool StatSave(P_char, int, int) { return saved; }
bool NewSaves(P_char, int, int mod) { last_save_mod = mod; return saved; }
bool saves_spell(P_char, int) { return saved; }
int get_default_save_mod(P_char, P_char, int, int) { return 0; }
bool ac_can_see(P_char, P_char, bool) { return true; }
bool racewar(P_char, P_char) { return war; }
int race_portal_check(P_char, P_char) { return portal_allowed; }
bool is_linked_to(P_char, P_char, ush_int) { return consent; }
int is_introd(P_char, P_char) { return introduced; }
P_char get_linked_char(P_char, ush_int) { return pet_master; }
bool is_wearing_necroplasm(P_char) { return necroplasm; }
int get_max_circle(P_char) { return 5; }
int max_spells_in_circle(P_char, int) { return 3; }
void gmcp_spell_preparation_changed(P_char) { ++restored; }
void event_short_affect(P_char, P_char, P_obj, void *);
static void refresh_flags(P_char ch) {
    ch->specials.affected_by = ch->specials.affected_by2 = 0;
    ch->specials.affected_by3 = ch->specials.affected_by4 = ch->specials.affected_by5 = 0;
    for (auto *af = ch->affected; af; af = af->next) {
        if (af->flags & AFFTYPE_NOAPPLY) continue;
        ch->specials.affected_by |= af->bitvector;
        ch->specials.affected_by2 |= af->bitvector2;
        ch->specials.affected_by3 |= af->bitvector3;
        ch->specials.affected_by4 |= af->bitvector4;
        ch->specials.affected_by5 |= af->bitvector5;
    }
}
void affect_remove(P_char ch, affected_type *target) {
    for (auto **p = &ch->affected; *p; p = &(*p)->next) {
        if (*p != target) continue;
        *p = target->next; delete target; refresh_flags(ch); return;
    }
    assert(false);
}
void affect_from_char(P_char ch, int type) {
    for (auto *af = ch->affected; af;) {
        auto *next = af->next;
        if (af->type == type) affect_remove(ch, af);
        af = next;
    }
}
bool affected_by_spell(P_char ch, int type) {
    for (auto *af = ch->affected; af; af = af->next) if (af->type == type) return true;
    return false;
}
affected_type *get_spell_from_char(P_char ch, int type, void *, int) {
    for (auto *af = ch->affected; af; af = af->next) if (af->type == type) return af;
    return nullptr;
}
nevent_schedule_result add_event(event_func fn, int delay, P_char ch, P_char, P_obj, int,
                                 const void *data, int length) {
    Pending event{ch, fn, delay, {}};
    if (length) event.payload.assign(static_cast<const char *>(data), static_cast<const char *>(data) + length);
    pending.push_back(event); return {};
}
affected_type *affect_to_char(P_char ch, affected_type *af) {
    auto *copy = new affected_type(*af); copy->next = ch->affected; ch->affected = copy;
    refresh_flags(ch);
    if (af->flags & AFFTYPE_SHORT) {
        event_short_affect_data data{ch, copy};
        add_event(event_short_affect, af->duration, ch, nullptr, nullptr, 0, &data, sizeof(data));
    }
    return copy;
}
void wear_off_message(P_char, affected_type *) {}
bool nevent_reschedule_after(nevent_handle, unsigned long long delay) { rescheduled = delay; return true; }
nevent_handle nevent_handle_from_event(P_nevent e) { return {e, 1}; }
int spell_damage(P_char, P_char victim, double dam, int, uint flags, damage_messages *, int *) {
    precise_damage = dam; damage_done = dam; damage_flags = flags; ++damage_calls; recipients.push_back(victim);
    if (damage_result == DAM_VICTDEAD) {
        for (auto &room : rooms) {
            for (auto **person = &room.people; *person; person = &(*person)->next_in_room) {
                if (*person == victim) { *person = victim->next_in_room; break; }
            }
        }
        delete victim;
    }
    return damage_result;
}
int melee_damage(P_char, P_char victim, double dam, int flags, damage_messages *, int *) {
    damage_done = dam; damage_flags = flags; ++damage_calls; victim->points.hit -= dam;
    return DAM_NONEDEAD;
}
bool damage(P_char, P_char, double, int) { return false; }
static void buff(P_char ch) { recipients.push_back(ch); }
void spell_vitality(int, P_char, char *, int, P_char ch, P_obj) { buff(ch); }
void spell_armor(int, P_char, char *, int, P_char ch, P_obj) { buff(ch); }
void spell_bless(int, P_char, char *, int, P_char ch, P_obj) { buff(ch); }
void spell_vitalize_undead(int, P_char, char *, int, P_char ch, P_obj) { buff(ch); }
void spell_protection_from_living(int, P_char, char *, int, P_char ch, P_obj) { buff(ch); }
void heal(P_char victim, P_char, int amount, int) { victim->points.hit += amount; }
int vamp(P_char, double amount, double, bool) { return amount; }
void StartRegen(P_char, regen_resource) {}
int fight_in_room(P_char) { return 0; }
bool resurrect_corpse(int, P_char, P_obj obj) {
    if (obj->value[2] <= 0) return false;
    extract_obj(obj, false); return true;
}
bool check_freedom_of_movement(P_char) { return false; }
void DamageStuff(P_char, int) {}
void disarm_char_nevents(P_char, event_func_type) {}
P_nevent get_scheduled(P_char, event_func_type) { return reinterpret_cast<P_nevent>(1); }
int is_Raidable(P_char, char *, int) { return true; }
int how_close(int, int, int) { return 0; }
void char_from_room(P_char ch) { ch->in_room = NOWHERE; }
bool char_to_room(P_char ch, int room, int) { ch->in_room = room; return true; }
bool grouped(P_char ch, P_char target) { return ch->group && ch->group == target->group; }
int IS_MORPH(P_char) { return false; }
bool AdjacentInRoom(P_char, P_char) { return true; }
P_char get_linking_char(P_char, ush_int) { return nullptr; }
int is_char_in_room(const P_char ch, int room) {
    for (auto *person = rooms[room].people; person; person = person->next_in_room)
        if (person == ch) return true;
    return false;
}
static room_affect room_af[4]{};
room_affect *get_spell_from_room(P_room room, int type) {
    auto *af = &room_af[room - rooms]; return af->type == type ? af : nullptr;
}
room_affect *affect_to_room(int room, room_affect *af) { room_af[room] = *af; return &room_af[room]; }
void affect_room_remove(int room, room_affect *) { room_af[room] = {}; }
nevent_cancel_result nevent_cancel(nevent_handle h) {
    ne_schedule[h.event->element] = h.event->next_sched;
    return nevent_cancel_result::canceled;
}
int real_object(int vnum) { return vnum; }
P_obj read_object(int vnum, int) {
    if (fail_object) return nullptr;
    auto *obj = new obj_data{}; obj->R_num = vnum; objects.push_back(obj); return obj;
}
void obj_to_room(P_obj obj, int room) { obj->next_content = rooms[room].contents; rooms[room].contents = obj; }
void extract_obj(P_obj obj, int) {
    for (auto &room : rooms) for (auto **p = &room.contents; *p; p = &(*p)->next_content)
        if (*p == obj) { *p = obj->next_content; goto unlinked; }
unlinked:
    objects.erase(std::find(objects.begin(), objects.end(), obj)); delete obj;
}
void set_obj_affected(P_obj, int duration, int, int) { decay_duration = duration; }
static char_data alive() {
    char_data ch{}; ch.player.level = 50; ch.player.race = RACE_HUMAN;
    ch.specials.position = POS_STANDING + STAT_NORMAL; ch.in_room = 1;
    ch.points.hit = ch.points.max_hit = 1000; return ch;
}
static void clear(P_char ch) { while (ch->affected) affect_remove(ch, ch->affected); pending.clear(); }
#define PROFILE_START(name)
#define PROFILE_END(name)
'''

SCALARS = {
    "fight.c": "essence_of_wolf_attacks essence_of_wolf_attack_cap essence_of_wolf_offhand_roll",
    "utility.c": "GET_CLASS GET_PRIME_CLASS GET_SECONDARY_CLASS should_area_hit",
    "smagic.c": "mending_improved_bonus mending_healing greater_mending_healing",
    "magic.c": "aid_duration spore_burst_level stigmata_draconica_duration globe_duration spell_globe "
               "sleep_duration spell_sleep death_blessing_leader_level death_blessing_member_level "
               "spell_miracle spell_death_blessing burning_hands_damage spell_burning_hands "
               "firestorm_room_duration spell_firestorm immolate_damage magma_burst_flares "
               "decaying_flesh_damage decaying_flesh_interval event_fleshdecay "
               "heavens_aid_slay_level heavens_aid_slay_damage heavens_aid_damage heavens_aid_pc_damage "
               "heavens_aid_factor spell_heavens_aid energy_drain_duration "
               "energy_drain_level energy_drain_damage energy_drain_saved energy_drain_kill_level "
               "energy_drain_vamp energy_drain_taps energy_drain_moves energy_drain_regen spell_energy_drain "
               "can_do_general_portal grow_spike_damage grow_spike_saved grow_spike_terrain grow_spike "
               "banish_base_chance banish_outlevel_margin banish_outlevel_chance banish_zealot_chance "
               "banish_greater_chance banish_bounded_chance banish_roll spell_single_banish can_banish spell_banish "
               "ray_of_enfeeblement_chance ray_of_enfeeblement_duration ray_of_enfeeblement_damroll spell_ray_of_enfeeblement "
               "entangle_bind_chance entangle_bind_roll entangle_duration spell_entangle",
    "psionics.c": "memory_block_forget_roll memory_block_duration spell_memory_block "
                  "inertial_barrier_duration spell_inertial_barrier cannibalize_duration spell_cannibalize "
                  "improved_wormhole_bonus wormhole_throughput thought_beacon_duration spell_thought_beacon "
                  "psionic_wave_blast_damage psionic_wave_blast_shrug_roll psionic_wave_blast_waves "
                  "psionic_wave_blast_wave_damage psionic_wave_blast_failed_save psionic_wave_blast_away "
                  "psionic_wave_blast_interval psionic_wave_blast_mana spell_psionic_wave_blast event_psionic_wave_blast",
    "ethermancer.c": "cosmic_vacuum_curse static_discharge_level static_discharge_damage "
                    "static_discharge_failed_save static_discharge_wet_damage static_discharge "
                    "etheric_gust_range etheric_gust_limited_range etheric_gust_direction_roll "
                    "etheric_gust_zone_room_roll etheric_gust_lag etheric_gust_room_limited spell_etheric_gust",
    "blispells.c": "waves_fatigue_moves waves_fatigue_saved event_waves_fatigue "
                  "toxic_fog_damage toxic_fog_saved spell_toxic_fog thornskin_duration "
                  "thornskin_armor_class spell_thornskin bloodstone_duration spell_bloodstone",
    "memorize.c": "uses_slot_recovery lucubration_roll lucubration_chance spell_mordenkainens_lucubration",
    "necromancy.c": "raised_undead_death_delay corpse_pet_death_delay undead_to_death_fixed_save "
                    "undead_to_death_save undead_to_death_level undead_to_death_damage "
                    "undead_to_death_soulshield_damage undead_to_death_soulshield_save "
                    "undead_to_death_lucky_roll undead_to_death_lucky_damage undead_to_death_other_damage "
                    "undead_to_death_weak_duration undead_to_death_strength_loss undead_to_death_constitution_loss "
                    "undead_to_death_agility_loss undead_to_death_dexterity_loss spell_undead_to_death",
    "reavers.c": "lliendils_stormshock_damage lliendils_stormshock",
    "affects.c": "event_short_affect",
    "magic/spells.c": "aura_of_rebirth_hit_points aura_of_rebirth_fatal_above aura_of_rebirth_lag "
                "cast_area_resurrect event_transmute_bye finish_room_transmute spike_growth_damage "
                "spike_growth_duration spike_growth_interval spike_growth_affect_chance "
                "spike_growth_affect_roll spike_growth_technique spike_growth_foot_damage "
                "spike_growth_foot_lag spike_growth_bone_damage event_spike_growth "
                "awaken_forest_duration awaken_forest_interval awaken_forest_affect_roll "
                "awaken_forest_pass_above awaken_forest_technique awaken_forest_entangle_level "
                "awaken_forest_root_roll awaken_forest_root_save awaken_forest_root_lag "
                "awaken_forest_branch_damage event_awaken_forest",
}

DRIVER = r'''
int main() {
    char_data caster = alive(), target = alive();
    std::remove_pointer_t<decltype(caster.only.pc)> pc{}, target_pc{};
    caster.only.pc = &pc; target.only.pc = &target_pc; character_list = &target;
    for (int level : {1, 2, 5, 9, 10, 50, 56, 60}) {
        caster.player.level = level; roll = -100;
        assert(mending_healing(live_rolls, level, &caster) >= 1);
        assert(greater_mending_healing(live_rolls, level, &caster) >= 1);
        assert(wormhole_throughput(live_rolls, &caster) >= 1);
        assert(cosmic_vacuum_curse(level) >= 0);
        assert(waves_fatigue_saved(waves_fatigue_moves(live_rolls, &caster)) >= 1);
        assert(aid_duration(level) == std::max(3, (level + 4) / 10));
        assert(energy_drain_duration(level) <= 5 * WAIT_SEC);
        assert(raised_undead_death_delay(level, 1) == level * PULSES_IN_TICK + 2 * 60 * WAIT_SEC);
        assert(corpse_pet_death_delay(level) > level * PULSES_IN_TICK);
        assert(inertial_barrier_duration() == 30);
        clear(&caster); spell_inertial_barrier(level, &caster, nullptr, 0, &caster, nullptr);
        caster.affected->duration = 1;
        spell_inertial_barrier(level, &caster, nullptr, 0, &caster, nullptr);
        assert(caster.affected->duration == 30); clear(&caster);
        spell_cannibalize(level, &caster, nullptr, 0, &caster, nullptr);
        caster.affected->duration = 1;
        spell_cannibalize(level, &caster, nullptr, 0, &caster, nullptr);
        assert(caster.affected->duration == level); clear(&caster);
    }
    caster.player.level = 50;
    for (int skill : {0, 25, 50, 100}) {
        pc.skills[SKILL_SPELL_KNOWLEDGE_SHAMAN].learned = skill;
        assert(stigmata_draconica_duration(&caster) == 15 + skill / 5);
    }
    caster.specials.affected_by5 = AFF5_MENTAL_ANGUISH;
    assert(GET_CHAR_SKILL((&caster), SKILL_SPELL_KNOWLEDGE_SHAMAN) == 10);
    caster.specials.affected_by5 = 0;
    for (int spores : {1, 2, 6}) assert(spore_burst_level(&caster, spores) == 50 + (spores - 1) * 4);
    caster.points.damsizedice = 6; target.points.damsizedice = 8;
    caster.player.m_class = CLASS_SHAMAN; caster.player.spec = SPEC_ANIMALIST;
    summon_beast_bonus(&caster, &target);
    assert(caster.points.damsizedice == 6 && target.points.damsizedice == 12);
    obj_data offhand{}; caster.equipment[SECONDARY_WEAPON] = &offhand; roll = 1;
    for (int level : {1, 5, 9, 10, 20, 50}) {
        caster.player.level = level;
        auto attacks = wolf_attacks(&caster);
        assert(std::count(attacks.begin(), attacks.end(), SECONDARY_WEAPON) == (level < 10 ? 1 : 2));
        assert(attacks.size() <= size_t(1 + level / 10));
    }
    caster.equipment[SECONDARY_WEAPON] = nullptr; caster.player.level = 50;
    for (int hp : {-1, 0, 1, 2, 20, 100}) {
        target.points.hit = hp; target.specials.affected_by5 = AFF5_DECAYING_FLESH;
        damage_calls = 0; int waves = 2;
        event_fleshdecay(&target, &caster, nullptr, &waves);
        assert(target.points.hit == (hp > 1 ? std::max(1, hp - 50) : hp));
        assert(damage_calls == (hp > 1));
        if (hp > 1) assert(damage_flags & RAWDAM_NOKILL);
    }
    clear(&target); saved = false;
    for (auto spell : {spell_globe, spell_sleep}) {
        spell(50, &caster, nullptr, 0, &target, nullptr);
        int duration = target.affected->duration;
        target.affected->duration = duration - 1;
        spell(50, &caster, nullptr, 0, &target, nullptr);
        assert(target.affected && !target.affected->next);
        assert(target.affected->duration <= duration); clear(&target);
    }
    for (int intensity = 1; intensity <= 6; ++intensity) {
        static_discharge(&caster, &target, 50, intensity);
        assert(damage_flags & SPLDAM_NODEFLECT);
        assert(bool(damage_flags & SPLDAM_GLOBE) == (intensity < 2));
        assert(bool(damage_flags & SPLDAM_GRSPIRIT) == (intensity < 3));
        assert(bool(damage_flags & SPLDAM_NOSHRUG) == (intensity >= 5));
    }
    for (bool save : {false, true}) {
        saved = save; spell_toxic_fog(50, &caster, nullptr, 0, &target, nullptr);
        assert(damage_done == (save ? int(560 / 1.5) : 560));
    }
    saved = false; target.points.hit = 1000;
    for (int level : {1, 50}) {
        caster.player.level = level;
        spell_memory_block(level, &caster, nullptr, 0, &target, nullptr);
        assert(IS_AFFECTED5(&target, AFF5_MEMORY_BLOCK));
        assert(pending.back().delay == std::max(1, level / 2) * WAIT_SEC);
        auto data = pending.back().payload;
        event_short_affect(&target, nullptr, nullptr, data.data());
        assert(!IS_AFFECTED5(&target, AFF5_MEMORY_BLOCK) && !target.affected);
    }
    saved = true; spell_memory_block(50, &caster, nullptr, 0, &target, nullptr);
    assert(!target.affected); saved = false;
    roll = 0; assert(memory_block_forget_roll(live_rolls) == 0);
    roll = 1; assert(memory_block_forget_roll(live_rolls) == 1);
    for (int spec : {0, SPEC_DRAGON_HUNTER, SPEC_DRAGON_PRIEST}) {
        caster.player.m_class = CLASS_DRAGOON; caster.player.spec = spec; roll = 0;
        assert(magma_burst_flares(&caster) == (spec == SPEC_DRAGON_PRIEST ? 4 : 3));
        assert(firestorm_room_duration(&caster) == int((spec == SPEC_DRAGON_PRIEST ? 2 : 1.5) * PULSE_VIOLENCE));
        for (int type : {SPELL_TYPE_SPELL, SPELL_TYPE_POTION, SPELL_TYPE_WAND, SPELL_TYPE_STAFF, SPELL_TYPE_SCROLL}) {
            spell_burning_hands(50, &caster, nullptr, type, &target, nullptr);
            assert(damage_done == (spec == SPEC_DRAGON_PRIEST ? 252 : 240));
        }
        assert(immolate_damage(live_rolls, &caster) == (spec == SPEC_DRAGON_PRIEST ? 214 : 204));
    }
    caster.player.m_class = CLASS_CLERIC; caster.player.spec = 0;
    char_data remote = alive(); remote.in_room = 2;
    group_list g3{&target, nullptr}, g2{&remote, &g3}, g1{&caster, &g2}; caster.group = &g1;
    recipients.clear(); spell_miracle(50, &caster, nullptr, 0, nullptr, nullptr);
    assert(recipients.size() == 6 && std::find(recipients.begin(), recipients.end(), &remote) == recipients.end());
    recipients.clear(); spell_death_blessing(50, &caster, nullptr, 0, nullptr, nullptr);
    assert(recipients.size() == 4 && std::find(recipients.begin(), recipients.end(), &remote) == recipients.end());
    caster.group = nullptr;
    for (int level : {24, 25, 26}) {
        target.player.level = level; paralyzed = 0;
        spell_heavens_aid(50, &caster, nullptr, 0, &target, nullptr);
        assert(paralyzed == (level < 25));
    }
    saved = true; target.base_stats.Str = target.curr_stats.Str = 100;
    target.points.damroll = 50; roll_count = 0; roll = 1;
    spell_ray_of_enfeeblement(50, &caster, nullptr, 0, &target, nullptr);
    assert(roll_count == 3); // One success roll, one strength roll, one damroll roll.
    clear(&target); saved = false;
    for (int hit = 0; hit < 3; ++hit) {
        roll = hit; shrug_attempts = 0; caster.points.mana = 1000;
        target.points.hit = target.points.max_hit = 1000;
        spell_psionic_wave_blast(50, &caster, nullptr, 0, &target, nullptr);
        assert(shrug_attempts == (hit == 0));
        shrug_attempts = 0; int level = 50;
        event_psionic_wave_blast(&caster, &target, nullptr, &level);
        assert(shrug_attempts == (hit == 0));
        clear(&target);
    }
    clear(&caster);
    obj_data sword{}; sword.type = ITEM_WEAPON; sword.value[0] = WEAPON_LONGSWORD;
    caster.specials.affected_by3 = AFF3_LIGHTNINGSHIELD;
    draws = {5, 5};
    lliendils_stormshock(&caster, &target, &sword);
    assert(std::abs(precise_damage - 5.5) < 0.00001);
    caster.specials.affected_by3 = 0; roll = 5;
    lliendils_stormshock(&caster, &target, &sword);
    assert(precise_damage == 5);
    target.player.race = RACE_LICH; target.player.level = 40;
    caster.specials.act = ACT_ELITE;
    spell_undead_to_death(50, &caster, nullptr, 0, &target, nullptr);
    assert(last_save_mod == 10);
    caster.specials.act = 0; target.specials.act = ACT_ELITE;
    spell_undead_to_death(50, &caster, nullptr, 0, &target, nullptr);
    assert(last_save_mod == undead_to_death_fixed_save());
    target.specials.act = 0; target.player.race = RACE_HUMAN;
    // Recover the resource the existing preparation system selects, including multiclasses.
    for (int kind = 0; kind < 17; ++kind) {
        clear(&caster); caster.player.m_class = CLASS_SORCERER;
        caster.player.secondary_class = 0; caster.player.race = RACE_HUMAN;
        caster.specials.act = 0; necroplasm = false;
        switch (kind) {
        case 1: caster.player.m_class = CLASS_DRUID; break;
        case 2: caster.player.m_class = CLASS_RANGER; break;
        case 3: caster.player.m_class = CLASS_DRAGOON; break;
        case 4: caster.player.m_class = CLASS_BLIGHTER; break;
        case 5: caster.player.race = RACE_HARPY; break;
        case 6: caster.player.m_class = CLASS_ETHERMANCER; break;
        case 7: caster.player.race = RACE_DEVA; break;
        case 8: caster.player.m_class = CLASS_WARLOCK; break;
        case 9: caster.player.race = RACE_PSBEAST; break;
        case 10: caster.specials.affected_by4 = AFF4_VAMPIRE_FORM; break;
        case 11: caster.player.race = RACE_LICH; break;
        case 12: necroplasm = true; break;
        case 13: caster.specials.act = ACT_ISNPC; break;
        case 14: caster.player.m_class = CLASS_WARRIOR; caster.player.secondary_class = CLASS_DRUID; break;
        case 15: caster.player.secondary_class = CLASS_DRUID; break;
        case 16: caster.player.m_class = CLASS_PSIONICIST; break;
        }
        // Ordinary and secondary druid-on-sorcerer casters retain memorized recovery.
        const bool slots = kind != 0 && kind != 15 && kind != 16;
        affected_type af{}; af.type = TAG_MEMORIZE; af.modifier = SPELL_MAGIC_MISSILE;
        af.bitvector4 = caster.specials.affected_by4;
        affect_to_char(&caster, &af);
        for (auto &slot : caster.specials.undead_spell_slots) slot = 0;
        restored = 0; roll = 0;
        spell_mordenkainens_lucubration(50, &caster, nullptr, 0, nullptr, nullptr);
        assert(bool(caster.affected->flags & MEMTYPE_FULL) == (!slots && kind != 16));
        assert(caster.specials.undead_spell_slots[1] == (slots ? 3 : 0));
        assert(caster.specials.undead_spell_slots[5] == 0); // Highest circle stays excluded.
    }
    clear(&caster); clear(&target);
    // Invalid thornskin casts stop before saves, affects or damage.
    spell_thornskin(50, nullptr, nullptr, 0, &target, nullptr);
    spell_thornskin(50, &caster, nullptr, 0, nullptr, nullptr);
    target.specials.position = STAT_DEAD;
    spell_thornskin(50, &caster, nullptr, 0, &target, nullptr);
    assert(!target.affected);
    caster = alive(); caster.only.pc = &pc; target = alive(); target.only.pc = &target_pc;
    // Each short regeneration penalty's scheduled deadline is refreshed, even on a save.
    spell_energy_drain(50, &caster, nullptr, 0, &target, nullptr);
    assert(target.affected && target.affected->next);
    nevent_data e1{}, e2{};
    event_short_affect_data d1{&target, target.affected}, d2{&target, target.affected->next};
    e1.func = e2.func = event_short_affect; e1.data = &d1; e2.data = &d2;
    e1.next_char_nev = &e2; target.nevents = &e1;
    target.affected->duration = target.affected->next->duration = 1;
    saved = true; rescheduled = 0;
    spell_energy_drain(50, &caster, nullptr, 0, &target, nullptr);
    assert(rescheduled == 5 * WAIT_SEC);
    assert(target.affected->duration == 5 * WAIT_SEC && target.affected->next->duration == 5 * WAIT_SEC);
    target.nevents = nullptr; clear(&target); saved = false;
    // Restrictions work for ordinary targets independently of elite/greater-race flags.
    portal_settings portal{}; portal.to_room = 2;
    target.in_room = 2;
    assert(can_do_general_portal(50, &caster, &target, &portal, nullptr));
    target.specials.act2 = PLR2_NOLOCATE;
    assert(!can_do_general_portal(50, &caster, &target, &portal, nullptr));
    consent = introduced = true;
    assert(can_do_general_portal(50, &caster, &target, &portal, nullptr));
    target.specials.act2 = 0; target.specials.affected_by3 = AFF3_NON_DETECTION;
    assert(!can_do_general_portal(50, &caster, &target, &portal, nullptr));
    caster.player.level = 60;
    assert(can_do_general_portal(60, &caster, &target, &portal, nullptr));
    caster.player.level = 50; target.specials.affected_by3 = 0; war = true;
    assert(!can_do_general_portal(50, &caster, &target, &portal, nullptr));
    portal_allowed = true;
    assert(can_do_general_portal(50, &caster, &target, &portal, nullptr));
    war = false; target.in_room = 1;
    // Replace a beacon/stone in another room without removing someone else's object.
    caster.only.pc->pid = 1; character_list = &caster; caster.next = &target;
    for (auto spell : {spell_thought_beacon, spell_bloodstone}) {
        caster.in_room = 1; spell(50, &caster, nullptr, 0, nullptr, nullptr);
        const int type = caster.affected->type, vnum = objects.back()->R_num;
        auto *old = objects.back(); assert(caster.affected->duration == decay_duration);
        assert(caster.affected->flags & AFFTYPE_SHORT);
        auto *someone_elses = read_object(vnum, REAL); someone_elses->value[0] = 2;
        obj_to_room(someone_elses, 1);
        caster.in_room = 2; caster.affected->duration = 1;
        spell(50, &caster, nullptr, 0, nullptr, nullptr);
        assert(objects.size() == 2 && std::find(objects.begin(), objects.end(), old) == objects.end());
        assert(rooms[1].contents == someone_elses);
        assert(caster.affected->modifier == 2 && caster.affected->duration == decay_duration);
        fail_object = true;
        auto *link = caster.affected;
        spell(50, &caster, nullptr, 0, nullptr, nullptr);
        assert(caster.affected == link); fail_object = false;
        auto expiry = pending.back().payload;
        event_short_affect(&caster, nullptr, nullptr, expiry.data());
        assert(!affected_by_spell(&caster, type));
        while (!objects.empty()) extract_obj(objects.back(), false);
        clear(&caster);
    }
    // A terrain recast keeps the first terrain/flags until the final room-owned expiry.
    grow_data original{}; original.room = 1; original.old_sect = SECT_FIELD; original.flags = ROOM_DARK;
    nevent_data restore{}; restore.func = event_transmute_bye; restore.data = &original;
    restore.element = 3; ne_schedule[3] = &restore;
    rooms[1].sector_type = SECT_FOREST; rooms[1].room_flags = ROOM_INDOORS;
    grow_data recast{}; recast.room = 1; recast.duration = 200;
    finish_room_transmute(&caster, &recast);
    assert(!ne_schedule[3]);
    auto final_expiry = pending.back().payload;
    auto *original_again = reinterpret_cast<grow_data *>(final_expiry.data());
    assert(original_again->old_sect == SECT_FIELD && original_again->flags == ROOM_DARK);
    event_transmute_bye(nullptr, nullptr, nullptr, final_expiry.data());
    assert(rooms[1].sector_type == SECT_FIELD && rooms[1].room_flags == ROOM_DARK);
    rooms[1].room_flags = 0;
    // All three spike outcomes remain at the original room, with the same 10% penalty.
    caster.in_room = 2; rooms[2].sector_type = SECT_OCEAN; target.next_in_room = nullptr;
    rooms[1].people = &target; roll = 100;
    for (int effect : {1, 2, 3}) {
        technique = effect;
        spike_growth_data growth{1, 0}; rooms[1].sector_type = SECT_FOREST;
        event_spike_growth(&caster, nullptr, nullptr, &growth);
        assert(room_af[1].type == SPELL_SPIKE_GROWTH && room_af[2].type == 0);
        growth.iter = 2;
        event_spike_growth(&caster, nullptr, nullptr, &growth);
        int normal = damage_done;
        rooms[1].sector_type = SECT_FIELD;
        event_spike_growth(&caster, nullptr, nullptr, &growth);
        assert(damage_done == normal * 9 / 10);
        // A killing wave must not read its freed occupant or lose the next occupant.
        auto *first = new char_data(target), *second = new char_data(target);
        first->next_in_room = second; rooms[1].people = first;
        damage_result = DAM_VICTDEAD; damage_calls = 0;
        event_spike_growth(&caster, nullptr, nullptr, &growth);
        assert(damage_calls == 2); damage_result = DAM_NONEDEAD;
        rooms[1].people = &target;
    }
    room_af[1] = {}; rooms[1].sector_type = SECT_FOREST;
    awaken_forest_data forest{1, 0};
    event_awaken_forest(&caster, nullptr, nullptr, &forest);
    assert(room_af[1].type == SPELL_AWAKEN_FOREST && room_af[2].type == 0);
    forest.iter = 2; technique = 1; roll = 1;
    event_awaken_forest(&caster, nullptr, nullptr, &forest);
    assert(IS_AFFECTED(&target, AFF_BOUND)); clear(&target);
    technique = 3; damage_calls = 0;
    event_awaken_forest(&caster, nullptr, nullptr, &forest);
    assert(damage_calls == 1);
    // Both room opponents stop fighting the departing target; the world-list decoy stays.
    char_data opponent1 = alive(), opponent2 = alive(), elsewhere = alive();
    rooms[1].people = &opponent1; opponent1.next_in_room = &opponent2;
    opponent1.next = &elsewhere;
    opponent1.specials.fighting = opponent2.specials.fighting = elsewhere.specials.fighting = &target;
    rooms[2].sector_type = SECT_FIELD; roll = 0;
    spell_etheric_gust(50, &caster, nullptr, 0, &target, nullptr);
    assert(!IS_FIGHTING(&opponent1) && !IS_FIGHTING(&opponent2));
    assert(IS_FIGHTING(&elsewhere) && target.in_room != 1);
    // Rebirth charges only successful raises, including a mixed success/refusal cast.
    caster.in_room = 3; caster.points.hit = 1000;
    cast_area_resurrect(50, &caster, nullptr, 0, nullptr, nullptr);
    assert(caster.points.hit == 1000);
    auto *corpse1 = read_object(1, REAL), *corpse2 = read_object(1, REAL);
    corpse1->type = corpse2->type = ITEM_CORPSE;
    corpse1->value[1] = corpse2->value[1] = PC_CORPSE;
    obj_to_room(corpse1, 3); obj_to_room(corpse2, 3);
    cast_area_resurrect(50, &caster, nullptr, 0, nullptr, nullptr);
    assert(caster.points.hit == 1000);
    corpse1->value[2] = 1;
    cast_area_resurrect(50, &caster, nullptr, 0, nullptr, nullptr);
    assert(caster.points.hit == 19);
    while (!objects.empty()) extract_obj(objects.back(), false);
    // A calculated percent is the count of successes among all 100 equally likely rolls.
    target = alive(); std::remove_pointer_t<decltype(target.only.npc)> npc{};
    target.only.npc = &npc; target.specials.act = ACT_ISNPC; target.player.race = RACE_UNDEAD;
    caster.in_room = target.in_room = 1;
    for (int chance : {1, 95}) {
        caster.player.level = chance == 1 ? 1 : 50;
        target.player.level = chance == 1 ? 100 : 1;
        extracted = 0;
        for (roll = 1; roll <= 100; ++roll) spell_single_banish(caster.player.level, &caster, nullptr, 0, &target, nullptr);
        assert(extracted == chance);
    }
    target.player.race = RACE_E_ELEMENTAL; rooms[1].sector_type = SECT_EARTH_PLANE;
    rooms[1].people = &target; target.next_in_room = nullptr; pet_master = &caster;
    refusals = 0; spell_banish(50, &caster, nullptr, 0, nullptr, nullptr);
    assert(refusals == 1);
    // Moving away must preserve the real area selector's protections.
    caster = alive(); caster.only.pc = &pc;
    target = alive(); target.only.pc = &target_pc;
    caster.in_room = 2; rooms[1].people = &target; rooms[1].sector_type = SECT_FOREST;
    spike_growth_data spikes{1, 2}; awaken_forest_data woods{1, 2};
    technique = 3; roll = 100;
    for (int protection : {0, 1, 2, 3}) {
        rooms[1].room_flags = protection == 0 ? ROOM_SAFE : 0;
        target.group = protection == 1 ? &g1 : nullptr;
        caster.group = protection == 1 ? &g1 : nullptr;
        target.specials.z_cord = protection == 2 ? 1 : 0;
        target.player.level = protection == 3 ? MINLVLIMMORTAL : 50;
        room_af[1].type = SPELL_SPIKE_GROWTH; damage_calls = 0;
        event_spike_growth(&caster, nullptr, nullptr, &spikes);
        assert(damage_calls == 0);
        room_af[1].type = SPELL_AWAKEN_FOREST; damage_calls = 0;
        event_awaken_forest(&caster, nullptr, nullptr, &woods);
        assert(damage_calls == 0);
    }
    rooms[1].room_flags = 0; target.group = caster.group = nullptr;
    target.specials.z_cord = 0; target.player.level = 50;
    // Privacy protects other targets, without blocking travel to one's own anchor.
    portal.to_room = 1; caster.in_room = 2; consent = false; introduced = true;
    affected_type anchor{}; anchor.type = SPELL_THOUGHT_BEACON; anchor.modifier = 1;
    affect_to_char(&caster, &anchor);
    caster.specials.act2 = PLR2_NOLOCATE;
    assert(can_do_general_portal(50, &caster, &caster, &portal, nullptr));
    caster.specials.act2 = 0; caster.specials.affected_by3 = AFF3_NON_DETECTION;
    assert(can_do_general_portal(50, &caster, &caster, &portal, nullptr));
    caster.specials.affected_by3 = 0; clear(&caster);
    // Deflected area damage can extract an NPC caster before firestorm returns.
    auto *fire_caster = new char_data(alive()); fire_caster->only.npc = &npc;
    fire_caster->specials.act = ACT_ISNPC;
    kill_area_caster = true;
    spell_firestorm(50, fire_caster, nullptr, 0, nullptr, nullptr);
    kill_area_caster = false;
    // The count pass must not consume one-shot immunity before the hit pass.
    caster.in_room = 1; roll = 1; technique = 3;
    room_af[1].type = SPELL_AWAKEN_FOREST;
    affected_type immunity{}; immunity.type = TAG_IMMUNE_AREA;
    affect_to_char(&target, &immunity); damage_calls = 0;
    event_awaken_forest(&caster, nullptr, nullptr, &woods);
    assert(!target.affected && damage_calls == 0);
    auto *forest_first = new char_data(target), *forest_second = new char_data(target);
    forest_first->next_in_room = forest_second; rooms[1].people = forest_first;
    damage_result = DAM_VICTDEAD; damage_calls = 0;
    event_awaken_forest(&caster, nullptr, nullptr, &woods);
    assert(damage_calls == 2 && !rooms[1].people);
    damage_result = DAM_NONEDEAD; rooms[1].people = &target;
    // Expiry wins over terrain, including cancellation of the grow we await.
    for (int sector : {SECT_FIELD, SECT_FOREST}) {
        rooms[1].sector_type = sector; room_af[1] = {};
        pending.clear(); damage_calls = 0;
        event_awaken_forest(&caster, nullptr, nullptr, &woods);
        assert(pending.empty() && damage_calls == 0);
    }
    rooms[1].sector_type = SECT_FIELD;
    woods.iter = 0; room_af[1].type = SPELL_GROW; pending.clear();
    event_awaken_forest(&caster, nullptr, nullptr, &woods);
    assert(pending.size() == 1 && woods.iter == 0);
    room_af[1] = {}; pending.clear();
    event_awaken_forest(&caster, nullptr, nullptr, &woods);
    assert(pending.empty());
    // A temporary non-forest interval keeps only a still-live forest effect.
    woods.iter = 2; room_af[1].type = SPELL_AWAKEN_FOREST; pending.clear();
    event_awaken_forest(&caster, nullptr, nullptr, &woods);
    assert(pending.size() == 1);
    rooms[1].sector_type = SECT_FOREST; damage_calls = 0;
    event_awaken_forest(&caster, nullptr, nullptr, &woods);
    assert(damage_calls == 1);
    rooms[1].sector_type = SECT_FIELD; room_af[1] = {}; pending.clear();
    event_awaken_forest(&caster, nullptr, nullptr, &woods);
    assert(pending.empty());
    std::puts("PASS #715 spell decisions: bounds, saves, flags, refreshes, memory expiry and caster resources");
}
'''


out = ROOT / "bin/tests/medium-spell-decisions"
out.mkdir(parents=True, exist_ok=True)
cpp, binary = out / "harness.cpp", out / "harness"
room_source = source("magic/spells.c").read_text()
structs = "\n".join(room_source[start:room_source.index("};", start) + 2]
                    for start in (room_source.index("struct " + name + "\n")
                                  for name in ("grow_data", "spike_growth_data", "awaken_forest_data")))
beast = function_bodies(source("smagic.c").read_text(), r"\bP_char\s+summon_beast_common\s*\(")[0]
beast = beast[beast.index("MonkSetSpecialDie(mob);"):]
beast_condition = r"if\s*\(GET_SPEC\(ch, CLASS_SHAMAN, SPEC_ANIMALIST\) \|\| IS_ELITE\(ch\)\)"
beast_bonus = re.search(beast_condition, beast).group() + function_bodies(beast, beast_condition)[0]
wolf = function_bodies(source("fight.c").read_text(), r"if\s*\(get_linking_char\(ch, LNK_ESSENCE_OF_WOLF\)\)")[0]
combat_blocks = "static void summon_beast_bonus(P_char ch, P_char mob) {" + beast_bonus + "}\n" + r'''
static std::vector<int> wolf_attacks(P_char ch) {
    std::vector<int> result;
#define ADD_ATTACK(slot) result.push_back(slot)
''' + wolf + r'''
#undef ADD_ATTACK
    return result;
}
'''
cpp.write_text(PRELUDE + structs + "\n".join(functions(f, names) for f, names in SCALARS.items()) + combat_blocks + DRIVER)
subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
                "-fsanitize=address,undefined", "-fno-sanitize-recover=all", "-fno-pie", "-no-pie",
                "-Isrc", str(cpp), "-o", str(binary)], cwd=ROOT, check=True)
subprocess.run([str(binary)], check=True, timeout=30)
