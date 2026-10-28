#!/usr/bin/env python3
"""Read live, non-reusable allocator watermarks on an owned SQL instance."""
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[2]


def main():
    if not os.environ.get("TEST_DB_HOST"):
        wrapper = ROOT / "tests/async/with_disposable_mariadb.sh"
        os.execv(str(wrapper), [str(wrapper), sys.executable, str(Path(__file__).resolve())])
    assert os.environ["TEST_DB_HOST"] == "127.0.0.1"
    assert os.environ["TEST_DB_PORT"] not in ("3306", "3307")
    database = "allocator_" + uuid.uuid4().hex[:12]
    env = dict(os.environ, MYSQL_PWD=os.environ["TEST_DB_PASSWORD"], TEST_ALLOCATOR_DB=database)
    mysql = ["mysql", "--protocol=tcp", "-h", "127.0.0.1", "-P", env["TEST_DB_PORT"],
             "-u", env["TEST_DB_USER"], "-N", "-B"]

    def sql(query):
        return subprocess.check_output(mysql, input=query, env=env, text=True).strip()

    sql("CREATE DATABASE " + database)
    try:
        for table, column in (("player_data", "pid"), ("account_bound_rewards", "id")):
            sql(f"CREATE TABLE {database}.{table} ({column} BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY)")
        sql(f"CREATE TABLE {database}.ordinary_table (id BIGINT UNSIGNED PRIMARY KEY)")
        source = (ROOT / "src/sql/sql.c").read_text()
        execute = source[source.index("static bool sql_connection_execute("):
                         source.index("static bool sql_connection_execute_affected(")]
        live = source[source.index("static bool sql_use_live_table_statistics("):
                      source.index("static uint64_t pwipe_recovery_epoch")]
        reader = source[source.index("unsigned long long sql_next_auto_increment("):
                        source.index("/* Fail boot unless")]
        program = r'''
#include <mysql/mysql.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdarg>
#include <string>
MYSQL *DB;
MYSQL_RES *db_query(const char *format, ...) {
    char query[4096]; va_list args; va_start(args, format);
    vsnprintf(query, sizeof query, format, args); va_end(args);
    return mysql_real_query(DB, query, strlen(query)) ? nullptr : mysql_store_result(DB);
}
''' + execute + live + reader + r'''
int main(int argc, char **argv) {
    if (argc != 2 || (strcmp(argv[1], "player_data") &&
                     strcmp(argv[1], "account_bound_rewards") &&
                     strcmp(argv[1], "ordinary_table") &&
                     strcmp(argv[1], "missing_table") && strcmp(argv[1], "disconnect"))) return 2;
    DB = mysql_init(nullptr);
    bool reconnect = false;
    mysql_options(DB, MYSQL_OPT_RECONNECT, &reconnect);
    if (!mysql_real_connect(DB, "127.0.0.1", getenv("TEST_DB_USER"),
                            getenv("TEST_DB_PASSWORD"), getenv("TEST_ALLOCATOR_DB"),
                            atoi(getenv("TEST_DB_PORT")), nullptr, 0)) return 2;
    if (!strcmp(argv[1], "disconnect")) {
        const std::string kill = "KILL " + std::to_string(mysql_thread_id(DB));
        mysql_real_query(DB, kill.data(), kill.size());
    }
    printf("%llu\n", sql_next_auto_increment(argv[1]));
    mysql_close(DB);
}
'''
        build = ROOT / "bin/tests"
        build.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="allocator-", dir=build) as directory:
            cpp = Path(directory) / "allocator.cpp"
            cpp.write_text(program)
            binary = cpp.with_suffix("")
            flags = shlex.split(subprocess.check_output(["mysql_config", "--cflags", "--libs"], text=True))
            subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                            str(cpp), *flags, "-o", str(binary)], check=True)

            def read(table):
                return int(subprocess.check_output([str(binary), table], env=env, text=True))

            for table, column in (("player_data", "pid"), ("account_bound_rewards", "id")):
                assert read(table) == 1, "fresh allocator was not available"
                # A separate connection warms MySQL's shared statistics cache.
                sql("SELECT AUTO_INCREMENT FROM information_schema.TABLES WHERE TABLE_SCHEMA='" +
                    database + "' AND TABLE_NAME='" + table + "'")
                sql(f"INSERT INTO {database}.{table}({column}) VALUES(1),(4096); DELETE FROM {database}.{table}")
                assert read(table) == 4097, "deleted identities were lost behind cached metadata"
                sql(f"INSERT INTO {database}.{table}({column}) VALUES({read(table)})")
                assert sql(f"SELECT {column} FROM {database}.{table}") == "4097"
                assert read(table) == 4098
            assert read("missing_table") == 0
            assert read("ordinary_table") == 0
            assert read("disconnect") == 0
        print("Live player/reward allocator counters survive cached metadata and deletion; missing/lost SQL refuses")
    finally:
        sql("DROP DATABASE " + database)


if __name__ == "__main__":
    main()
