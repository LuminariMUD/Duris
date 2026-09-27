#!/usr/bin/env python3
"""Character renames move everything the name keys, in one transaction.

rename_character() used to decide whether to move ship ownership with
get_ship_from_char(), which asks whether the character is standing aboard any
ship.  It did so after the database and locker renames had already happened, and
the paid rename hook then moved ownership again unconditionally.  So:

- an immortal renaming an owner who was ashore left the ship under the old name;
- a character without a ship standing aboard someone else's ship was renamed in
  the database but not in the game;
- a paid rename was free for a character without a ship, or one aboard their own
  ship, who was told "Ship ownership update failed".

A first fix moved the ship by ownership, in its own write, before the player
rename, and wrote it back when a later step failed.  If the database failed after
that first write, the write-back failed too, and the ship stayed stored under a
name no character had.

Renames also left the account's login mapping under the old name.  The next
save added a second mapping for the new one, and the account could not load
again.  A personal locker, the character's locker grants and guild roster entry
stayed under the old name too.

Now one transaction stores the player row, everything else the name keys
(sql_rename_character_references()) and the ship.  The ship's owner changes in
memory first and is put back from memory, with no further write, unless the
transaction committed; the live guild roster follows only a committed rename.  A
failed COMMIT may still have been applied, so the player row is read back to tell
which.  An open personal locker would save under the old name afterwards, so the
rename waits for it.

This runs the real rename_character(), mob_do_rename_hook(),
sql_rename_character(), sql_rename_character_references(), sql_player_rename()
and the ship owner-change helpers against a fake transactional store that can
fail each statement, the COMMIT (rejected, or applied with its reply lost), the
ROLLBACK and the read-back.  After every case the stored player, ship and
reference rows must carry the same name.  get_ship_from_char() is deliberately
not defined here.
"""

from pathlib import Path
import os
import subprocess
import tempfile

from _paths import ROOT, extract_function

FUNCTIONS = "\n\n".join(
    [extract_function("sql_player.c", "bool sql_player_rename(P_char ch, const char *new_name)\n{")]
    + [
        extract_function("sql_player.c", signature)
        for signature in (
            "static int sql_player_row_named(",
            "static bool sql_rename_character_references(",
            "sql_commit_outcome sql_rename_character(P_char ch,",
        )
    ]
    + [
        extract_function("ship_base.c", signature)
        for signature in (
            "bool begin_ship_owner_change(",
            "void finish_ship_owner_change(",
            "void undo_ship_owner_change(",
        )
    ]
    + [
        extract_function("modify.c", signature)
        for signature in (
            "static sql_commit_outcome store_character_name(",
            "bool rename_character(P_char ch, char *old_name, char *new_name)\n{",
            "int mob_do_rename_hook(P_char npc, P_char ch, int cmd, char *arg)",
        )
    ]
)

HARNESS = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "cmd/interp.h"
#include "core/utility.h"
#include "core/utils.h"
#include "player/player_name.h"
#include "ships/ships.h"
#include "sql/sql.h"
#include "sql/sql_player.h"

#include <cassert>
#include <cctype>
#include <cstdarg>
#include <cstdlib>
#include <cstring>
#include <strings.h>
#include <string>
#include <unistd.h>
#include <vector>

bool rename_character(P_char ch, char *old_name, char *new_name);

// --- a fake transactional store: one player row and one ship row -------------
static int handle = 0, result_handle = 0;
MYSQL *DB = reinterpret_cast<MYSQL *>(&handle);
static const int PID = 42;

struct Rows
{
	std::string player, ship, references;
	int ship_id;
};
static Rows durable, pending;
static bool in_transaction = false, connection_lost = false;
// Faults, each failing one step.
static bool fail_player_update, fail_ship_save, fail_references, fail_rollback, fail_read_back;
static std::vector<std::string> statements; // every reference statement, in order
static enum { COMMIT_OK, COMMIT_REJECTED, COMMIT_APPLIED_REPLY_LOST } commit_mode;
static int fail_transaction = 0; // 1: the first transaction, 2: the second, 0: every one
static int transactions = 0, ship_saves = 0, next_ship_id = 7;

static bool faulty(bool fault) { return fault && (!fail_transaction || transactions == fail_transaction); }

bool sql_in_transaction(void) { return in_transaction; }
bool sql_begin_transaction(void)
{
	assert(!in_transaction && !connection_lost);
	in_transaction = true;
	pending = durable;
	++transactions;
	return true;
}
bool sql_commit(void)
{
	assert(in_transaction);
	if (commit_mode == COMMIT_OK || !faulty(true))
	{
		durable = pending;
		in_transaction = false;
		return true;
	}
	if (commit_mode == COMMIT_APPLIED_REPLY_LOST)
		durable = pending; // the server committed; the connection dropped
	return false; // in_transaction stays set, as in the real sql_commit()
}
bool sql_rollback(void)
{
	assert(in_transaction);
	in_transaction = false; // the real sql_rollback() clears it even on failure
	// A ROLLBACK that fails has lost its connection, and the server discards
	// the transaction itself: nothing pending is ever stored.
	return !faulty(fail_rollback);
}

static bool sql_run_query(const char *query)
{
	assert(in_transaction);
	char name[64];
	int pid;
	if (sscanf(query, "UPDATE player_data SET name='%63[^']' WHERE pid='%d'", name, &pid) == 2)
	{
		assert(pid == PID);
		if (faulty(fail_player_update))
			return false;
		pending.player = name;
		return true;
	}
	// The references: the account mapping stands for all of them.
	statements.emplace_back(query);
	if (faulty(fail_references) && statements.size() == 4)
		return false;
	if (sscanf(query, "UPDATE account_characters SET char_name='%63[^']' WHERE pid=%d", name,
		   &pid) == 2)
	{
		assert(pid == PID);
		pending.references = name;
	}
	return true;
}
bool sql_save_ship(P_ship ship)
{
	assert(in_transaction);
	++ship_saves;
	if (ship->db_id == -1)
		ship->db_id = next_ship_id++; // a ship never stored before is inserted
	if (faulty(fail_ship_save))
		return false;
	pending.ship = ship->ownername;
	pending.ship_id = ship->db_id;
	return true;
}
char *sql_escape_string(const char *text) { return strdup(text); }

static char read_name[64];
static char *read_row[] = { read_name };
MYSQL_RES *db_query_at(struct persistence_query_site, const char *format, ...)
{
	assert(!in_transaction && !strcmp(format, "SELECT name FROM player_data WHERE pid=%d"));
	va_list args;
	va_start(args, format);
	assert(va_arg(args, int) == PID);
	va_end(args);
	if (faulty(fail_read_back))
		return nullptr;
	strcpy(read_name, durable.player.c_str());
	return reinterpret_cast<MYSQL_RES *>(&result_handle);
}
MYSQL_ROW mysql_fetch_row(MYSQL_RES *) { return read_row; }
void mysql_free_result(MYSQL_RES *) {}

// --- the ship registry, keyed by the live ship's owner -------------------------
static ShipData ships[2];
static obj_data hulls[2];
static std::string invalidated, guild_renamed;

P_ship get_ship_from_owner(char *name)
{
	for (auto &ship : ships)
		if (ship.ownername && !strcasecmp(ship.ownername, name))
			return &ship;
	return nullptr;
}
void name_ship(const char *name, P_ship ship) { ship->name = strdup(name); }
unsigned long long ship_save_signature(const P_ship) { return 99; }
void redis_invalidate_ship_snapshot(const char *owner) { invalidated = owner; }
void rename_guild_member(const char *from, const char *to)
{
	assert(!in_transaction && durable.player == to);
	guild_renamed = std::string(from) + ">" + to;
}
// --- the rest of the rename ----------------------------------------------------
static bool locker_open = false, fail_core_save = false;
static int charged = 0;
static std::string told;

bool personal_locker_in_use(const char *name)
{
	assert(!strcmp(name, "Oldname"));
	return locker_open;
}
bool sql_player_exists(const char *) { return false; }
bool pfile_exists(const char *, char *) { return false; }
int sql_save_player_core(P_char) { return fail_core_save ? FALSE : TRUE; }
int writeCharacter(P_char, int, int) { return TRUE; }
void deny_name(char *) {}
void moveToBackup(char *) {}
static acct_chars listed;
static int account_writes = 0;
struct acct_chars *find_char_in_list(struct acct_chars *list, char *name)
{
	return list && !strcasecmp(list->charname, name) ? list : nullptr;
}
int write_account(P_acct)
{
	++account_writes;
	return 0;
}

bool _parse_name(char *arg, char *name, bool)
{
	for (char *p = arg; *p; p++)
		name[p - arg] = tolower(*p);
	name[strlen(arg)] = '\0';
	return false;
}

static char_data people[3];
P_char get_char_vis(P_char, const char *name)
{
	for (auto &person : people)
		if (person.player.name && !strcasecmp(person.player.name, name))
			return &person;
	return nullptr;
}

char *str_dup(const char *text) { return strdup(text); }
void str_free(const char *text) { free(const_cast<char *>(text)); }
void CAP(char *text) { *text = toupper(*text); }
void __free(void *p, const char *, int) { free(p); }
void send_to_char(const char *text, P_char) { told += text; }
void wizlog(int, const char *, ...) {}
void logit(const char *, const char *, ...) {}
void statuslog(int, const char *, ...) {}
void persistence_alert(int, const char *, const char *, const char *, const char *, const char *,
		       const char *, ...)
{
}
void sql_log(P_char, const char *, const char *, ...) {}
int panic_corruption_int(const char *, const char *, ...) { abort(); }

// --- the rename banker ---------------------------------------------------------
char *one_argument(const char *arg, char *first)
{
	while (*arg == ' ')
		arg++;
	while (*arg && *arg != ' ')
		*first++ = *arg++;
	*first = '\0';
	return const_cast<char *>(arg);
}
bool ac_can_see(P_char, P_char, bool) { return true; }
P_char get_linked_char(P_char, ush_int) { return nullptr; }
int GET_CLASS(P_char, uint) { return 0; }
void mobsay(P_char, const char *) {}
int get_property(const char *, int fallback) { return fallback; }
char *coin_stringv(int, int) { return const_cast<char *>("coins"); }
int SUB_MONEY(P_char, int amount, int)
{
	charged += amount;
	return 0;
}

''' + FUNCTIONS + r'''

static const int PRICE = 5000000;
static char_data &immortal = people[0], &owner = people[1], &banker = people[2];
static descriptor_data owner_desc;
static acct_entry owner_account;
static pc_only_data owner_pc;

static void reset(bool owns_ship = true)
{
	for (auto &person : people)
	{
		free(person.player.name);
		person = char_data{};
		person.specials.position = STAT_NORMAL;
	}
	immortal.player.name = strdup("Warden");
	immortal.player.level = 60;
	owner.player.name = strdup("Oldname");
	owner.player.level = 50;
	owner_pc = pc_only_data{};
	owner_pc.pid = PID;
	owner.only.pc = &owner_pc;
	owner.desc = &owner_desc;
	owner_desc.account = &owner_account;
	listed = acct_chars{};
	listed.charname = strdup("Oldname");
	owner_account.acct_character_list = &listed;
	owner.points.cash[3] = PRICE / 1000;
	banker.player.name = strdup("banker");
	banker.player.race = RACE_HUMAN;
	SET_BIT(banker.specials.act, ACT_ISNPC);

	for (int i = 0; i < 2; i++)
	{
		ships[i] = ShipData{};
		ships[i].shipobj = &hulls[i];
		ships[i].db_id = 3 + i;
		ships[i].save_pending = true;
	}
	ships[0].ownername = strdup(owns_ship ? "Oldname" : "Someoneelse");
	ships[0].name = strdup("Brine");
	ships[1].ownername = strdup("Stranger");
	ships[1].name = strdup("Gull");

	durable = { "Oldname", owns_ship ? "Oldname" : "Someoneelse", "Oldname", 3 };
	pending = durable;
	in_transaction = connection_lost = false;
	fail_player_update = fail_ship_save = fail_references = fail_rollback = fail_read_back =
		false;
	commit_mode = COMMIT_OK;
	fail_transaction = transactions = ship_saves = charged = account_writes = 0;
	next_ship_id = 7;
	locker_open = fail_core_save = false;
	statements.clear();
	invalidated.clear();
	guild_renamed.clear();
	told.clear();
}

static bool rename_by_immortal()
{
	char old_name[64] = "oldname", new_name[64] = "newname";
	return rename_character(&immortal, old_name, new_name);
}

// The player row and the ship row are always stored under one name, and the
// live character and their ship carry the name the store has.
static void check_owned_by(const char *name)
{
	assert(durable.player == name && durable.ship == name && durable.references == name);
	assert(!strcmp(GET_NAME(&owner), name) && !strcmp(ships[0].ownername, name));
	assert(!strcmp(ships[0].name, "Brine") && !strcmp(ships[1].ownername, "Stranger"));
	assert(!in_transaction);
}

int main()
{
	// An immortal renames an owner who is ashore: the player row, the ship and
	// every name reference move together, in one transaction, and the ship is
	// marked saved.  The live guild roster and account list follow.
	reset();
	assert(rename_by_immortal());
	check_owned_by("Newname");
	assert(transactions == 1 && ship_saves == 1);
	assert(!ships[0].save_pending && ships[0].save_saved_signature == 99);
	assert(invalidated == "Oldname" && guild_renamed == "Oldname>Newname");
	assert(!strcmp(listed.charname, "Newname") && account_writes == 1);

	// The references cover the login mapping, a personal locker and its access
	// list, locker grants, the guild roster and top fragger, and the leaderboard.
	for (const char *table : { "account_characters", "UPDATE lockers", "locker_access SET owner",
				   "locker_access SET visitor", "guild_members", "guilds SET topfragger",
				   "frag_leaderboard" })
	{
		bool found = false;
		for (const std::string &statement : statements)
			found = found || statement.find(table) != std::string::npos;
		assert(found);
	}
	for (const std::string &statement : statements)
		assert(statement.find("corpses") == std::string::npos);

	// A character with no ship is renamed without touching anyone's ship.
	reset(false);
	assert(rename_by_immortal());
	assert(durable.player == "Newname" && durable.references == "Newname");
	assert(!strcmp(GET_NAME(&owner), "Newname"));
	assert(ship_saves == 0 && !strcmp(ships[0].ownername, "Someoneelse"));

	// An open personal locker would save under the old name: nothing is written.
	reset();
	locker_open = true;
	assert(!rename_by_immortal());
	assert(told.find("currently using that locker") != std::string::npos);
	assert(transactions == 0);
	check_owned_by("Oldname");

	// A failed statement, player row, reference or ship, rolls the whole rename
	// back, and the live ship is put back without another write.
	for (bool *fault : { &fail_player_update, &fail_references, &fail_ship_save })
	{
		reset();
		*fault = true;
		assert(!rename_by_immortal());
		assert(told.find("Failed to rename character in DB!") != std::string::npos);
		check_owned_by("Oldname");
		assert(transactions == 1 && ships[0].save_pending && guild_renamed.empty());
		assert(!strcmp(listed.charname, "Oldname"));
	}

	// The same when the ROLLBACK also fails: the server discards the transaction.
	reset();
	fail_ship_save = fail_rollback = true;
	assert(!rename_by_immortal());
	check_owned_by("Oldname");

	// A rejected COMMIT: the read-back finds the old name, so the rename failed.
	reset();
	commit_mode = COMMIT_REJECTED;
	assert(!rename_by_immortal());
	check_owned_by("Oldname");
	assert(guild_renamed.empty());

	// A COMMIT applied with its reply lost: the read-back finds the new name, so
	// the rename goes on and completes.
	reset();
	commit_mode = COMMIT_APPLIED_REPLY_LOST;
	assert(rename_by_immortal());
	check_owned_by("Newname");
	assert(guild_renamed == "Oldname>Newname");

	// A failed COMMIT that cannot be read back is reported as failed, and every
	// row still carries one name, whichever it turned out to be.
	for (auto mode : { COMMIT_REJECTED, COMMIT_APPLIED_REPLY_LOST })
	{
		reset();
		commit_mode = mode;
		fail_read_back = true;
		assert(!rename_by_immortal());
		assert(durable.player == durable.ship && durable.player == durable.references);
		assert(durable.player == (mode == COMMIT_REJECTED ? "Oldname" : "Newname"));
		assert(!strcmp(GET_NAME(&owner), "Oldname") && !strcmp(ships[0].ownername, "Oldname"));
		assert(!in_transaction && guild_renamed.empty());
	}

	// A ship that was never stored is inserted by the rename.  If the rename is
	// rolled back, it keeps that row id only as unconfirmed, for its next save
	// to check.
	reset();
	ships[0].db_id = -1;
	commit_mode = COMMIT_REJECTED;
	assert(!rename_by_immortal());
	check_owned_by("Oldname");
	assert(ships[0].db_id == 7 && ships[0].db_id_unconfirmed);

	// A linkdead character has no descriptor: the rename completes, and their
	// account menu reads the renamed mapping at their next login.
	reset();
	owner.desc = nullptr;
	assert(rename_by_immortal());
	check_owned_by("Newname");
	assert(account_writes == 0 && !strcmp(listed.charname, "Oldname"));

	// Once the rename is stored, a failed core save is reported but does not
	// undo it, and the account list still follows.
	reset();
	fail_core_save = true;
	assert(rename_by_immortal());
	check_owned_by("Newname");
	assert(told.find("failed to save the renamed character") != std::string::npos);
	assert(!strcmp(listed.charname, "Newname"));

	// A paid rename charges an owner once, and moves the ship once.
	reset();
	char arg[64] = "banker rename newname";
	assert(mob_do_rename_hook(&banker, &owner, CMD_ASK, arg) == TRUE);
	assert(charged == PRICE && ship_saves == 1);
	check_owned_by("Newname");

	// A paid rename charges a character with no ship too.
	reset(false);
	strcpy(arg, "banker rename newname");
	assert(mob_do_rename_hook(&banker, &owner, CMD_ASK, arg) == TRUE);
	assert(charged == PRICE && ship_saves == 0 && !strcmp(GET_NAME(&owner), "Newname"));

	// A paid rename that fails costs nothing.
	reset();
	fail_ship_save = true;
	strcpy(arg, "banker rename newname");
	assert(mob_do_rename_hook(&banker, &owner, CMD_ASK, arg) == TRUE);
	assert(charged == 0);
	check_owned_by("Oldname");

	puts("character renames store the player, their references and their ship in one transaction");
	return 0;
}
'''

with tempfile.TemporaryDirectory(prefix="duris-rename-ship-") as directory:
    path = Path(directory)
    (path / "test.cpp").write_text(HARNESS, encoding="utf-8")
    subprocess.run(
        ["g++", "-std=c++20", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
         "-Isrc", "-Itests/async", "-I/usr/include/mysql",
         str(path / "test.cpp"), "-o", str(path / "test")],
        cwd=ROOT, check=True)
    # finish_ship_owner_change() unlinks the legacy Ships/<owner> file: run
    # where there is none to remove.
    subprocess.run([str(path / "test")], check=True, cwd=path,
                   env={**os.environ, "ASAN_OPTIONS": "detect_leaks=0"})
