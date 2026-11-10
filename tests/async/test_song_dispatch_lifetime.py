#!/usr/bin/env python3
'''Run song dispatch lifetime, ongoing stealth and command reveal regressions.'''
from pathlib import Path
import re
import subprocess
import tempfile
from _paths import ROOT, extract_function, source
from contract_text import contains

fixture = r'''
#include "abilities/abilities.h"
#include "core/prototypes.h"
#include "cmd/interp.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "net/comm.h"
#include "world/weather.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <vector>
#define SONG_AGGRESSIVE BIT_1
#define SONG_ALLIES BIT_2
#define SONG_SELF_ONLY BIT_3
#define BARD_SKILL_NOTCH_CHANCE 5.0
typedef void song_function(int, P_char, P_char, int);
struct echo_details { int song; int room; };
static room_data room_store[2]{};
P_room world = room_store;
P_char character_list;
uint64_t character_removal_generation;
static std::vector<P_char> sung;
static P_char ally;
static std::vector<uint64_t> doomed; // Runtime ids released on the next effect.
static int aggros, rests, waits, scheduled, song_chance = 100;
time_info_data time_info{};
static uint64_t next_id = 1;
static P_char make_char() {
    auto ch = new char_data{};
    ch->runtime_id = next_id++;
    ch->in_room = 1;
    ch->player.level = 50;
    ch->specials.position = POS_STANDING | STAT_NORMAL;
    ch->next = character_list;
    character_list = ch;
    ch->next_in_room = world[1].people;
    world[1].people = ch;
    return ch;
}
static void release(P_char ch) {
    for (P_char *link = &character_list; *link; link = &(*link)->next)
        if (*link == ch) { *link = ch->next; break; }
    for (P_char *link = &world[1].people; *link; link = &(*link)->next_in_room)
        if (*link == ch) { *link = ch->next_in_room; break; }
    ++character_removal_generation;
    delete ch;
}
P_char find_character_by_runtime_id(uint64_t id) {
    for (P_char ch = character_list; ch; ch = ch->next) if (ch->runtime_id == id) return ch;
    return nullptr;
}
static void killing_song(int, P_char, P_char target, int) {
    sung.push_back(target);
    auto ids = doomed;
    doomed.clear();
    for (auto id : ids) if (P_char ch = find_character_by_runtime_id(id)) release(ch);
}
struct song_description { const char *name; song_function *funct; int instrument; int song; int flags; };
static song_description songs[] = {
    { "harming", killing_song, 0, SONG_HARMING, SONG_AGGRESSIVE },
    {},
};
struct song_text { int num; char tochar[100]; char toroom[100]; };
static song_text songwords[] = { { 0, "", "" } };
void send_to_char(const char *, P_char) {}
void send_to_room(const char *, int) {}
void act(const char *, int, P_char, P_obj, void *, int) {}
void logit(const char *, const char *, ...) {}
bool should_area_hit(P_char ch, P_char t) { return ch != t; }
bool grouped(P_char, P_char target) { return target == ally; }
bool bard_saves(P_char, P_char, int) { return true; }
void bard_aggro(P_char, P_char) { ++aggros; }
int bard_song_level(P_char, int) { return 30; }
int bard_calc_chance(P_char, int) { return song_chance; }
int number(int low, int) { return low; }
int dice(int count, int) { return count; }
const Rolls live_rolls = { dice, number };
int get_bard_pulse(P_char) { return 8; }
int get_property(const char *, int fallback) { return fallback; }
float get_property(const char *, double fallback) { return fallback; }
void sing_verses(P_char, int) {}
void stop_singing(P_char) {}
bool is_silent(P_char, bool) { return false; }
int flag2idx(int) { return 0; }
int get_song_level(int, int, int) { return 1; }
void affect_remove(P_char, affected_type *) {}
bool affected_by_spell(P_char, int) { return false; }
void affect_from_char(P_char, int) { assert(false); }
bool IS_OUTDOORS(int) { return false; }
bool IS_TWILIGHT_ROOM(int) { return false; }
void set_short_affected_by(P_char, int, int) { ++rests; }
void CharWait(P_char, int) { ++waits; }
void do_action(P_char, char *, int) {}
bool has_innate(P_char, int) { return false; }
bool notch_skill(P_char, int, float) { return false; }
int GET_CHAR_SKILL_P(P_char, int) { return 100; }
char *skip_spaces(char *text) { return text; }
bool is_abbrev(const char *, const char *) { return true; }
int is_char_in_room(P_char ch, int room) {
    for (P_char t = world[room].people; t; t = t->next_in_room) if (t == ch) return 1;
    return 0;
}
P_nevent get_scheduled(P_char, event_func_type) { return nullptr; }
nevent_schedule_result add_event(event_func, int, P_char, P_char, P_obj, int, const void *, int) {
    ++scheduled; return {};
}
void event_bardsong(P_char, P_char, P_obj, void *);
''' + '\n'.join(extract_function('bard.c', signature) for signature in [
    'static int song_learned_level(',
    'static int song_level_roll(',
    'static int song_verse_failure_rest(',
    'static int song_area_threshold(',
    'static int song_area_roll(',
    'static bool sing_to_target(',
    'static int echo_song_level(',
    'void event_echosong(P_char ch,',
    'static int echo_chance(',
    'static int echo_roll(',
    'static int echo_delay(',
    'void event_bardsong(P_char ch,',
    'static int riff_failed_rest(',
    'static int riff_rest(',
    'static int riff_lag(',
    'void do_riff(P_char ch,',
]) + r'''
// Execute the production interpreter's hide gate before a song command.
static void command_hide_rule(P_char ch, int cmd) {
    P_char exec_char = ch;
    const char *argument = "";
    COMMAND_HIDE_RULE
}
struct Crowd { P_char bard, first, second, third; };
static Crowd crowd() {
    character_list = nullptr;
    world[1].people = nullptr;
    sung.clear(); doomed.clear();
    aggros = rests = waits = scheduled = 0;
    song_chance = 100;
    Crowd c{};
    c.third = make_char();
    c.second = make_char();
    c.first = make_char();
    c.bard = make_char(); // Head of the room, so the dispatch sees first, second, third.
    c.bard->player.m_class = CLASS_BARD;
    c.bard->specials.affected_by3 = AFF3_SINGING;
    c.bard->player.spec = SPEC_MINSTREL;
    return c;
}
static void clear_room() {
    while (character_list) release(character_list);
}
static void dispatch(int path, P_char bard) {
    int song = SONG_HARMING;
    if (path == 0) event_bardsong(bard, nullptr, nullptr, &song);
    else if (path == 1) {
        echo_details details{ SONG_HARMING, 1 };
        event_echosong(bard, nullptr, nullptr, &details);
    } else {
        char arg[] = "harming";
        do_riff(bard, arg, 0);
    }
}
int main() {
    for (int path : {0, 1, 2}) {
        // The singer dies on the first target: nothing may touch it afterwards. A riff aggroes
        // before its effect, the other paths after it.
        Crowd c = crowd();
        doomed = { c.bard->runtime_id };
        dispatch(path, c.bard);
        assert(sung.size() == 1 && aggros == (path == 2) && !rests && !waits && !scheduled);
        clear_room();
        // The target dies: it is not aggroed, and the remaining targets still hear the song.
        c = crowd();
        doomed = { c.first->runtime_id };
        dispatch(path, c.bard);
        assert(sung.size() == 3);
        assert(aggros == (path == 2 ? 3 : 2));
        clear_room();
        // The next target dies: the walk stops rather than following its released link.
        c = crowd();
        doomed = { c.second->runtime_id };
        dispatch(path, c.bard);
        assert(sung.size() == 1);
        clear_room();
        // Nobody dies: every target hears the song, and the singer carries on.
        c = crowd();
        dispatch(path, c.bard);
        assert(sung.size() == 3 && aggros == 3);
        if (path == 2) assert(rests == 1 && waits == 1);
        clear_room();
    }
    // A retained Riff rating cannot be used before respecializing.
    {
        Crowd c = crowd(); c.bard->player.spec = 0;
        dispatch(2, c.bard);
        assert(sung.empty() && !rests && !waits);
        clear_room();
    }
    // Run all dispatch paths with the actual catalog flags for the four songs.
    // A callback records delivery; the separate dissonance harness exercises its
    // handler's hostile/group/room eligibility checks.
    for (int flags : {TARGET_FLAGS}) for (int path : {0,1,2}) {
        Crowd c = crowd(); ally = c.first; songs[0].flags = flags;
        dispatch(path, c.bard);
        assert(sung.size() == (flags == SONG_ALLIES ? 2 : 4));
        if (flags == SONG_ALLIES) {
            assert(sung[0] == c.bard && sung[1] == c.first);
        }
        sung.clear(); c.third->player.level = MAXLVL;
        dispatch(path, c.bard);
        assert(sung.size() == (flags == SONG_ALLIES ? 2 : 3));
        assert(!aggros);
        ally = nullptr; clear_room();
    }
    // Starting and switching via either song command still reveal ordinary hide.
    // Look/scan/sneak are controls for commands that preserve it. Sneak survives.
    for (int cmd : {CMD_PLAY, CMD_WAIL, CMD_LOOK, CMD_SCAN, CMD_SNEAK})
        for (bool already_singing : {false, true}) {
            Crowd c = crowd();
            if (!already_singing) REMOVE_BIT(c.bard->specials.affected_by3, AFF3_SINGING);
            c.bard->specials.affected_by = AFF_HIDE | AFF_SNEAK;
            command_hide_rule(c.bard, cmd);
            assert(bool(IS_AFFECTED(c.bard, AFF_HIDE)) == (cmd != CMD_PLAY && cmd != CMD_WAIL));
            assert(IS_AFFECTED(c.bard, AFF_SNEAK));
            assert(bool(IS_AFFECTED3(c.bard, AFF3_SINGING)) == already_singing);
            clear_room();
        }
    // A Bard who hides after starting Flight/Sleep stays hidden on later beats,
    // even if a verse fails. Recording effects isolate this from combat/reveal
    // effects inside individual song handlers.
    struct song_case { int song, flags; };
    for (auto song : {STEALTH_SONGS}) for (bool fail : {false, true}) {
        Crowd c = crowd(); ally = c.first;
        songs[0].song = song.song; songs[0].flags = song.flags;
        c.bard->specials.affected_by = c.first->specials.affected_by = AFF_HIDE | AFF_SNEAK;
        affected_type singing{};
        singing.bitvector3 = AFF3_SINGING; singing.modifier = 4;
        c.bard->affected = &singing;
        song_chance = fail ? 0 : 100;
        for (int beat = 0; beat < (fail ? 1 : 2); ++beat) {
            event_bardsong(c.bard, nullptr, nullptr, &song.song);
            assert(IS_AFFECTED(c.bard, AFF_HIDE) && IS_AFFECTED(c.bard, AFF_SNEAK));
            assert(IS_AFFECTED(c.first, AFF_HIDE) && IS_AFFECTED(c.first, AFF_SNEAK));
        }
        assert(scheduled == (fail ? 0 : 2) && rests == (fail ? 1 : 0));
        assert(sung.size() == (fail ? 0u : song.flags == SONG_ALLIES ? 4u : 6u));
        assert(singing.modifier == (fail ? 4 : 2));
        ally = nullptr; clear_room();
    }
    std::puts("PASS song dispatch survives the singer, target and next target dying mid-song");
    std::puts("PASS ongoing Flight/Sleep preserve hide and sneak; start/switch still reveal hide");
}
'''

catalog = source('bard.c').read_text()
song_catalog = {name: (song, flags) for name, song, flags in re.findall(
    r'\{ "(\w+)", \w+, \w+, (\w+), ([\w |]+) \}', catalog)}
target_flags = []
for song in ('flight', 'calming', 'peace', 'forgetfulness'):
    flags = song_catalog[song][1]
    assert flags == ('SONG_ALLIES' if song == 'flight' else '0'), (song, flags)
    target_flags.append('int('+flags+')')
fixture = fixture.replace('TARGET_FLAGS', ','.join(target_flags))
fixture = fixture.replace('STEALTH_SONGS', ','.join(
    'song_case{' + ','.join(song_catalog[name]) + '}' for name in ('flight', 'sleep')))

interpreter = extract_function('interp.c', 'void command_interpreter(')
hide_start = interpreter.index('// Kill hide if applicable')
hide_end = interpreter.index('if (IS_AFFECTED(exec_char, AFF_MEDITATE))', hide_start)
assert hide_start < interpreter.index('((*cmd_info[cmd].command_pointer)')
fixture = fixture.replace('COMMAND_HIDE_RULE', interpreter[hide_start:hide_end])
for command in ('CMD_PLAY', 'CMD_WAIL'):
    assert contains(source('interp.c').read_text(),
                    f'CMD_Y({command}, STAT_RESTING + POS_SITTING, do_play, 0, TRUE);')

out = ROOT / 'bin/tests'
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='song-dispatch-', dir=out) as temporary:
    cpp, binary = Path(temporary) / 'test.cpp', Path(temporary) / 'test'
    cpp.write_text(fixture)
    subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    '-g', '-Isrc', str(cpp), '-o', str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=30)
