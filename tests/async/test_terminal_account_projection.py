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
#include "flatfile/flatfile_identity_repository.h"
#include "flatfile/flatfile_account_adapter.h"
#include "persistence/persistence_mode.h"
#include <cassert>
#include <cstring>
#include <string>

struct deferred_save_slot { int pending; };
static deferred_save_slot slot;
static bool account_ok = true;
P_desc descriptor_list = nullptr;
static P_acct detached_account=nullptr;
const char *persistence_mode_flatfile_root() { return "fixture"; }
flatfile_identity_result flatfile_identity_lookup_pid(const std::string &, int32_t,
    flatfile_identity_record *record, std::string *) {
    record->account="fixture"; return flatfile_identity_result::ok;
}
P_acct flatfile_account_state_load(const char *, std::string *) { return detached_account; }
void flatfile_account_state_release(P_acct) {}
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
    assert(account->acct_good >= time(nullptr)-1 || account->acct_evil >= time(nullptr)-1);
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
    detached_account=&account;
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
            account.acct_good=time(nullptr)-7200;
            account.acct_evil=0;
            slot.pending = 7;
            hooks = writes = cleared = alerts = 0;
            assert(persistence_save_character_terminal(&player, RENT_DEATH));
            const bool accepted = result == player_save_pipeline_result::queued ||
                                  result == player_save_pipeline_result::coalesced;
            assert(hooks == 1 && writes == 1);
            assert(cleared == (accepted ? 1 : 0));
            assert(entry.level == (accepted ? 16 : 1));
            assert(slot.pending == (accepted ? 0 : 7));
            assert(alerts == (!accepted + !store_ok));
            if (!store_ok) assert(last_alert == "write_failed");
            else if (!accepted) assert(last_alert == "queue_failed");
            const auto denied=account_racewar_evaluate(ACCOUNT_RACEWAR_EVIL,false,
                account.acct_good,account.acct_evil,time(nullptr),3600);
            assert(!denied.allowed && denied.remaining_seconds>=3599);
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
    writes = 0; account_ok=true;
    account.acct_good=time(nullptr)-7200;
    assert(persistence_save_character_terminal(&player, RENT_DEATH));
    assert(writes == 1 && account.acct_good>=time(nullptr)-1);
    // The other side is stamped independently; immortals preserve both timestamps.
    player.desc=&desc; player.player.racewar=RACEWAR_EVIL;
    writes=0; account.acct_evil=0;
    assert(save_account_character_departure(&player));
    assert(writes==1 && account.acct_evil>=time(nullptr)-1);
    const auto good_stamp=account.acct_good, evil_stamp=account.acct_evil;
    player.player.level=MAXLVL;
    assert(save_account_character_departure(&player));
    assert(account.acct_good==good_stamp && account.acct_evil==evil_stamp);
    assert(!persistence_save_character_terminal(nullptr, RENT_DEATH));
    player.specials.act |= ACT_ISNPC;
    assert(!persistence_save_character_terminal(&player, RENT_DEATH));
}
'''


SQL_CASE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "account/account.h"
#include "sql/sql_async.h"
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <string>
P_desc descriptor_list=nullptr;
static std::string queued;
static bool queue_ok = true;
bool sql_queue_at(persistence_query_site,const char *format,...) {
    char buffer[2048]; va_list args; va_start(args,format);
    vsnprintf(buffer,sizeof buffer,format,args); va_end(args);
    queued=buffer; return queue_ok;
}
int write_account(P_acct) { assert(false); return -1; }
@DEPARTURE@
int main() {
    char_data player{}; pc_only_data pc{}; pc.pid=42;
    player.only.pc=&pc; player.player.level=10;
    player.player.racewar=RACEWAR_GOOD;
    assert(save_account_character_departure(&player));
    assert(queued.find("UPDATE accounts SET last_good_char=")!=std::string::npos);
    assert(queued.find("WHERE account_name=(SELECT account_name FROM player_data WHERE pid=42 AND active=1)")!=std::string::npos);
    queued.clear(); player.player.racewar=RACEWAR_EVIL;
    assert(save_account_character_departure(&player));
    assert(queued.find("last_evil_char=")!=std::string::npos);
    queued.clear(); player.player.level=MAXLVL;
    assert(save_account_character_departure(&player) && queued.empty());
    // Attached sessions use the same password-free write even when a full
    // account snapshot is fenced, and publish only the departure timestamp.
    descriptor_data desc{}, other{};
    acct_entry account{}, sibling{};
    account.acct_name = sibling.acct_name = const_cast<char *>("Fixture");
    account.acct_password = const_cast<char *>("old");
    sibling.acct_password = const_cast<char *>("different");
    desc.account = &account; desc.next = &other; other.account = &sibling;
    descriptor_list = &desc; player.desc = &desc; player.player.level = 10;
    for (auto side : {RACEWAR_GOOD, RACEWAR_EVIL}) {
        player.player.racewar = side;
        assert(save_account_character_departure(&player));
        assert(queued.find("password") == std::string::npos);
        assert(account.acct_good == sibling.acct_good && account.acct_evil == sibling.acct_evil);
        assert((side == RACEWAR_GOOD ? account.acct_good : account.acct_evil) >= time(nullptr)-1);
        assert(std::string(sibling.acct_password) == "different");
    }
    queue_ok = false;
    assert(!save_account_character_departure(&player));
}
'''

def main():
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="terminal-projection-", dir=build) as temporary:
        cpp, binary = Path(temporary) / "harness.cpp", Path(temporary) / "harness"
        cpp.write_text("\n".join((PRELUDE,
            extract_function("account.c", "int sync_account_character_projection("),
            extract_function("account.c", "bool save_account_character_departure("),
            extract_function("actoth.c", "bool persistence_save_character_terminal("), CASES)))
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Og", "-g",
                        "-D__NO_MYSQL__", "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
                        "-Isrc", "src/account/racewar_admission.c", str(cpp), str(HARNESS_STUBS), "-o", str(binary)],
                       cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True)
        sql_cpp, sql_binary = Path(temporary) / "sql.cpp", Path(temporary) / "sql"
        sql_cpp.write_text(SQL_CASE.replace("@DEPARTURE@",
            extract_function("account.c", "bool save_account_character_departure(")))
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-fno-pie", "-no-pie", "-Isrc",
                        str(sql_cpp), str(HARNESS_STUBS), "-o", str(sql_binary)],
                       cwd=ROOT, check=True)
        subprocess.run([str(sql_binary)], check=True)
    print("terminal account projection, detached SQL timestamp and failure cases passed under ASan/UBSan")


if __name__ == "__main__":
    main()
