#!/usr/bin/env python3
"""Run the real wave event, golem dispatch and radial spell under sanitizers."""
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
static char_data master{};
static bool mastered, shrug;
static int scheduled, damage_calls, mana_before, removed, disarmed, moved, waited, golem_calls, golem_type;
static std::string feedback;
void send_to_char(const char *text, P_char) { feedback += text; }
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
nevent_schedule_result add_event(event_func, int, P_char, P_char, P_obj, int, const void *, int) {
    ++scheduled; return {};
}
int spell_damage(P_char, P_char, double, int, uint, damage_messages *, int *) {
    ++damage_calls; return DAM_NONEDEAD;
}
void create_golem(int, P_char, P_char, P_obj, int type) {
    ++golem_calls; golem_type = type;
    assert(type >= NECROGOLEM_FLESH && type <= NECROGOLEM_LAST);
}
void argument_interpreter(char *, char *direction, char *distance) {
    std::strcpy(direction, "n"); std::strcpy(distance, "1");
}
bool is_number(char *) { return true; }
void char_from_room(P_char ch) { ch->in_room = NOWHERE; }
bool char_to_room(P_char ch, int room, int) { ++moved; ch->in_room = room; return true; }
void CharWait(P_char, int ticks) { waited += ticks; }
void KnockOut(P_char, int) { assert(false); }
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
}
int main(int argc, char **argv) {
    assert(argc == 2);
    if (!std::strcmp(argv[1], "wave")) wave();
    else if (!std::strcmp(argv[1], "golem")) golem();
    else if (!std::strcmp(argv[1], "radial")) radial();
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
               for case in ('wave', 'golem', 'radial')]
    assert not any(results), results
