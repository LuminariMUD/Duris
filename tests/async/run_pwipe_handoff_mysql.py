#!/usr/bin/env python3
"""Run the real launcher/filesystem handoff on a private DB and synthetic tree.

This qualifies the cross-process handoff, not the real game command or writer drain.
"""
import argparse
import fcntl
import os
import re
from pathlib import Path
import shutil
import socket
import select
import signal
import time
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import migration_runner


def run(server=None):
    if not os.environ.get("TEST_DB_HOST"):
        wrapper = ROOT / "tests/async/with_disposable_mariadb.sh"
        os.execv(str(wrapper), [str(wrapper), sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]])
    env = dict(PATH=os.environ.get("PATH", "/usr/bin:/bin"), ENVIRONMENT="local",
               PERSISTENCE_MODE="mariadb-primary", DB_HOST=os.environ["TEST_DB_HOST"],
               DB_PORT=os.environ["TEST_DB_PORT"], DB_USER=os.environ["TEST_DB_USER"],
               DB_PASSWD=os.environ["TEST_DB_PASSWORD"], DB_NAME="duris_test")
    env["DB_ALLOWED_TARGETS"] = env["DB_HOST"] + "/duris_test"
    env["MYSQL_PWD"] = env["DB_PASSWD"]
    mysql = [shutil.which("mysql"), "--protocol=tcp", "-h", env["DB_HOST"], "-P", env["DB_PORT"],
             "-u", env["DB_USER"], "-N", "-B"]

    def sql(statement, database=True):
        return subprocess.check_output(mysql + (["duris_test"] if database else []) +
                                       ["-e", statement], env=env, text=True).strip()

    sql("CREATE DATABASE duris_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci", False)
    manifest = migration_runner.load_manifest()
    subprocess.run(mysql + ["duris_test"], input=(ROOT / "migrations/bootstrap_multithread_safe.sql").read_bytes(),
                   env=env, check=True, stdout=subprocess.DEVNULL)
    for arguments in (("adopt", "--kind", "fresh_bootstrap"), ("run",)):
        subprocess.run([sys.executable, str(ROOT / "scripts/migration_runner.py"), *arguments],
                       env=env, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    import json
    lifecycle = json.loads((ROOT / "migrations/data_lifecycle_manifest.json").read_text())
    expected = {entry["locator"] for entry in lifecycle["entries"] if entry["kind"] == "database_table"}
    actual = set(sql("SHOW TABLES").splitlines())
    assert actual == expected, (actual - expected, expected - actual)
    assert sql("SELECT roster_recreated IS NULL FROM season_reset_state") == "1"
    sql("UPDATE season_reset_state SET roster_recreated=1")
    checkpoint = next(step for step in manifest.migrations if step.migration_id == "0052_pwipe_roster_checkpoint")
    for _ in range(2):
        subprocess.run(mysql + ["duris_test"], input=checkpoint.apply_path.read_bytes(), env=env,
                       check=True, stdout=subprocess.DEVNULL)
    assert sql("SELECT roster_recreated FROM season_reset_state") == "1"
    sql("UPDATE season_reset_state SET roster_recreated=NULL")
    print("Roster checkpoint migration preserves legacy NULL and committed values on repeat", flush=True)
    print(f"Fully migrated SQL inventory matches all {len(actual)} lifecycle tables ({sql('SELECT VERSION()')})", flush=True)

    # Compile the actual season-state functions with a tiny real-MariaDB caller.
    # The surrounding server remains covered by the later full command journey.
    source = (ROOT / "src/sql/sql.c").read_text()
    functions = source[source.index("static bool sql_connection_execute("):
                       source.index("bool sql_pwipe_crossed_boundary(void)",
                                    source.index("static bool sql_load_active_season_state"))]
    metadata = source[source.index("static bool sql_verify_metadata_fingerprint(void)\n{"):
                      source.index("/* Store core player data", source.index("static bool sql_verify_metadata_fingerprint(void)\n{"))]
    native = ROOT / "bin/tests/pwipe_epoch_mysql.cpp"
    native.parent.mkdir(parents=True, exist_ok=True)
    signals = (ROOT / "src/core/signals.c").read_text()
    child_status = signals[signals.index("void reap(int sig)\n{"):signals.index("void reaper(")]
    rewards_source = (ROOT / "src/account/account_reward.c").read_text()
    rewards = rewards_source[rewards_source.index("bool account_bound_rewards_on_successful_pwipe(void)"):
                             rewards_source.index("\n#ifndef __NO_MYSQL__\nstatic void dissolve_reward_containers")]
    native.write_text('''#include <mysql/mysql.h>
#include "economy/divine_boon_repository.h"
#include "guild/artifact_identity.h"
#include "guild/artifact_guild_repository.h"
#include "economy/divine_trade_repository.h"
#include "ships/ships.h"
#include "core/files.h"
#include "guild/artifact_population_repository.h"
#include "redis/redis_maintenance.h"
#include "redis/redis_connection.h"
#include "redis/redis_namespace.h"
#include "core/runtime_compatibility_contract.h"
#include <openssl/sha.h>
#include "economy/collector_repository.h"
#include "economy/collector_purchase_preparation.h"
#include "persistence/critical_command_repository.h"
#include "player/player_snapshot_codec.h"
#include "player/player_load_repository.h"
#include "item/item_uid_allocator.h"
#include "persistence/persistence_mode.h"
#include "persistence/persistence_observability.h"
#include <sys/time.h>
#include <memory>
#include <fstream>
#include <iterator>
#include <new>
#include <algorithm>
#include <ctime>
#include <spawn.h>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>
#include <cerrno>
#include <climits>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#define REAPED_CHILD_STATUS_CAPACITY 64
static volatile sig_atomic_t reaped_child_pids[64];
static volatile sig_atomic_t reaped_child_statuses[64];
static volatile sig_atomic_t reaped_child_cursor;
''' + child_status + '''
extern "C" int __real_posix_spawn(pid_t *, const char *, const posix_spawn_file_actions_t *,
                                  const posix_spawnattr_t *, char *const[], char *const[]);
extern "C" int __wrap_posix_spawn(pid_t *pid, const char *path, const posix_spawn_file_actions_t *files,
                                  const posix_spawnattr_t *attributes, char *const argv[], char *const env[]) {
    int result = __real_posix_spawn(pid, path, files, attributes, argv, env);
    // Force the real game reaper to consume the exit before preflight calls waitpid.
    for (int tries = 0; !result && reaped_child_cursor == 0 && tries < 200; ++tries) usleep(10000);
    return result;
}
bool boundary_epoch_updated = false, boundary_commit_fault = false;
extern "C" int __real_mysql_real_query(MYSQL *, const char *, unsigned long);
extern "C" int __wrap_mysql_real_query(MYSQL *connection, const char *statement, unsigned long length) {
    const char *mode = getenv("PWIPE_TEST_BOUNDARY_ACK");
    const bool before = mode && !strcmp(mode,"before"), after = mode && !strcmp(mode,"after");
    const std::string_view query(statement,length);
    if (before && boundary_epoch_updated && query == "COMMIT") {
        boundary_epoch_updated = false; boundary_commit_fault = true;
        return 1;
    }
    const int result = __real_mysql_real_query(connection,statement,length);
    if (!result && (before || after)) {
        if (query.starts_with("UPDATE season_reset_state SET season_epoch=")) boundary_epoch_updated = true;
        else if (after && boundary_epoch_updated && query == "COMMIT") {
            boundary_epoch_updated = false; boundary_commit_fault = true;
            return 1;
        }
    }
    return result;
}
MYSQL *DB;
#define TRUE true
#define FALSE false
#define OVERLORD 62
#define ACCT_IMMORTAL 0
bool pwipe_crossed_boundary, pwipe_filesystem_ready;
void logit(const char *, const char *format, ...) {
    va_list args; va_start(args, format); vfprintf(stderr, format, args); va_end(args); fputc(10, stderr);
}
void send_to_all(const char *) {}
int frag_cap_config_reset_level() { return 26; }
bool pwipe_quiesce_writers() { return true; }
unsigned int writer_resumes = 0;
void pwipe_resume_writers() { ++writer_resumes; }
redis_maintenance_config fixture_redis{};
bool redis_cache_store_delete(const char *) { return true; }
bool redis_validate_pwipe_state() { return !fixture_redis.connection || redis_maintenance_validate(&fixture_redis); }
bool redis_clear_pwipe_state() { return !fixture_redis.connection || redis_maintenance_clear(&fixture_redis); }
bool redis_recover_pwipe_state(uint64_t, bool apply) {
    return apply ? redis_clear_pwipe_state() : redis_validate_pwipe_state();
}
uint64_t current_season_epoch;
MYSQL_RES *db_query(const char *format, ...) {
    char statement[16384]; va_list args; va_start(args, format);
    vsnprintf(statement, sizeof statement, format, args); va_end(args);
    return mysql_real_query(DB, statement, strlen(statement)) ? nullptr : mysql_store_result(DB);
}
bool qry(const char *format, ...) {
    char statement[16384]; va_list args; va_start(args, format);
    vsnprintf(statement, sizeof statement, format, args); va_end(args);
    const char *fail = getenv("PWIPE_TEST_FAIL_SQL");
    if (fail && strstr(statement, fail)) return false;
    if (mysql_real_query(DB, statement, strlen(statement))) return false;
    MYSQL_RES *result = mysql_store_result(DB); if (result) mysql_free_result(result);
    return true;
}
''' + metadata + functions + '''
unsigned long next_obj_uid = 1;
uint64_t sql_season_epoch() { return current_season_epoch; }
bool sql_begin_transaction() { return qry("START TRANSACTION"); }
bool sql_rollback() { return qry("ROLLBACK"); }
bool sql_commit() { return qry("COMMIT") && !getenv("PWIPE_TEST_LOST_REWARD_ACK"); }
bool account_reward_config_preserve_on_pwipe() { return !getenv("PWIPE_TEST_DELETE_REWARDS"); }
''' + rewards + source[source.index("// One preparation path serves the read-only preflight"):
                            source.index("void sql_log_player_login", source.rindex("bool sql_pwipe(int code_verify)"))] + '''
bool retained_items(bool after) {
    player_load_request request;
    request.request_id = 1; request.pid = 1002; request.account_name = "fixturebank";
    request.deadline_usec = persistence_observability_now_usec() + PLAYER_LOAD_TIMEOUT_USEC;
    const auto old = player_load_repository_execute(DB, request);
    if (old.outcome != player_load_outcome::applied || old.item_owner_revision != 1) return false;
    if (!after) {
        for (const auto &item : old.item_identities) if (item.item_uid == 991001) return true;
        return false;
    }
    // A retained custody row has no object payload to materialize after reset.
    if (!old.snapshot.items.empty() || !old.snapshot.pets.empty() || old.missing_payload_rows < 1) return false;
    MYSQL_RES *rows = db_query("SELECT pid FROM player_data WHERE name='Freshgod' AND active=1");
    MYSQL_ROW row = rows ? mysql_fetch_row(rows) : nullptr;
    const int fresh_pid = row && row[0] ? atoi(row[0]) : 0;
    if (rows) mysql_free_result(rows);
    if (fresh_pid <= 1004) return false;
    request.request_id = 2; request.pid = fresh_pid;
    request.deadline_usec = persistence_observability_now_usec() + PLAYER_LOAD_TIMEOUT_USEC;
    const auto fresh = player_load_repository_execute(DB, request);
    if (fresh.outcome != player_load_outcome::applied || !fresh.snapshot.items.empty() ||
        !fresh.snapshot.pets.empty() || fresh.item_owner_revision != 0) return false;
    if (!item_uid_allocator_reserve(DB, 4)) return false;
    const uint64_t first = item_uid_allocator_next();
    if (first <= 991001) return false;
    for (uint64_t offset = 1; offset < 4; ++offset) if (item_uid_allocator_next() != first + offset) return false;
    if (item_uid_allocator_next() != 0) return false;
    printf("%llu", static_cast<unsigned long long>(first));
    return true;
}
bool seed_boons() {
    divine_boon_state state;
    const int64_t now = time(nullptr) / DIVINE_BOON_HOUR * DIVINE_BOON_HOUR;
    state.mode = divine_boon_mode::divine; state.paused = true;
    state.next_id = 3; state.last_opportunity = now;
    state.slots[0].id = 1; state.slots[0].category = divine_boon_category::experience;
    state.slots[0].starts_at = now - DIVINE_BOON_HOUR;
    state.slots[0].expires_at = state.slots[0].starts_at + divine_boon_duration(state.slots[0].category);
    state.slots[0].zones = {900, 901};
    state.slots[1].id = 2; state.slots[1].category = divine_boon_category::cargo;
    state.slots[1].starts_at = now;
    state.slots[1].expires_at = now + divine_boon_duration(state.slots[1].category);
    state.slots[1].source_port = 0; state.slots[1].destination_port = 1;
    state.slots[1].cargo_commodity = 0; state.slots[1].contraband_commodity = 0;
    state.history.push_back({599, 0, now - DIVINE_BOON_HOUR});
    return qry("DELETE FROM divine_boon_state") &&
           divine_boon_sql_save(DB, 0, state) == divine_boon_store_result::ok;
}
bool check_boons() {
    divine_boon_state state;
    if (divine_boon_sql_load(DB, &state) != divine_boon_store_result::ok ||
        state.next_id != 3 || !state.paused || state.history.size() || state.recent.size() != 2 ||
        !std::all_of(state.slots.begin(), state.slots.end(), [](const auto &slot) { return !slot.id; })) return false;
    const auto retired = state;
    if (divine_boon_sql_reset_season(DB, time(nullptr)) != divine_boon_store_result::already_applied ||
        divine_boon_sql_load(DB, &state) != divine_boon_store_result::ok || state != retired) return false;
    divine_boon_slot choice; choice.category = divine_boon_category::experience; choice.zones = {900, 901};
    return divine_boon_set_paused(&state, false, state.last_opportunity) &&
           divine_boon_rotate(&state, state.last_opportunity + DIVINE_BOON_HOUR, &choice) &&
           state.slots[0].id == 3;
}
std::string fixture_hex(const uint8_t *bytes, size_t size) {
    static constexpr char digits[] = "0123456789abcdef";
    std::string text; text.reserve(size * 2);
    for (size_t i=0; i<size; ++i) { text += digits[bytes[i]>>4]; text += digits[bytes[i]&15]; }
    return text;
}
bool seed_collectors(uint64_t base, uint32_t owner, uint64_t count) {
    const uint64_t now = static_cast<uint64_t>(time(nullptr));
    collector::rules rules; rules.enabled = true;
    for (uint64_t i=0; i<count; ++i) {
        char operation[33]; snprintf(operation,sizeof operation,"%032llx",static_cast<unsigned long long>(base+i+1));
        const std::string death = operation;
        const uint64_t died = now - 30 * 3600 + base + i;
        const uint64_t listing = base+i, uid = 800000+base*10+i;
        if (!qry("INSERT INTO collector_deaths(death_operation_id,beneficiary_pid,death_time) "
                 "VALUES(UNHEX('%s'),%u,%llu)", death.c_str(), owner, static_cast<unsigned long long>(died))) return false;
        collector::record entry;
        if (collector::enroll(listing, death, owner, uid, 1, died, rules, &entry) != collector::outcome::applied) return false;
        std::vector<uint8_t> item_blob;
        uint64_t due = entry.collect_at;
        if (i) {
            if (collector::collect(&entry, entry.revision, 1, 1, true, 250, now) != collector::outcome::applied) return false;
            due = entry.sale_at;
            if (i>=2) {
                if (collector::activate(&entry, entry.revision, now) != collector::outcome::applied) return false;
                due = entry.expires_at;
                if (i==3) {
                    if (collector::pause(&entry, entry.revision, now) != collector::outcome::applied) return false;
                    due = 0;
                }
            }
            player_item_snapshot item{}; item.object_uid=uid; item.vnum=900; item.cost=250;
            item.parent_index=PLAYER_SNAPSHOT_NO_PARENT; item.type=15; item.weight=1;
            if (player_item_snapshot_list_encode({item}, &item_blob) != player_snapshot_codec_result::ok) return false;
            if (!qry("INSERT INTO item_owner_revision(owner_type,owner_id,owner_context_id,revision) VALUES(10,%llu,0,1)",
                     static_cast<unsigned long long>(listing)) ||
                !qry("INSERT INTO item_current_owner(item_uid,root_item_uid,parent_item_uid,owner_type,owner_id,owner_context_id,"
                     "item_revision,vnum,state) VALUES(%llu,%llu,NULL,10,%llu,0,%llu,900,1)",
                     static_cast<unsigned long long>(uid), static_cast<unsigned long long>(uid),
                     static_cast<unsigned long long>(listing), static_cast<unsigned long long>(entry.item_revision))) return false;
        }
        if (i==2 && getenv("PWIPE_TEST_COLLECTOR_BUY")) {
            collector_purchase_actor_snapshot actor;
            actor.pid=owner; strcpy(actor.account_name.data(),"fixturebank");
            actor.carried_currency_value=999; actor.carry_item_limit=10; actor.carry_weight_limit=100;
            actor.observed_at=now;
            const item_ownership_runtime_entry held{uid,uid,0,{item_owner_type::collector,listing,0},entry.item_revision,1,900,item_custody_state::active};
            std::unique_ptr<collector_command_payload> payload; player_item_snapshot decoded;
            if (collector_purchase_prepare(entry,{entry,item_blob},held,actor,&payload,&decoded) != collector_purchase_prepare_outcome::prepared) return false;
            critical_operation_id operation; critical_command command;
            if (!critical_operation_id_generate(&operation) || !collector_command_build(&command,operation,*payload,
                    critical_source_site::command,critical_deadline_class::interactive)) return false;
            command.accepted_at_usec=now*1000000;
            std::vector<uint8_t> bytes;
            if (critical_command_encode(command,&bytes) != critical_command_codec_result::ok) return false;
            std::ofstream output(getenv("PWIPE_TEST_COLLECTOR_BUY"),std::ios::binary);
            output.write(reinterpret_cast<const char *>(bytes.data()),static_cast<std::streamsize>(bytes.size()));
            if (!output.good()) return false;
        }
        std::array<uint8_t,collector::encoded_record_bytes> encoded;
        if (collector::record_encode(entry, &encoded) != collector::codec_result::ok) return false;
        const auto record = fixture_hex(encoded.data(),encoded.size());
        const auto blob = item_blob.empty() ? "NULL" : "UNHEX('"+fixture_hex(item_blob.data(),item_blob.size())+"')";
        const auto deadline = due ? std::to_string(due) : "NULL";
        if (!qry("INSERT INTO collector_listings(listing_id,death_operation_id,beneficiary_pid,item_uid,status,holding_paused,"
                 "due_at,listing_revision,item_revision,price_value,record_blob,item_blob) "
                 "VALUES(%llu,UNHEX('%s'),%u,%llu,%u,%u,%s,%llu,%llu,%llu,UNHEX('%s'),%s)",
                 static_cast<unsigned long long>(listing),death.c_str(),owner,static_cast<unsigned long long>(uid),
                 static_cast<unsigned>(entry.status),static_cast<unsigned>(entry.holding_paused),deadline.c_str(),
                 static_cast<unsigned long long>(entry.revision),static_cast<unsigned long long>(entry.item_revision),
                 static_cast<unsigned long long>(entry.price_value),record.c_str(),blob.c_str())) return false;
    }
    return qry("UPDATE collector_catalog_state SET next_listing=%llu WHERE state_id=1", static_cast<unsigned long long>(base+count));
}
bool artifact_history_command(bool prepared, critical_command *command) {
    artifact_guild_payload payload{};
    payload.parent_operation_id.bytes.fill(19); payload.actor_pid=1004;
    payload.artifact_count=1; payload.feeding_cap=2000100000;
    payload.artifacts[0]={900,ARTIFACT_DELTA_FEED,1999999700,2000000000,1004,1004,20,20,880001,300};
    critical_operation_id operation{};
    operation.bytes.fill(20);
    const bool built=prepared ?
        critical_operation_id_derive(payload.parent_operation_id,ARTIFACT_GUILD_DERIVATION_DOMAIN,1004,&operation) &&
            artifact_guild_command_build_prepared(command,operation,payload) :
        artifact_guild_command_build(command,operation,payload);
    command->accepted_at_usec=1;
    return built;
}
bool seed_artifact_history() {
    if (!qry("INSERT INTO critical_operation_inbox(operation_id,command_hash,keys_hash,command_type,schema_version,"
             "payload_version,status,result_payload,committed_at) VALUES(REPEAT(CHAR(19),16),REPEAT(CHAR(1),32),"
             "REPEAT(CHAR(2),32),2,1,1,1,'',NOW(6))")) return false;
    critical_command history, delivery;
    if (!artifact_history_command(false,&history) || !artifact_history_command(true,&delivery)) return false;
    if (critical_command_repository_apply(DB,history).outcome!=critical_apply_outcome::applied) return false;
    return qry("START TRANSACTION") && artifact_guild_repository_prepare_delivery(DB,delivery) && qry("COMMIT");
}
bool check_artifact_history() {
    critical_command history, delivery, loaded;
    bool acknowledged=true, saved=false;
    if (!artifact_history_command(false,&history) || !artifact_history_command(true,&delivery)) return false;
    return critical_command_repository_apply(DB,history).outcome==critical_apply_outcome::already_applied &&
        artifact_guild_repository_load_delivery(DB,delivery.operation_id,&loaded,&acknowledged) && !acknowledged &&
        artifact_guild_repository_delivery_saved(DB,loaded,&saved) && saved;
}
bool seed_trade() {
    if (!qry("INSERT INTO ships(id,owner_name,ship_name,ship_class) VALUES(600,'Oldmortal','Old trade',0)") ||
        !qry("INSERT INTO ship_slots(ship_id,slot_index,slot_type,item_index,position,timer,val0,val1,val2,val3,val4) "
             "VALUES(600,3,%d,0,%d,0,9,900,-1,-1,-1)",SLOT_CARGO,SLOT_HOLD)) return false;
    divine_boon_state state;
    if (divine_boon_sql_load(DB,&state)!=divine_boon_store_result::ok) return false;
    const auto &boon=state.slots[1];
    critical_entity_key account;
    if (!currency_account_key("fixturebank",0,&account)) return false;
    divine_trade_book book;
    for (unsigned i=0; i<2; ++i) {
        critical_operation_id operation{}; operation.bytes.fill(30+i);
        divine_trade_purchase buy;
        buy.operation=operation; buy.account=account.id; buy.ship_id=600; buy.full_hold=100;
        buy.slot=3; buy.source_port=boon.source_port; buy.at=boon.starts_at+1;
        buy.quantity=1; buy.paid=100; buy.slot_quantity_before=9+i; buy.slot_basis_before=900+100*i;
        divine_trade_payload payload;
        payload.pid=payload.ship_owner_pid=1004; payload.ship_id=600;
        if (!divine_trade_sql_generation(DB,&payload.generation,false)) return false;
        payload.wallet_revision=i; payload.book_revision=book.revision;
        payload.admitted_at=buy.at; payload.payment=-100;
        payload.wallet_after.amount={899-static_cast<int64_t>(100*i),0,0,0};
        payload.slots_before.push_back({3,SLOT_CARGO,0,SLOT_HOLD,0,{9+static_cast<int>(i),900+100*static_cast<int>(i),-1,-1,-1}});
        payload.slots_after.push_back({3,SLOT_CARGO,0,SLOT_HOLD,0,{10+static_cast<int>(i),1000+100*static_cast<int>(i),-1,-1,-1}});
        payload.market_after.push_back({0,0,divine_trade_goods::cargo,1.03f,100});
        if (!divine_trade_prepare_purchase(book,boon,buy,&payload.book_after)) return false;
        critical_command command;
        if (!divine_trade_command_build(&command,operation,payload)) return false;
        command.accepted_at_usec=1;
        std::vector<uint8_t> bytes;
        if (critical_command_encode(command,&bytes)!=critical_command_codec_result::ok) return false;
        std::ofstream output(std::string(getenv("PWIPE_TEST_TRADE_PREFIX"))+std::to_string(i),std::ios::binary);
        output.write(reinterpret_cast<const char *>(bytes.data()),static_cast<std::streamsize>(bytes.size()));
        if (!output.good()) return false;
        if (!i && critical_command_repository_apply(DB,command).outcome!=critical_apply_outcome::applied) return false;
        book=payload.book_after;
    }
    return true;
}
bool replay_trade(bool submit) {
    for (unsigned i=0; i<2; ++i) {
        std::ifstream input(std::string(getenv("PWIPE_TEST_TRADE_PREFIX"))+std::to_string(i),std::ios::binary);
        const std::vector<uint8_t> bytes{std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
        critical_command command;
        if (critical_command_decode(bytes.data(),bytes.size(),&command)!=critical_command_codec_result::ok) return false;
        if (!i) {
            if (critical_command_repository_apply(DB,command).outcome!=critical_apply_outcome::already_applied) return false;
        } else if (submit) {
            const auto result=critical_command_repository_apply(DB,command);
            if (result.outcome!=critical_apply_outcome::terminal_failure || result.error_code!=ESTALE) return false;
        } else {
            divine_trade_result result; unsigned error=0; bool mutated=true;
            if (!divine_trade_sql_execute(DB,command,&result,&error,&mutated) || error!=ESTALE || mutated) return false;
        }
    }
    return true;
}
bool payload_readers(bool empty) {
    artifact_population_sql_page siege, auction;
    return !artifact_population_read_sql_page(DB,artifact_payload_domain::siege,0,&siege) && siege.complete &&
        siege.rows.size()==(empty?0:2) &&
        !artifact_population_read_sql_blob_page(DB,artifact_payload_domain::auction,0,&auction) && auction.complete &&
        auction.rows.size()==(empty?0:1);
}
bool seed_payloads() {
    std::vector<uint8_t> bytes;
    const auto append=[&]<typename T>(T value) {
        const auto *begin=reinterpret_cast<const uint8_t *>(&value);
        bytes.insert(bytes.end(),begin,begin+sizeof(value));
    };
    append(uint8_t{SAV_ITEMVERS}); append(uint32_t{1});
    append(static_cast<uint8_t>(O_F_UNIQUE|O_F_UID)); append(int32_t{904});
    append(int16_t{0}); append(int16_t{100}); append(uint64_t{890001});
    append(uint32_t{O_U_EXTRA}); append(uint32_t{1U<<28}); append(uint8_t{O_F_EOL});
    const auto blob=fixture_hex(bytes.data(),bytes.size());
    return qry("INSERT IGNORE INTO item_current_owner(item_uid,root_item_uid,owner_type,owner_id,item_revision,vnum,state) "
               "VALUES(890001,890001,6,700,1,904,1)") &&
        qry("INSERT INTO auctions(id,obj_vnum,quantity,obj_blob_str,custody_state,listing_operation_id) VALUES(700,904,1,UNHEX('%s'),1,REPEAT(CHAR(18),16))",blob.c_str()) &&
        qry("INSERT INTO auction_item_custody(auction_id,slot,item_uid,item_revision,vnum,obj_blob,claim_pid) "
            "VALUES(700,0,890001,1,904,UNHEX('%s'),1004)",blob.c_str()) &&
        qry("INSERT INTO siege_items(id,room_vnum,vnum,obj_uid,extra_flags) VALUES(701,900,904,890002,268435456)") &&
        qry("INSERT INTO siege_items(id,room_vnum,vnum,obj_uid,container_id,extra_flags) VALUES(702,900,904,890003,701,268435456)") &&
        qry("INSERT INTO siege_item_affects(item_id,location,modifier) VALUES(701,1,15)") &&
        qry("INSERT INTO siege_item_extra_descr(item_id,keyword,description) VALUES(702,'fixture','old siege')") &&
        payload_readers(false);
}
bool check_collectors() {
    collector_bootstrap_snapshot loaded;
    return collector_repository_read_bootstrap(DB,&loaded) && loaded.catalog.records.empty() &&
           loaded.held_items.empty() && loaded.deaths.empty() && loaded.catalog.next_listing==104;
}
bool stale_collector_purchase() {
    std::ifstream input(getenv("PWIPE_TEST_COLLECTOR_BUY"),std::ios::binary);
    const std::vector<uint8_t> bytes{std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
    critical_command command;
    if (critical_command_decode(bytes.data(),bytes.size(),&command) != critical_command_codec_result::ok) return false;
    const auto result=critical_command_repository_apply(DB,command);
    return result.outcome==critical_apply_outcome::terminal_failure && result.error_code==ESTALE;
}
bool new_collector_candidate() {
    MYSQL_RES *rows=db_query("SELECT pid FROM player_data WHERE name='Oldmortal' AND active=1");
    MYSQL_ROW row=rows?mysql_fetch_row(rows):nullptr;
    const uint32_t owner=row && row[0]?static_cast<uint32_t>(strtoul(row[0],nullptr,10)):0;
    if (rows) mysql_free_result(rows);
    if (!owner || !seed_collectors(104,owner,1)) return false;
    collector_bootstrap_snapshot loaded;
    return collector_repository_read_bootstrap(DB,&loaded) && loaded.catalog.records.size()==1 &&
           loaded.catalog.records[0].listing==104 && loaded.catalog.next_listing==105;
}
int main(int argc, char **argv) {
    char mode_error[512];
    if (!persistence_mode_configure(mode_error, sizeof mode_error)) return 2;
    if (argc != 3) return 2;
    signal(SIGCHLD, reap);
    DB = mysql_init(nullptr);
    if (!mysql_real_connect(DB, getenv("DB_HOST"), getenv("DB_USER"), getenv("DB_PASSWD"),
                            getenv("DB_NAME"), atoi(getenv("DB_PORT")), nullptr, 0)) return 2;
    if (const char *clock = getenv("PWIPE_TEST_NOW")) qry("SET TIMESTAMP=%lld", atoll(clock));
    current_season_epoch = strtoull(argv[2], nullptr, 10);
    redis_connection_settings *settings=nullptr;
    char current[160], sessions[160], retries[160], caches[160];
    if (const char *port=getenv("PWIPE_TEST_REDIS_PORT")) {
        const redis_connection_options options{"127.0.0.1",atoi(port),250,250,0,nullptr,nullptr,false,nullptr,nullptr,false,nullptr};
        settings=redis_connection_settings_create(&options);
        constexpr const char *ns="duris:local:pwipe-sql";
        if (!settings || !redis_namespace_season_key(ns,current_season_epoch,"presence:current",current,sizeof current) ||
            !redis_namespace_season_key(ns,current_season_epoch,"presence:session:*",sessions,sizeof sessions) ||
            !redis_namespace_season_key(ns,current_season_epoch,"presence_op:*",retries,sizeof retries) ||
            !redis_namespace_season_key(ns,current_season_epoch,"cache:*",caches,sizeof caches)) return 2;
        fixture_redis={settings,ns,current_season_epoch,current,sessions,retries,caches};
    }
    bool ok = !strcmp(argv[1], "clear-redis") ? redis_clear_pwipe_state() :
              !strcmp(argv[1], "seed-payloads") ? seed_payloads() :
              !strcmp(argv[1], "empty-payloads") ? payload_readers(true) :
              !strcmp(argv[1], "seed-trade") ? seed_trade() :
              !strcmp(argv[1], "replay-trade") ? replay_trade(false) :
              !strcmp(argv[1], "submit-stale-trade") ? replay_trade(true) :
              !strcmp(argv[1], "seed-artifact-history") ? seed_artifact_history() :
              !strcmp(argv[1], "check-artifact-history") ? check_artifact_history() :
              !strcmp(argv[1], "seed-collectors") ? seed_collectors(strtoull(argv[2],nullptr,10),1004,4) :
              !strcmp(argv[1], "stale-collector") ? stale_collector_purchase() :
              !strcmp(argv[1], "new-collector") ? new_collector_candidate() :
              !strcmp(argv[1], "check-collectors") ? check_collectors() :
              !strcmp(argv[1], "reset-collectors") ? sql_reset_collector_state(true) :
              !strcmp(argv[1], "items-before") ? retained_items(false) :
              !strcmp(argv[1], "items-after") ? retained_items(true) :
              !strcmp(argv[1], "seed-boons") ? seed_boons() :
              !strcmp(argv[1], "check-boons") ? check_boons() :
              !strcmp(argv[1], "end-boons") ?
                  divine_boon_sql_reset_season(DB, time(nullptr)) == divine_boon_store_result::ok :
              !strcmp(argv[1], "begin") ? sql_begin_pwipe_epoch() :
              !strcmp(argv[1], "ready") ? sql_prepare_pwipe_filesystem() :
              !strcmp(argv[1], "wipe") ? sql_pwipe(1723699) :
              !strcmp(argv[1], "rewards") ? account_bound_rewards_on_successful_pwipe() : sql_load_active_season_state();
    const bool boundary_ok = !getenv("PWIPE_TEST_BOUNDARY_ACK") ||
        (boundary_commit_fault && pwipe_crossed_boundary && !pwipe_filesystem_ready && !ok && !writer_resumes);
    redis_connection_settings_destroy(settings);
    mysql_close(DB);
    return boundary_ok ? (ok ? 0 : 1) : 3;
}
''')
    binary = native.with_suffix("")
    build_script = (ROOT / "tests/async/run_collector_repository_schema_mysql.sh").read_text()
    compile_sources = build_script[build_script.index("g++ -std=c++20"):build_script.index('"${MYSQL_LIBS[@]}" -lcrypto')]
    repository_sources = re.findall(r"(?:src|tests/async)/[A-Za-z0-9_/]+\.(?:cpp|c)", compile_sources)
    repository_sources.remove("tests/async/collector_repository_mysql_harness.cpp")
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-ffunction-sections", "-fdata-sections", "-Isrc", "-I/usr/include/mysql", "-pthread",
                    str(native), "src/economy/divine_boon.c", "src/economy/divine_boon_repository.c",
                    "src/economy/collector_purchase_preparation.c", "src/guild/artifact_population_repository.c",
                    "src/item/legacy_object_identity.c", "src/player/player_load_repository.c", "src/player/player_load_topology.c",
                    "src/item/item_uid_allocator.c", "src/flatfile/flatfile_item_uid_allocator.c", "src/flatfile/flatfile_store.c",
                    "src/persistence/persistence_mode.c", "src/redis/redis_maintenance.c", "src/redis/redis_ship_legacy.c",
                    "src/redis/redis_connection.c", "src/redis/redis_command_observability.c", "src/redis/redis_namespace.c", *repository_sources,
                    "-lmysqlclient", "-lcrypto", "-lhiredis", "-lhiredis_ssl", "-lssl", "-Wl,--gc-sections", "-Wl,--wrap=posix_spawn", "-Wl,--wrap=mysql_real_query", "-o", str(binary)], cwd=ROOT, check=True)

    def epoch_call(command, epoch, expected_code, cwd=None):
        result = subprocess.run([str(binary), command, str(epoch)], env=env, cwd=cwd,
                                capture_output=True, text=True)
        assert result.returncode == expected_code, (command, epoch, result.returncode, result.stderr)
        return result

    epoch_call("active", 1, 0)
    epoch_call("begin", 1, 0)
    epoch_call("active", 2, 1)
    epoch_call("begin", 2, 1)
    assert sql("SELECT season_epoch FROM season_reset_state WHERE state_id=1") == "2"
    epoch_call("ready", 3, 1)
    assert sql("SELECT roster_recreated FROM season_reset_state") == "0"
    epoch_call("ready", 2, 1)
    assert sql("SELECT reset_completed_at IS NULL FROM season_reset_state") == "1"
    sql("UPDATE season_reset_state SET roster_recreated=1")
    epoch_call("ready", 2, 0)
    epoch_call("active", 2, 1)
    print("Native begin/SQL-ready/boot fence passed with real SQL", flush=True)

    output = ROOT / "bin/tests"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pwipe-handoff-", dir=output) as temporary:
        root = Path(temporary)
        for directory in ("scripts", "Players/wipers", "Players/a", "Players/Backup", "bin/server", "lib"):
            (root / directory).mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "scripts/cycle_mud.sh", root / "scripts/cycle_mud.sh")
        wiper = root / "Players/wipers/wipe_it_all"
        shutil.copy2(ROOT / "Players/wipers/wipe_it_all", wiper)
        original = wiper.read_text()
        (root / "lib/frag_cap.cfg").write_text("cap.reset.level=37\n")
        reward_config = root / "lib/account_rewards.cfg"
        reward_config.write_text("pwipe.preserve=true\n")
        recovery_canary = root / "Players/a/recovery-keep"
        recovery_canary.write_text("SQL recovery must not clear files")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            recovery_port = listener.getsockname()[1]

        def recovery_command(epoch):
            return [str(server), "--resume-pwipe", str(epoch), str(recovery_port)]

        def recover(epoch, expected, environment=None):
            result = subprocess.run(recovery_command(epoch), env=environment or env, cwd=root,
                                    capture_output=True, text=True, timeout=30)
            assert result.returncode == expected, (result.returncode, result.stdout, result.stderr)
            assert "Entering game loop" not in result.stderr
            assert recovery_canary.read_text() == "SQL recovery must not clear files"
            return result

        sql("UPDATE season_reset_state SET season_epoch=1,reset_status='active',"
            "reset_completed_at=NULL WHERE state_id=1")
        sql("INSERT INTO zones(number,name,alignment,epic_type) VALUES(900,'fixture',1,1)")
        sql("INSERT INTO accounts(account_name,password,email,total_donated,confirmed) "
            "VALUES('fixturebank','fixture-password','fixture@example.invalid',123.45,1)")
        account_before = sql("SELECT CONCAT_WS(':',password,email,total_donated,confirmed) "
                             "FROM accounts WHERE account_name='fixturebank'")
        sql("INSERT INTO account_banks(id,account_name,racewar,bank_copper,bank_silver,bank_gold,bank_platinum) "
            "VALUES(900,'fixturebank',1,123,456,789,987),"
            "(901,'fixturebank',2,2,3,4,5),(902,'fixturebank',0,6,7,8,9)")
        sql("INSERT INTO currency_bank_baseline(bank_id,opening_copper,opening_silver,opening_gold,opening_platinum) "
            "SELECT id,bank_copper,bank_silver,bank_gold,bank_platinum FROM account_banks")
        for pid, name, level in ((1001, "Freshgod", 62), (1002, "Lesserstaff", 61),
                                 (1003, "Outofrange", 63), (1004, "Oldmortal", 56),
                                 (1005, "Stalegod", 62), (1006, "Deletedgod", 62)):
            sql("INSERT INTO player_data(pid,name,account_name,level,highest_level,m_class,race,sex,"
                "copper,epics,frags,learned_flight_stops) VALUES(" + str(pid) + ",'" + name +
                "','fixturebank'," + str(level) + "," + str(level) + ",1,1,1,999,888,777,63)")
            if name == "Freshgod":
                continue  # Durable owner with no projection.
            sql("INSERT INTO account_characters(account_name,pid,char_name) VALUES('fixturebank'," +
                str(pid) + ",'" + name + "')")
        sql("UPDATE account_characters SET char_name='Stalename' WHERE pid=1005")
        sql("UPDATE account_characters SET deleted_at=NOW() WHERE pid=1006")
        def cover_baselines():
            sql("INSERT IGNORE INTO currency_wallet_baseline(pid,opening_copper,opening_silver,opening_gold,opening_platinum,opening_revision) "
                "SELECT pid,copper,silver,gold,platinum,wallet_revision FROM player_data")
            sql("INSERT IGNORE INTO epic_balance_baseline(pid,opening_balance,opening_revision) SELECT pid,epics,epic_revision FROM player_data")
            sql("INSERT IGNORE INTO combat_frag_baseline(pid,opening_frags,opening_revision) SELECT pid,frags,frag_revision FROM player_data")
        cover_baselines()
        sql("INSERT INTO associations(id,name,prestige) VALUES(777,'old guild',999)")
        sql("INSERT INTO kingdom_realms(assoc_id,realm_id,hall_vnum,highest_claim,res_wood) "
            "VALUES(777,3,900,80,9999)")
        sql("INSERT INTO kingdom_garrison(assoc_id,slot,guard_class,level) VALUES(777,0,1,50)")
        sql("INSERT INTO kingdom_land(kingdom_id,start_vnum,end_vnum) VALUES(777,900,980)")
        sql("INSERT INTO artifacts(vnum,owned,locType,location,timer,type,lastUpdate) "
            "VALUES(900,'Y',3,1004,FROM_UNIXTIME(2000000000),1,NOW())")
        sql("INSERT INTO artifact_bind(vnum,owner_pid,timer) VALUES(900,1004,20)")
        sql("INSERT INTO artifact_domain_state(vnum,owned,loc_type,location,timer_epoch,artifact_type,"
            "bind_owner_pid,bind_timer_epoch,canonical_item_uid,identity_state,rejected_item_uids,revision) "
            "VALUES(900,1,3,1004,2000000000,1,1004,20,880001,1,'879999',700),"
            "(901,0,1,0,1234,1,1004,20,880002,2,NULL,9),"
            "(902,1,3,1004,1234,1,1004,20,NULL,0,NULL,0)")
        sql("INSERT INTO artifact_domain_baseline(vnum,opening_timer_epoch,opening_bind_owner_pid,"
            "opening_bind_timer_epoch,opening_revision) VALUES(900,1900000000,1004,10,700)")
        epoch_call("seed-payloads", 1, 0)
        epoch_call("seed-artifact-history", 1, 0)
        artifact_baseline = sql("SELECT * FROM artifact_domain_baseline ORDER BY vnum")
        artifact_history = sql("SELECT * FROM artifact_delta_ledger ORDER BY vnum,revision")
        assert sql("SELECT revision FROM artifact_delta_ledger WHERE vnum=900") == "701"
        env["PWIPE_TEST_COLLECTOR_BUY"] = str(root / "old-buy.command")
        epoch_call("seed-collectors", 100, 0)
        listing_bytes = sql("SELECT HEX(record_blob) FROM collector_listings WHERE listing_id=101")
        sql("UPDATE collector_listings SET record_blob=REPEAT(CHAR(0),154) WHERE listing_id=101")
        refusal = epoch_call("wipe", 1, 1, cwd=root)
        assert "Collector retirement preflight failed" in refusal.stderr
        assert sql("SELECT CONCAT(season_epoch,':',reset_status) FROM season_reset_state") == "1:active"
        sql("UPDATE collector_listings SET record_blob=UNHEX('" + listing_bytes + "') WHERE listing_id=101")
        epoch_call("seed-boons", 1, 0)
        env["PWIPE_TEST_TRADE_PREFIX"] = str(root / "old-trade-")
        epoch_call("seed-trade", 1, 0)
        trade_books = sql("SELECT account_key,boon_id,revision,HEX(snapshot) FROM divine_trade_state ORDER BY account_key,boon_id")
        boon_bytes = sql("SELECT HEX(snapshot) FROM divine_boon_state WHERE state_id=1")
        sql("UPDATE divine_boon_state SET snapshot=0x00 WHERE state_id=1")
        refusal = epoch_call("wipe", 1, 1, cwd=root)
        assert "Divine Boon state cannot be safely retired" in refusal.stderr
        assert sql("SELECT CONCAT(season_epoch,':',reset_status) FROM season_reset_state") == "1:active"
        sql("UPDATE divine_boon_state SET snapshot=UNHEX('" + boon_bytes + "') WHERE state_id=1")
        sql("INSERT INTO player_items(pid,vnum,obj_uid,equip_slot,quantity,weight,cost) VALUES(1002,1108,991001,0,1,4,5)")
        sql("INSERT INTO item_owner_revision(owner_type,owner_id,owner_context_id,revision) VALUES(1,1002,0,1)")
        sql("INSERT INTO item_current_owner(item_uid,root_item_uid,owner_type,owner_id,item_revision,vnum,state) VALUES(991001,991001,1,1002,1,1108,1)")
        sql("INSERT INTO item_ownership_baseline(item_uid,root_item_uid,owner_type,owner_id,opening_item_revision,vnum,source_table,source_row_id) "
            "SELECT obj_uid,obj_uid,1,pid,1,vnum,'player_items',id FROM player_items WHERE obj_uid=991001")
        sql("UPDATE item_uid_allocator SET next_uid=(SELECT COALESCE(MAX(item_uid),0)+1000000 FROM item_current_owner) WHERE allocator_id=1")
        custody = sql("SELECT * FROM item_current_owner WHERE item_uid=991001")
        owner_revision = sql("SELECT * FROM item_owner_revision WHERE owner_type=1 AND owner_id=1002")
        ownership_baseline = sql("SELECT * FROM item_ownership_baseline WHERE item_uid=991001")
        payload_id_before = int(sql("SELECT AUTO_INCREMENT FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='player_items'"))
        assert payload_id_before > int(sql("SELECT source_row_id FROM item_ownership_baseline WHERE item_uid=991001"))
        allocator_before = int(sql("SELECT next_uid FROM item_uid_allocator WHERE allocator_id=1"))
        epoch_call("items-before", 1, 0)
        epoch_call("wipe", 1, 0, cwd=root)
        assert sql("SELECT * FROM item_current_owner WHERE item_uid=991001") == custody
        assert sql("SELECT * FROM item_owner_revision WHERE owner_type=1 AND owner_id=1002") == owner_revision
        assert sql("SELECT * FROM item_ownership_baseline WHERE item_uid=991001") == ownership_baseline
        assert int(sql("SELECT next_uid FROM item_uid_allocator WHERE allocator_id=1")) == allocator_before
        assert int(sql("SELECT AUTO_INCREMENT FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='player_items'")) == payload_id_before
        assert int(epoch_call("items-after", 2, 0).stdout.strip()) == allocator_before
        assert int(sql("SELECT next_uid FROM item_uid_allocator WHERE allocator_id=1")) == allocator_before + 4
        print("Ordinary item custody/revision/baseline retained unchanged; actual loader finds no old payload, fresh Overlord has no old graph, allocator grants only new UIDs", flush=True)
        assert sql("SELECT alignment FROM zones WHERE number=900") == "0"
        assert sql("SELECT CONCAT(season_epoch,':',reset_status,':',reset_completed_at IS NOT NULL) "
                   "FROM season_reset_state WHERE state_id=1") == "2:resetting:1"
        print("Actual native SQL reset/preflight/postflight passed without shared-writer admission", flush=True)
        assert sql("SELECT COUNT(*) FROM artifact_domain_state WHERE owned<>0 OR loc_type<>1 OR location<>0 "
                   "OR timer_epoch<>0 OR bind_owner_pid<>0 OR bind_timer_epoch<>0 OR item_uid IS NOT NULL "
                   "OR item_revision IS NOT NULL") == "0"
        assert sql("SELECT CONCAT_WS(':',vnum,canonical_item_uid,identity_state,COALESCE(rejected_item_uids,''),revision) "
                   "FROM artifact_domain_state ORDER BY vnum") == "900:880001:2:879999:700\n901:880002:2::9\n902:3::0"
        assert sql("SELECT * FROM artifact_domain_baseline ORDER BY vnum") == artifact_baseline
        assert sql("SELECT * FROM artifact_delta_ledger ORDER BY vnum,revision") == artifact_history
        epoch_call("empty-payloads", 2, 0)
        for table in ("auction_item_custody", "siege_items", "siege_item_affects", "siege_item_extra_descr"):
            assert sql("SELECT COUNT(*) FROM " + table) == "0"
        print("Auction custody and nested siege payloads/affects/descriptions reset; real startup readers return no old bodies", flush=True)
        epoch_call("check-artifact-history", 2, 0)
        subprocess.run([str(ROOT / "migrations/reconcile_artifact_guild_outcomes.sh")],
                       cwd=ROOT, env=env, check=True)
        recovery_env = dict(env, TEST_DB_HOST=env["DB_HOST"], TEST_DB_PORT=env["DB_PORT"])
        subprocess.run([sys.executable, str(ROOT / "tests/async/test_artifact_guild_snapshots.py"),
                        "--pwipe-recovery"], cwd=ROOT, env=recovery_env, check=True)
        assert sql("SELECT * FROM artifact_delta_ledger ORDER BY vnum,revision") == artifact_history
        print("Artifact reset/restart: old bodies retired, ownership/timers/souls cleared, history/revisions retained; old delivery and receipt replay cannot restore state", flush=True)
        trade_wallet = sql("SELECT CONCAT_WS(':',copper,wallet_revision) FROM player_data WHERE pid=1004")
        epoch_call("replay-trade", 2, 0)
        assert sql("SELECT CONCAT_WS(':',copper,wallet_revision) FROM player_data WHERE pid=1004") == trade_wallet
        assert sql("SELECT account_key,boon_id,revision,HEX(snapshot) FROM divine_trade_state ORDER BY account_key,boon_id") == trade_books
        for table in ("ships", "ship_slots", "ship_crew", "ship_cargo_market_mods", "ship_cargo_prices"):
            assert sql("SELECT COUNT(*) FROM " + table) == "0"
        print("Committed cargo receipt replay is harmless; unapplied prepared cargo trade is stale after real reset with retained book/generation", flush=True)
        epoch_call("check-collectors", 2, 0)
        assert sql("SELECT COUNT(*) FROM collector_listings WHERE status=5") == "4"
        assert sql("SELECT COUNT(*) FROM item_current_owner WHERE owner_type=8 AND state=2") == "3"
        assert sql("SELECT COUNT(*) FROM collector_ledger WHERE closed_reason=6") == "4"
        preserved = sql("SELECT HEX(item_blob) FROM collector_listings WHERE listing_id=103")
        assert preserved
        receipts = sql("SELECT COUNT(*) FROM collector_ledger")
        epoch_call("reset-collectors", 2, 0)
        assert sql("SELECT COUNT(*) FROM collector_ledger") == receipts
        assert sql("SELECT HEX(item_blob) FROM collector_listings WHERE listing_id=103") == preserved
        print("Collector reset: candidate/collected/available/paused retired, custody destroyed, audit/payload/IDs retained and restart view empty", flush=True)
        retired_wallet = sql("SELECT copper FROM player_data WHERE pid=1004")
        epoch_call("stale-collector", 2, 0)
        assert sql("SELECT copper FROM player_data WHERE pid=1004") == retired_wallet
        assert sql("SELECT COUNT(*) FROM player_items WHERE obj_uid IN (SELECT item_uid FROM collector_listings)") == "0"
        del env["PWIPE_TEST_COLLECTOR_BUY"]
        print("A real pre-reset prepared purchase was refused as stale without payment or item resurrection", flush=True)


        epoch_call("check-boons", 2, 0)
        print("Divine reset: no old objectives/repeat preferences, IDs/audit/pause retained, retry idempotent and next ID fresh", flush=True)

        for table in ("kingdom_garrison", "kingdom_land", "kingdom_realms"):
            assert sql("SELECT COUNT(*) FROM " + table) == "0", table
        sql("INSERT INTO associations(id,name) VALUES(777,'new guild')")
        assert sql("SELECT COUNT(*) FROM kingdom_realms WHERE assoc_id=777") == "0"
        assert sql("SELECT COUNT(*) FROM kingdom_garrison WHERE assoc_id=777") == "0"
        print("Kingdom reset: territory/resources/guards absent, including a reused association ID", flush=True)

        new_god = int(sql("SELECT pid FROM player_data WHERE name='Freshgod' AND active=1 AND level=62"))
        assert new_god > 1006
        assert sql("SELECT COUNT(*) FROM player_data WHERE active=1") == "2"
        assert sql("SELECT CONCAT_WS(':',copper,epics,frags,learned_flight_stops,assoc_id) "
                   "FROM player_data WHERE pid=" + str(new_god)) == "0:0:0:0:0"
        assert sql("SELECT COUNT(*) FROM account_characters WHERE deleted_at IS NULL AND pid=" + str(new_god)) == "1"
        assert sql("SELECT COUNT(*) FROM player_data WHERE pid BETWEEN 1001 AND 1006 AND active=0 "
                   "AND name=CONCAT('~pwipe-',pid)") == "6"
        assert sql("SELECT COUNT(*) FROM currency_wallet_baseline WHERE pid=" + str(new_god)) == "1"
        assert sql("SELECT COUNT(*) FROM player_data p JOIN account_characters a ON a.pid=p.pid "
                   "AND a.char_name=p.name AND a.account_name=p.account_name "
                   "WHERE p.active=1 AND a.deleted_at IS NULL AND p.last_save=p.birth_time "
                   "AND p.last_save IS NOT NULL") == "2"
        assert sql("SELECT COUNT(*) FROM player_data WHERE name='Stalegod' AND active=1") == "1"
        assert sql("SELECT COUNT(*) FROM player_data WHERE name='Deletedgod' AND active=1") == "0"
        sql("INSERT INTO player_data(name,account_name) VALUES('Oldmortal','fixturebank')")
        cover_baselines()
        assert sql("SELECT roster_recreated FROM season_reset_state") == "1"
        print("Overlord recreation: exact 62 only, new PID, clean balances/progression, account mapping and freed mortal name passed", flush=True)
        new_trader = sql("SELECT pid FROM player_data WHERE name='Oldmortal' AND active=1")
        assert int(new_trader) > 1004
        sql("INSERT INTO ships(owner_name,ship_name,ship_class) VALUES('Oldmortal','Fresh trade',0)")
        new_ship = sql("SELECT id FROM ships WHERE owner_name='Oldmortal'")
        assert int(new_ship) > 600
        epoch_call("replay-trade", 2, 0)
        epoch_call("submit-stale-trade", 2, 0)
        assert sql("SELECT CONCAT_WS(':',copper,wallet_revision) FROM player_data WHERE pid=1004") == trade_wallet
        assert sql("SELECT CONCAT_WS(':',copper,wallet_revision) FROM player_data WHERE pid=" + new_trader) == "0:0"
        assert sql("SELECT account_key,boon_id,revision,HEX(snapshot) FROM divine_trade_state ORDER BY account_key,boon_id") == trade_books
        for table in ("ship_slots", "ship_crew", "ship_cargo_market_mods", "ship_cargo_prices"):
            assert sql("SELECT COUNT(*) FROM " + table) == "0"
        sql("DELETE FROM ships WHERE id=" + new_ship)
        print("Same-named fresh mortal/new ship use higher IDs; stale cargo command cannot restore wallet/cargo/market after-images", flush=True)
        epoch_call("new-collector", 2, 0)
        assert sql("SELECT COUNT(*) FROM collector_listings") == "5"
        print("Fresh collector enrollment/bootstrap uses the next ID and excludes retired protected history", flush=True)

        assert sql("SELECT COUNT(*) FROM account_banks") == "0"
        assert sql("SELECT CONCAT_WS(':',password,email,total_donated,confirmed) "
                   "FROM accounts WHERE account_name='fixturebank'") == account_before
        assert sql("SELECT opening_platinum FROM currency_bank_baseline WHERE bank_id=900") == "987"
        sql("INSERT INTO account_banks(account_name,racewar) VALUES('fixturebank',1)")
        new_bank = int(sql("SELECT id FROM account_banks WHERE account_name='fixturebank' AND racewar=1"))
        assert new_bank > 902
        assert sql("SELECT CONCAT_WS(':',bank_copper,bank_silver,bank_gold,bank_platinum) "
                   "FROM account_banks WHERE id=" + str(new_bank)) == "0:0:0:0"
        assert sql("SELECT COUNT(*) FROM currency_bank_baseline WHERE bank_id=" + str(new_bank)) == "0"
        print("Bank reset: all sides removed, credentials/donations/history retained, new ID and zero balances passed", flush=True)
        roster_before = sql("SELECT pid,name,level,active FROM player_data ORDER BY pid")
        mappings_before = sql("SELECT pid,char_name,deleted_at FROM account_characters ORDER BY id")
        sql("UPDATE season_reset_state SET reset_status='active' WHERE state_id=1")
        env["PWIPE_TEST_FAIL_SQL"] = "INSERT INTO epic_balance_baseline"
        try:
            epoch_call("wipe", 2, 1, cwd=root)
        finally:
            del env["PWIPE_TEST_FAIL_SQL"]
        assert sql("SELECT pid,name,level,active FROM player_data ORDER BY pid") == roster_before
        assert sql("SELECT pid,char_name,deleted_at FROM account_characters ORDER BY id") == mappings_before
        assert sql("SELECT CONCAT(reset_status,':',reset_completed_at IS NULL) "
                   "FROM season_reset_state WHERE state_id=1") == "resetting:1"
        assert sql("SELECT roster_recreated FROM season_reset_state") == "0"
        print("Mid-recreation failure rolled back the entire roster and kept startup fenced", flush=True)
        if server:
            recover(4, 58)
            sql("UPDATE season_reset_state SET reset_status='active'")
            recover(3, 58)
            sql("UPDATE season_reset_state SET reset_status='resetting',roster_recreated=NULL")
            recover(3, 58)
            sql("UPDATE season_reset_state SET roster_recreated=0")
            assert sql("SELECT pid,name,level,active FROM player_data ORDER BY pid") == roster_before
            sql("CREATE TRIGGER fixture_roster_pause BEFORE UPDATE ON season_reset_state "
                "FOR EACH ROW SET @fixture_pause=IF(NEW.roster_recreated=1 AND OLD.roster_recreated=0,SLEEP(5),0)")
            interrupted = subprocess.Popen(recovery_command(3), env=env, cwd=root,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                for _ in range(200):
                    if sql("SELECT COUNT(*) FROM information_schema.PROCESSLIST WHERE "
                           "LOWER(STATE)='user sleep'") != "0":
                        break
                    assert interrupted.poll() is None, interrupted.communicate()
                    time.sleep(.05)
                else:
                    raise AssertionError("SQL recovery did not reach the roster commit checkpoint")
                refusal = recover(3, 58)
                assert "runtime exclusion guard" in (root / "logs/log/status").read_text()
            finally:
                if interrupted.poll() is None:
                    interrupted.kill()
                interrupted.communicate(timeout=10)
                sql("DROP TRIGGER fixture_roster_pause")
            assert sql("SELECT roster_recreated FROM season_reset_state") == "0"
            assert sql("SELECT pid,name,level,active FROM player_data ORDER BY pid") == roster_before
            assert sql("SELECT pid,char_name,deleted_at FROM account_characters ORDER BY id") == mappings_before
            recover(3, 55)
            assert sql("SELECT CONCAT(season_epoch,':',reset_status,':',roster_recreated,':',"
                       "reset_completed_at IS NOT NULL) FROM season_reset_state") == "3:resetting:1:1"
            assert sql("SELECT level FROM level_cap") == "37"
            resumed_roster = sql("SELECT pid,name,level,active FROM player_data ORDER BY pid")
            assert resumed_roster != roster_before
            recover(3, 55)
            assert sql("SELECT pid,name,level,active FROM player_data ORDER BY pid") == resumed_roster
            result = subprocess.run([str(root / "scripts/cycle_mud.sh"), "--dev", "--resume-pwipe", "3"],
                                    env=env, capture_output=True, text=True, timeout=30)
            assert result.returncode == 55, (result.returncode, result.stdout, result.stderr)
            assert sql("SELECT CONCAT(season_epoch,':',reset_status) FROM season_reset_state") == "3:active"
            assert not recovery_canary.exists()
            recovery_canary.write_text("SQL recovery must not clear files")
            print("Real SQL-only binary refuses wrong/active/unknown resets, excludes another process, "
                  "survives SIGKILL before roster commit, loads lifecycle config and completes the same epoch once", flush=True)
        sql("UPDATE season_reset_state SET reset_status='active' WHERE state_id=1")
        before = sql("SELECT season_epoch,reset_status FROM season_reset_state WHERE state_id=1")
        sql("ALTER TABLE player_data RENAME COLUMN base_luk TO fixture_base_luk")
        try:
            epoch_call("wipe", 3, 1, cwd=root)
            assert sql("SELECT season_epoch,reset_status FROM season_reset_state WHERE state_id=1") == before
        finally:
            sql("ALTER TABLE player_data RENAME COLUMN fixture_base_luk TO base_luk")
        print("Missing recreation schema rejected before the irreversible boundary", flush=True)
        sql("RENAME TABLE kingdom_realms TO fixture_kingdom_realms")
        try:
            epoch_call("wipe", 3, 1, cwd=root)
            assert sql("SELECT season_epoch,reset_status FROM season_reset_state WHERE state_id=1") == before
        finally:
            sql("RENAME TABLE fixture_kingdom_realms TO kingdom_realms")
        print("Missing kingdom store rejected before the irreversible boundary", flush=True)
        sql("ALTER TABLE collector_ledger RENAME COLUMN source_site TO fixture_source_site")
        try:
            epoch_call("wipe", 3, 1, cwd=root)
            assert sql("SELECT season_epoch,reset_status FROM season_reset_state WHERE state_id=1") == before
        finally:
            sql("ALTER TABLE collector_ledger RENAME COLUMN fixture_source_site TO source_site")
        print("Delegated collector ledger schema drift rejected before epoch advance", flush=True)
        sql("RENAME TABLE siege_item_extra_descr TO fixture_siege_item_extra_descr")
        try:
            epoch_call("wipe", 3, 1, cwd=root)
            assert sql("SELECT season_epoch,reset_status FROM season_reset_state WHERE state_id=1") == before
        finally:
            sql("RENAME TABLE fixture_siege_item_extra_descr TO siege_item_extra_descr")
        print("Missing siege payload child schema rejected before epoch advance", flush=True)




        # Exercise the real policy hook. Its fixed reset boundary separates retry
        # identity from the 28-day business protection, with no schema extension.
        def policy_boundary(epoch, started):
            sql("UPDATE season_reset_state SET season_epoch=" + str(epoch) +
                ",reset_status='resetting',reset_started_at='" + started +
                "',reset_completed_at=NULL WHERE state_id=1")

        def summons():
            sql("INSERT INTO account_bound_reward_summons(grant_id,pid) VALUES(1,1001)")

        def remaining():
            return sql("SELECT remaining_pwipes FROM account_bound_rewards WHERE id=3")

        sql("UPDATE account_bound_reward_pwipe_state SET last_processed_at=NULL WHERE id=1")
        sql("INSERT INTO account_bound_rewards(id,account_name,remaining_pwipes,expires_at,created_at) VALUES"
            "(1,'fixturebank',NULL,NULL,'2024-01-01'),(2,'fixturebank',1,NULL,'2024-01-01'),"
            "(3,'fixturebank',3,NULL,'2024-01-01'),(4,'fixturebank',NULL,'2030-01-01','2024-01-01'),"
            "(5,'fixturebank',NULL,'2020-01-01','2019-01-01')")
        policy_boundary(20, "2025-01-01 12:00:00.123456")
        env["PWIPE_TEST_NOW"] = sql("SELECT UNIX_TIMESTAMP('2025-01-01 12:00:01')")
        summons()
        epoch_call("rewards", 19, 1)
        assert remaining() == "3" and sql("SELECT COUNT(*) FROM account_bound_reward_summons") == "1"
        epoch_call("rewards", 0, 1)
        sql("UPDATE season_reset_state SET reset_status='active' WHERE state_id=1")
        epoch_call("rewards", 20, 1)
        sql("UPDATE season_reset_state SET reset_status='resetting',reset_started_at=NULL WHERE state_id=1")
        epoch_call("rewards", 20, 1)
        assert remaining() == "3" and sql("SELECT COUNT(*) FROM account_bound_reward_summons") == "1"
        policy_boundary(20, "2025-01-01 12:00:00.123456")
        epoch_call("rewards", 20, 0)
        assert remaining() == "2"
        assert sql("SELECT GROUP_CONCAT(id ORDER BY id) FROM account_bound_rewards") == "1,3,4"
        assert sql("SELECT COUNT(*) FROM account_bound_reward_summons") == "0"
        stamp = sql("SELECT last_processed_at FROM account_bound_reward_pwipe_state WHERE id=1")
        assert stamp == "2025-01-01 12:00:00"
        # Same reset, much later clock: no second decrement.
        env["PWIPE_TEST_NOW"] = sql("SELECT UNIX_TIMESTAMP('2025-04-01')")
        env["PWIPE_TEST_DELETE_REWARDS"] = "1"
        epoch_call("rewards", 20, 0); assert remaining() == "2"
        del env["PWIPE_TEST_DELETE_REWARDS"]
        assert sql("SELECT last_processed_at FROM account_bound_reward_pwipe_state WHERE id=1") == stamp
        # A distinct reset inside 28 days keeps grants but clears old body links,
        # even if the operator retries it after the protection window has passed.
        policy_boundary(21, "2025-01-02 12:00:00")
        summons(); epoch_call("rewards", 21, 0)
        assert remaining() == "2" and sql("SELECT COUNT(*) FROM account_bound_reward_summons") == "0"
        assert sql("SELECT last_processed_at FROM account_bound_reward_pwipe_state WHERE id=1") == stamp
        # Eligible distinct reset: rollback preserves both grants and summons.
        policy_boundary(22, "2025-02-01 12:00:00")
        summons(); env["PWIPE_TEST_FAIL_SQL"] = "SET g.last_processed_at="
        try:
            epoch_call("rewards", 22, 1)
        finally:
            del env["PWIPE_TEST_FAIL_SQL"]
        assert remaining() == "2" and sql("SELECT COUNT(*) FROM account_bound_reward_summons") == "1"
        env["PWIPE_TEST_LOST_REWARD_ACK"] = "1"
        try:
            epoch_call("rewards", 22, 1)
        finally:
            del env["PWIPE_TEST_LOST_REWARD_ACK"]
        assert remaining() == "1" and sql("SELECT COUNT(*) FROM account_bound_reward_summons") == "0"
        epoch_call("rewards", 22, 0); assert remaining() == "1"
        policy_boundary(23, "2025-03-01 12:00:00")
        env["PWIPE_TEST_DELETE_REWARDS"] = "1"
        try:
            epoch_call("rewards", 23, 0)
        finally:
            del env["PWIPE_TEST_DELETE_REWARDS"]
        assert sql("SELECT COUNT(*) FROM account_bound_rewards") == "0"
        del env["PWIPE_TEST_NOW"]
        print("Real reward hook: permanent/finite/expiry, wrong epoch, delayed retry, distinct reset guard, rollback/lost ACK and preserve=false passed", flush=True)
        epoch_call("seed-boons", 23, 0)
        sql("UPDATE season_reset_state SET reset_status='active' WHERE state_id=1")
        sql("CREATE TRIGGER fixture_boon_failure BEFORE UPDATE ON divine_boon_state "
            "FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='fixture write failure'")
        try:
            epoch_call("wipe", 23, 1, cwd=root)
        finally:
            sql("DROP TRIGGER fixture_boon_failure")
        assert sql("SELECT CONCAT(reset_status,':',reset_completed_at IS NULL) FROM season_reset_state") == "resetting:1"
        assert sql("SELECT revision FROM divine_boon_state WHERE state_id=1") == "1"
        epoch_call("end-boons", 24, 0)
        epoch_call("check-boons", 24, 0)
        print("Failed Divine update fenced the reset; repaired retirement completed once", flush=True)





        sql("UPDATE artifact_domain_state SET owned=1,timer_epoch=1234 WHERE vnum=900")
        sql("UPDATE season_reset_state SET reset_status='active' WHERE state_id=1")
        sql("CREATE TRIGGER fixture_artifact_failure BEFORE UPDATE ON artifact_domain_state "
            "FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='fixture artifact failure'")
        try:
            epoch_call("wipe", 24, 1, cwd=root)
        finally:
            sql("DROP TRIGGER fixture_artifact_failure")
        assert sql("SELECT CONCAT(reset_status,':',reset_completed_at IS NULL) FROM season_reset_state") == "resetting:1"
        assert sql("SELECT timer_epoch FROM artifact_domain_state WHERE vnum=900") == "1234"
        print("Failed artifact retirement kept the reset fenced with its old snapshot intact", flush=True)
        sql("UPDATE season_reset_state SET season_epoch=24 WHERE state_id=1")

        epoch_call("seed-collectors", 200, 0)
        sql("UPDATE season_reset_state SET reset_status='active' WHERE state_id=1")
        prior_ledger = int(sql("SELECT COUNT(*) FROM collector_ledger"))
        sql("CREATE TRIGGER fixture_collector_failure BEFORE INSERT ON collector_ledger "
            "FOR EACH ROW SET NEW.closed_reason=IF(NEW.listing_id=202,99,NEW.closed_reason)")
        try:
            epoch_call("wipe", 24, 1, cwd=root)
        finally:
            sql("DROP TRIGGER fixture_collector_failure")
        assert sql("SELECT CONCAT(reset_status,':',reset_completed_at IS NULL) FROM season_reset_state") == "resetting:1"
        assert int(sql("SELECT COUNT(*) FROM collector_ledger")) == prior_ledger + 2
        epoch_call("reset-collectors", 25, 0)
        assert sql("SELECT COUNT(*) FROM collector_listings WHERE status BETWEEN 1 AND 3") == "0"
        repaired = sql("SELECT COUNT(*) FROM collector_ledger")
        epoch_call("reset-collectors", 25, 0)
        assert sql("SELECT COUNT(*) FROM collector_ledger") == repaired
        print("Partial collector failure stayed fenced; repaired retry closed remaining rows without duplicate receipts", flush=True)

        epoch_call("seed-payloads", 25, 0)
        sql("UPDATE season_reset_state SET reset_status='active' WHERE state_id=1")
        sql("CREATE TRIGGER fixture_siege_failure BEFORE DELETE ON siege_item_extra_descr "
            "FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='fixture siege failure'")
        try:
            refused = epoch_call("wipe", 25, 1, cwd=root)
            assert "Siege cleanup failed" in refused.stderr
        finally:
            sql("DROP TRIGGER fixture_siege_failure")
        assert sql("SELECT CONCAT(season_epoch,':',reset_status,':',reset_completed_at IS NULL) FROM season_reset_state") == "26:resetting:1"
        assert sql("SELECT COUNT(*) FROM siege_items") == "2"
        print("A real siege cleanup failure remains fenced and never publishes SQL-ready", flush=True)

        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            redis_port = listener.getsockname()[1]
        redis_process = subprocess.Popen(["redis-server", "--bind", "127.0.0.1", "--port", str(redis_port),
                                          "--save", "", "--appendonly", "no", "--dir", str(root)],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        def redis(*arguments):
            return subprocess.check_output(["redis-cli", "--raw", "-h", "127.0.0.1", "-p", str(redis_port),
                                            *arguments], text=True).strip()
        try:
            for _ in range(100):
                probe = subprocess.run(["redis-cli", "-p", str(redis_port), "PING"], capture_output=True, text=True)
                if probe.returncode == 0 and probe.stdout.strip() == "PONG":
                    break
                time.sleep(.05)
            else: raise AssertionError("private Redis did not start")
            old_key = "duris:local:pwipe-sql:season:26:cache:fixture"
            assert redis("SET", old_key, "old") == "OK"
            assert redis("SET", "unrelated:fixture", "retained") == "OK"
            sql("UPDATE season_reset_state SET reset_status='active' WHERE state_id=1")
            state_before = sql("SELECT season_epoch,reset_status FROM season_reset_state")
            players_before = sql("SELECT pid,name,active FROM player_data ORDER BY pid")
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                unavailable_port = listener.getsockname()[1]
            env["PWIPE_TEST_REDIS_PORT"] = str(unavailable_port)
            refusal = epoch_call("wipe", 26, 1, cwd=root)
            assert "fresh Redis administrative connection unavailable" in refusal.stderr
            assert sql("SELECT season_epoch,reset_status FROM season_reset_state") == state_before
            assert sql("SELECT pid,name,active FROM player_data ORDER BY pid") == players_before
            assert redis("GET", old_key) == "old"
            print("Real unavailable Redis endpoint aborts before boundary without changing SQL/old Redis state", flush=True)
            env["PWIPE_TEST_REDIS_PORT"] = str(redis_port)
            assert redis("ACL", "SETUSER", "default", "-scan") == "OK"
            try:
                refusal = epoch_call("wipe", 26, 1, cwd=root)
                assert "Redis pwipe invalidation failed" in refusal.stderr
            finally:
                assert redis("ACL", "SETUSER", "default", "+scan") == "OK"
            assert sql("SELECT CONCAT(season_epoch,':',reset_status,':',reset_completed_at IS NULL) FROM season_reset_state") == "27:resetting:1"
            assert redis("GET", old_key) == "old"
            assert sql("SELECT roster_recreated FROM season_reset_state") == "1"
            epoch_call("active", 27, 1)
            epoch_call("clear-redis", 26, 0)
            epoch_call("clear-redis", 26, 0)
            assert redis("EXISTS", old_key) == "0"
            assert redis("GET", "unrelated:fixture") == "retained"
            assert sql("SELECT reset_status FROM season_reset_state") == "resetting"
            print("Real post-boundary Redis SCAN denial stays fenced; repaired cleanup is idempotent and preserves unrelated keys", flush=True)
            if server:
                assert redis("SET", old_key, "old") == "OK"
                new_key = "duris:local:pwipe-sql:season:27:cache:fixture"
                assert redis("SET", new_key, "new") == "OK"
                recovery_env = dict(env, REDIS="TRUE", REDIS_HOST="127.0.0.1",
                                    REDIS_PORT=str(redis_port), REDIS_NAMESPACE="duris:local:pwipe-sql")
                post_roster = sql("SELECT pid,name,level,active FROM player_data ORDER BY pid")
                assert redis("ACL", "SETUSER", "default", "-scan") == "OK"
                try:
                    recover(27, 58, recovery_env)
                finally:
                    assert redis("ACL", "SETUSER", "default", "+scan") == "OK"
                assert sql("SELECT reset_completed_at IS NULL FROM season_reset_state") == "1"
                assert sql("SELECT pid,name,level,active FROM player_data ORDER BY pid") == post_roster
                assert redis("GET", old_key) == "old"
                sql("UPDATE account_bound_reward_pwipe_state SET last_processed_at=NULL")
                sql("INSERT INTO account_bound_rewards(id,account_name,remaining_pwipes,created_at) "
                    "VALUES(10,'fixturebank',3,'2024-01-01')")
                sql("CREATE TRIGGER fixture_ready_failure BEFORE UPDATE ON season_reset_state "
                    "FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='fixture ready failure'")
                try:
                    recover(27, 58, recovery_env)
                finally:
                    sql("DROP TRIGGER fixture_ready_failure")
                assert sql("SELECT remaining_pwipes FROM account_bound_rewards WHERE id=10") == "2"
                assert sql("SELECT reset_completed_at IS NULL FROM season_reset_state") == "1"
                reward_stamp = sql("SELECT last_processed_at FROM account_bound_reward_pwipe_state")
                assert reward_stamp != "NULL"
                assert redis("EXISTS", old_key) == "0"
                assert redis("GET", new_key) == "new"
                assert redis("GET", "unrelated:fixture") == "retained"
                recover(27, 55, recovery_env)
                assert sql("SELECT remaining_pwipes FROM account_bound_rewards WHERE id=10") == "2"
                assert sql("SELECT last_processed_at FROM account_bound_reward_pwipe_state") == reward_stamp
                assert sql("SELECT pid,name,level,active FROM player_data ORDER BY pid") == post_roster
                assert sql("SELECT CONCAT(season_epoch,':',reset_status,':',roster_recreated) "
                           "FROM season_reset_state") == "27:resetting:1"
                recover(27, 55, recovery_env)
                assert sql("SELECT remaining_pwipes FROM account_bound_rewards WHERE id=10") == "2"
                # A distinct eligible reset uses the configured discard policy.
                reward_config.write_text("pwipe.preserve=false\n")
                sql("UPDATE season_reset_state SET season_epoch=28,reset_started_at='2035-01-01',"
                    "reset_completed_at=NULL")
                recover(28, 55, recovery_env)
                assert sql("SELECT COUNT(*) FROM account_bound_rewards") == "0"
                assert sql("SELECT pid,name,level,active FROM player_data ORDER BY pid") == post_roster
                print("Real cold recovery selects the original Redis epoch, skips committed roster, "
                      "retries after reward commit without double consumption and honors preserve=false", flush=True)
        finally:
            env.pop("PWIPE_TEST_REDIS_PORT", None)
            redis_process.terminate(); redis_process.wait(timeout=10)

        (root / "Players/Backup/keep").write_text("archive")
        old = root / "Players/a/old"
        native_handoff = root / "copyover.dat"

        def prepare(ready=True):
            old.write_text("old season")
            native_handoff.write_bytes(b"COPYold season handoff")
            sql("UPDATE season_reset_state SET season_epoch=2,reset_status='resetting',roster_recreated=NULL,"
                "reset_started_at=UTC_TIMESTAMP(6),reset_completed_at=" +
                ("UTC_TIMESTAMP(6)" if ready else "NULL") + " WHERE state_id=1")

        def launch(epoch=2, expected=58, environment=None):
            result = subprocess.run([str(root / "scripts/cycle_mud.sh"), "--dev", "--resume-pwipe", str(epoch)],
                                    env=environment or env, text=True, capture_output=True, timeout=30)
            assert result.returncode == expected, (result.returncode, result.stdout, result.stderr)
            return result

        def status():
            return sql("SELECT CONCAT(season_epoch,':',reset_status) FROM season_reset_state WHERE state_id=1")

        prepare(False); launch(); assert old.exists() and native_handoff.exists() and status() == "2:resetting"
        prepare(); launch(epoch=3); assert old.exists()
        with (root / "bin/server/.pwipe.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            launch(); assert old.exists()
        # Pause the actual wiper after clearing Players/a and archiving copyover,
        # before clearing Players/b. The test shim delegates to the real find after
        # release; launcher and wiper sources are unmodified.
        held_commands = root / "held-commands"; held_commands.mkdir()
        held_find = held_commands / "find"
        held_find.write_text("#!/usr/bin/env python3\nimport os, sys\nfrom pathlib import Path\n"
                             "if len(sys.argv)>1 and sys.argv[1]=='Players/b':\n"
                             "    with open(os.environ['PWIPE_FIXTURE_RELEASE'],'rb',buffering=0) as release:\n"
                             "        ready=Path(os.environ['PWIPE_FIXTURE_READY'])\n"
                             "        temporary=ready.with_suffix('.tmp')\n"
                             "        temporary.write_text(str(os.getpid())+' '+str(os.getppid()))\n"
                             "        temporary.replace(ready)\n"
                             "        if release.read(1)!=b'1': sys.exit(1)\n"
                             "os.execv('/usr/bin/find',['find',*sys.argv[1:]])\n")
        held_find.chmod(0o700)
        second = root / "Players/b/old"
        second.parent.mkdir(exist_ok=True)
        for kill_group in (False, True):
            prepare(); second.write_text("second old payload")
            ready = root / "held-find-ready"
            release = root / "held-find-release"
            os.mkfifo(release, 0o600)
            release_fd = os.open(release, os.O_RDWR | os.O_NONBLOCK)
            child_fd = None
            held_env = dict(env, PATH=str(held_commands) + ":" + env["PATH"],
                            PWIPE_FIXTURE_READY=str(ready), PWIPE_FIXTURE_RELEASE=str(release))
            with (root / "launcher-kill.log").open("w+") as output:
                process = subprocess.Popen([str(root / "scripts/cycle_mud.sh"), "--dev", "--resume-pwipe", "2"],
                                           env=held_env, cwd=root, stdout=output, stderr=subprocess.STDOUT,
                                           start_new_session=True)
                try:
                    deadline = time.monotonic() + 10
                    while not ready.exists() and time.monotonic() < deadline and process.poll() is None:
                        time.sleep(.01)
                    output.flush(); output.seek(0)
                    assert ready.exists(), (process.poll(), output.read())
                    find_pid, child_pid = map(int, ready.read_text().split())
                    # The real wiper is find's parent; finish_pwipe is its parent,
                    # and the main launcher is one further parent.
                    def parent_pid(pid):
                        return int(next(line.split()[1] for line in Path(f"/proc/{pid}/status").read_text().splitlines()
                                        if line.startswith("PPid:")))
                    finish_pid = parent_pid(child_pid)
                    assert parent_pid(finish_pid) == process.pid
                    assert os.getpgid(find_pid) == os.getpgid(child_pid) == process.pid
                    child_fd = os.pidfd_open(child_pid)
                    lock_path = root / "bin/server/.pwipe.lock"
                    inherited_lock = Path(f"/proc/{child_pid}/fd/9")
                    assert inherited_lock.stat().st_ino == lock_path.stat().st_ino
                    assert not old.exists() and second.exists() and not native_handoff.exists()
                    assert status() == "2:resetting"
                    if kill_group:
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill(); os.kill(finish_pid, signal.SIGKILL)
                    assert process.wait(timeout=5) == -signal.SIGKILL
                    if not kill_group:
                        # All launcher parents are dead. Its still-held real wipe
                        # child keeps fd 9 and the kernel lock, so a second launcher
                        # cannot overlap even though the original PID is gone.
                        assert inherited_lock.stat().st_ino == lock_path.stat().st_ino
                        refused = launch()
                        assert "Another filesystem reset is in progress" in refused.stderr
                        assert second.exists() and status() == "2:resetting"
                        os.write(release_fd, b"1")
                    assert select.select([child_fd], [], [], 10)[0], "owned wipe child did not exit"
                    assert status() == "2:resetting" # No activator survived either kill.
                    assert second.exists() == kill_group
                    assert (root / "Players/Backup/keep").read_text() == "archive"
                finally:
                    if process.poll() is None or (child_fd is not None and not select.select([child_fd], [], [], 0)[0]):
                        try: os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError: pass
                    process.wait(timeout=5)
                    if child_fd is not None: os.close(child_fd)
                    os.close(release_fd)
                    release.unlink()
                    ready.unlink(missing_ok=True)
            launch(expected=55)
            assert status() == "2:active" and not second.exists()
            old.write_text("fresh state after launcher kill")
            launch(expected=55)
            assert old.read_text() == "fresh state after launcher kill"
        print("Real launcher SIGKILL: orphan wipe child retains inherited flock; concurrent resume refuses; "
              "orphan completion and whole-group partial kill remain fenced, legitimate resume/duplicate preserve fresh state", flush=True)
        prepare()
        if (root / "Ships").is_dir():
            (root / "Ships").rmdir()
        (root / "Ships").symlink_to(root / "Players/Backup")
        launch(); assert old.exists() and status() == "2:resetting"
        (root / "Ships").unlink()
        wiper.chmod(0o600); launch(); assert old.exists(); wiper.chmod(0o700)
        # Fail after real cleanup: no activation, and a repaired retry finishes once.
        prior_archives = set((root / "Players/Backup").glob("pwipe-copyover.*"))
        wiper.write_text(original.replace('echo "wipe_it_all: filesystem cleanup completed"', 'exit 1'))
        launch(); assert not old.exists() and not native_handoff.exists() and status() == "2:resetting"
        archive, = set((root / "Players/Backup").glob("pwipe-copyover.*")) - prior_archives
        assert (archive / "publication").read_bytes() == b"COPYold season handoff"
        wiper.write_text(original)
        launch(expected=55); assert status() == "2:active"
        old.write_text("new season sentinel")
        launch(expected=55); assert old.read_text() == "new season sentinel"
        # A lost activation ACK must be recovered by reading the same epoch;
        # replay must not delete a new season's files.
        prepare()
        commands = root / "commands"; commands.mkdir()
        wrapper = commands / "mysql"
        wrapper.write_text("#!/usr/bin/env python3\nimport subprocess, sys\n"
                           f"result = subprocess.run([{mysql[0]!r}, *sys.argv[1:]])\n"
                           "sys.exit(1 if any(\"UPDATE season_reset_state SET reset_status='active'\" in arg "
                           "for arg in sys.argv) else result.returncode)\n")
        wrapper.chmod(0o700)
        failing_env = dict(env, PATH=str(commands) + ":" + env["PATH"])
        launch(environment=failing_env); assert status() == "2:active"
        old.write_text("saved after ambiguous completion")
        native_handoff.write_bytes(b"COPYfresh season handoff")
        launch(expected=55); assert old.read_text() == "saved after ambiguous completion"
        assert native_handoff.read_bytes() == b"COPYfresh season handoff"
        assert (root / "Players/Backup/keep").read_text() == "archive"
        print("Launcher handoff: incomplete SQL, wrong epoch, concurrent cleanup, symlink, missing access, "
              "partial cleanup, retry, duplicate completion and lost activation ACK passed", flush=True)

        # Model an unknown boundary COMMIT result, both before and after application.
        # Each caller closes its connection; only durable state decides recovery.
        recovery_canary.write_text("SQL recovery must not clear files")
        reward_config.write_text("pwipe.preserve=true\n")
        sql("UPDATE account_bound_reward_pwipe_state SET last_processed_at=NULL")
        sql("INSERT INTO account_bound_rewards(account_name,remaining_pwipes,display_name) VALUES('fixturebank',3,'boundary-ack-fixture')")
        grant_id = sql("SELECT id FROM account_bound_rewards WHERE display_name='boundary-ack-fixture'")
        active_god = sql("SELECT pid FROM player_data WHERE name='Freshgod' AND active=1")
        assert int(active_god) > 1004
        sql("INSERT INTO account_bound_reward_summons(grant_id,pid) VALUES(" + grant_id + "," + active_god + ")")
        sql("INSERT INTO player_items(pid,vnum,quantity,name) VALUES(" + active_god + ",1108,1,'boundary-ack-payload')")
        roster_before = sql("SELECT pid,name,active FROM player_data ORDER BY pid")
        payload_before = sql("SELECT id,pid,vnum,name FROM player_items ORDER BY id")
        file_before = old.read_bytes(), native_handoff.read_bytes()
        for mode in ("before", "after"):
            env["PWIPE_TEST_BOUNDARY_ACK"] = mode
            try:
                refusal = epoch_call("wipe", 2, 1, cwd=root)
            finally:
                del env["PWIPE_TEST_BOUNDARY_ACK"]
            assert "Failed to establish durable season reset boundary" in refusal.stderr
            assert status() == ("2:active" if mode == "before" else "3:resetting")
            assert sql("SELECT pid,name,active FROM player_data ORDER BY pid") == roster_before
            assert sql("SELECT id,pid,vnum,name FROM player_items ORDER BY id") == payload_before
            assert sql("SELECT remaining_pwipes FROM account_bound_rewards WHERE id=" + grant_id) == "3"
            assert sql("SELECT COUNT(*) FROM account_bound_reward_summons WHERE grant_id=" + grant_id) == "1"
            assert (old.read_bytes(), native_handoff.read_bytes()) == file_before
        assert sql("SELECT CONCAT(roster_recreated,':',reset_completed_at IS NULL) FROM season_reset_state") == "0:1"
        epoch_call("active", 3, 1)
        launch(epoch=3); assert (old.read_bytes(), native_handoff.read_bytes()) == file_before
        if server:
            import test_flatfile_combat_journey as journey
            direct_root = root / "direct-fence"; direct_root.mkdir()
            journey.make_fixture(direct_root); journey.generate_certificate(direct_root)
            (direct_root / "logs/log").mkdir(parents=True)
            direct_port, tls_port, ws_port = journey.available_ports()
            direct_env = dict(env, DURIS_DEV_PORT=str(direct_port), DURIS_TLS_PORT=str(tls_port),
                              DURIS_WEBSOCKET_PORT=str(ws_port), DURIS_WEBSOCKET_LISTEN_ADDRESS="127.0.0.1",
                              LISTEN_ADDRESS="127.0.0.1")
            direct = subprocess.run([str(server), "--minimal", str(direct_port)], env=direct_env,
                                    cwd=direct_root, capture_output=True, text=True, timeout=30)
            direct_logs = journey.runtime_logs(direct_root)
            assert direct.returncode == 1, (direct.returncode, direct.stdout, direct.stderr, direct_logs)
            assert "season reset state is missing, invalid, or not active; recovery is required" in direct_logs, direct_logs
            assert "Entering game loop" not in direct.stderr
            assert sql("SELECT pid,name,active FROM player_data ORDER BY pid") == roster_before
            assert sql("SELECT id,pid,vnum,name FROM player_items ORDER BY id") == payload_before
            recover(3, 55)
            assert sql("SELECT remaining_pwipes FROM account_bound_rewards WHERE id=" + grant_id) == "2"
            assert sql("SELECT COUNT(*) FROM account_bound_reward_summons WHERE grant_id=" + grant_id) == "0"
            assert sql("SELECT COUNT(*) FROM player_items") == "0"
            recovered_roster = sql("SELECT pid,name,active FROM player_data ORDER BY pid")
            recovered_stamp = sql("SELECT last_processed_at FROM account_bound_reward_pwipe_state")
            recover(3, 55)
            assert sql("SELECT pid,name,active FROM player_data ORDER BY pid") == recovered_roster
            assert sql("SELECT last_processed_at FROM account_bound_reward_pwipe_state") == recovered_stamp
            assert sql("SELECT remaining_pwipes FROM account_bound_rewards WHERE id=" + grant_id) == "2"
            launch(epoch=3, expected=55); assert status() == "3:active"
            old.write_text("fresh epoch-3 sentinel")
            launch(epoch=3, expected=55); assert old.read_text() == "fresh epoch-3 sentinel"
            print("Epoch COMMIT unknown before/after application: no writer resume/readiness, preserved old state; actual direct/launcher fence and same-epoch recovery/one reward decrement/activation/retry passed", flush=True)
        else:
            print("Epoch COMMIT unknown before/after application: no writer resume/readiness, preserved old state and fenced launcher; actual server recovery not requested", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, help="also qualify SQL-only recovery using this built native server")
    args = parser.parse_args()
    run(args.server.resolve() if args.server else None)
