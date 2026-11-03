#!/usr/bin/env python3
"""Execute the production Keep continuation with controlled writer/session outcomes."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def function(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


nanny = (ROOT / "src/account/nanny.c").read_text()
start = nanny.index("namespace\n{\nenum class kept_save_kind")
controller = nanny[start:nanny.index("void nanny(P_desc", start)]
account = (ROOT / "src/account/account.c").read_text()
requests = "\n".join(function(account, signature) for signature in (
    "uint64_t wait_for_writer(P_desc", "P_desc writer_replied(uint64_t"))

PRELUDE = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/files.h"
#include "net/ws_handlers.h"
#include "player/player_save_pipeline.h"
#include "item/item_movement_transaction.h"
#include "combat/chaos_config.h"
#include <cassert>
#include <cstdlib>
#include <map>
#include <mutex>
#include <new>
#include <string>

P_desc descriptor_list = nullptr;
int approve_mode = 0;
bool accepted = false, busy = false, publish_ok = true;
int published = 0, released = 0, approved = 0, denied = 0, websocket_entries = 0;
int ended = 0, deletions = 0;
std::string output;
std::map<int, std::string> reservations;
acct_chars account_kept_character_projection(P_char ch) { acct_chars value{}; value.pid = GET_PID(ch); return value; }
/* PRODUCTION_ACCOUNT_PUBLICATION */
player_save_pipeline_result admission = player_save_pipeline_result::queued;
std::function<void(character_delete_result)> deletion_reply;

[[noreturn]] int panic_corruption_int(const char *, const char *, ...) { abort(); }
void write_to_q(const char *text, txt_q *, const int) { output += text; }
void statuslog(int, const char *, ...) {}
void *__malloc(size_t size, const char *, const char *, int) { return std::malloc(size); }
char *str_dup(const char *text) { return strdup(text); }
bool chaos_mud_enabled() { return false; }
bool pfile_exists(const char *, char *) { return accepted; }
void mark_chaos_starter_reward_intents(P_char) { assert(false); }
bool kept_character_recovery_pending(int) { return false; }
bool kept_character_recovery_owner_pending(const char *) { return false; }
void newby_announce(P_desc) {}
void display_account_menu(P_desc, char *) {}
void ws_send_system(P_desc, const char *, const char *) {}
void ws_send_auth_success(P_desc, const char *) {}
void ws_finish_kept_character(P_desc, bool) { ++websocket_entries; }
void approve_name(const char *) { ++approved; }
void deny_name(const char *) { ++denied; }
bool publish_initial_character_baseline(P_char) { ++published; return publish_ok; }
void release_preentry_character(P_desc d) { ++released; d->character = nullptr; }
void sql_player_names_forget(int pid) { reservations.erase(pid); }
void sql_player_names_release(int pid, const char *) { reservations.erase(pid); }
bool player_save_worker_pid_pending(int) { return busy; }
bool player_save_pipeline_load_held(int) { return busy; }
bool item_movement_transaction_player_busy(P_char) { return busy; }
void player_save_pipeline_end_session(int) { ++ended; }
player_save_pipeline_result player_save_pipeline_request(P_char, player_component_mask_t, int, int) {
    return admission;
}
bool player_revision_snapshot_copy(int, player_revision_snapshot *out) {
    *out = {}; out->acknowledged_revision = 7; return true;
}
void delete_character(P_char, bool, std::function<void(character_delete_result)> done) {
    ++deletions; deletion_reply = std::move(done);
}

struct session {
    char_data ch{};
    pc_only_data pc{};
    acct_entry account{};
    descriptor_data d{};
    char name[24] = "Kept";
    char owner[24] = "Owner";
    explicit session(int pid) {
        snprintf(name, sizeof(name), "Kept%d", pid);
        ch.only.pc = &pc; pc.pid = pid; ch.player.name = name;
        ch.runtime_id = static_cast<uint64_t>(pid); ch.desc = &d;
        account.acct_name = owner; d.account = &account; d.character = &ch;
        d.connected = CON_RMOTD; d.next = descriptor_list; descriptor_list = &d;
        reservations[pid] = name;
    }
    void detach() {
        auto cursor = &descriptor_list;
        while (*cursor && *cursor != &d) cursor = &(*cursor)->next;
        if (*cursor) *cursor = d.next;
    }
    ~session() { detach(); }
};
'''

MAIN = r'''
void complete(int pid, player_save_apply_outcome outcome, bool absent = false) {
    player_save_completion result{};
    result.kind = persistence_job_kind::player; result.pid = pid; result.revision = 7;
    result.outcome = outcome; result.creation_not_committed = absent;
    account_creation_saved(result); account_creation_pulse();
}
int main() {
    session other(99);
    {
        session s(1);
        assert(keep_new_character(&s.d) && account_creation_pending(1));
        assert(STATE(&s.d) == CON_CREATION_SAVE && s.d.writer_wait_id && published == 0);
        busy = true;
        complete(1, player_save_apply_outcome::applied);
        assert(published == 0 && account_creation_pending(1));
        busy = false; account_creation_pulse();
        assert(!account_creation_pending(1) && published == 1 && STATE(&s.d) == CON_RMOTD);
        assert(s.account.num_chars == 1);
        assert(account_publish_kept_character(&s.account, account_kept_character_projection(&s.ch), s.name));
        assert(s.account.num_chars == 1); // retries do not consume another slot

        assert(output.find("PRESS RETURN") != std::string::npos);
    }
    {
        session s(2); admission = player_save_pipeline_result::unavailable;
        assert(!keep_new_character(&s.d) && !account_creation_pending(2));
        assert(!s.d.character && !reservations.count(2) && reservations.count(99));
        admission = player_save_pipeline_result::queued;
    }
    {
        session s(3); assert(keep_new_character(&s.d));
        busy = true; complete(3, player_save_apply_outcome::terminal_failure, true);
        assert(reservations.count(3) && s.d.character);
        busy = false; account_creation_pulse();
        assert(!account_creation_pending(3) && !reservations.count(3) && !s.d.character);
    }
    {
        session s(4); assert(keep_new_character(&s.d));
        s.detach(); s.d.character = nullptr;
        const int before = published;
        complete(4, player_save_apply_outcome::applied);
        assert(!account_creation_pending(4) && published == before);
        assert(other.account.acct_character_list->pid == 4 && other.account.num_chars == 2); // a login during the pending save sees the committed membership
    }
    {
        session s(5); assert(keep_new_character(&s.d));
        const auto old_request = s.d.writer_wait_id;
        s.ch.runtime_id += 100; wait_for_writer(&s.d); // reused session/new request
        const int before = published;
        complete(5, player_save_apply_outcome::applied);
        assert(s.d.writer_wait_id != old_request && s.d.writer_wait_id && published == before);
        assert(!account_creation_pending(5));
    }
    for (auto outcome : {player_save_apply_outcome::terminal_failure, player_save_apply_outcome::stale_revision}) {
        session s(6); assert(keep_new_character(&s.d));
        complete(6, outcome);
        assert(account_creation_pending(6) && reservations.count(6) && STATE(&s.d) == CON_FLUSH);
        kept_saves.clear(); // only an explicit recovery decision may release this in production
    }
    {
        session s(7); approve_mode = 1;
        assert(keep_new_character(&s.d)); complete(7, player_save_apply_outcome::applied);
        assert(STATE(&s.d) == CON_ACCEPTWAIT && IS_SET(s.ch.specials.act3, PLR3_APPROVAL_PENDING));
        approve_mode = 0; continue_kept_character(&s.d);
        assert(STATE(&s.d) == CON_ACCEPTWAIT); // configuration cannot bypass the saved decision
        const int before = approved;
        assert(approve_kept_character(&s.d) && approved == before);
        assert(STATE(&s.d) == CON_CREATION_SAVE);
        complete(7, player_save_apply_outcome::terminal_failure);
        assert(STATE(&s.d) == CON_ACCEPTWAIT && IS_SET(s.ch.specials.act3, PLR3_APPROVAL_PENDING));
        assert(approve_kept_character(&s.d));
        complete(7, player_save_apply_outcome::applied);
        assert(approved == before + 1 && STATE(&s.d) == CON_RMOTD);
        assert(!IS_SET(s.ch.specials.act3, PLR3_APPROVAL_PENDING));
    }
    {
        session s(8); STATE(&s.d) = CON_ACCEPTWAIT;
        SET_BIT(s.ch.specials.act3, PLR3_KEPT_CHARACTER | PLR3_APPROVAL_PENDING);
        const int before = denied;
        assert(decline_kept_character(&s.d, "synthetic reason") && denied == before);
        assert(s.d.character && STATE(&s.d) == CON_CREATION_SAVE);
        deletion_reply(character_delete_result::refused);
        assert(s.d.character && STATE(&s.d) == CON_ACCEPTWAIT && denied == before);
        assert(decline_kept_character(&s.d, "synthetic reason"));
        deletion_reply(character_delete_result::deleted);
        assert(!s.d.character && denied == before + 1 && STATE(&s.d) == CON_DISPLAY_ACCT_MENU);
    }
    {
        session s(9); STATE(&s.d) = CON_ACCEPTWAIT;
        SET_BIT(s.ch.specials.act3, PLR3_KEPT_CHARACTER | PLR3_APPROVAL_PENDING);
        assert(decline_kept_character(&s.d, ""));
        s.detach(); s.d.character = nullptr;
        const int before = denied;
        deletion_reply(character_delete_result::deleted);
        assert(denied == before + 1); // staff decision persists after descriptor loss
    }
    assert(reservations.count(99));
}
'''

build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="kept-lifecycle-", dir=build) as temporary:
    source = Path(temporary) / "harness.cpp"
    publication = function(account, "bool account_publish_kept_character(")
    source.write_text("\n".join((PRELUDE.replace("/* PRODUCTION_ACCOUNT_PUBLICATION */", publication), requests, controller, MAIN)))
    for backend in ("mariadb", "flatfile"):
        binary = Path(temporary) / backend
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Isrc",
                        *(["-D__NO_MYSQL__", "-Isrc/no_mysql"] if backend == "flatfile" else []),
                        str(source), "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True)
        print(f"PASS: {backend} production Keep completion, failure, session identity and approval/decline lifecycle")
