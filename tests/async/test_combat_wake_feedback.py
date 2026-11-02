#!/usr/bin/env python3
"""Execute damage wake delivery and existing wake paths with production code.

The raw_damage message/wake slice, act, dam_message, do_wake and update_pos are
extracted verbatim. Room occupants, effects, visibility and unrelated services
are fixtures; this does not replace the real-server sleeper/witness journey.
"""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function, source


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "combat/damage.h"
#include "magic/spells.h"
#include "net/comm.h"
#include "net/output_style.h"
#include "player/output_preferences.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <map>
#include <string>

static room_data rooms[1]{};
P_room world = rooms;
static index_data objects[1]{};
P_index obj_index = objects;
static char_data sleeper{}, attacker{}, witness{};
static pc_only_data sleeper_pc{}, attacker_pc{}, witness_pc{};
static descriptor_data sleeper_desc{}, attacker_desc{}, witness_desc{};
static std::map<P_char, std::string> output;
static bool sleeping_spell, sleeping_song, visible;
static int attackers;

void send_to_char(const char *s, P_char ch) { output[ch] += s ? s : ""; }
void send_to_char(const char *s, P_char ch, int, const OutputContext &) { send_to_char(s, ch); }
void logit(const char *, const char *, ...) {}
int number(int, int hi) { return hi; }
int dice(int, int) { return 1; }
int NumAttackers(P_char) { return attackers; }
int tutorial_mobile_mechanics_race(P_char ch) { return ch->player.race; }
P_char get_linked_char(P_char, ush_int) { return nullptr; }
void stop_riding(P_char) {}
void stop_fighting(P_char ch) { ch->specials.fighting = nullptr; }
void StopAllAttackers(P_char) {}
void StopMercifulAttackers(P_char) {}
void clear_links(P_char, ush_int) {}
void Stun(P_char, P_char, int, bool) {}
int raw_damage(P_char, P_char, double, uint, damage_messages *, int *) { return DAM_NONEDEAD; }
bool affected_by_spell(P_char, int s) {
    return (s == SPELL_SLEEP && sleeping_spell) || (s == SONG_SLEEP && sleeping_song);
}
void affect_from_char(P_char, int s) {
    if (s == SPELL_SLEEP) sleeping_spell = false;
    if (s == SONG_SLEEP) sleeping_song = false;
}
void do_alert(P_char, char *, int) {}
void do_stand(P_char, char *, int) {}
void gmcp_char_vitals(P_char) {}
void stop_memorizing(P_char, memorization_stop_reason) {}
void telemetry_gameplay_context_changed(P_char) {}
P_char get_char_room_vis(P_char, const char *) { return &sleeper; }
int fill_word(char *) { return 0; }
int GET_CLASS(P_char, uint) { return 0; }
[[noreturn]] int panic_corruption_int(const char *, const char *, ...) { std::abort(); }
bool check_crippling_strike(P_char) { return false; }
bool ac_can_see(P_char, P_char, bool) { return visible; }
bool ac_can_see_obj(P_char, P_obj, int) { return true; }
char *PERS(P_char ch, P_char, int) { return ch->player.name; }
char *FirstWord(char *s) { return s; }
ResolvedOutputProfile player_output_profile(P_char, const OutputContext &ctx) {
    ResolvedOutputProfile p{}; p.context = ctx; return p;
}
bool soul_trap(P_char, P_char) { return false; }
'''

DRIVER = r'''
static constexpr const char *wake = "You are rudely awakened!\r\n";

static size_t count(const std::string &text, const std::string &needle) {
    size_t result = 0, pos = 0;
    while ((pos = text.find(needle, pos)) != std::string::npos) {
        ++result;
        pos += needle.size();
    }
    return result;
}

static void reset(int posture = POS_PRONE) {
    sleeper = {}; attacker = {}; witness = {};
    sleeper_pc = {}; attacker_pc = {}; witness_pc = {};
    sleeper.only.pc = &sleeper_pc; attacker.only.pc = &attacker_pc; witness.only.pc = &witness_pc;
    sleeper.desc = &sleeper_desc; attacker.desc = &attacker_desc; witness.desc = &witness_desc;
    sleeper.player.name = const_cast<char *>("Sleeper");
    attacker.player.name = const_cast<char *>("Attacker");
    witness.player.name = const_cast<char *>("Witness");
    sleeper.player.race = attacker.player.race = witness.player.race = RACE_HUMAN;
    sleeper.in_room = attacker.in_room = witness.in_room = 0;
    sleeper.next_in_room = &attacker; attacker.next_in_room = &witness;
    rooms[0].people = &sleeper;
    SET_POS(&sleeper, posture + STAT_SLEEPING);
    SET_POS(&attacker, POS_STANDING + STAT_NORMAL);
    SET_POS(&witness, POS_STANDING + STAT_NORMAL);
    GET_HIT(&sleeper) = 100;
    output.clear(); attackers = 0;
    sleeping_spell = sleeping_song = false; visible = true;
}

int main() {
    damage_messages ordinary{};
    ordinary.attacker = "You strike $N.";
    ordinary.victim = "$n strikes you.";
    ordinary.room = "$n strikes $N.";
    ordinary.type = DAMMSG_TERSE;
    damage_messages effect{};
    effect.attacker = "Your blow %s.";
    effect.victim = "$n's blow %s.";
    effect.room = "$n's blow %s.";
    effect.type = DAMMSG_EFFECT;
    for (int posture : {POS_PRONE, POS_SITTING, POS_KNEELING, POS_STANDING}) {
        for (damage_messages *msg : {&ordinary, &effect, static_cast<damage_messages *>(nullptr)}) {
            for (bool terse : {false, true}) {
                for (bool spell : {false, true}) {
                    reset(posture);
                    if (terse) SET_BIT(sleeper.specials.act2, PLR2_TERSE);
                    sleeping_spell = spell;
                    if (spell) SET_BIT(sleeper.specials.affected_by, AFF_SLEEP);
                    production_damage_delivery(&attacker, &sleeper, 1, msg);
                    assert(IS_AWAKE(&sleeper) && GET_STAT(&sleeper) == STAT_NORMAL);
                    assert(GET_POS(&sleeper) == posture);
                    assert(!sleeping_spell && !IS_AFFECTED(&sleeper, AFF_SLEEP));
                    assert(count(output[&sleeper], wake) == 1);
                    assert(count(output[&witness], "Sleeper has a RUDE awakening!") == 1);
                    assert(count(output[&attacker], "Sleeper has a RUDE awakening!") == 1);
                    // Later position updates and another hit must not add a wake.
                    update_pos(&sleeper);
                    production_damage_delivery(&attacker, &sleeper, 1, msg);
                    assert(count(output[&sleeper], wake) == 1);
                    assert(count(output[&witness], "RUDE awakening!") == 1);
                    assert(sleeper.specials.fighting == nullptr);
                }
            }
        }
    }
    puts("PASS: all postures, ordinary/effect/no messages, terse and SPELL_SLEEP; one wake, cleanup and posture preserved");

    for (int hp : {-11, -6, -3}) {
        reset(); GET_HIT(&sleeper) = hp;
        production_damage_delivery(&attacker, &sleeper, 1, nullptr);
        assert(output[&sleeper].empty());
        if (hp == -11) assert(output[&witness].empty());
        update_pos(&sleeper);
        assert(!IS_AWAKE(&sleeper));
    }
    for (unsigned int stat : {STAT_DEAD, STAT_DYING, STAT_INCAP, STAT_RESTING, STAT_NORMAL}) {
        reset(); SET_POS(&sleeper, POS_PRONE + stat);
        production_damage_delivery(&attacker, &sleeper, 1, nullptr);
        assert(output[&sleeper].empty() && output[&witness].empty());
    }
    reset(); SET_BIT(sleeper.specials.affected_by, AFF_KNOCKED_OUT);
    production_damage_delivery(&attacker, &sleeper, 1, nullptr);
    assert(output[&sleeper].empty() && !IS_AWAKE(&sleeper));
    assert(IS_AFFECTED(&sleeper, AFF_KNOCKED_OUT));
    reset(); SET_BIT(sleeper.specials.affected_by2, AFF2_MAJOR_PARALYSIS);
    production_damage_delivery(&attacker, &sleeper, 1, nullptr);
    assert(count(output[&sleeper], wake) == 1 && IS_AWAKE(&sleeper));
    assert(IS_AFFECTED2(&sleeper, AFF2_MAJOR_PARALYSIS));
    puts("PASS: dead/incapacitated/dying/already-awake/knocked-out boundaries and paralysis semantics");

    reset(); visible = false;
    production_damage_delivery(&attacker, &sleeper, 1, nullptr);
    assert(output[&sleeper] == wake && output[&witness].empty());
    reset(); SET_POS(&witness, POS_PRONE + STAT_SLEEPING);
    production_damage_delivery(&attacker, &sleeper, 1, nullptr);
    assert(output[&sleeper] == wake && output[&witness].empty());
    puts("PASS: direct notification bypasses sleep filter; room visibility/awake filters retained");

    reset(); do_wake(&sleeper, nullptr, 0);
    production_damage_delivery(&attacker, &sleeper, 1, nullptr);
    assert(count(output[&sleeper], "You wake up.") == 1);
    assert(output[&sleeper].find(wake) == std::string::npos);
    reset(); char target[] = "Sleeper";
    do_wake(&attacker, target, 0);
    production_damage_delivery(&attacker, &sleeper, 1, nullptr);
    assert(count(output[&sleeper], "You are awakened by Attacker.") == 1);
    assert(output[&sleeper].find(wake) == std::string::npos);
    for (int spell : {0, SPELL_SLEEP, SONG_SLEEP}) {
        reset(); attackers = 1;
        sleeping_spell = spell == SPELL_SLEEP; sleeping_song = spell == SONG_SLEEP;
        if (spell) SET_BIT(sleeper.specials.affected_by, AFF_SLEEP);
        update_pos(&sleeper);
        production_damage_delivery(&attacker, &sleeper, 1, nullptr);
        assert(count(output[&sleeper], "You wake up.") == 1);
        assert(output[&sleeper].find(wake) == std::string::npos);
        assert(!sleeping_spell && !sleeping_song && !IS_AFFECTED(&sleeper, AFF_SLEEP));
    }
    puts("PASS: voluntary, wake-by-another and update_pos-first normal/spell/song sleep without duplicate notifications");
}
'''

raw = extract_function("fight.c", "int raw_damage(")
start = raw.index("\t\tif (!messages)")
end = raw.index("\n\t\t/* instant nuke", start)
functions = [
    extract_function(name, signature)
    for name, signature in (
        ("utility.c", "int BOUNDED(int a, int b, int c)"),
        ("fight.c", "void dam_message("),
        ("utility.c", "bool is_ansi_char("),
        ("utility.c", "void CAP(char *str)"),
        ("interp.c", "char *one_argument("),
        ("actmove.c", "static int resting_posture("),
        ("actmove.c", "void do_wake("),
        ("fight.c", "unsigned int calculate_ch_state("),
        ("fight.c", "void update_pos("),
        ("comm.c", "void act(const char *str, int hide_invisible, P_char ch, P_obj obj, void *vict_obj, int type)"),
        ("comm.c", "void act(const char *str, int hide_invisible, P_char ch, P_obj obj, void *vict_obj, int type,"),
    )
]
functions.append(
    "void production_damage_delivery(P_char ch, P_char victim, double dam, damage_messages *messages) {\n"
    "int act_flag = messages && (messages->type & DAMMSG_TERSE) ? ACT_NOTTERSE : 0;\n"
    "unsigned int new_stat = calculate_ch_state(victim);\n" + raw[start:end] + "\n}"
)
build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="combat-wake-", dir=build) as temporary:
    harness = Path(temporary) / "harness.cpp"
    binary = Path(temporary) / "harness"
    harness.write_text("\n".join((PRELUDE, *functions, DRIVER)))
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        f"-I{ROOT / 'src'}", str(harness), str(source("safe_format.c")), "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True)
