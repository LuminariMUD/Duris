#!/usr/bin/env python3
"""Execute locker name resolution and access verdicts, including delayed worker replies."""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function, source

text = source('storage_lockers.c').read_text()
entry = text[text.index('struct locker_entry\n{'):text.index('\n};', text.index('struct locker_entry\n{')) + 3]
prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "sql/sql.h"
#include "sql/sql_async.h"
#include "flatfile/flatfile_corpse_ownership.h"
#include "flatfile/flatfile_identity_repository.h"
#include "flatfile/flatfile_locker_repository.h"
#include <algorithm>
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <set>
#include <string>
#include <strings.h>

using locker_entered = std::function<void(P_char, P_char, int)>;
static std::string feedback, target, query;
static std::string state_root, visitor_account = "GuestAccount";
MYSQL *DB = reinterpret_cast<MYSQL *>(1);
const char *persistence_mode_flatfile_root() { return state_root.c_str(); }
const char *get_account_name_safe(P_char) { return visitor_account.c_str(); }
int panic_corruption_int(const char *, const char *, ...) { std::abort(); }
flatfile_corpse_ownership_result flatfile_world_load_item_ownership(
    const std::string &, const item_owner_identity &,
    const std::vector<player_item_snapshot> &items, std::vector<player_item_snapshot> *,
    uint64_t *, std::vector<player_load_item_identity> *, std::string *)
{
    assert(items.empty()); // This fixture exercises persisted identity/grants, not item loading.
    return flatfile_corpse_ownership_result::ok;
}
static bool admit = true, present = true, owner = false, direct = false, account = false;
static int enters, grant_reads, content_reads;
static unsigned int fail_read;
static std::function<void(P_char, const sql_rows &)> reply;
static std::set<std::string> locker_entries;
static room_data rooms[2];
P_room world = rooms;
P_char character_list;
static bool saving;
class StorageLocker {
public:
    P_char character;
    P_char GetLockerChar() { return character; }
};
static StorageLocker *active;
StorageLocker *GetChestList(int room) { return room == 1 ? active : nullptr; }
int real_room0(const int vnum) { return vnum == 65201 ? 0 : vnum == 65202 ? 1 : NOWHERE; }
int storage_locker(int, P_char, int, char *) { return 0; }
int locker_async_name_busy(const char *) { return saving; }
P_nevent get_scheduled(P_char, event_func) { return nullptr; }
static void event_deferredTerminalSave(P_char, P_char, P_obj, void *) {}
void logit(const char *, const char *, ...) {}

void send_to_char(const char *message, P_char) { feedback += message; }
std::string escape_str(const char *value) { return value; }
bool sql_read_for_at(persistence_query_site, P_char, std::string sql,
                     std::function<void(P_char, const sql_rows &)> done)
{
    query = std::move(sql);
    reply = std::move(done);
    return admit;
}
static void locker_enter(P_char, const char *name, int validate, locker_entered)
{
    assert(validate == 1); // Resolving a name must never bypass authorization.
    ++enters;
    target = name;
}
std::string sql_format(const char *format, ...)
{
    char buffer[4096];
    va_list args;
    va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);
    return buffer;
}
unsigned int sql_execute(MYSQL *, const std::string &) { std::abort(); }
unsigned int sql_select(MYSQL *, const std::string &sql, sql_rows *rows)
{
    if (fail_read) return fail_read;
    if (sql.find("SELECT 'locker'") == 0) {
        if (present) rows->push_back({{"locker", "11", "1", "3"}});
    } else if (sql.find("SELECT 1 FROM lockers l") == 0) {
        if (owner) rows->push_back({{"1"}});
    } else if (sql.find("SELECT 1 FROM locker_access") == 0) {
        ++grant_reads;
        if (sql.find("JOIN account_characters") != std::string::npos ? account : direct)
            rows->push_back({{"1"}});
    } else {
        ++content_reads;
        std::abort(); // All these access checks address a busy locker: never load its items.
    }
    return 0;
}
'''
constants = '\n'.join(line for line in text.splitlines()
                      if line.startswith(('#define LOCKERS_START ', '#define LOCKERS_MAX ')))
flat_chest = text[text.index('struct flat_locker_chest\n{'):text.index('\n};', text.index('struct flat_locker_chest\n{')) + 3]
production = constants + '\n' + flat_chest + '\n' + '\n'.join(extract_function('storage_lockers.c', signature) for signature in (
    'static std::string locker_entry_key(',
    'static StorageLocker *active_locker_for(',
    'static int lockerName_is_inuse(char *lockerName)\n{',
    'static void locker_enter_character(P_char ch, const char *name, locker_entered entered)\n{',
    'static unsigned int locker_granted(',
    'static sql_row locker_outcome(',
    'static unsigned int locker_entry_read(',
    'static bool flat_locker_read(',
))
driver = r'''
int main(int argc, char **argv)
{
    assert(argc == 2);
    char locker_name[] = "account.owner.1.locker";
    char_data holding{}, other{};
    holding.player.name = locker_name;
    holding.in_room = 0; // The storage character stays in holding room 65201.
    character_list = &holding;
    StorageLocker wrapper{&holding};
    active = &wrapper;
    rooms[1].funct = storage_locker; // Its wrapper is in private room 65202.
    assert(active_locker_for(&holding) == &wrapper);
    assert(active_locker_for(&other) == nullptr);
    assert(lockerName_is_inuse(locker_name) == 1);
    active = nullptr;
    assert(lockerName_is_inuse(locker_name) == 0);
    saving = true;
    assert(lockerName_is_inuse(locker_name) == 1);
    saving = false;
    locker_entries.insert(locker_name);
    assert(lockerName_is_inuse(locker_name) == 1);
    locker_entries.clear();

    char_data visitor{};
    visitor.in_room = 10;
    locker_enter_character(&visitor, "ownerchar", {});
    assert(enters == 0); // Nothing enters until the worker answers.
    assert(query.find("blocked=0 AND deleted_at IS NULL") != std::string::npos);
    reply(&visitor, {{{"DifferentAccount", "2"}}});
    assert(enters == 1 && target == "account.differentaccount.2.locker");
    locker_enter_character(&visitor, "legacy", {});
    reply(&visitor, {});
    assert(enters == 2 && target == "legacy.locker");
    locker_enter_character(&visitor, "ownerchar", {});
    visitor.in_room = 11;
    reply(&visitor, {{{"DifferentAccount", "2"}}});
    assert(enters == 2 && feedback.find("moved away") != std::string::npos);
    admit = false;
    feedback.clear();
    locker_enter_character(&visitor, "ownerchar", {});
    assert(enters == 2 && feedback.find("could not be opened") != std::string::npos);

    locker_entry entry{"account.owner.1.locker", "visitor", 42, 1, true,
                       false, false, 0, 1, 3};
    auto verdict = [&](bool allowed) {
        sql_rows rows;
        assert(locker_entry_read(nullptr, entry, &rows) == 0);
        assert(rows.size() == 1 && std::string(rows[0][0]) == "access");
        assert(std::string(rows[0][1]) == (allowed ? "1" : "0"));
        assert(content_reads == 0);
    };
    verdict(false);
    direct = true;
    verdict(true);
    entry.visitor_racewar = 2;
    const int before = grant_reads;
    verdict(false); // A stale direct grant never exposes an opposite-side occupant.
    assert(grant_reads == before);
    entry.visitor_racewar = 1;
    direct = false;
    account = true;
    verdict(true);
    account = false;
    owner = true;
    verdict(true); // Stable personal ownership still works.
    owner = false;
    present = false;
    verdict(false); // A visitor's explicit name cannot create a missing locker.
    fail_read = 2013;
    sql_rows rows;
    assert(locker_entry_read(nullptr, entry, &rows) == 2013 && rows.empty());

    // The same production resolver reads an on-disk flat-file identity catalog.
    namespace fs = std::filesystem;
    state_root = argv[1];
    fs::create_directories(fs::path(state_root) / "identities/names");
    fs::create_directories(fs::path(state_root) / "domains");
    for (const auto &path : {fs::path(state_root), fs::path(state_root) / "identities",
                            fs::path(state_root) / "identities/names", fs::path(state_root) / "domains"})
        fs::permissions(path, fs::perms::owner_all, fs::perm_options::replace);
    DB = nullptr;
    std::string error;
    flatfile_identity_record identity;
    assert(flatfile_identity_allocate_pid(state_root, &identity.pid, &error) == flatfile_identity_result::ok);
    identity.name = "Ownerchar";
    identity.account = "DifferentAccount";
    identity.active = true;
    identity.racewar = 2;
    auto sync = [&]() {
        assert(flatfile_identity_sync_account(state_root, identity.account, {identity}, &error) ==
               flatfile_identity_result::ok);
    };
    sync();
    locker_enter_character(&visitor, "oWNERCHAR", {});
    assert(target == "account.differentaccount.2.locker");
    locker_enter_character(&visitor, "legacy", {});
    assert(target == "legacy.locker");
    identity.blocked = true;
    sync();
    locker_enter_character(&visitor, "Ownerchar", {});
    assert(target == "Ownerchar.locker");
    assert(flatfile_identity_sync_account(state_root, identity.account, {}, &error) ==
           flatfile_identity_result::ok);
    locker_enter_character(&visitor, "Ownerchar", {});
    assert(target == "Ownerchar.locker");

    // Stored grants and typed ownership supply the same access verdict as MariaDB.
    flatfile_locker_record account_locker;
    account_locker.locker_id = 1;
    account_locker.locker_name = "account.differentaccount.2.locker";
    account_locker.account_owner = flatfile_account_locker_identity{"differentaccount", 2};
    account_locker.racewar = 2;
    account_locker.revision = 1;
    flatfile_locker_chest_record chest;
    chest.chest_id = 1;
    chest.chest_name = "public";
    chest.is_public = true;
    chest.revision = 1;
    account_locker.chests = {chest};
    auto legacy_locker = account_locker;
    legacy_locker.locker_id = 2;
    legacy_locker.locker_name = "ownerchar.locker";
    legacy_locker.account_owner.reset();
    legacy_locker.owner_pid = 1;
    legacy_locker.chests[0].chest_id = 2;
    assert(flatfile_locker_establish(state_root, {account_locker, legacy_locker},
        {{account_locker.locker_name, "Directguest", 1},
         {account_locker.locker_name, "GuestAccount", 1}}, &error) == flatfile_locker_result::ok);
    pc_only_data pc{};
    visitor.only.pc = &pc;
    pc.pid = 99;
    char guest[] = "Visitor", direct_guest[] = "dIRECTGUEST";
    visitor.player.name = guest;
    visitor.player.racewar = 2;
    auto flat_verdict = [&](const std::string &name, bool allowed) {
        sql_rows loaded;
        flat_locker_chest contents;
        assert(flat_locker_read(&visitor, name, &loaded, &contents));
        assert(loaded.size() == 2 && std::string(loaded[0][0]) == "access");
        assert(std::string(loaded[0][1]) == (allowed ? "1" : "0"));
    };
    flat_verdict(account_locker.locker_name, true); // Account grant.
    visitor_account = "OtherAccount";
    flat_verdict(account_locker.locker_name, false);
    visitor.player.name = direct_guest;
    flat_verdict(account_locker.locker_name, true); // Case-insensitive character grant.
    visitor.player.racewar = 1;
    flat_verdict(account_locker.locker_name, false); // Opposite-side grant cannot disclose occupancy.
    visitor.player.racewar = 2;
    visitor.player.name = guest;
    visitor_account = "dIFFERENTACCOUNT";
    flat_verdict(account_locker.locker_name, true); // Named account owner.
    flat_verdict(legacy_locker.locker_name, false); // Grants stay with the account locker.
    pc.pid = 1;
    flat_verdict(legacy_locker.locker_name, true); // Stable legacy ownership.
    pc.pid = 99;
    sql_rows missing;
    flat_locker_chest contents;
    assert(flat_locker_read(&visitor, "missing.locker", &missing, &contents) && missing.empty());
    const int before_failure = enters;
    std::ofstream(fs::path(state_root) / "identities/names/catalog.identity", std::ios::trunc) << "corrupt";
    feedback.clear();
    locker_enter_character(&visitor, "Ownerchar", {});
    assert(enters == before_failure && feedback.find("could not be opened") != std::string::npos);
    std::ofstream(fs::path(state_root) / "domains/locker_catalog", std::ios::trunc) << "corrupt";
    assert(!flat_locker_read(&visitor, account_locker.locker_name, &missing, &contents));
    puts("PASS holding/private-room occupancy, pending saves/entries, delayed name resolution, legacy fallback, move-away/admission failure, owner/visitor grants and racewar");
    puts("PASS persisted flat-file name resolution, blocked/deleted fallback, grants, ownership, racewar and corrupt-catalog failure");
}
'''

build = ROOT / 'bin/tests'
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='locker-named-entry-', dir=build) as directory:
    cpp, binary = Path(directory) / 'harness.cpp', Path(directory) / 'harness'
    cpp.write_text(prelude + entry + '\n' + production + driver)
    subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-pie', '-no-pie',
                    '-I' + str(ROOT / 'src'), '-I/usr/include/mysql', str(cpp),
                    *(str(source(name)) for name in (
                        'flatfile_identity_repository.c', 'flatfile_locker_repository.c',
                        'flatfile_authority_transaction.c', 'flatfile_store.c',
                        'player_snapshot_codec.c', 'item_transfer_command.c', 'critical_command.c')),
                    '-lcrypto', '-pthread', '-o', str(binary)],
                   check=True, timeout=120)
    subprocess.run([str(binary), str(Path(directory) / 'state')], check=True, timeout=30)
