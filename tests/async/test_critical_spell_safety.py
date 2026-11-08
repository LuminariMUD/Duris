#!/usr/bin/env python3
"""Run critical spell handlers against released affects, targets and boundary casts."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function

fixture = r'''
#include "abilities/abilities.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "classes/necromancy.h"
#include "magic/spells.h"
#include "combat/damage.h"
#include "net/comm.h"
#include "world/graph.h"
#include "world/map.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
static room_data rooms[2]{};
static zone_data zones[1]{};
P_room world = rooms;
zone_data *zone_table = zones;
const int top_of_world = 1;
int bfs_cur_marker = 1;
int STAT_INDEX(int stat) { return stat; }
int get_property(const char *, int fallback) { return fallback; }
float get_property(const char *, double fallback) { return fallback; }
static char_data master{};
static bool mastered, shrug;
static int scheduled, damage_calls, mana_before, removed, disarmed, moved, waited, golem_calls, golem_type;
static int damage_result = DAM_NONEDEAD, last_damage;
static bool release_on_damage;
static std::string feedback;
static P_char feedback_target;
void send_to_char(const char *text, P_char ch) { feedback += text; feedback_target = ch; }
void act(const char *, int, P_char, P_obj, void *, int) {}
void logit(const char *, const char *, ...) {}
void debug(const char *, ...) {}
P_char get_linked_char(P_char, ush_int) { return mastered ? &master : nullptr; }
int GET_CLASS(P_char ch, uint cls) { return ch->player.m_class & cls; }
int number(int low, int) { return low; }
int dice(int count, int size) { return count * size; }
const Rolls live_rolls = {dice, number};
bool resists_spell(P_char, P_char) { return shrug; }
bool StatSave(P_char, int, int) { return true; }
bool affected_by_spell(P_char ch, int type) { return ch->affected && ch->affected->type == type; }
void affect_from_char(P_char ch, int) {
    ++removed;
    delete ch->affected; // Poison the released affect to detect any subsequent use.
    ch->affected = nullptr;
}
P_nevent get_scheduled(P_char, event_func_type) { return reinterpret_cast<P_nevent>(1); }
void disarm_char_nevents(P_char, event_func_type) { ++disarmed; }
static P_char event_target;
nevent_schedule_result add_event(event_func, int, P_char, P_char target, P_obj, int, const void *, int) {
    ++scheduled; event_target = target; return {};
}
int spell_damage(P_char ch, P_char victim, double amount, int, uint, damage_messages *, int *) {
    ++damage_calls; last_damage = amount;
    if (release_on_damage) {
        if (damage_result == DAM_VICTDEAD || damage_result == DAM_BOTHDEAD) {
            delete victim->affected;
            delete victim;
        }
        if (damage_result == DAM_CHARDEAD || damage_result == DAM_BOTHDEAD) delete ch;
    }
    return damage_result;
}
void spell_minor_paralysis(int, P_char, char *, int, P_char, P_obj) {}
void create_golem(int, P_char, P_char, P_obj, int type) {
    ++golem_calls; golem_type = type;
    assert(type >= NECROGOLEM_FLESH && type <= NECROGOLEM_LAST);
}
static const char *radial_distance = "1";
void argument_interpreter(char *, char *direction, char *distance) {
    std::strcpy(direction, "n"); std::strcpy(distance, radial_distance);
}
bool is_number(char *) { return true; }
void char_from_room(P_char ch) { ch->in_room = NOWHERE; }
bool char_to_room(P_char ch, int room, int) { ++moved; ch->in_room = room; return true; }
void CharWait(P_char, int ticks) { waited += ticks; }
void KnockOut(P_char, int) { assert(false); }
static int weakened, stunned, fled;
bool fear_check(P_char, bool) { return false; }
void do_flee(P_char ch, char *, int) { assert(ch->in_room == 1); ++fled; }
void Stun(P_char, P_char attacker, int, bool) { assert(attacker->in_room == 1); ++stunned; }
void zone_spellmessage(int, bool, const char *, const char *) {}
void send_to_room(const char *, int) {}
P_char get_random_char_in_room(int, P_char, int) { return nullptr; }
struct call_lightning_data { int room; int waves; int level; };
int get_default_save_mod(P_char victim, P_char aggressor, int, int) {
    return victim->player.level - aggressor->player.level;
}
bool NewSaves(P_char, int, int) { return false; }
affected_type *affect_to_char(P_char, affected_type *) { ++weakened; return nullptr; }
''' + '\n'.join(extract_function(path, signature) for path, signature in [
    ('psionics.c', 'static int psionic_wave_blast_shrug_roll('),
    ('psionics.c', 'static int psionic_wave_blast_wave_damage('),
    ('psionics.c', 'static int psionic_wave_blast_failed_save('),
    ('psionics.c', 'static int psionic_wave_blast_away('),
    ('psionics.c', 'static int psionic_wave_blast_interval('),
    ('psionics.c', 'static int psionic_wave_blast_mana('),
    ('psionics.c', 'void event_psionic_wave_blast('),
    ('necromancy.c', 'static int golem_flesh_level('),
    ('necromancy.c', 'static int golem_blood_level('),
    ('necromancy.c', 'static int golem_bone_level('),
    ('necromancy.c', 'void spell_create_golem('),
    ('psionics.c', 'static int radial_navigation_range('),
    ('psionics.c', 'static int radial_navigation_mana('),
    ('psionics.c', 'static int radial_navigation_lag('),
    ('psionics.c', 'static int radial_navigation_knockout('),
    ('psionics.c', 'void spell_radial_navigation('),
    ('magic.c', 'static int heavens_aid_slay_level('),
    ('magic.c', 'static int heavens_aid_slay_damage('),
    ('magic.c', 'static int heavens_aid_damage('),
    ('magic.c', 'static int heavens_aid_pc_damage('),
    ('magic.c', 'static int heavens_aid_factor('),
    ('magic.c', 'void spell_heavens_aid('),
    ('magic.c', 'static int frostbite_damage('),
    ('magic.c', 'static int frostbite_strength('),
    ('magic.c', 'static int frostbite_duration('),
    ('magic.c', 'void spell_frostbite('),
    ('magic.c', 'static int call_lightning_damage('),
    ('magic.c', 'static int call_lightning_stun('),
    ('magic.c', 'static int call_lightning_more_strikes('),
    ('magic.c', 'static int call_lightning_interval('),
    ('magic.c', 'void event_call_lightning('),
]) + r'''
static char_data alive() {
    char_data ch{};
    ch.specials.position = POS_STANDING | STAT_NORMAL;
    ch.points.mana = 500;
    ch.player.level = 50;
    return ch;
}
static void wave() {
    for (int interruption : {0, 1, 2, 3}) {
        char_data caster = alive(), victim = alive();
        victim.affected = new affected_type{};
        victim.affected->type = SPELL_PSIONIC_WAVE_BLAST;
        victim.affected->modifier = interruption == 3 ? 0 : 6;
        caster.specials.affected_by2 = AFF2_CASTING;
        if (interruption == 1) caster.specials.position = POS_SITTING | STAT_NORMAL;
        if (interruption == 2) caster.specials.affected_by2 |= AFF2_STUNNED;
        scheduled = damage_calls = removed = disarmed = 0;
        mana_before = GET_MANA(&caster);
        int level = 50;
        event_psionic_wave_blast(&caster, &victim, nullptr, &level);
        if (interruption == 3) assert(feedback_target == &caster);
        const bool continuing = interruption == 0;
        assert(scheduled == continuing && damage_calls == continuing);
        assert(GET_MANA(&caster) == mana_before - (continuing ? 50 : 0));
        assert(bool(IS_AFFECTED2(&caster, AFF2_CASTING)) == continuing);
        assert(removed == !continuing);
        assert(disarmed == (interruption == 1 || interruption == 2));
        if (continuing) {
            assert(victim.affected->modifier == 5);
            delete victim.affected;
        } else assert(!victim.affected);
    }
    char_data caster = alive(), victim = alive();
    caster.specials.affected_by2 = AFF2_CASTING;
    scheduled = damage_calls = 0;
    int level = 50;
    event_psionic_wave_blast(&caster, &victim, nullptr, &level);
    assert(!scheduled && !damage_calls && !IS_AFFECTED2(&caster, AFF2_CASTING));

    release_on_damage = true;
    for (int result : {DAM_VICTDEAD, DAM_CHARDEAD, DAM_BOTHDEAD}) {
        auto dying_caster = new char_data(alive()), dying_victim = new char_data(alive());
        dying_victim->affected = new affected_type{};
        dying_victim->affected->type = SPELL_PSIONIC_WAVE_BLAST;
        dying_victim->affected->modifier = 6;
        dying_caster->specials.affected_by2 = AFF2_CASTING;
        damage_result = result;
        scheduled = 0;
        event_psionic_wave_blast(dying_caster, dying_victim, nullptr, &level);
        assert(!scheduled);
        if (result == DAM_VICTDEAD) assert(!IS_AFFECTED2(dying_caster, AFF2_CASTING));
        if (result == DAM_CHARDEAD) {
            delete dying_victim->affected;
            delete dying_victim;
        }
        if (result == DAM_VICTDEAD) delete dying_caster;
    }
    release_on_damage = false;
    damage_result = DAM_NONEDEAD;
}
static void golem() {
    for (bool theurgist : {false, true}) {
        for (int level : {1, 40, 41, 45, 46, 50, 51, 60}) {
            for (int corpse_level : {1, 40, 41, 45, 46, 50, 51, 60}) {
                char_data caster = alive();
                caster.player.m_class = theurgist ? CLASS_THEURGIST : CLASS_NECROMANCER;
                obj_data corpse{};
                corpse.type = ITEM_CORPSE;
                corpse.value[CORPSE_LEVEL] = corpse_level;
                golem_calls = 0;
                spell_create_golem(level, &caster, nullptr, SPELL_TYPE_SCROLL, nullptr, &corpse);
                if (!theurgist && level < 41) {
                    assert(golem_calls == 0); // Never forward an uninitialized table index.
                } else {
                    const int expected = theurgist ? THEURGOLEM_VALOR :
                        level >= 51 && corpse_level >= 51 ? NECROGOLEM_BONE :
                        level >= 46 && corpse_level >= 46 ? NECROGOLEM_BLOOD : NECROGOLEM_FLESH;
                    assert(golem_calls == 1 && golem_type == expected);
                }
            }
        }
    }
}
static void radial() {
    room_direction_data exit{};
    exit.to_room = 1;
    rooms[0].dir_option[0] = &exit;
    zones[0].flags = ZONE_MAP;
    for (bool npc : {false, true}) {
        for (bool has_master : {false, true}) {
            for (bool no_teleport : {false, true}) {
                char_data caster = alive();
                caster.specials.act = npc ? ACT_ISNPC : 0;
                mastered = has_master;
                rooms[1].room_flags = no_teleport ? ROOM_NO_TELEPORT : 0;
                moved = waited = 0;
                char args[] = "n 1";
                spell_radial_navigation(50, &caster, args, SPELL_TYPE_SPELL, nullptr, nullptr);
                const bool allowed = !no_teleport && !(has_master && !npc);
                assert(moved == allowed && caster.in_room == (allowed ? 1 : 0));
                assert(waited == 2.5 * WAIT_SEC && GET_MANA(&caster) == 488);
            }
        }
    }
    mastered = false;
    rooms[1].room_flags = 0;
    for (const char *distance : {"-1000", "-1", "0"}) {
        char_data caster = alive();
        moved = waited = 0;
        radial_distance = distance;
        char args[] = "n distance";
        spell_radial_navigation(50, &caster, args, SPELL_TYPE_SPELL, nullptr, nullptr);
        assert(!moved && !waited && caster.in_room == 0 && GET_MANA(&caster) == 500);
    }
    radial_distance = "1";
}
static void heavens() {
    for (int result : {DAM_NONEDEAD, DAM_VICTDEAD, DAM_CHARDEAD, DAM_BOTHDEAD}) {
        auto caster = new char_data(alive()), victim = new char_data(alive());
        victim->player.level = 9;
        victim->player.race = RACE_ORC;
        victim->player.racewar = RACEWAR_EVIL;
        victim->specials.act = ACT_ISNPC;
        damage_calls = 0;
        damage_result = result;
        release_on_damage = true;
        spell_heavens_aid(50, caster, nullptr, SPELL_TYPE_SPELL, victim, nullptr);
        assert(damage_calls == 1 && last_damage == 10000);
        if (result != DAM_VICTDEAD && result != DAM_BOTHDEAD) delete victim;
        if (result != DAM_CHARDEAD && result != DAM_BOTHDEAD) delete caster;
    }
    release_on_damage = false;
    damage_result = DAM_NONEDEAD;
    for (bool npc : {false, true}) {
        char_data caster = alive(), victim = alive();
        victim.player.level = 10; // The slay threshold is strict.
        victim.player.race = RACE_ORC;
        victim.player.racewar = RACEWAR_EVIL;
        victim.specials.act = npc ? ACT_ISNPC : 0;
        damage_calls = 0;
        spell_heavens_aid(50, &caster, nullptr, SPELL_TYPE_SPELL, &victim, nullptr);
        assert(damage_calls == 1 && last_damage == (npc ? 250 : 125));
        victim.player.racewar = RACEWAR_GOOD;
        damage_calls = 0;
        spell_heavens_aid(50, &caster, nullptr, SPELL_TYPE_SPELL, &victim, nullptr);
        assert(!damage_calls);
    }
}
static void frostbite() {
    release_on_damage = true;
    for (int result : {DAM_NONEDEAD, DAM_VICTDEAD, DAM_CHARDEAD, DAM_BOTHDEAD}) {
        auto caster = new char_data(alive()), victim = new char_data(alive());
        damage_result = result;
        weakened = 0;
        spell_frostbite(50, caster, nullptr, SPELL_TYPE_SPELL, victim, nullptr);
        assert(weakened == (result == DAM_NONEDEAD));
        if (result != DAM_VICTDEAD && result != DAM_BOTHDEAD) delete victim;
        if (result != DAM_CHARDEAD && result != DAM_BOTHDEAD) delete caster;
    }
}
static void call_lightning() {
    release_on_damage = true;
    for (int result : {DAM_NONEDEAD, DAM_VICTDEAD, DAM_CHARDEAD, DAM_BOTHDEAD}) {
        auto caster = new char_data(alive()), victim = new char_data(alive());
        caster->in_room = victim->in_room = 1;
        call_lightning_data data{1, 0, 50};
        damage_result = result;
        stunned = fled = scheduled = 0;
        event_target = victim;
        event_call_lightning(caster, victim, nullptr, &data);
        assert((stunned + fled != 0) == (result == DAM_NONEDEAD));
        assert(scheduled == (result == DAM_NONEDEAD || result == DAM_VICTDEAD));
        if (result == DAM_VICTDEAD) assert(!event_target); // A dead target is never rescheduled.
        if (result != DAM_VICTDEAD && result != DAM_BOTHDEAD) delete victim;
        if (result != DAM_CHARDEAD && result != DAM_BOTHDEAD) delete caster;
    }
}
int main(int argc, char **argv) {
    assert(argc == 2);
    if (!std::strcmp(argv[1], "wave")) wave();
    else if (!std::strcmp(argv[1], "golem")) golem();
    else if (!std::strcmp(argv[1], "radial")) radial();
    else if (!std::strcmp(argv[1], "heavens")) heavens();
    else if (!std::strcmp(argv[1], "frostbite")) frostbite();
    else if (!std::strcmp(argv[1], "lightning")) call_lightning();
    else assert(false);
    std::printf("PASS critical spell safety: %s\n", argv[1]);
}
'''

out = ROOT / 'bin/tests'
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='critical-spells-', dir=out) as temporary:
    cpp, binary = Path(temporary) / 'test.cpp', Path(temporary) / 'test'
    cpp.write_text(fixture)
    subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    '-g', '-Isrc', str(cpp), '-o', str(binary)], cwd=ROOT, check=True)
    results = [subprocess.run([str(binary), case], timeout=30).returncode
               for case in ('wave', 'golem', 'radial', 'heavens', 'frostbite', 'lightning')]
    assert not any(results), results
