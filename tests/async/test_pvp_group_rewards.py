#!/usr/bin/env python3
"""Exercise PvP capture with player/pet groups and the real reward calculation."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, SRC, extract_function


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/config.h"
#include "guild/assocs.h"
#include "guild/artifact_guild_transaction.h"
#include "combat/combat_outcome_transaction.h"
#include "world/epic.h"
#include "magic/spells.h"
#include "world/db.h"
#include "economy/divine_boon_runtime.h"
#include "economy/divine_boon_math.h"
#include "economy/nexus_stones.h"
#include "world/epic_bonus.h"
#include <cmath>
#include <limits>
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstring>

static room_data rooms[2]{};
P_room world = rooms;
static zone_data zones[1]{};
zone_data *zone_table = zones;
static divine_boon_state boons;
int errand_notch = 500;
static char_data characters[6]{};
static pc_only_data pcs[6]{};
static group_list groups[6]{};
extern const race_names race_names_table[RACE_HUMAN + 1] = {
    {}, {"Human", "Human", "Human", "PH"}
};
static combat_outcome_payload captured;
static unsigned submissions;
static bool accept_submission = true;
static unsigned rolled_back;

const char *get_account_name_safe(P_char) { return "fixture"; }
const char *get_class_name(P_char, P_char) { return "Fixture"; }
void get_equipment_list(P_char, char *buffer, int) { buffer[0] = '\0'; }
bool opposite_racewar(P_char a, P_char b) { return GET_RACEWAR(a) != GET_RACEWAR(b); }
bool grouped(P_char a, P_char b) { return a->group && a->group == b->group; }
P_char find_player_by_pid(int pid) {
    for (auto &ch : characters)
        if (IS_PC(&ch) && GET_PID(&ch) == pid) return &ch;
    return nullptr;
}
float get_property(const char *key, double fallback) {
    if (!strcmp(key, "frag.evil.penalty")) return 1.0F;
    if (!strcmp(key, "epic.frag.amount")) return 250.0F;
    if (!strcmp(key, "epic.frag.threshold")) return 0.15F;
    return fallback;
}
int get_property(const char *, int fallback) { return fallback; }
affected_type *get_epic_task(P_char) { return nullptr; }
const divine_boon_state *divine_boon_runtime_state() { return &boons; }
int check_nexus_bonus(P_char, int value, int) { return value; }
double check_nexus_bonus_precise(P_char, double value, int, bool) { return value; }
float get_epic_bonus(P_char, int) { return 0; }
double get_epic_bonus_precise(P_char, int) { return 0; }
bool artifact_guild_transaction_submit(P_char, const critical_operation_id &, int, int) {
    return true;
}
void logit(const char *, const char *, ...) {}
[[noreturn]] int panic_corruption_int(const char *, const char *, ...) { std::abort(); }
int GET_CLASS(P_char ch, uint cls) { return (ch->player.m_class & cls) != 0; }
uint64_t gameplay_read_state_add_provisional(gameplay_read_state *, int64_t) { return 1; }
bool gameplay_read_state_finish_provisional(gameplay_read_state *, uint64_t, bool committed) {
    assert(!committed);
    ++rolled_back;
    return true;
}
static void combat_outcome_committed(bool, const combat_outcome_result &, unsigned int,
                                     const combat_outcome_payload &) {}
bool combat_outcome_transaction_submit(const combat_outcome_payload &payload,
                                       combat_outcome_completion_fn,
                                       critical_operation_id *) {
    ++submissions;
    critical_operation_id id{};
    assert(critical_operation_id_generate(&id));
    critical_command command{};
    assert(combat_outcome_command_build(&command, id, payload));
    assert(combat_outcome_command_decode_payload(command, &captured));
    return accept_submission;
}
'''

CASES = r'''
static void reset() {
    submissions = rolled_back = 0;
    boons = {};
    accept_submission = true;
    for (int i = 0; i < 6; ++i) {
        characters[i] = {};
        pcs[i] = {};
        groups[i] = {};
        auto &ch = characters[i];
        ch.only.pc = &pcs[i];
        ch.only.pc->pid = i + 1;
        ch.player.name = const_cast<char *>("Fixture");
        ch.player.level = 25;
        ch.player.race = RACE_HUMAN;
        ch.player.racewar = i == 1 ? RACEWAR_EVIL : RACEWAR_GOOD;
        ch.in_room = 0;
    }
    rooms[0].number = 123;
    rooms[0].name = const_cast<char *>("Fixture room");
    rooms[0].people = &characters[0];
    characters[0].next_in_room = &characters[1];
    // NPCs must never enter the player-only payload, even with no pc allocation.
    for (int i : {4, 5}) {
        characters[i].specials.act = ACT_ISNPC;
        characters[i].only.npc = nullptr;
    }
}
static void group(P_char leader, P_char follower, int slot) {
    groups[slot].ch = leader;
    groups[slot].next = &groups[slot + 1];
    groups[slot + 1].ch = follower;
    leader->group = follower->group = &groups[slot];
    follower->following = leader;
}
static const combat_outcome_participant &entry(P_char ch) {
    for (size_t i = 0; i < captured.participant_count; ++i)
        if (captured.participants[i].pid == static_cast<uint32_t>(GET_PID(ch)))
            return captured.participants[i];
    assert(false);
    return captured.participants[0];
}
int main() {
    auto *killer = &characters[0], *victim = &characters[1];
    auto *ally = &characters[2], *enemy = &characters[3];
    auto *pet = &characters[4], *enemy_pet = &characters[5];
    reset();
    assert(submit_pvp_outcome(killer, victim, true));
    assert(submissions == 1 && captured.participant_count == 2);
    assert(entry(killer).frag_delta == 100 && entry(killer).epic_delta == 250);

    // A pet on either side used to abort the entire kill before submission.
    for (int side = 0; side < 3; ++side) {
        reset();
        if (side != 1) group(killer, pet, 0);
        if (side != 0) group(victim, enemy_pet, 2);
        assert(submit_pvp_outcome(killer, victim, true));
        assert(submissions == 1 && captured.participant_count == 2);
        assert(captured.killer_allies == 1);
        assert(entry(killer).frag_delta == 100 && entry(killer).epic_delta == 250);
        assert(entry(victim).frag_delta == -100);
    }

    // Two players with a pet: split frags/epics among the players; mercenary
    // blood money uses the same share. An absent group member stays in history.
    reset();
    killer->player.level = 28;
    killer->player.m_class = CLASS_MERCENARY;
    victim->player.level = 23;
    ally->player.level = 27;
    group(killer, ally, 0);
    groups[1].next = &groups[2]; groups[2].ch = pet; pet->group = killer->group;
    groups[2].next = &groups[3]; groups[3].ch = enemy; enemy->group = killer->group;
    enemy->in_room = 1;
    ally->next_in_room = rooms[0].people; rooms[0].people = ally;
    pet->next_in_room = rooms[0].people; rooms[0].people = pet;
    assert(submit_pvp_outcome(killer, victim, true));
    assert(captured.participant_count == 4 && captured.killer_allies == 2);
    assert(entry(killer).frag_delta == 50 && entry(killer).epic_delta == 125);
    assert(entry(killer).wallet_delta_copper == 500000);
    assert(entry(ally).frag_delta == 50 && entry(ally).epic_delta == 125);
    assert(entry(victim).frag_delta == -50);
    assert(!entry(enemy).frag_delta && !(entry(enemy).flags & COMBAT_PARTICIPANT_IN_ROOM));

    // The active Divine PvP boon preserves the same split and adds 50% epics.
    boons.mode = divine_boon_mode::divine;
    boons.slots[0].id = 100;
    boons.slots[0].category = divine_boon_category::pvp;
    boons.slots[0].starts_at = time(nullptr) - 1;
    boons.slots[0].expires_at = time(nullptr) + 3600;
    assert(submit_pvp_outcome(killer, victim, true));
    assert(entry(killer).epic_delta == 187 && entry(ally).epic_delta == 187);
    assert(entry(killer).flags & COMBAT_PARTICIPANT_DIVINE_EPIC);
    assert(entry(killer).epic_base == 125 && entry(killer).epic_boon_id == 100);
    assert(entry(killer).wallet_delta_copper == 500000);

    // A pet's killing blow still credits its grouped, present owner.
    reset();
    group(killer, pet, 0);
    assert(submit_pvp_outcome(pet, victim, true));
    assert(entry(killer).role == combat_participant_role::killer);
    assert(entry(killer).frag_delta == 100);
    pet->in_room = 1;
    assert(!submit_pvp_outcome(pet, victim, true));

    // Level differences and non-fraggable deaths retain their existing rules.
    reset();
    group(killer, pet, 0);
    killer->player.level = 27; victim->player.level = 21;
    assert(submit_pvp_outcome(killer, victim, true));
    assert(entry(killer).frag_delta == 50 && entry(killer).epic_delta == 125);
    assert(submit_pvp_outcome(killer, victim, false));
    assert(!entry(killer).frag_delta && !entry(killer).epic_delta);
    assert(!entry(victim).frag_delta);
    victim->player.level = 19;
    assert(!fragWorthy(killer, victim));
    victim->player.level = 20; killer->player.level = 31;
    assert(!fragWorthy(killer, victim));

    // An invalid real player and a rejected submission still fail without
    // leaking the provisional recent-death entry.
    reset();
    group(killer, ally, 0); ally->only.pc->pid = 0;
    assert(!submit_pvp_outcome(killer, victim, true) && submissions == 0);
    reset();
    group(killer, pet, 0); accept_submission = false;
    assert(!submit_pvp_outcome(killer, victim, true));
    assert(submissions == 1 && rolled_back == 1);
    puts("PvP player/pet groups: capture, shares, epics, blood money and refusals passed");
}
'''


def main():
    harness = PRELUDE
    for file, signature in (
        ("fraglist.c", "int fragWorthy("),
        ("epic.c", "int epic_calculate_pvp_award("),
        ("epic.c", "bool epic_prepare_pvp_award("),
        ("fight.c", "static combat_outcome_participant *combat_outcome_add_participant("),
        ("fight.c", "static bool submit_pvp_outcome("),
    ):
        harness += extract_function(file, signature) + "\n"
    harness += CASES
    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / "bin/tests") as directory:
        source = Path(directory) / "pvp.cpp"
        binary = source.with_suffix("")
        source.write_text(harness)
        subprocess.run([
            "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", f"-I{SRC}",
            str(source), str(SRC / "critical_command.c"), str(SRC / "currency_command.c"),
            str(SRC / "combat_outcome_command.c"), str(SRC / "artifact_guild_command.c"),
            str(SRC / "divine_boon.c"), "-lcrypto", "-lbsd", "-o", str(binary),
        ], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
