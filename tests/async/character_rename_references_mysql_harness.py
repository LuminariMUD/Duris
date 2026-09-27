#!/usr/bin/env python3
"""Run a character rename's reference updates against MySQL/MariaDB tables.

sql_rename_character() renames a character in one transaction, and
sql_rename_character_references() carries over what else the old name keys:
the account mapping that login reads, a personal locker and its access list, the
character's own locker grants, their guild roster row and top-fragger credit,
and their leaderboard name.  Before, a rename left the account mapping under the
old name, the next save added a second mapping for the new one, and the account
could no longer load.

This runs the real function against fixture tables shaped like production:
account_characters is unique on char_name only, not on pid.
"""

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
source_text = (SRC / "sql_player.c").read_text(encoding="utf-8", errors="replace")
mysql_source_text = source_text[source_text.index("\n// globals\n") :]


def body(text, signature):
    """Extract one production function definition for the isolated harness."""
    start = index(text, signature)
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


references = body(mysql_source_text, "static bool sql_rename_character_references(")

harness = f'''\
#include <mysql/mysql.h>

#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>

MYSQL *DB = nullptr;

/* Escape one value through the live client connection. */
char *sql_escape_string(const char *value)
{{
    if (!DB || !value)
        return nullptr;
    const size_t length = std::strlen(value);
    char *escaped = static_cast<char *>(std::malloc(length * 2 + 1));
    if (!escaped)
        return nullptr;
    mysql_real_escape_string(DB, escaped, value, length);
    return escaped;
}}

/* Execute one extracted production statement. */
static bool sql_run_query(const char *query)
{{
    if (mysql_query(DB, query) == 0)
        return true;
    std::cerr << "rename query failed: " << mysql_error(DB) << '\\n';
    return false;
}}

{references}

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

int main()
{{
    DB = mysql_init(nullptr);
    assert(DB);
    const char *port_text = std::getenv("DB_PORT");
    const unsigned int port = port_text ? std::strtoul(port_text, nullptr, 10) : 3306;
    assert(mysql_real_connect(DB, required_env("DB_HOST"), required_env("DB_USER"),
                              required_env("DB_PASSWD"), required_env("DB_NAME"),
                              port, nullptr, 0));

    const char *collation = " DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci";
    const std::string tables[] = {{
        "CREATE TEMPORARY TABLE account_characters ("
        "id INT NOT NULL AUTO_INCREMENT PRIMARY KEY, account_name VARCHAR(255) NOT NULL, "
        "pid BIGINT NOT NULL, char_name VARCHAR(255) NOT NULL, "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, deleted_at DATETIME NULL, "
        "UNIQUE KEY idx_char_name_unique (char_name))",
        "CREATE TEMPORARY TABLE accounts (account_name VARCHAR(255) NOT NULL PRIMARY KEY)",
        "CREATE TEMPORARY TABLE lockers ("
        "id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY, "
        "locker_name VARCHAR(100) NOT NULL, owner_pid INT NULL, owner_assoc_id INT NULL, "
        "UNIQUE KEY locker_name (locker_name))",
        "CREATE TEMPORARY TABLE locker_access (owner VARCHAR(255) NOT NULL, "
        "visitor VARCHAR(255) NOT NULL, PRIMARY KEY (owner, visitor))",
        "CREATE TEMPORARY TABLE guild_members ("
        "id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY, guild_id INT UNSIGNED NOT NULL, "
        "player_name VARCHAR(64) NOT NULL, player_pid INT UNSIGNED NULL, "
        "UNIQUE KEY uk_guild_members_name (guild_id, player_name))",
        "CREATE TEMPORARY TABLE guilds (id INT UNSIGNED NOT NULL PRIMARY KEY, "
        "topfragger VARCHAR(64) NOT NULL DEFAULT '')",
        "CREATE TEMPORARY TABLE frag_leaderboard ("
        "id INT NOT NULL AUTO_INCREMENT PRIMARY KEY, pid BIGINT NOT NULL, "
        "char_name VARCHAR(255) NOT NULL, UNIQUE KEY pid (pid))",
    }};
    for (const std::string &table : tables)
        execute((table + collation).c_str());

    // Veridian (pid 7) is renamed to Qelvarin.  An earlier rename left a second
    // active mapping for the same pid.  Friend (pid 8) is someone else.
    execute("INSERT INTO accounts VALUES ('Acct'),('Sharedname')");
    execute("INSERT INTO account_characters (account_name,pid,char_name) VALUES "
            "('Acct',7,'Veridian'),('Acct',7,'Oldveridian'),('Acct',8,'Friend'),"
            "('Acct',10,'Sharedname')");
    execute("INSERT INTO lockers (locker_name,owner_pid) VALUES "
            "('Veridian.locker',7),('Friend.locker',8),('Nopidhero.locker',NULL)");
    execute("INSERT INTO locker_access VALUES "
            "('Veridian.locker','Friend'),('Friend.locker','veridian'),"
            "('Other.locker','Veridian'),('Other.locker','Qelvarin'),"
            "('Friend.locker','Sharedname')");
    execute("INSERT INTO guild_members (guild_id,player_name,player_pid) VALUES "
            "(1,'Veridian',7),(1,'Friend',8),(2,'Nopidhero',NULL),(2,'Sharedname',10)");
    execute("INSERT INTO guilds VALUES (1,'Veridian'),(2,'Friend')");
    execute("INSERT INTO frag_leaderboard (pid,char_name) VALUES (7,'Veridian'),(8,'Friend')");

    assert(sql_rename_character_references(7, "Veridian", "Qelvarin"));

    // One login mapping, under the new name; nobody else's changes.
    assert(scalar("SELECT COUNT(*) FROM account_characters WHERE pid=7") == 1);
    assert(scalar("SELECT COUNT(*) FROM account_characters "
                  "WHERE pid=7 AND char_name='Qelvarin' AND deleted_at IS NULL") == 1);
    assert(scalar("SELECT COUNT(*) FROM account_characters "
                  "WHERE pid=8 AND char_name='Friend'") == 1);
    // The personal locker, its access list, and the character's own grants
    // move; a grant the new name already held absorbs the old one.
    assert(scalar("SELECT COUNT(*) FROM lockers "
                  "WHERE locker_name='Qelvarin.locker' AND owner_pid=7") == 1);
    assert(scalar("SELECT COUNT(*) FROM lockers WHERE locker_name='Veridian.locker'") == 0);
    assert(scalar("SELECT COUNT(*) FROM locker_access "
                  "WHERE owner='Qelvarin.locker' AND visitor='Friend'") == 1);
    assert(scalar("SELECT COUNT(*) FROM locker_access "
                  "WHERE owner='Friend.locker' AND visitor='Qelvarin'") == 1);
    assert(scalar("SELECT COUNT(*) FROM locker_access WHERE visitor='Veridian'") == 0);
    assert(scalar("SELECT COUNT(*) FROM locker_access "
                  "WHERE owner='Other.locker' AND visitor='Qelvarin'") == 1);
    // The guild roster and top-fragger credit follow; the leaderboard too.
    assert(scalar("SELECT COUNT(*) FROM guild_members "
                  "WHERE guild_id=1 AND player_name='Qelvarin' AND player_pid=7") == 1);
    assert(scalar("SELECT COUNT(*) FROM guild_members WHERE player_name='Friend'") == 1);
    assert(scalar("SELECT COUNT(*) FROM guilds WHERE id=1 AND topfragger='Qelvarin'") == 1);
    assert(scalar("SELECT COUNT(*) FROM guilds WHERE id=2 AND topfragger='Friend'") == 1);
    assert(scalar("SELECT COUNT(*) FROM frag_leaderboard "
                  "WHERE pid=7 AND char_name='Qelvarin'") == 1);

    // A roster row from before pids were stored is matched by name, and a
    // legacy locker without an owner pid by its name.
    assert(sql_rename_character_references(9, "Nopidhero", "Newhero"));
    assert(scalar("SELECT COUNT(*) FROM guild_members "
                  "WHERE guild_id=2 AND player_name='Newhero'") == 1);
    assert(scalar("SELECT COUNT(*) FROM lockers WHERE locker_name='Newhero.locker'") == 1);

    // A grant that also names an account is ambiguous, and stays with it.
    assert(sql_rename_character_references(10, "Sharedname", "Newshared"));
    assert(scalar("SELECT COUNT(*) FROM locker_access "
                  "WHERE owner='Friend.locker' AND visitor='Sharedname'") == 1);
    assert(scalar("SELECT COUNT(*) FROM guild_members "
                  "WHERE guild_id=2 AND player_name='Newshared' AND player_pid=10") == 1);
    assert(scalar("SELECT COUNT(*) FROM account_characters "
                  "WHERE pid=10 AND char_name='Newshared'") == 1);

    // A name another character's mapping holds cannot be taken: the statement
    // fails, for the transaction around it to roll back.
    assert(!sql_rename_character_references(8, "Friend", "Qelvarin"));

    mysql_close(DB);
    DB = nullptr;
    std::cout << "character rename references MySQL/MariaDB behavior passed\\n";
    return 0;
}}
'''

# Ordinary fixture tables with unique names, as in the account projection
# harness, so the configured game tables are never created, shadowed or dropped.
fixture_tables = re.findall(r"CREATE TEMPORARY TABLE (\w+)", harness)
prefix = "rename_" + uuid.uuid4().hex[:12] + "_"
table_names = {name: prefix + name for name in fixture_tables}
harness = re.sub(
    r"\b(" + "|".join(map(re.escape, fixture_tables)) + r")\b",
    lambda match: table_names[match.group()],
    harness,
).replace("CREATE TEMPORARY TABLE", "CREATE TABLE")

build_root = ROOT / "bin" / "tests"
build_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="character-rename-", dir=build_root) as directory:
    temp = Path(directory)
    source = temp / "rename_references.cpp"
    binary = temp / "rename_references"
    source.write_text(harness, encoding="utf-8")
    cflags = shlex.split(subprocess.check_output(["mysql_config", "--cflags"], text=True))
    libs = shlex.split(subprocess.check_output(["mysql_config", "--libs"], text=True))
    compile_result = subprocess.run(
        ["g++", "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", *cflags, str(source),
         *libs, "-o", str(binary)],
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
