#!/usr/bin/env python3
"""Run the real launcher/filesystem handoff on a private DB and synthetic tree.

This qualifies the cross-process handoff, not the real game command or writer drain.
"""
import fcntl
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import migration_runner


def run():
    if not os.environ.get("TEST_DB_HOST"):
        wrapper = ROOT / "tests/async/with_disposable_mariadb.sh"
        os.execv(str(wrapper), [str(wrapper), sys.executable, str(Path(__file__).resolve())])
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
    for path in [ROOT / "migrations/bootstrap_multithread_safe.sql",
                 *(step.apply_path for step in manifest.migrations)]:
        subprocess.run(mysql + ["duris_test"], input=path.read_bytes(), env=env,
                       check=True, stdout=subprocess.DEVNULL)
    import json
    lifecycle = json.loads((ROOT / "migrations/data_lifecycle_manifest.json").read_text())
    expected = {entry["locator"] for entry in lifecycle["entries"] if entry["kind"] == "database_table"}
    actual = set(sql("SHOW TABLES").splitlines())
    assert actual == expected, (actual - expected, expected - actual)
    print(f"Fully migrated MariaDB inventory matches all {len(actual)} lifecycle tables", flush=True)

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
#include "core/runtime_compatibility_contract.h"
#include <openssl/sha.h>
#include "economy/collector_repository.h"
#include "economy/collector_purchase_preparation.h"
#include "persistence/critical_command_repository.h"
#include "player/player_snapshot_codec.h"
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
MYSQL *DB;
#define TRUE true
#define FALSE false
#define LOG_DEBUG 0
#define LOG_STATUS 1
#define OVERLORD 62
#define ACCT_IMMORTAL 0
bool pwipe_crossed_boundary, pwipe_filesystem_ready;
void logit(int, const char *format, ...) {
    va_list args; va_start(args, format); vfprintf(stderr, format, args); va_end(args); fputc(10, stderr);
}
void send_to_all(const char *) {}
int frag_cap_config_reset_level() { return 26; }
bool pwipe_quiesce_writers() { return true; }
void pwipe_resume_writers() {}
bool redis_validate_pwipe_state() { return true; }
bool redis_clear_pwipe_state() { return true; }
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
uint64_t sql_season_epoch() { return current_season_epoch; }
bool sql_begin_transaction() { return qry("START TRANSACTION"); }
bool sql_rollback() { return qry("ROLLBACK"); }
bool sql_commit() { return qry("COMMIT") && !getenv("PWIPE_TEST_LOST_REWARD_ACK"); }
bool account_reward_config_preserve_on_pwipe() { return !getenv("PWIPE_TEST_DELETE_REWARDS"); }
''' + rewards + source[source.index("// One preparation path serves the read-only preflight"):
                            source.index("void sql_log_player_login", source.rindex("bool sql_pwipe(int code_verify)"))] + '''
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
    if (argc != 3) return 2;
    signal(SIGCHLD, reap);
    DB = mysql_init(nullptr);
    if (!mysql_real_connect(DB, getenv("DB_HOST"), getenv("DB_USER"), getenv("DB_PASSWD"),
                            getenv("DB_NAME"), atoi(getenv("DB_PORT")), nullptr, 0)) return 2;
    if (const char *clock = getenv("PWIPE_TEST_NOW")) qry("SET TIMESTAMP=%lld", atoll(clock));
    current_season_epoch = strtoull(argv[2], nullptr, 10);
    bool ok = !strcmp(argv[1], "seed-collectors") ? seed_collectors(strtoull(argv[2],nullptr,10),1004,4) :
              !strcmp(argv[1], "stale-collector") ? stale_collector_purchase() :
              !strcmp(argv[1], "new-collector") ? new_collector_candidate() :
              !strcmp(argv[1], "check-collectors") ? check_collectors() :
              !strcmp(argv[1], "reset-collectors") ? sql_reset_collector_state(true) :
              !strcmp(argv[1], "seed-boons") ? seed_boons() :
              !strcmp(argv[1], "check-boons") ? check_boons() :
              !strcmp(argv[1], "end-boons") ?
                  divine_boon_sql_reset_season(DB, time(nullptr)) == divine_boon_store_result::ok :
              !strcmp(argv[1], "begin") ? sql_begin_pwipe_epoch() :
              !strcmp(argv[1], "ready") ? sql_prepare_pwipe_filesystem() :
              !strcmp(argv[1], "wipe") ? sql_pwipe(1723699) :
              !strcmp(argv[1], "rewards") ? account_bound_rewards_on_successful_pwipe() : sql_load_active_season_state();
    mysql_close(DB);
    return ok ? 0 : 1;
}
''')
    binary = native.with_suffix("")
    build_script = (ROOT / "tests/async/run_collector_repository_schema_mysql.sh").read_text()
    compile_sources = build_script[build_script.index("g++ -std=c++20"):build_script.index('"${MYSQL_LIBS[@]}" -lcrypto')]
    repository_sources = re.findall(r"(?:src|tests/async)/[A-Za-z0-9_/]+\.(?:cpp|c)", compile_sources)
    repository_sources.remove("tests/async/collector_repository_mysql_harness.cpp")
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-ffunction-sections", "-fdata-sections", "-Isrc", "-I/usr/include/mysql", "-pthread",
                    str(native), "src/economy/divine_boon.c", "src/economy/divine_boon_repository.c",
                    "src/economy/collector_purchase_preparation.c", *repository_sources,
                    "-lmysqlclient", "-lcrypto", "-Wl,--gc-sections", "-Wl,--wrap=posix_spawn", "-o", str(binary)], cwd=ROOT, check=True)

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
    epoch_call("ready", 2, 0)
    epoch_call("active", 2, 1)
    print("Native begin/SQL-ready/boot fence passed with real MariaDB", flush=True)

    output = ROOT / "bin/tests"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pwipe-handoff-", dir=output) as temporary:
        root = Path(temporary)
        for directory in ("scripts", "Players/wipers", "Players/a", "Players/Backup", "bin/server"):
            (root / directory).mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "scripts/cycle_mud.sh", root / "scripts/cycle_mud.sh")
        wiper = root / "Players/wipers/wipe_it_all"
        shutil.copy2(ROOT / "Players/wipers/wipe_it_all", wiper)
        original = wiper.read_text()
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
        sql("INSERT INTO associations(id,name,prestige) VALUES(777,'old guild',999)")
        sql("INSERT INTO kingdom_realms(assoc_id,realm_id,hall_vnum,highest_claim,res_wood) "
            "VALUES(777,3,900,80,9999)")
        sql("INSERT INTO kingdom_garrison(assoc_id,slot,guard_class,level) VALUES(777,0,1,50)")
        sql("INSERT INTO kingdom_land(kingdom_id,start_vnum,end_vnum) VALUES(777,900,980)")
        env["PWIPE_TEST_COLLECTOR_BUY"] = str(root / "old-buy.command")
        epoch_call("seed-collectors", 100, 0)
        listing_bytes = sql("SELECT HEX(record_blob) FROM collector_listings WHERE listing_id=101")
        sql("UPDATE collector_listings SET record_blob=REPEAT(CHAR(0),154) WHERE listing_id=101")
        refusal = epoch_call("wipe", 1, 1, cwd=root)
        assert "Collector retirement preflight failed" in refusal.stderr
        assert sql("SELECT CONCAT(season_epoch,':',reset_status) FROM season_reset_state") == "1:active"
        sql("UPDATE collector_listings SET record_blob=UNHEX('" + listing_bytes + "') WHERE listing_id=101")
        epoch_call("seed-boons", 1, 0)
        boon_bytes = sql("SELECT HEX(snapshot) FROM divine_boon_state WHERE state_id=1")
        sql("UPDATE divine_boon_state SET snapshot=0x00 WHERE state_id=1")
        refusal = epoch_call("wipe", 1, 1, cwd=root)
        assert "Divine Boon state cannot be safely retired" in refusal.stderr
        assert sql("SELECT CONCAT(season_epoch,':',reset_status) FROM season_reset_state") == "1:active"
        sql("UPDATE divine_boon_state SET snapshot=UNHEX('" + boon_bytes + "') WHERE state_id=1")
        epoch_call("wipe", 1, 0, cwd=root)
        assert sql("SELECT alignment FROM zones WHERE number=900") == "0"
        assert sql("SELECT CONCAT(season_epoch,':',reset_status,':',reset_completed_at IS NOT NULL) "
                   "FROM season_reset_state WHERE state_id=1") == "2:resetting:1"
        print("Actual native SQL reset/preflight/postflight passed without shared-writer admission", flush=True)
        assert sql("SELECT COUNT(*) FROM player_data WHERE active=1") == "2"
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
        print("Overlord recreation: exact 62 only, new PID, clean balances/progression, account mapping and freed mortal name passed", flush=True)
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
        print("Mid-recreation failure rolled back the entire roster and kept startup fenced", flush=True)
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
        sql("ALTER TABLE collector_ledger RENAME COLUMN closed_reason TO fixture_closed_reason")
        try:
            epoch_call("wipe", 3, 1, cwd=root)
            assert sql("SELECT season_epoch,reset_status FROM season_reset_state WHERE state_id=1") == before
        finally:
            sql("ALTER TABLE collector_ledger RENAME COLUMN fixture_closed_reason TO closed_reason")
        print("Delegated collector ledger schema drift rejected before epoch advance", flush=True)



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

        (root / "Players/Backup/keep").write_text("archive")
        old = root / "Players/a/old"

        def prepare(ready=True):
            old.write_text("old season")
            sql("UPDATE season_reset_state SET season_epoch=2,reset_status='resetting',"
                "reset_started_at=UTC_TIMESTAMP(6),reset_completed_at=" +
                ("UTC_TIMESTAMP(6)" if ready else "NULL") + " WHERE state_id=1")

        def launch(epoch=2, expected=58, environment=None):
            result = subprocess.run([str(root / "scripts/cycle_mud.sh"), "--dev", "--resume-pwipe", str(epoch)],
                                    env=environment or env, text=True, capture_output=True, timeout=30)
            assert result.returncode == expected, (result.returncode, result.stdout, result.stderr)
            return result

        def status():
            return sql("SELECT CONCAT(season_epoch,':',reset_status) FROM season_reset_state WHERE state_id=1")

        prepare(False); launch(); assert old.exists() and status() == "2:resetting"
        prepare(); launch(epoch=3); assert old.exists()
        with (root / "bin/server/.pwipe.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            launch(); assert old.exists()
        (root / "Ships").symlink_to(root / "Players/Backup")
        launch(); assert old.exists() and status() == "2:resetting"
        (root / "Ships").unlink()
        wiper.chmod(0o600); launch(); assert old.exists(); wiper.chmod(0o700)
        # Fail after real cleanup: no activation, and a repaired retry finishes once.
        wiper.write_text(original.replace('echo "wipe_it_all: filesystem cleanup completed"', 'exit 1'))
        launch(); assert not old.exists() and status() == "2:resetting"
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
        launch(expected=55); assert old.read_text() == "saved after ambiguous completion"
        assert (root / "Players/Backup/keep").read_text() == "archive"
        print("Launcher handoff: incomplete SQL, wrong epoch, concurrent cleanup, symlink, missing access, "
              "partial cleanup, retry, duplicate completion and lost activation ACK passed", flush=True)


if __name__ == "__main__":
    run()
