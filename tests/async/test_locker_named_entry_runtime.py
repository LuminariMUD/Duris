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
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <set>
#include <string>

using locker_entered = std::function<void(P_char, P_char, int)>;
static std::string feedback, target, query;
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
production = constants + '\n' + '\n'.join(extract_function('storage_lockers.c', signature) for signature in (
    'static std::string locker_entry_key(',
    'static StorageLocker *active_locker_for(',
    'static int lockerName_is_inuse(char *lockerName)\n{',
    'static void locker_enter_character(P_char ch, const char *name, locker_entered entered)\n{',
    'static unsigned int locker_granted(',
    'static sql_row locker_outcome(',
    'static unsigned int locker_entry_read(',
))
driver = r'''
int main()
{
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

    locker_entry entry{"account.owner.1.locker", "visitor", 42, 1, true, false,
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
    entry.account_owner = true;
    verdict(true);
    entry.visitor_racewar = 2;
    verdict(false);
    entry.visitor_racewar = 1;
    present = false;
    verdict(false); // Explicit names do not create missing lockers, even for their owner.
    fail_read = 2013;
    sql_rows rows;
    assert(locker_entry_read(nullptr, entry, &rows) == 2013 && rows.empty());
    puts("PASS holding/private-room occupancy, pending saves/entries, delayed name resolution, legacy fallback, move-away/admission failure, owner/visitor grants and racewar");
}
'''

build = ROOT / 'bin/tests'
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='locker-named-entry-', dir=build) as directory:
    cpp, binary = Path(directory) / 'harness.cpp', Path(directory) / 'harness'
    cpp.write_text(prelude + entry + '\n' + production + driver)
    subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-pie', '-no-pie',
                    '-I' + str(ROOT / 'src'), '-I/usr/include/mysql', str(cpp), '-o', str(binary)],
                   check=True, timeout=120)
    subprocess.run([str(binary)], check=True, timeout=30)
