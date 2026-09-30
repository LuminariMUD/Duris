#!/usr/bin/env python3
"""A ship save never waits on the game loop (persistence reset phase 2, step 8).

sql_save_ship() inserted a new ship's row, read its id back, and wrote the armour,
crew and slot rows in a transaction on the game loop; a failed COMMIT left the id
"unconfirmed" and the next save looked the row up again. Now a new ship takes its
id from memory (the highest stored id, read at boot), and the save is one writer
job that inserts or updates every row by that id. A character rename builds the same
statements into its own writer job.

This runs the real sql_save_ship() and its statement builder with the writer
queue and the connection stubbed.
"""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, source

SQL_PLAYER = source("sql_player.c").read_text(encoding="utf-8")
START = SQL_PLAYER.index("static int ship_next_db_id = -1;")
SAVE_SHIP = SQL_PLAYER[START:SQL_PLAYER.index("/* The stored rows of one ship", START)]

HARNESS = r'''
#include "core/structs.h"
#include "ships/ships.h"
#include "sql/sql.h"
#include "sql/sql_async.h"
#include "sql/sql_player.h"

#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

static int handle = 0;
MYSQL *DB = reinterpret_cast<MYSQL *>(&handle);
static bool in_transaction = false;
static std::vector<std::vector<std::string>> queued;
static std::vector<std::string> joined;

bool sql_in_transaction(void) { return in_transaction; }
bool sql_run_query(const char *query)
{
	joined.emplace_back(query);
	return true;
}
bool sql_queue_statements_at(struct persistence_query_site, std::vector<std::string> statements)
{
	queued.push_back(std::move(statements));
	return true;
}
std::string sql_format(const char *format, ...)
{
	char text[4096];
	va_list args;
	va_start(args, format);
	vsnprintf(text, sizeof text, format, args);
	va_end(args);
	return text;
}
std::string escape_str(const char *text) { return text; }
void sql_player_error(const char *) {}

''' + SAVE_SHIP + r'''

static bool starts(const std::string &text, const char *prefix)
{
	return !text.compare(0, strlen(prefix), prefix);
}

int main()
{
	static char owner[] = "Owner", name[] = "Brine";
	ShipData ship = {};
	ship.ownername = owner;
	ship.name = name;
	ship.db_id = -1;

	// Before the boot has read the highest id, a new ship is not saved.
	assert(!sql_save_ship(&ship) && ship.db_id == -1 && queued.empty());

	// A new ship takes the next id, and its save is one job: its row by id, then
	// four armour sides, its crew and every slot.
	ship_next_db_id = 7;
	assert(sql_save_ship(&ship) && ship.db_id == 8 && queued.size() == 1);
	const std::vector<std::string> &first = queued[0];
	assert((int)first.size() == 1 + 4 + 1 + MAXSLOTS);
	assert(starts(first[0], "insert into ships (id, owner_name,"));
	assert(first[0].find("values (8, 'Owner', 'Brine',") != std::string::npos);
	assert(first[0].find("on duplicate key update owner_name=values(owner_name)") !=
	       std::string::npos);
	assert(starts(first[1], "insert into ship_armor") && starts(first[5], "insert into ship_crew") &&
	       starts(first[6], "insert into ship_slots"));

	// Its next save updates the same row; another new ship takes the next id.
	assert(sql_save_ship(&ship) && ship.db_id == 8 && queued.size() == 2);
	ShipData other = {};
	other.ownername = name;
	other.db_id = -1;
	assert(sql_save_ship(&other) && other.db_id == 9);

	// There is no caller's transaction to join any more: a save is always one job.
	in_transaction = true;
	assert(sql_save_ship(&ship) && queued.size() == 4 && joined.empty());

	puts("ship saves take their id from memory and queue one job");
	return 0;
}
'''

with tempfile.TemporaryDirectory(prefix="duris-ship-save-") as directory:
    path = Path(directory)
    (path / "test.cpp").write_text(HARNESS, encoding="utf-8")
    subprocess.run(
        ["g++", "-std=c++20", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
         "-Isrc", "-Itests/async", "-I/usr/include/mysql",
         str(path / "test.cpp"), "-o", str(path / "test")],
        cwd=ROOT, check=True)
    subprocess.run([str(path / "test")], check=True)
