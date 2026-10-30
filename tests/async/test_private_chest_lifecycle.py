#!/usr/bin/env python3
"""Execute private chest session boundaries with controlled password completions."""
import os
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function, HARNESS_STUBS

bodies = extract_function("cmd/interp.c", "char *one_argument(") + "\n" + "\n".join(extract_function("item/storage_lockers.c", signature) for signature in (
    "inline StorageLocker *GetChestList(",
    "static StorageLocker *locker_current(",
    "static bool locker_private_chests_available(",
    "StorageLocker::StorageLocker(",
    "LockerChest *StorageLocker::AddLockerChest(",
    "LockerChest *StorageLocker::FindChestForObject(",
    "static StorageLocker *locker_for_room_object(",
    "bool locker_object_is_private_chest(",
    "bool locker_container_access_allowed(",
    "void locker_invalidate_chest_access(",
    "PrivateChest *StorageLocker::FindPrivateChest(",
    "std::vector<PrivateChest *> StorageLocker::GetPrivateChests(",
    "void StorageLocker::RemovePrivateChest(",
    "PrivateChest::PrivateChest(",
    "static int locker_chest_id(",
    "static int locker_opencmd(P_char ch, char *arg)\n{",
    "static int locker_closecmd(P_char ch, char *arg)\n{",
    "static int locker_logcmd(P_char ch, char * /*arg*/)\n{",
)) + "\n" + extract_function("item/item_command_policy.c", "bool item_command_object_is_takeable(")

harness = r"""
#include "core/prototypes.h"
#include "core/utils.h"
#include "account/password_async.h"
#include "item/storage_lockers.h"
#include "item/item_command_policy.h"
#include "sql/sql.h"
#include "sql/sql_player.h"
#include "sql/sql_async.h"
#include "persistence/persistence_mode.h"
#include <cassert>
#include <cstdarg>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <string>
#include <vector>

static room_data rooms[2];
P_room world = rooms;
extern const int top_of_world = 1;
static bool manager;
static bool flat_backend;
MYSQL *DB = reinterpret_cast<MYSQL *>(1);
persistence_mode persistence_mode_get() {
    return flat_backend ? PERSISTENCE_MODE_FLATFILE_PRIMARY : PERSISTENCE_MODE_MARIADB_PRIMARY;
}
static uint64_t next_uid = 1;
static password_completion completion;
static std::function<void(P_char, const sql_rows &)> log_completion;
static std::string feedback;
static std::vector<int> events;
const unsigned LockerChest::m_chestVnum = 173;

char *str_dup(const char *value) { return strdup(value); }
int fill_word(char *) { return 0; }
void *__malloc(size_t n, const char *, const char *, int) { return calloc(1, n); }
void send_to_char(const char *s, P_char) { feedback += s; }
void send_to_char_f(P_char, const char *s, ...) {
    char buffer[2048]; va_list args; va_start(args, s);
    vsnprintf(buffer, sizeof(buffer), s, args); va_end(args); feedback += buffer;
}
bool esc_locker_name_matches_player(const char *, P_char) { return manager; }
bool locker_require_owner(StorageLocker *, P_char, const char *) { return manager; }
P_obj read_object(int vnum, int mode) {
    assert(vnum == 173 && mode == VIRTUAL);
    P_obj result = new obj_data{};
    result->obj_uid = next_uid++;
    result->loc_p = LOC_NOWHERE;
    return result;
}
void obj_to_room(P_obj obj, int room) {
    obj->loc_p = LOC_ROOM; obj->loc.room = room;
    obj->next_content = world[room].contents; world[room].contents = obj;
}
void extract_obj(P_obj obj, int) {
    if (OBJ_ROOM(obj)) {
        P_obj *entry = &world[obj->loc.room].contents;
        while (*entry != obj) entry = &(*entry)->next_content;
        *entry = obj->next_content;
    }
    if (obj->str_mask & STRUNG_KEYS) free(obj->name);
    if (obj->str_mask & STRUNG_DESC1) free(obj->description);
    delete obj;
}
LockerChest::~LockerChest() { if (m_pChestObject) extract_obj(m_pChestObject, TRUE); }
void LockerChest::FillExtraDescBuf(char *) {}
StorageLocker::~StorageLocker() {
    while (m_pChestList) {
        LockerChest *chest = m_pChestList;
        // RemovePrivateChest owns list unlinking, not this fixture destructor.
        RemovePrivateChest(static_cast<PrivateChest *>(chest));
    }
    auto *extra = world[m_realRoom].ex_description;
    free(extra->keyword); free(extra->next->keyword); free(extra->next); free(extra);
    world[m_realRoom].ex_description = nullptr;
}
std::string escape_str(const char *s) { return s; }
int is_bcrypt_hash(const char *) { return 1; }
password_login_job *password_work_submit(const char *, const char *, const char *, int, int) {
    return reinterpret_cast<password_login_job *>(1);
}
bool password_async_start(P_desc, password_login_job *, const char *, password_completion done) {
    assert(!completion); completion = std::move(done); return true;
}
bool sql_log_chest_activity(int locker, int chest, const char *, int action, const char *) {
    assert(locker == 7 && chest > 0); events.push_back(action); return true;
}
bool sql_queue_at(persistence_query_site, const char *, ...) { return true; }
std::string sql_format(const char *, ...) { return "fixture query"; }
bool sql_read_for_at(persistence_query_site, P_char, std::string,
                     std::function<void(P_char, const sql_rows &)> done) {
    assert(!log_completion); log_completion = std::move(done); return true;
}

// PRODUCTION

static void run(const std::string &mode) {
    char_data actor = {}, locker_char = {};
    descriptor_data descriptor = {};
    actor.runtime_id = 1;
    actor.player.name = const_cast<char *>("Visitor");
    actor.desc = &descriptor; descriptor.character = &actor;
    actor.in_room = 0;
    world[0].room_flags = ROOM_LOCKER;
    locker_char.runtime_id = 77;
    locker_char.player.name = const_cast<char *>("account.owner.1.locker");
    StorageLocker locker(0, &locker_char, &actor);
    locker.SetLockerId(7); locker.SetPublicChestId(8);
    auto *chest = new PrivateChest(10, "vault", "$2b$fixture");
    locker.AddPrivateChest(chest); obj_to_room(chest->GetChestObj(), 0);
    obj_data inner = {};
    inner.loc_p = LOC_INSIDE; inner.loc.inside = chest->GetChestObj();
    assert(!locker_container_access_allowed(&actor, chest->GetChestObj()));
    assert(!locker_container_access_allowed(&actor, &inner));
    obj_data ordinary = {};
    ordinary.loc_p = LOC_ROOM; ordinary.loc.room = 0;
    assert(locker_container_access_allowed(&actor, &ordinary));
    assert(locker_container_access_allowed(&actor, nullptr));
    if (mode == "not-locker") {
        // A regular room's descriptions are not a StorageLocker attachment,
        // even when fixture text happens to carry an otherwise valid address.
        world[1].ex_description = world[0].ex_description;
        actor.in_room = 1;
        assert(locker_current(&actor) == nullptr);
        world[1].ex_description = nullptr;
        return;
    }
    if (mode == "furniture") {
        actor.player.level = 62;
        assert(!item_command_object_is_takeable(&actor, chest->GetChestObj()));
        assert(item_command_object_is_takeable(&actor, &ordinary));
        return;
    }
    if (mode.starts_with("log")) {
        manager = true;
        flat_backend = mode == "log-flatfile";
        char no_arg[] = "";
        assert(locker_logcmd(&actor, no_arg));
        if (flat_backend) {
            assert(!log_completion);
            assert(feedback.find("require SQL storage") != std::string::npos);
            return;
        }
        assert(log_completion);
        if (mode == "log-role-revoked") manager = false;
        else if (mode == "log-visit-replaced") ++locker_char.runtime_id;
        else if (mode == "log-other-user") ++actor.runtime_id;
        else if (mode == "log-departed") actor.in_room = 1;
        else assert(mode == "log");
        sql_row row;
        row.fields = {"now", "Visitor", "3", "vault", "hidden-item"};
        log_completion(&actor, sql_rows{row});
        assert((feedback.find("hidden-item") != std::string::npos) == (mode == "log"));
        return;
    }
    if (mode == "manager" || mode == "role-revoked") manager = true;
    if (mode == "flatfile" || mode == "sql-unavailable") {
        flat_backend = mode == "flatfile";
        if (!flat_backend) DB = nullptr;
        char unavailable[] = "vault correct";
        assert(locker_opencmd(&actor, unavailable));
        assert(!completion && events.empty());
        assert(locker.GetCurrentChestId() == 0);
        assert(feedback.find(flat_backend ? "require SQL storage" : "temporarily unavailable") != std::string::npos);
        return;
    }
    char request[] = "vault correct";
    assert(locker_opencmd(&actor, request));
    if (manager) {
        assert(!completion);
        assert(locker_container_access_allowed(&actor, chest->GetChestObj()));
        manager = mode != "role-revoked";
        assert(locker_container_access_allowed(&actor, chest->GetChestObj()) == manager);
        return;
    }
    assert(completion);
    if (mode == "close-pending") {
        char no_arg[] = "";
        locker_closecmd(&actor, no_arg);
    } else if (mode == "recreated") {
        locker.RemovePrivateChest(chest);
        auto *replacement = new PrivateChest(10, "vault", "$2b$fixture");
        locker.AddPrivateChest(replacement); obj_to_room(replacement->GetChestObj(), 0);
    } else if (mode == "changed-hash") {
        chest->SetPasswordHash("$2b$new-fixture");
    } else if (mode == "stale-user") {
        ++actor.runtime_id;
    } else assert(mode == "open" || mode == "wrong" || mode == "close" ||
                  mode == "close-door" || mode == "disconnect" || mode == "select-other");
    auto done = std::move(completion); completion = {};
    done(&descriptor, mode == "wrong" ? 0 : 1, nullptr);
    if (mode == "open" || mode == "close" || mode == "close-door" ||
        mode == "disconnect" || mode == "select-other") {
        assert(locker.GetCurrentChestId() == 10);
        assert(events == std::vector<int>{CHEST_ACTION_OPEN});
        assert(locker_container_access_allowed(&actor, chest->GetChestObj()));
        assert(locker_container_access_allowed(&actor, &inner));
        char_data stranger = {}; stranger.runtime_id = 2; stranger.in_room = 0;
        stranger.desc = &descriptor;
        assert(!locker_container_access_allowed(&stranger, chest->GetChestObj()));
        locker_invalidate_chest_access(&stranger);
        assert(locker_container_access_allowed(&actor, chest->GetChestObj()));
        ++actor.runtime_id;
        assert(!locker_container_access_allowed(&actor, chest->GetChestObj()));
        --actor.runtime_id;
        if (mode == "close") {
            char no_arg[] = "";
            assert(locker_closecmd(&actor, no_arg));
            assert(!locker_container_access_allowed(&actor, &inner));
        } else if (mode == "close-door") {
            char door[] = "door";
            assert(!locker_closecmd(&actor, door));
            assert(locker_container_access_allowed(&actor, &inner));
        } else if (mode == "disconnect") {
            locker_invalidate_chest_access(&actor);
            assert(!locker_container_access_allowed(&actor, &inner));
        } else if (mode == "select-other") {
            auto *other = new PrivateChest(11, "other", nullptr);
            locker.AddPrivateChest(other); obj_to_room(other->GetChestObj(), 0);
            char another[] = "other";
            assert(locker_opencmd(&actor, another));
            assert(!completion);
            assert(!locker_container_access_allowed(&actor, &inner));
            assert(locker_container_access_allowed(&actor, other->GetChestObj()));
            char public_name[] = "public";
            assert(locker_opencmd(&actor, public_name));
            assert(locker.GetCurrentChestId() == 0);
            assert(!locker_container_access_allowed(&actor, other->GetChestObj()));
        }
    } else {
        assert(locker.GetCurrentChestId() == 0);
        assert(std::find(events.begin(), events.end(), CHEST_ACTION_OPEN) == events.end());
    }
}
int main(int argc, char **argv) {
    assert(argc == 2); run(argv[1]);
}
""".replace("// PRODUCTION", bodies)

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="private-chest-lifecycle-", dir=build) as temporary:
    directory = Path(temporary)
    source = directory / "test.cpp"
    binary = directory / "test"
    source.write_text(harness)
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-g",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
        "-I", str(ROOT / "src"), "-I/usr/include/mysql", str(source),
        str(HARNESS_STUBS), "-lbsd", "-o", str(binary),
    ], check=True)
    failures = []
    for case in ("open", "wrong", "changed-hash", "close-pending", "recreated",
                 "stale-user", "close", "close-door", "disconnect", "select-other",
                 "manager", "role-revoked", "flatfile", "sql-unavailable",
                 "log", "log-role-revoked", "log-visit-replaced", "log-other-user",
                 "log-departed", "log-flatfile", "furniture", "not-locker"):
        result = subprocess.run([str(binary), case],
                                env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1"})
        if result.returncode:
            failures.append(case)
        else:
            print(f"private chest lifecycle {case} PASS")
    assert not failures, f"private chest lifecycle failures: {failures}"
