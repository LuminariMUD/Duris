#!/usr/bin/env python3
"""SQL boot loads every ship row, not just the first 512.

sql_load_all_ships() collects the owner names first and then loads each ship, so
the load never nests a query inside the open result.  It collected them into a
fixed `char owner_names[512][64]` and stopped reading at 512, silently leaving
every further ship unloaded, although MAXSHIPS is 2000 and the flat-file backend
has no such cap.  Names were also cut to 63 bytes.

This runs the real sql_load_all_ships() against a result of 700 rows, one of
them with a NULL owner and one with a long owner name, and checks it reads the
highest ship id new ships count on.
"""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function

HARNESS = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "ships/ships.h"
#include "sql/sql.h"
#include "sql/sql_player.h"
#include "sql/sql_work.h"

#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

static const int ROWS = 700, NULL_ROW = 300, LONG_ROW = 650;
static const std::string LONG_NAME(80, 'q');

static int handle = 0, result_handle = 0;
MYSQL *DB = reinterpret_cast<MYSQL *>(&handle);
const ShipTypeData ship_type_data[MAXSHIPCLASS] = {};

static std::vector<std::string> names, ids;
static std::vector<std::vector<char *>> rows;
static size_t next_row = 0;
static bool result_open = false;
static std::vector<std::string> loaded;
static ShipData ships[ROWS];
ShipObjHash shipObjHash;
ShipObjHash::ShipObjHash() {}
bool ShipObjHash::erase(P_ship) { return true; } // for a ship load_ship() refused
void delete_ship(P_ship, bool) {}

MYSQL_RES *db_query_at(struct persistence_query_site, const char *, ...)
{
	next_row = 0;
	result_open = true;
	return reinterpret_cast<MYSQL_RES *>(&result_handle);
}
MYSQL_ROW mysql_fetch_row(MYSQL_RES *)
{
	return next_row < rows.size() ? rows[next_row++].data() : nullptr;
}
void mysql_free_result(MYSQL_RES *) { result_open = false; }

struct ship_rows
{
	sql_rows ship, armor, crew, slots;
};
static std::vector<std::pair<std::string, ship_rows>> stored_ships;
static int ship_next_db_id = -1;
static bool sql_read_ship_rows(const char *, ship_rows *)
{
	assert(!result_open);
	return true;
}

P_ship sql_place_ship(const char *owner_name, bool *unplaced)
{
	assert(!result_open); // no query while the owner list is still open
	loaded.emplace_back(owner_name);
	*unplaced = false;
	return &ships[loaded.size() - 1];
}
void note_unplaced_ship(const char *) { assert(false); }

''' + extract_function("sql_player.c", "bool sql_load_all_ships()") + r'''

int main()
{
	names.reserve(ROWS);
	ids.reserve(ROWS);
	for (int i = 0; i < ROWS; i++)
	{
		names.push_back(i == LONG_ROW ? LONG_NAME : "Owner" + std::to_string(i));
		ids.push_back(std::to_string(i == 42 ? 5000 : i + 1));
	}
	for (int i = 0; i < ROWS; i++)
		rows.push_back({ i == NULL_ROW ? nullptr : names[i].data(), ids[i].data() });

	assert(sql_load_all_ships());
	// New ships take their ids from past the highest stored one.
	assert(ship_next_db_id == 5000);
	assert(loaded.size() == ROWS - 1);
	assert(loaded.front() == "Owner0" && loaded.back() == "Owner699");
	assert(loaded[LONG_ROW - 1] == LONG_NAME);

	puts("sql_load_all_ships loads every ship row");
	return 0;
}
'''

with tempfile.TemporaryDirectory(prefix="duris-ship-boot-") as directory:
    path = Path(directory)
    (path / "test.cpp").write_text(HARNESS, encoding="utf-8")
    subprocess.run(
        ["g++", "-std=c++20", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
         "-Isrc", "-Itests/async", "-I/usr/include/mysql",
         str(path / "test.cpp"), "-o", str(path / "test")],
        cwd=ROOT, check=True)
    subprocess.run([str(path / "test")], check=True)
