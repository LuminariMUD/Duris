#!/usr/bin/env python3
"""Execute the production last handler; --mysql also checks its queries on disposable SQL."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid

from _paths import ROOT

HARNESS = r'''
#include "cmd/last.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "sql/sql_async.h"
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <ctime>
#include <set>
#include <string>

static std::string output, query;
static std::function<void(P_char, const sql_rows &)> reply;
static bool admit = true;
static constexpr time_t NOW = 1700000000;
extern "C" time_t time(time_t *out) noexcept { if (out) *out = NOW; return NOW; }
void send_to_char(const char *text, P_char) { output += text; }
void send_to_char_f(P_char, const char *format, ...) {
    char text[4096]; va_list args; va_start(args, format);
    vsnprintf(text, sizeof(text), format, args); va_end(args); output += text;
}
std::string sql_format(const char *format, ...) {
    char text[4096]; va_list args; va_start(args, format);
    vsnprintf(text, sizeof(text), format, args); va_end(args); return text;
}
int get_player_pid_from_name(char *name) { return !strcasecmp(name, "Alice") ? 1 : 0; }
bool sql_read_for_at(persistence_query_site, P_char, std::string sql,
                     std::function<void(P_char, const sql_rows &)> done) {
    query = std::move(sql); reply = std::move(done); return admit;
}
static char_data staff{};
static void run(std::string arguments) {
    output.clear(); query.clear(); reply = {};
    do_last(&staff, arguments.data(), 0);
}
static bool contains(const char *text) { return output.find(text) != std::string::npos; }

#ifndef __NO_MYSQL__
static void execute(MYSQL *db, const std::string &sql) {
    if (mysql_real_query(db, sql.data(), sql.size())) {
        fprintf(stderr, "%s\n%s\n", mysql_error(db), sql.c_str()); abort();
    }
}
static sql_rows read(MYSQL *db, const std::string &args) {
    run(args); assert(reply && output.empty());
    execute(db, query);
    MYSQL_RES *result = mysql_store_result(db); assert(result);
    sql_rows rows;
    while (MYSQL_ROW row = mysql_fetch_row(result)) {
        sql_row copied;
        for (unsigned i = 0; i < mysql_num_fields(result); ++i) {
            if (row[i]) copied.fields.emplace_back(row[i]);
            else copied.fields.emplace_back();
        }
        rows.push_back(std::move(copied));
    }
    mysql_free_result(result); reply(&staff, rows); return rows;
}
static void database_tests() {
    MYSQL *db = mysql_init(nullptr); assert(db);
    assert(mysql_real_connect(db, getenv("TEST_DB_HOST"), getenv("TEST_DB_USER"),
                             getenv("TEST_DB_PASSWORD"), getenv("TEST_DB_DATABASE"),
                             atoi(getenv("TEST_DB_PORT")), nullptr, 0));
    execute(db, "SET time_zone='+03:00',sql_mode='STRICT_TRANS_TABLES,ONLY_FULL_GROUP_BY'");
    execute(db, "CREATE TEMPORARY TABLE session_audit_outcome (operation_id BINARY(16) PRIMARY KEY,"
                "pid INT UNSIGNED NOT NULL,event_type TINYINT NOT NULL,occurred_at TIMESTAMP NOT NULL,"
                "account_name VARCHAR(50) COLLATE utf8mb4_unicode_ci NULL)");
    execute(db, "CREATE TEMPORARY TABLE player_data (pid INT PRIMARY KEY,name VARCHAR(20),account_name VARCHAR(50))");
    for (int i = 1; i <= 45; ++i) {
        execute(db, sql_format("INSERT INTO player_data VALUES(%d,'Name%d','newowner')", i, i));
        execute(db, sql_format("INSERT INTO session_audit_outcome VALUES(UNHEX(LPAD(HEX(%d),32,'0')),"
                              "%d,1,FROM_UNIXTIME(%lld),'acct%d')", i, i, (long long)NOW - 10 - i, i));
    }
    execute(db, "UPDATE player_data SET name='Alice' WHERE pid=1");
    auto insert = [&](int id, int pid, int type, int age, const char *account) {
        execute(db, sql_format("INSERT INTO session_audit_outcome VALUES(UNHEX(LPAD(HEX(%d),32,'0')),"
                              "%d,%d,FROM_UNIXTIME(%lld),%s)", id, pid, type, (long long)NOW-age, account));
    };
    insert(100, 1, 1, 3600, "'oldowner'");
    insert(101, 1, 1, 86400, "'firstowner'");
    insert(102, 1, 1, 86401, "'outside'");
    insert(103, 1, 2, 1, "'logout'");
    insert(104, 1, 1, -1, "'future'");
    insert(105, 99, 1, 5, "NULL");
    insert(106, 1, 1, 2, "'shared'");
    insert(107, 2, 1, 2, "'SHARED'"); // Same account, tied time; higher operation wins.
    insert(108, 3, 1, 4, "''");
    auto rows = read(db, "alice 24h");
    assert(rows.size() == 4 && std::string(rows.front()[2]) == "shared");
    assert(std::string(rows.back()[2]) == "firstowner"); // Inclusive lower boundary.
    assert(contains("2023-11-14 22:13:18")); // UTC despite connection +03:00.
    assert(contains("oldowner") && !contains("newowner")); // Event-time ownership.
    assert(read(db, "Alice 1h").size() == 3);
    assert(read(db, "Alice").size() == 5);
    assert(read(db, "Alice 7d").size() == 5);
    rows = read(db, "24h");
    assert(rows.size() == 21 && contains("(deleted)") && contains("(unknown)"));
    assert(std::string(rows[0][3]) == "2" && std::string(rows[1][3]) == "1");
    assert(!contains("logout") && !contains("future"));
    assert(contains("Next: last 24h page 2"));
    size_t total = 0;
    std::set<std::string> seen;
    for (int page = 1; page <= 3; ++page) {
        rows = read(db, "24h page " + std::to_string(page));
        for (size_t i = 0; i < rows.size() && i < 20; ++i) {
            std::string key = std::string(rows[i][0]) + ":" + rows[i][3];
            assert(seen.insert(key).second); ++total;
        }
    }
    assert(total == 51 && contains("End of login history") && !contains("Next:"));
    seen.clear(); total = 0;
    for (int page = 1; page <= 3; ++page) {
        rows = read(db, "unique 24h page " + std::to_string(page));
        if (page == 1) assert(std::string(rows[0][2]) == "SHARED" && std::string(rows[0][3]) == "2");
        for (size_t i = 0; i < rows.size() && i < 20; ++i) {
            assert(rows[i][2] && *rows[i][2]);
            assert(seen.insert(rows[i][2]).second); ++total;
        }
    }
    assert(total == 48 && !seen.count("shared") && !seen.count("outside"));
    assert(read(db, "page 99").empty() && contains("No logins on this page"));
    mysql_close(db);
    puts("PASS: SQL time boundaries, UTC, repeated logins, unique accounts, tie ordering, missing identities and all pages");
}
#endif

int main(int argc, char **) {
    staff.player.level = AVATAR;
#ifdef __NO_MYSQL__
    (void)argc;
    run("unique 7d page 2"); assert(contains("requires MariaDB") && query.empty());
#else
    for (const char *bad : {"0h", "1m", "24", "1.5h", "4294967296d", "24h 7d",
                           "page", "page 0", "page -1", "page +1", "page 1x", "page 4294967296",
                           "page 1 page 2", "unique unique", "unique Alice", "Alice unique",
                           "Alice Bob", "help"}) {
        run(bad); assert(contains("Usage:") && query.empty());
    }
    run("missing"); assert(contains("No such character") && query.empty());
    run("Alice'OR'1"); assert(contains("No such character") && query.empty());
    run(""); assert(reply && output.empty());
    sql_rows rows;
    for (int i=0; i<21; ++i) rows.push_back({{{"1700000000"}, {"Alice"}, {"firstowner"}, {"1"}}});
    rows.back().fields[1] = "Sentinel";
    reply(&staff, rows);
    assert(contains("all retained history") && contains("Next: last page 2"));
    assert(!contains("Previous:") && !contains("Sentinel"));
    run("UNIQUE 7D page 2"); assert(reply && output.empty());
    reply(&staff, {});
    assert(contains("No logins") && contains("Previous: last unique 7d page 1"));
    run("Alice 24h"); assert(reply);
    staff.player.level = 1; reply(&staff, rows); assert(output.empty());
    staff.player.level = AVATAR;
    admit = false; run(""); assert(contains("unavailable right now")); admit = true;
    if (argc > 1) database_tests();
#endif
    staff.player.level = 1; run(""); assert(output.empty() && query.empty());
    staff.player.level = AVATAR; staff.specials.act = PLR_MORTAL;
    run(""); assert(output.empty() && query.empty());
    staff.specials.act = ACT_ISNPC; run(""); assert(output.empty() && query.empty());
    do_last(nullptr, nullptr, 0);
    puts("PASS: production last handler parsing, staff access, deferred output and backend behavior");
}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mysql', action='store_true')
    args = parser.parse_args()
    # The running-game journey exercises dispatch too; keep the numeric command table aligned.
    interp = (ROOT / 'src/cmd/interp.c').read_text()
    assert re.search(r'CMD_GRT\(CMD_LAST, STAT_DEAD \+ POS_PRONE, do_last, AVATAR\)', interp)
    assert '"last",\n\t"\\n"' in interp
    command_id = int(re.search(r'#define CMD_LAST (\d+)', (ROOT / 'src/cmd/interp.h').read_text())[1])
    maximum = int(re.search(r'#define MAX_CMD (\d+)', (ROOT / 'src/core/config.h').read_text())[1])
    assert maximum == command_id + 1
    build = ROOT / 'bin/tests'
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='last-', dir=build) as temporary:
        directory = Path(temporary)
        source = directory / 'harness.cpp'
        source.write_text(HARNESS)
        for flat in (False, True):
            binary = directory / ('flat' if flat else 'sql')
            flags = ['-D__NO_MYSQL__', '-I', str(ROOT / 'src/no_mysql')] if flat else ['-lmysqlclient']
            subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-Isrc',
                            str(source), 'src/cmd/last.c', *flags, '-o', str(binary)],
                           cwd=ROOT, check=True)
            subprocess.run([str(binary)], check=True)
            if args.mysql and not flat:
                env = dict(os.environ)
                assert env['TEST_DB_HOST'] in ('127.0.0.1', 'localhost')
                database = 'last_command_test_' + uuid.uuid4().hex[:12]
                env.update(TEST_DB_DATABASE=database, MYSQL_PWD=env['TEST_DB_PASSWORD'])
                client = ['mysql', '--protocol=tcp', '-h', env['TEST_DB_HOST'], '-P', env['TEST_DB_PORT'],
                          '-u', env['TEST_DB_USER']]
                subprocess.run(client + ['-e', 'CREATE DATABASE ' + database], env=env, check=True)
                try:
                    subprocess.run([str(binary), '--mysql'], env=env, check=True)
                finally:
                    subprocess.run(client + ['-e', 'DROP DATABASE ' + database], env=env, check=True)


if __name__ == '__main__':
    main()
