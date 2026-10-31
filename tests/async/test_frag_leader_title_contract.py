#!/usr/bin/env python3
"""Exercise the frag report and title queries with mortal and staff fixtures."""

from _paths import ROOT, SRC, extract_function
from pathlib import Path
import sqlite3
import subprocess
import tempfile


SOURCE = (SRC / "fraglist.c").read_text()

# Capture queries from the actual C++ functions, including the configured mortal
# boundary. SQLite executes their SELECT predicates, sorting and limits below.
HARNESS = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "core/config.h"
#include "sql/sql_async.h"
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <iostream>

constexpr int max_frag_size = 10;
P_char find_character_by_runtime_id(uint64_t) { return nullptr; }
bool isname(const char *, const char *) { return false; }

std::string sql_format(const char *format, ...)
{
    char buffer[4096];
    va_list args;
    va_start(args, format);
    int length = vsnprintf(buffer, sizeof buffer, format, args);
    va_end(args);
    assert(length >= 0 && static_cast<size_t>(length) < sizeof buffer);
    return buffer;
}

bool sql_read_at(persistence_query_site, std::string query,
                 std::function<void(bool, const sql_rows &)>)
{
    std::cout << query << '\n';
    return true;
}

unsigned int sql_select(MYSQL *, const std::string &query, sql_rows *)
{
    std::cout << query << '\n';
    return 0;
}
'''
HARNESS += extract_function("fraglist.c", "static void check_frag_position(")
HARNESS += extract_function("redis_report_cache.c", "bool fraglist_leaders(")
HARNESS += r'''
int main(int argc, char **argv)
{
    char_data character{};
    check_frag_position(&character);
    sql_rows rows;
    assert(fraglist_leaders(nullptr, argc > 1 ? argv[1] : nullptr, &rows));
}
'''

database = sqlite3.connect(":memory:")
database.execute("""CREATE TABLE frag_leaderboard (
    id INTEGER PRIMARY KEY, char_name TEXT, total_frags INTEGER, level INTEGER,
    racewar INTEGER, race TEXT, class TEXT, deleted_at TEXT)""")
fixtures = [
    (index, f"Mortal{index}", (index - 6) * 100, 56 if index == 12 else 30,
     1 if index % 2 else 2, "human" if index % 2 else "elf",
     "warrior" if index % 2 else "ranger", None)
    for index in range(1, 13)
]
fixtures += [
    (100 + level, f"Staff{level}", 100000 if level % 2 else -50000,
     level, 1, "human", "warrior", None)
    for level in range(57, 63)
]
fixtures += [
    (200, "DeletedHigh", 200000, 56, 2, "elf", "warrior", "deleted"),
    (201, "DeletedLow", -200000, 56, 2, "elf", "warrior", "deleted"),
]
database.executemany("INSERT INTO frag_leaderboard VALUES (?,?,?,?,?,?,?,?)", fixtures)

directory = ROOT / "bin" / "tests"
directory.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="frag-queries-", dir=directory) as temporary:
    source = Path(temporary) / "queries.cpp"
    binary = Path(temporary) / "queries"
    source.write_text(HARNESS)
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Isrc",
        str(source), "-o", str(binary),
    ], cwd=ROOT, check=True)

    for filter_text in ("", "racewar = 1", "race = 'human'", "class = 'warrior'"):
        title_query, total_query, top_query, low_query = subprocess.check_output(
            [str(binary), filter_text], text=True,
        ).splitlines()
        # MariaDB accepts parenthesized UNION arms; execute each arm in SQLite.
        lead_query, last_query = title_query.split(" UNION ALL ")
        assert database.execute(lead_query[1:-1]).fetchall() == [("lead", "Mortal12")]
        assert database.execute(last_query[1:-1]).fetchall() == [("low", "Mortal1")]

        eligible = fixtures[:12]
        if filter_text:
            eligible = [row for row in eligible if row[0] % 2]
        for query, tag, descending in ((top_query, "top", True), (low_query, "low", False)):
            expected = sorted(eligible, key=lambda row: row[2], reverse=descending)[:10]
            assert database.execute(query).fetchall() == [(tag, row[1], row[2]) for row in expected]
        assert dict((row[1], row[2]) for row in database.execute(total_query)) == {
            side: sum(row[2] for row in fixtures if row[3] <= 56 and row[4] == side)
            for side in (1, 2)
        }

    database.execute("UPDATE frag_leaderboard SET total_frags = 600 WHERE id = 11")
    assert database.execute(lead_query[1:-1]).fetchall() == [("lead", "Mortal11")]
    database.execute("UPDATE frag_leaderboard SET total_frags = 0 WHERE level <= 56")
    assert database.execute(lead_query[1:-1]).fetchall() == []
    database.execute("DELETE FROM frag_leaderboard WHERE level <= 56")
    for query in (lead_query[1:-1], last_query[1:-1], top_query, low_query, total_query):
        assert database.execute(query).fetchall() == []

# Both the cached default and filtered command use the exercised report query.
report_cache = (SRC / "redis_report_cache.c").read_text()
assert "fraglist_leaders(connection, NULL, rows)" in report_cache
assert "fraglist_leaders(connection, filter.c_str(), rows)" in SOURCE

print("mortal-only frag lists, side totals and title queries passed")
