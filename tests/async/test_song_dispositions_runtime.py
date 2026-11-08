#!/usr/bin/env python3
"""Run Heroism's production handler, affect links and stop/movement cleanup."""
import re
import subprocess
from _paths import ROOT, HARNESS_STUBS, extract_function

prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/mm.h"
#include "net/gmcp.h"
#include "magic/spells.h"
#include "abilities/abilities.h"
#include "net/comm.h"
#include "world/events.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <map>
#include <string>
#include <vector>
static mm_ds aff_pool{}, link_pool{};
mm_ds *dead_affect_pool = &aff_pool, *dead_link_pool = &link_pool;
link_description link_types[LNK_MAX + 1]{};
static std::map<P_char, std::vector<std::string>> recipient_messages;
static int empower = 45, haste_calls, healing;
int GET_CHAR_SKILL_P(P_char, int skill) { return skill == SKILL_EMPOWER_SONG ? empower : 100; }
int GET_CLASS(P_char ch, uint cls) { return (ch->player.m_class & cls) != 0; }
void send_to_char(const char *s, P_char ch) { recipient_messages[ch].emplace_back(s); }
void act(const char *, int, P_char, P_obj, void *, int) {}
void spell_haste(int, P_char, char *, int, P_char, P_obj) { ++haste_calls; }
void *_mm_get(mm_ds *pool, const char *, int) {
    if (pool == dead_link_pool) return new char_link_data{};
    return new affected_type{};
}
void mm_release(mm_ds *pool, void *p) {
    if (pool == dead_link_pool) delete static_cast<char_link_data *>(p);
    else delete static_cast<affected_type *>(p);
}
mm_ds *mm_create(const char *, size_t, size_t, unsigned) { assert(false); return nullptr; }
void all_affects(P_char, int) {}
void balance_affects(P_char) {}
void gmcp_char_affects(P_char) {}
int char_light(P_char) { return 0; }
int room_light(int, int) { return 0; }
void wear_off_message(P_char, affected_type *) {}
void unlink_char_obj_affect(P_char, affected_type *) { assert(false); }
void unlink_char_affect(P_char, affected_type *);
void disarm_char_nevents(P_char, event_func_type) {}
void event_web_spray(P_char, P_char, P_obj, void *) {}
nevent_schedule_result add_event(event_func, int, P_char, P_char, P_obj, int, const void *, int) { return {}; }
nevent_handle nevent_handle_from_event(P_nevent) { return {}; }
nevent_cancel_result nevent_cancel(nevent_handle) { return nevent_cancel_result::canceled; }
P_nevent get_scheduled(P_char, event_func_type) { return nullptr; }
void event_bardsong(P_char, P_char, P_obj, void *) {}
void heal(P_char, P_char, int amount, int) { healing = amount; }
void update_pos(P_char) {}
void spell_cure_blind(int, P_char, char *, int, P_char, P_obj) {}
void spell_remove_poison(int, P_char, char *, int, P_char, P_obj) {}
void spell_cure_disease(int, P_char, char *, int, P_char, P_obj) {}
bool is_silent(P_char ch, bool) { return IS_AFFECTED2(ch, AFF2_SILENCED); }
int number(int low, int) { return low; }
int dice(int n, int) { return n; }
const Rolls live_rolls = {dice, number};
'''
functions = [("affects.c", s) for s in (
    "bool affected_by_spell(", "struct affected_type *affect_to_char(",
    "void affect_remove(", "void affect_from_char(", "void define_link(",
    "struct char_link_data *link_char_with_affect(", "P_char get_linked_char(",
    "P_char get_linking_char(", "void dispose_link(", "void internal_unlink_char(",
    "void unlink_char(", "void unlink_char_affect(P_char ch, struct affected_type *af)",
    "void clear_links(P_char ch, ush_int type)", "void check_room_links(",
    "void linked_affect_to_char(",
)] + [("bard.c", s) for s in (
    "void stop_singing(", "static int song_heroism_haste_level(",
    "static int song_heroism_pulse(", "static int song_heroism_singer_pulse(",
    "static int song_heroism_hit_dam(", "void bard_heroism(int l,",
    "static int song_healing_amount(", "static int song_healing_ally_amount(",
    "static int song_healing_cap_gap(", "static int song_healing_duration(",
    "static int song_healing_blind_rating(", "static int song_healing_poison_rating(",
    "static int song_healing_disease_rating(", "void bard_healing(int level,",
)]
# Reuse the production registration's room/affect ownership flags.
registration = re.search(r'define_link\(LNK_SONG,.*?;', extract_function("affects.c", "void initialize_links()"), re.S)[0]
registration = registration.replace("song_broken", "nullptr")  # callback acts only on Song of Sleep
# A verse discards effects for an old song or an absent listener before dispatch.
verse = extract_function("bard.c", "void event_bardsong(P_char ch,")
a = verse.index("\tfor (cld = ch->linked;")
b = verse.index("\n\tif (!CAN_SING(ch))", a)
cleanup = "void next_song(P_char ch, int song) { char_link_data *cld, *next_cld;\n" + verse[a:b] + "}\n"
driver = r'''
static std::map<int,int> bonuses(P_char ch) {
    std::map<int,int> out;
    for (auto *af = ch->affected; af; af = af->next) {
        assert(af->type == SONG_HEROISM);
        assert((af->flags & (AFFTYPE_LINKED_CH | AFFTYPE_NOSAVE)) == (AFFTYPE_LINKED_CH | AFFTYPE_NOSAVE));
        out[af->location] += af->modifier;
    }
    assert(out.size() == 4);
    return out;
}
int main() {
    REGISTER
    define_link(LNK_SNG_HEALING, "healing", nullptr, LNKFLG_AFFECT | LNKFLG_ROOM);
    for (int level : {20,21,40,56}) for (bool self_first : {false,true}) for (bool npc : {false,true}) {
        char_data singer{}, listener{};
        SET_POS(&singer, POS_STANDING + STAT_NORMAL);
        SET_POS(&listener, POS_STANDING + STAT_NORMAL);
        singer.player.m_class = CLASS_BARD;
        listener.player.m_class = CLASS_WARRIOR;
        singer.player.level = level;
        if (npc) SET_BIT(singer.specials.act, ACT_ISNPC);
        recipient_messages.clear(); haste_calls = 0;
        bard_heroism(level, &singer, self_first ? &singer : &listener, SONG_HEROISM);
        bard_heroism(level, &singer, self_first ? &listener : &singer, SONG_HEROISM);
        for (P_char recipient : {&singer,&listener}) {
            auto values = bonuses(recipient);
            assert(values[APPLY_COMBAT_PULSE] == (recipient == &singer ? -level/20 : -1));
            assert(values[APPLY_SPELL_PULSE] == values[APPLY_COMBAT_PULSE]);
            assert(values[APPLY_HITROLL] == level/10 + (empower + (npc ? 100 : 0))/15);
            assert(values[APPLY_DAMROLL] == values[APPLY_HITROLL]);
            assert(recipient_messages[recipient].size() == 2);
        }
        assert(haste_calls == (level >= 21 ? 2 : 0));
        bard_heroism(level, &singer, &listener, SONG_HEROISM);
        assert(recipient_messages[&singer].size() == 2 && recipient_messages[&listener].size() == 2);
        bonuses(&singer); bonuses(&listener); // repeated verses do not stack
        listener.in_room = 1;
        check_room_links(&listener, NOWHERE, 1);
        assert(!listener.affected && !listener.linking);
        assert(singer.affected);
        next_song(&singer, SONG_PROTECTION);
        assert(!singer.affected && !singer.linked && !singer.linking);
        listener.in_room = 0;
        bard_heroism(level, &singer, &listener, SONG_HEROISM);
        stop_singing(&singer);
        assert(!singer.affected && !listener.affected && !singer.linked);
    }
    char_data singer{};
    singer.player.m_class = CLASS_BARD; singer.player.spec = SPEC_DISHARMONIST;
    singer.curr_stats.Cha = 100;
    SET_POS(&singer, POS_STANDING + STAT_NORMAL);
    SET_BIT(singer.specials.affected_by2, AFF2_SILENCED);
    assert(!CAN_SING(&singer));
    // Even a direct handler call cannot cure silence; normal dispatch refuses it.
    bard_healing(56, &singer, &singer, SONG_HEALING);
    assert(IS_AFFECTED2(&singer, AFF2_SILENCED) && healing == 30);
    affect_from_char(&singer, SONG_HEALING);
    puts("Songs: singer order, all four bonuses, recipient_messages, repeat/leave/change/stop cleanup and retained silence passed.");
}
'''.replace("REGISTER", registration)
build = ROOT / "bin/tests/song-dispositions"
build.mkdir(parents=True, exist_ok=True)
cpp, binary = build / "harness.cpp", build / "harness"
cpp.write_text(prelude + "\n".join(extract_function(f,s) for f,s in functions) + cleanup + driver)
subprocess.run(["g++", "-std=c++20", "-g", "-fsanitize=address,undefined", "-I" + str(ROOT / "src"),
                str(cpp), str(HARNESS_STUBS), "-o", str(binary)], check=True)
subprocess.run([str(binary)], check=True)
