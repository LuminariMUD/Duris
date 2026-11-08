#!/usr/bin/env python3
"""Land spell effects on an NPC that has already died, using the real server objects."""
import os
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function

# Apocalypse's wither can kill an undead target before the rest of the breath.
apocalypse = extract_function('magic/magic.c', 'void event_apocalypse(')
wither = apocalypse.index('spell_wither(GET_LEVEL(ch)')
assert wither < apocalypse.index('if (!IS_ALIVE(tch))', wither) < apocalypse.index('poison_weakness', wither)

# Nothing ever wrote these buffers, so the player was sent leftover stack contents.
assert 'char buf[256]' not in extract_function('actoff.c', 'void do_consume(')

SPELL = 'iP9char_dataPciS0_P8obj_data'
WRAPPED = ['_Z6numberii', '_Z8NewSavesP9char_dataii', '_Z3hitP9char_dataS0_P8obj_dataPi',
           '_Z12spell_damageP9char_dataS0_dijP15damage_messagesPi',
           '_Z15spell_frostbite' + SPELL, '_Z20spell_lightning_bolt' + SPELL,
           '_Z15spell_holy_word' + SPELL, '_Z17spell_dispel_evil' + SPELL]

fixture = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "combat/damage.h"
#include "magic/spells.h"
#include "world/specs.prototypes.h"
#include "cmd/interp.h"
#include <cassert>
#include <cstdio>
#include <cstring>

extern "C" {
int __real__Z6numberii(int, int);
bool __real__Z8NewSavesP9char_dataii(P_char, int, int);
int __real__Z12spell_damageP9char_dataS0_dijP15damage_messagesPi(P_char, P_char, double, int, uint, damage_messages *, int *);
void __real__Z15spell_frostbiteiP9char_dataPciS0_P8obj_data(int, P_char, char *, int, P_char, P_obj);
void __real__Z20spell_lightning_boltiP9char_dataPciS0_P8obj_data(int, P_char, char *, int, P_char, P_obj);
}
int storm_legplates(P_obj, P_char, int, char *);
int blur_shortsword(P_obj, P_char, int, char *);
int faith(P_obj, P_char, int, char *);
void event_acid_rain(P_char, P_char, P_obj, void *);
void event_sandstorm(P_char, P_char, P_obj, void *);

// With scripted set, each stand-in below kills `doomed` and counts instead of running.
static bool scripted;
static P_char doomed;
static int bolts, frostbites, dispels, saves, damages;

static void die_like_free_char(P_char ch) {
    delete ch->only.npc;
    ch->only.npc = nullptr;
    ch->in_room = NOWHERE;
    ch->next_in_room = nullptr;
    SET_POS(ch, GET_POS(ch) + STAT_DEAD);
}
static void land_on(P_char) {
    if (doomed) { die_like_free_char(doomed); doomed = nullptr; }
}

extern "C" {
int __wrap__Z6numberii(int low, int high) {
    if (!scripted) return __real__Z6numberii(low, high);
    return low == 1 && high == 20 ? 13 : low; // Frostbite in both blur branches.
}
bool __wrap__Z8NewSavesP9char_dataii(P_char ch, int type, int mod) {
    if (!scripted) return __real__Z8NewSavesP9char_dataii(ch, type, mod);
    ++saves;
    return false;
}
bool __wrap__Z3hitP9char_dataS0_P8obj_dataPi(P_char, P_char victim, P_obj, int *) {
    land_on(victim);
    return false;
}
int __wrap__Z12spell_damageP9char_dataS0_dijP15damage_messagesPi(P_char ch, P_char victim, double dam, int type, uint flags, damage_messages *messages, int *total) {
    if (!scripted) return __real__Z12spell_damageP9char_dataS0_dijP15damage_messagesPi(ch, victim, dam, type, flags, messages, total);
    ++damages;
    land_on(victim);
    return DAM_VICTDEAD;
}
void __wrap__Z15spell_frostbiteiP9char_dataPciS0_P8obj_data(int level, P_char ch, char *arg, int type, P_char victim, P_obj obj) {
    if (!scripted) return __real__Z15spell_frostbiteiP9char_dataPciS0_P8obj_data(level, ch, arg, type, victim, obj);
    ++frostbites;
}
void __wrap__Z20spell_lightning_boltiP9char_dataPciS0_P8obj_data(int level, P_char ch, char *arg, int type, P_char victim, P_obj obj) {
    if (!scripted) return __real__Z20spell_lightning_boltiP9char_dataPciS0_P8obj_data(level, ch, arg, type, victim, obj);
    ++bolts;
    land_on(victim);
}
void __wrap__Z15spell_holy_wordiP9char_dataPciS0_P8obj_data(int, P_char, char *, int, P_char, P_obj) {}
void __wrap__Z17spell_dispel_eviliP9char_dataPciS0_P8obj_data(int, P_char, char *, int, P_char victim, P_obj) {
    ++dispels;
    land_on(victim);
}
}

extern int top_of_world;
extern P_char character_list;
static room_data rooms[2]{};
static P_char person(bool npc) {
    auto ch = new char_data{};
    ch->specials.position = POS_STANDING + STAT_NORMAL;
    ch->player.level = 50;
    ch->player.m_class = CLASS_WARRIOR;
    ch->player.name = ch->player.short_descr = strdup("person");
    ch->in_room = 1;
    ch->next_in_room = world[1].people;
    world[1].people = ch;
    if (npc) {
        ch->specials.act |= ACT_ISNPC;
        ch->only.npc = new npc_only_data{};
    }
    return ch;
}
static P_char dead_npc() {
    auto ch = new char_data{};
    ch->specials.position = POS_STANDING + STAT_NORMAL;
    ch->specials.act |= ACT_ISNPC;
    ch->only.npc = new npc_only_data{};
    ch->player.level = 50;
    die_like_free_char(ch);
    return ch;
}
static void reset() {
    world[1].people = nullptr;
    bolts = frostbites = dispels = saves = damages = 0;
    doomed = nullptr;
    scripted = true;
}
static P_obj worn_by(P_char ch, int slot) {
    auto obj = new obj_data{};
    obj->loc_p = LOC_WORN;
    obj->loc.wearing = ch;
    ch->equipment[slot] = obj;
    return obj;
}

// The real calls that crashed: a dead target must simply be ignored.
static void real_calls() {
    scripted = false;
    world[1].people = nullptr;
    P_char caster = person(true), dead = dead_npc();
    assert(!has_innate(caster, INNATE_EVASION));
    assert(!has_innate(dead, INNATE_EVASION));
    NewSaves(dead, SAVING_SPELL, 0);
    damage_messages messages{};
    assert(spell_damage(caster, dead, 10, SPLDAM_FIRE, 0, &messages) == DAM_VICTDEAD);
    assert(spell_damage(caster, dead, 10, SPLDAM_FIRE, SPLDAM_NODEFLECT, &messages) == DAM_VICTDEAD);
    spell_lightning_bolt(50, caster, nullptr, SPELL_TYPE_SPELL, dead, nullptr);
    spell_frostbite(50, caster, nullptr, SPELL_TYPE_SPELL, dead, nullptr);
}
static void legplates() {
    reset();
    P_char wearer = person(false), attacker = person(true);
    wearer->specials.fighting = attacker;
    proc_data data{attacker, 0, 0, 0, nullptr};
    doomed = attacker;
    assert(storm_legplates(worn_by(wearer, WEAR_LEGS), wearer, CMD_GOTHIT, reinterpret_cast<char *>(&data)));
    assert(bolts == 1);
}
static void shortsword() {
    reset();
    P_char wearer = person(false), attacker = person(true);
    wearer->specials.fighting = attacker;
    P_obj sword = worn_by(wearer, WIELD);
    char word[] = "blur";
    doomed = attacker;
    assert(blur_shortsword(sword, wearer, CMD_SAY, word));
    assert(!frostbites);

    reset();
    wearer = person(false);
    attacker = person(true);
    wearer->specials.fighting = attacker;
    proc_data data{attacker, 0, 0, 0, nullptr};
    doomed = attacker;
    blur_shortsword(worn_by(wearer, WIELD), wearer, CMD_GOTHIT, reinterpret_cast<char *>(&data));
    assert(!frostbites);
}
// A kill removes the pet saved as the next person in the room.
static void acid_rain_and_sandstorm() {
    for (auto event : {event_acid_rain, event_sandstorm}) {
        reset();
        P_char pet = person(true);
        person(false); // The owner, whose death dismisses the pet.
        P_char caster = person(false);
        doomed = pet;
        event(caster, nullptr, nullptr, nullptr);
        assert(damages == 1 && saves == 1);
    }
}
static void faith_proc() {
    reset();
    P_char pet = person(true), owner = person(false), wearer = person(false);
    wearer->specials.fighting = owner;
    wearer->specials.alignment = 1000;
    wearer->player.level = MAXLVLMORTAL + 1; // Trusted wearers see in the unlit fixture room.
    character_list = wearer;
    doomed = pet;
    faith(worn_by(wearer, WIELD), wearer, CMD_MELEE_HIT, reinterpret_cast<char *>(owner));
    assert(dispels == 1);
}
int main() {
    world = rooms;
    top_of_world = 1;
    static index_data mobs[1]{};
    mob_index = mobs;
    real_calls();
    legplates();
    shortsword();
    acid_rain_and_sandstorm();
    faith_proc();
    std::printf("PASS spells on dead NPCs\n");
}
'''

subprocess.run(['make', '-C', 'src', f'-j{os.cpu_count()}'], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
# Print the Makefile's own object and library lists so the link matches the server's.
link = subprocess.check_output(['make', '-s', '-C', 'src', '--eval=print-link:;@echo $(DMS_OBJS) $(LIBS)',
                                'print-link'], cwd=ROOT, text=True).split()
out = ROOT / 'bin/tests'
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='spell-dead-npc-', dir=out) as temporary:
    cpp, binary = Path(temporary) / 'test.cpp', Path(temporary) / 'test'
    cpp.write_text(fixture)
    # Listed first so this main wins over the server's.
    subprocess.run(['g++', '-std=c++20', '-g', '-Isrc', '-I/usr/include/libxml2', '-I/usr/include/mysql',
                    str(cpp), '-o', str(binary), '-rdynamic', '-Wl,--allow-multiple-definition',
                    *[f'-Wl,--wrap={symbol}' for symbol in WRAPPED], *link], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=30)
