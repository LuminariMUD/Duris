#!/usr/bin/env python3
"""Game-thread SQL is queued on the writer: in order, never waited for.

Links the production sql_async.c with the real persistence writer and records what the
writer applies, in order, with the repository stubbed out.
"""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, rel


HARNESS = r'''
#include "sql/sql_async.h"
#include "player/player_save_worker.h"
#include "player/player_snapshot_repository.h"
#include "sql/sql.h"

#include <atomic>
#include <cassert>
#include <chrono>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

static int connection = 0;
MYSQL *DB = reinterpret_cast<MYSQL *>(&connection);
P_char character_list = nullptr;
static std::mutex applied_mutex;
static std::vector<std::string> applied;
static std::vector<std::string> told;
static std::atomic<int> lost_connections{0};

void logit(const char *, const char *, ...) {}
void send_to_char(const char *text, P_char) { told.push_back(text); }

// The writer-side SQL, recorded: a failure and a lost connection on request.
unsigned int sql_execute(MYSQL *, const std::string &statement)
{
    std::lock_guard<std::mutex> lock(applied_mutex);
    applied.push_back(statement);
    return 0;
}

unsigned int sql_select(MYSQL *, const std::string &query, sql_rows *rows)
{
    if (query == "SELECT lost" && lost_connections++ == 0)
        return 2013;
    if (query == "SELECT broken")
        return 1064;
    std::lock_guard<std::mutex> lock(applied_mutex);
    applied.push_back(query);
    sql_row row;
    row.fields.emplace_back(std::to_string(applied.size()));
    row.fields.emplace_back();
    rows->push_back(row);
    return 0;
}

player_save_apply_result sql_work_repository_apply_from_pool(const sql_work &work)
{
    const unsigned int error_code = work(reinterpret_cast<MYSQL *>(&connection));
    if (!error_code)
        return {player_save_apply_outcome::applied, 0, 0};
    return {error_code == 2013 ? player_save_apply_outcome::retryable_failure
                               : player_save_apply_outcome::terminal_failure,
            0, error_code};
}

static player_save_apply_result no_saves(const player_snapshot &, void *)
{
    return {player_save_apply_outcome::applied, 0, 0};
}

static void wait_for_writer()
{
    assert(persistence_writer_wait_idle(5000));
}

int main()
{
    assert(player_save_worker_init(no_saves, nullptr));
    char_data ch = {};
    ch.runtime_id = 7;
    character_list = &ch;

    // Writes and reads apply in the order they were queued, so a read sees the writes
    // queued before it. Its callback runs on a later pulse, never inside the call.
    std::vector<std::string> seen;
    assert(sql_queue("INSERT INTO t VALUES (%d)", 1));
    assert(sql_read(sql_format("SELECT %s", "one"),
                    [&](bool ok, const sql_rows &rows)
                    {
                        assert(ok && rows.size() == 1 && !rows[0][1] && !rows[0][9]);
                        seen.push_back(std::string("one:") + rows[0][0]);
                    }));
    assert(sql_queue_statements({"UPDATE t SET a=2", "DELETE FROM t WHERE a=3"}));
    assert(seen.empty());
    wait_for_writer();
    assert((applied == std::vector<std::string>{"INSERT INTO t VALUES (1)", "SELECT one",
                                                "UPDATE t SET a=2",
                                                "DELETE FROM t WHERE a=3"}));
    assert(seen.empty() && sql_async_pulse() == 1);
    assert((seen == std::vector<std::string>{"one:2"}));

    // A lost connection is retried and delivered once; a failed read tells the
    // character and does not call back.
    assert(sql_read_for(&ch, "SELECT lost",
                        [&](P_char live, const sql_rows &) { seen.push_back("lost"); assert(live == &ch); }));
    assert(sql_read_for(&ch, "SELECT broken",
                        [&](P_char, const sql_rows &) { seen.push_back("broken"); }));
    wait_for_writer();
    assert(sql_async_pulse() == 2);
    assert(seen.back() == "lost" && seen.size() == 2 && lost_connections == 2);
    assert(told.size() == 1);

    // Work that reads before it writes runs on the writer, in its place in the queue.
    assert(sql_queue_work([](MYSQL *connection) -> unsigned int
                          {
                              sql_rows found;
                              if (const unsigned int error_code =
                                      sql_select(connection, "SELECT id", &found))
                                  return error_code;
                              return sql_execute(connection,
                                                 std::string("UPDATE t SET id=") + found[0][0]);
                          }));
    wait_for_writer();
    assert(applied.back() == "UPDATE t SET id=6");

    // A character who left gets nothing.
    assert(sql_read_for(&ch, "SELECT gone", [&](P_char, const sql_rows &) { seen.push_back("gone"); }));
    character_list = nullptr;
    wait_for_writer();
    assert(sql_async_pulse() == 1 && seen.size() == 2);

    // Without a database nothing is queued.
    DB = nullptr;
    assert(!sql_queue("INSERT INTO t VALUES (2)"));
    assert(!sql_read("SELECT two", [](bool, const sql_rows &) {}));
    player_save_worker_shutdown();
    player_save_worker_reset_for_tests();
    return 0;
}
'''


with tempfile.TemporaryDirectory(prefix="duris-sql-async-") as temporary:
    source = Path(temporary) / "harness.cpp"
    binary = Path(temporary) / "harness"
    source.write_text(HARNESS)
    subprocess.run(
        [
            "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
            "-Wno-missing-field-initializers", "-g", "-O1", "-pthread",
            "-fsanitize=address,undefined", "-ffunction-sections", "-fdata-sections",
            "-Isrc", "-I/usr/include/mysql", str(source), rel("sql_async.c"),
            rel("player_save_worker.c"), rel("persistence_observability.c"),
            "-Wl,--gc-sections", "-lmysqlclient", "-o", str(binary),
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run([str(binary)], check=True, timeout=60)
print("[PASS] game-thread writes and reads apply on the writer in the order they were queued")
print("[PASS] a read's rows come back on a later pulse; a lost connection is retried once")
print("[PASS] a failed read tells the character; one who left gets nothing")
