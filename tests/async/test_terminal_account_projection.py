#!/usr/bin/env python3
"""Execute terminal-save publication, including deterministic writer failures.

The production terminal helper and projection helper run with real engine types;
snapshot submission, account storage and output are controlled service boundaries.
The socket journey separately proves death, both renderers and durable reload.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS, extract_function


PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/files.h"
#include "account/account.h"
#include "player/player_playtime.h"
#include "player/player_save_pipeline.h"
#include <cassert>
#include <cstring>
#include <string>

struct deferred_save_slot { int pending; };
static deferred_save_slot slot;
static bool account_ok = true;
static int writes, hooks, cleared, alerts;
static std::string last_alert;
static player_save_pipeline_result outcome = player_save_pipeline_result::queued;
int calculate_save_room(P_char, int, int) { return 22800; }
void locker_post_save_hook(P_char) { ++hooks; }
deferred_save_slot *find_deferred_save_slot(int) { return &slot; }
void clear_manual_save_status(int) { ++cleared; }
player_save_pipeline_result player_save_pipeline_request(P_char ch,
    player_component_mask_t components, int type, int room) {
    assert(ch->player.level == 16 && components == PLAYER_CHECKPOINT_COMPONENT_ALL);
    assert(type == RENT_DEATH && room == 22800);
    assert(writes == 0); // capture must precede account publication
    return outcome;
}
struct acct_chars *find_char_in_list(struct acct_chars *list, const char *name) {
    for (; list; list = list->next)
        if (!strcmp(list->charname, name)) return list;
    return nullptr;
}
int write_account(P_acct account) {
    ++writes;
    assert(account->acct_character_list->level == 16);
    return account_ok ? 1 : -1;
}
void persistence_alert(int, const char *, const char *, const char *, const char *,
                       const char *reason, const char *, ...) {
    ++alerts;
    last_alert = reason;
}
'''

CASES = r'''
int main() {
    char_data player{};
    pc_only_data pc{};
    descriptor_data desc{};
    acct_entry account{};
    acct_chars entry{}, sibling{};
    player.only.pc = &pc;
    pc.pid = 42;
    player.player.name = const_cast<char *>("Projection");
    player.player.level = 16;
    player.player.race = RACE_HUMAN;
    player.player.m_class = CLASS_MONK;
    player.player.racewar = RACEWAR_GOOD;
    player.player.time.logon = time(nullptr);
    player.player.time.played = 123;
    player.desc = &desc;
    desc.character = &player;
    desc.account = &account;
    account.acct_character_list = &entry;
    entry.charname = player.player.name;
    entry.next = &sibling;
    sibling.charname = const_cast<char *>("Other");
    sibling.level = 9;
    for (auto result : {player_save_pipeline_result::queued,
                        player_save_pipeline_result::coalesced,
                        player_save_pipeline_result::invalid,
                        player_save_pipeline_result::capture_failed,
                        player_save_pipeline_result::unavailable}) {
        for (bool store_ok : {true, false}) {
            outcome = result;
            account_ok = store_ok;
            entry.level = 1;
            slot.pending = 7;
            hooks = writes = cleared = alerts = 0;
            assert(persistence_save_character_terminal(&player, RENT_DEATH));
            const bool accepted = result == player_save_pipeline_result::queued ||
                                  result == player_save_pipeline_result::coalesced;
            assert(hooks == 1 && writes == (accepted ? 1 : 0));
            assert(cleared == (accepted ? 1 : 0));
            assert(entry.level == (accepted ? 16 : 1));
            assert(slot.pending == (accepted ? 0 : 7));
            assert(alerts == (accepted && store_ok ? 0 : 1));
            if (alerts) assert(last_alert == (accepted ? "write_failed" : "queue_failed"));
            if (accepted) {
                assert(entry.pid == 42 && entry.race == RACE_HUMAN);
                assert(entry.m_class == CLASS_MONK && entry.last_room == 22800);
                assert(entry.played >= 123 && entry.player_racewar == RACEWAR_GOOD);
            }
            assert(sibling.level == 9 && !strcmp(sibling.charname, "Other"));
            assert(desc.character == &player && player.desc == &desc);
        }
    }
    // Link-dead saves still submit without manufacturing an account context.
    player.desc = nullptr;
    outcome = player_save_pipeline_result::queued;
    writes = 0;
    assert(persistence_save_character_terminal(&player, RENT_DEATH));
    assert(writes == 0);
    assert(!persistence_save_character_terminal(nullptr, RENT_DEATH));
    player.specials.act |= ACT_ISNPC;
    assert(!persistence_save_character_terminal(&player, RENT_DEATH));
}
'''


def main():
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="terminal-projection-", dir=build) as temporary:
        cpp, binary = Path(temporary) / "harness.cpp", Path(temporary) / "harness"
        cpp.write_text("\n".join((PRELUDE,
            extract_function("account.c", "int sync_account_character_projection("),
            extract_function("actoth.c", "bool persistence_save_character_terminal("), CASES)))
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Og", "-g",
                        "-D__NO_MYSQL__", "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
                        "-Isrc", str(cpp), str(HARNESS_STUBS), "-o", str(binary)],
                       cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True)
    print("terminal account projection and writer failure cases passed under ASan/UBSan")


if __name__ == "__main__":
    main()
