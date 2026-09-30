#!/usr/bin/env python3
"""Execute the account-projection repair against isolated fixture tables."""

from _paths import SRC
from pathlib import Path
import os
import re
import shlex
import subprocess
import tempfile
import uuid

from contract_text import index

ROOT = Path(__file__).resolve().parents[2]
source_text = (SRC / "sql_player.c").read_text(
    encoding="utf-8", errors="replace"
)
mysql_source_text = source_text[source_text.index("\n// globals\n") :]


def body(text, signature):
    """Extract one production function definition for the isolated harness."""
    start = index(text, signature)
    while ";" in text[start + len(signature) : text.index("{", start)]:
        start = index(text, signature, start + len(signature))
    opening = text.index("{", start)
    depth = 0
    for position in range(opening, len(text)):
        if text[position] == "{":
            depth += 1
        elif text[position] == "}":
            depth -= 1
            if depth == 0:
                return text[start : position + 1]
    raise AssertionError(f"unterminated definition: {signature}")


repair = body(
    mysql_source_text,
    "unsigned int sql_repair_account_character_projection(MYSQL *connection,",
)

harness = f'''\
#include <mysql/mysql.h>

#include <cassert>
#include <climits>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>

MYSQL *DB = nullptr;

std::string sql_format(const char *format, ...)
{{
    va_list args;
    va_start(args, format);
    char text[8192];
    const int size = std::vsnprintf(text, sizeof(text), format, args);
    va_end(args);
    assert(size >= 0 && static_cast<size_t>(size) < sizeof(text));
    return text;
}}

/* Execute one extracted production repair statement, as the writer's sql_execute(). */
unsigned int sql_execute(MYSQL *connection, const std::string &statement)
{{
    if (mysql_query(connection, statement.c_str()) != 0)
    {{
        std::cerr << "repair query failed: " << mysql_error(connection) << '\\n';
        return mysql_errno(connection);
    }}
    if (MYSQL_RES *result = mysql_store_result(connection))
        mysql_free_result(result);
    return mysql_errno(connection);
}}

{repair}

/* The repair as the account read runs it: the mappings changed, or -1. */
static int repair(const char *account)
{{
    char escaped[256];
    mysql_real_escape_string(DB, escaped, account, std::strlen(account));
    int repaired = 0;
    return sql_repair_account_character_projection(DB, escaped, &repaired) ? -1 : repaired;
}}

/* Return one required database setting for the isolated fixture. */
static const char *required_env(const char *name)
{{
    const char *value = std::getenv(name);
    assert(value && *value);
    return value;
}}

/* Execute fixture SQL or terminate with the client error. */
static void execute(const char *query)
{{
    if (mysql_query(DB, query) != 0)
    {{
        std::cerr << "fixture query failed: " << mysql_error(DB) << '\\n';
        std::abort();
    }}
}}

/* Read one integral scalar from the fixture database. */
static long scalar(const char *query)
{{
    execute(query);
    MYSQL_RES *result = mysql_store_result(DB);
    assert(result);
    MYSQL_ROW row = mysql_fetch_row(result);
    assert(row && row[0]);
    const long value = std::strtol(row[0], nullptr, 10);
    mysql_free_result(result);
    return value;
}}

/* Exercise safe baseline establishment and projection repair behavior. */
int main()
{{
    DB = mysql_init(nullptr);
    assert(DB);
    const char *port_text = std::getenv("DB_PORT");
    const unsigned int port = port_text ? std::strtoul(port_text, nullptr, 10) : 3306;
    assert(mysql_real_connect(DB, required_env("DB_HOST"), required_env("DB_USER"),
                              required_env("DB_PASSWD"), required_env("DB_NAME"),
                              port, nullptr, 0));

    execute("CREATE TEMPORARY TABLE player_data ("
            "pid INT NOT NULL PRIMARY KEY, name VARCHAR(80) NOT NULL, "
            "account_name VARCHAR(255) NOT NULL, active TINYINT NOT NULL, "
            "copper INT NOT NULL DEFAULT 0, silver INT NOT NULL DEFAULT 0, "
            "gold INT NOT NULL DEFAULT 0, platinum INT NOT NULL DEFAULT 0, "
            "wallet_revision BIGINT UNSIGNED NOT NULL DEFAULT 0, "
            "epics BIGINT NOT NULL DEFAULT 0, "
            "epic_revision BIGINT UNSIGNED NOT NULL DEFAULT 0, "
            "frags BIGINT NOT NULL DEFAULT 0, "
            "frag_revision BIGINT UNSIGNED NOT NULL DEFAULT 0)");
    execute("CREATE TEMPORARY TABLE account_characters ("
            "id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY, "
            "account_name VARCHAR(255) NOT NULL, pid INT NOT NULL, "
            "char_name VARCHAR(80) NOT NULL, created_at DATETIME NOT NULL, "
            "deleted_at DATETIME NULL, KEY account_character_pid (pid), "
            "UNIQUE KEY account_character_name (char_name))");
    execute("CREATE TEMPORARY TABLE currency_wallet_baseline ("
            "pid INT NOT NULL PRIMARY KEY, opening_copper INT, opening_silver INT, "
            "opening_gold INT, opening_platinum INT, opening_revision BIGINT UNSIGNED)");
    execute("CREATE TEMPORARY TABLE epic_balance_baseline ("
            "pid INT NOT NULL PRIMARY KEY, opening_balance BIGINT, "
            "opening_revision BIGINT UNSIGNED)");
    execute("CREATE TEMPORARY TABLE combat_frag_baseline ("
            "pid INT NOT NULL PRIMARY KEY, opening_frags BIGINT, "
            "opening_revision BIGINT UNSIGNED)");
    execute("CREATE TEMPORARY TABLE currency_ledger (pid INT)");
    execute("CREATE TEMPORARY TABLE epic_ledger (pid INT)");
    execute("CREATE TEMPORARY TABLE combat_frag_ledger (pid INT)");
    execute("INSERT INTO player_data(pid,name,account_name,active) VALUES "
            "(101,'RepairHero','RepairAcct',1),"
            "(102,'MovedHero','RepairAcct',1),"
            "(103,'DeletedHero','RepairAcct',1),"
            "(104,'InactiveHero','RepairAcct',0)");
    execute("INSERT INTO player_data(pid,name,account_name,active,frags,frag_revision) "
            "VALUES(105,'HistoryHero','RepairAcct',1,9,1)");
    execute("INSERT INTO account_characters "
            "(account_name,pid,char_name,created_at,deleted_at) VALUES "
            "('WrongAcct',102,'MovedHero',NOW(),NULL),"
            "('RepairAcct',103,'DeletedHero',NOW(),NOW())");
    // Renames used to leave a second active mapping for the same pid, like
    // production, whose account_characters is unique on char_name only.
    execute("INSERT INTO player_data(pid,name,account_name,active) VALUES "
            "(106,'RenamedNew','RepairAcct',1),(107,'Twicenamed','RepairAcct',1)");
    execute("INSERT INTO account_characters "
            "(account_name,pid,char_name,created_at,deleted_at) VALUES "
            "('RepairAcct',106,'RenamedOld',NOW(),NULL),"
            "('RepairAcct',106,'RenamedNew',NOW(),NULL),"
            "('RepairAcct',107,'Firstname',NOW(),NULL),"
            "('RepairAcct',107,'Secondname',NOW(),NULL)");
    execute("INSERT INTO combat_frag_baseline VALUES(102,77,0)");
    execute("INSERT INTO combat_frag_ledger VALUES(105)");

    assert(repair("repairacct") > 0);
    assert(mysql_commit(DB) == 0);

    // These reload queries have no process-local account/character state. They
    // prove the missing and misassigned projections were written to the database.
    assert(scalar("SELECT COUNT(*) FROM account_characters "
                  "WHERE account_name='RepairAcct' AND deleted_at IS NULL") == 4);
    // One active mapping per renamed character, under its current name.
    assert(scalar("SELECT COUNT(*) FROM account_characters WHERE pid=106") == 1);
    assert(scalar("SELECT COUNT(*) FROM account_characters "
                  "WHERE pid=106 AND char_name='RenamedNew' AND deleted_at IS NULL") == 1);
    assert(scalar("SELECT COUNT(*) FROM account_characters WHERE pid=107") == 1);
    assert(scalar("SELECT COUNT(*) FROM account_characters "
                  "WHERE pid=107 AND char_name='Twicenamed' AND deleted_at IS NULL") == 1);
    assert(scalar("SELECT COUNT(*) FROM account_characters "
                  "WHERE pid=101 AND account_name='RepairAcct' AND deleted_at IS NULL") == 1);
    assert(scalar("SELECT COUNT(*) FROM account_characters "
                  "WHERE pid=102 AND account_name='RepairAcct' AND deleted_at IS NULL") == 1);
    assert(scalar("SELECT COUNT(*) FROM account_characters "
                  "WHERE pid=103 AND deleted_at IS NULL") == 0);
    assert(scalar("SELECT COUNT(*) FROM account_characters "
                  "WHERE pid=103 AND deleted_at IS NOT NULL") == 1);
    assert(scalar("SELECT COUNT(*) FROM account_characters WHERE pid=104") == 0);
    assert(scalar("SELECT COUNT(*) FROM account_characters WHERE pid=105") == 0);
    assert(scalar("SELECT COUNT(*) FROM currency_wallet_baseline "
                  "WHERE pid IN (101,102)") == 2);
    assert(scalar("SELECT COUNT(*) FROM epic_balance_baseline "
                  "WHERE pid IN (101,102)") == 2);
    assert(scalar("SELECT COUNT(*) FROM combat_frag_baseline "
                  "WHERE pid=101 AND opening_frags=0 AND opening_revision=0") == 1);
    assert(scalar("SELECT opening_frags FROM combat_frag_baseline WHERE pid=102") == 77);
    assert(scalar("SELECT COUNT(*) FROM combat_frag_baseline WHERE pid=105") == 0);
    assert(repair("RepairAcct") == 0);
    assert(scalar("SELECT opening_frags FROM combat_frag_baseline WHERE pid=102") == 77);
    assert(repair("EmptyAcct") == 0);

    mysql_close(DB);
    DB = nullptr;
    std::cout << "account character projection MySQL/MariaDB behavior passed\\n";
    return 0;
}}
'''

# MySQL cannot reopen a TEMPORARY table within the INSERT/SELECT used by the
# production repair. Give ordinary fixture tables unique names instead, and
# rewrite only their SQL identifiers in both the extracted function and fixture.
# Cleanup runs even when the native harness aborts; configured game tables are
# never created, shadowed, or dropped by this harness.
fixture_tables = re.findall(r"CREATE TEMPORARY TABLE (\w+)", harness)
prefix = "projection_" + uuid.uuid4().hex[:12] + "_"
table_names = {name: prefix + name for name in fixture_tables}
harness = re.sub(
    r"\b(" + "|".join(map(re.escape, fixture_tables)) + r")\b",
    lambda match: table_names[match.group()],
    harness,
).replace("CREATE TEMPORARY TABLE", "CREATE TABLE")

build_root = ROOT / "bin" / "tests"
build_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="account-projection-", dir=build_root) as directory:
    temp = Path(directory)
    source = temp / "projection_repair.cpp"
    binary = temp / "projection_repair"
    source.write_text(harness, encoding="utf-8")
    cflags = shlex.split(
        subprocess.check_output(["mysql_config", "--cflags"], text=True)
    )
    libs = shlex.split(subprocess.check_output(["mysql_config", "--libs"], text=True))
    compile_result = subprocess.run(
        [
            "g++",
            "-std=c++20",
            "-O1",
            "-Wall",
            "-Wextra",
            "-Werror",
            *cflags,
            str(source),
            *libs,
            "-o",
            str(binary),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert compile_result.returncode == 0, compile_result.stderr
    try:
        subprocess.run([str(binary)], check=True, env=os.environ.copy())
    finally:
        subprocess.run(
            ["mysql", "-h", os.environ["DB_HOST"],
             "-P", os.environ.get("DB_PORT", "3306"),
             "-u", os.environ["DB_USER"], os.environ["DB_NAME"]],
            input="DROP TABLE IF EXISTS " + ",".join(table_names.values()) + ";",
            text=True,
            env={**os.environ, "MYSQL_PWD": os.environ["DB_PASSWD"]},
            check=True,
        )
