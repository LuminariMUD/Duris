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

Now one writer job, so one transaction, stores the player row, everything else the
name keys (sql_rename_character_references()) and the ship, whose statements are built
under its new owner while memory keeps the old one.  Memory follows only once the job is
stored, on a later pulse: the ship's owner, the guild roster, the name index, the
character if still in the game, and every account list naming them; the requester is
told either way, and a paid rename is charged only then.  An open personal locker would
save under the old name afterwards, so the rename waits for it.

This runs the real rename_character(), mob_do_rename_hook(), store_character_name(),
sql_rename_character_statements(), sql_rename_character_references() and the ship
owner-change helpers against a fake writer that holds the job until a pulse and can fail
any of its statements.  After every case the stored player, ship and reference rows carry
the same name, and so does memory.  get_ship_from_char() is deliberately not defined here.
"""

from pathlib import Path
import os
import subprocess
import tempfile

from _paths import ROOT, extract_function

FUNCTIONS = "\n\n".join(
    [
        extract_function("sql_player.c", signature)
        for signature in (
            "static std::vector<std::string> sql_rename_character_references(",
            "std::vector<std::string> sql_rename_character_statements(int pid,",
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
            "static bool store_character_name(",
            "bool rename_character(P_char ch, char *old_name, char *new_name,\n\t\t      std::function<void(P_char ch, bool renamed)> done)\n{",
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

bool rename_character(P_char ch, char *old_name, char *new_name,
		      std::function<void(P_char ch, bool renamed)> done);

// --- a fake writer: one job, held until the next pulse, one transaction ---------
static const int PID = 42;

struct Rows
{
	std::string player, ship, references;
	int ship_id;
};
static Rows durable;
static bool fail_player_update, fail_ship_save, fail_references, refuse_queue;
static std::vector<std::string> statements; // the job's statements, in order
static std::function<void()> pending;
static int jobs = 0, next_ship_id = 7;

std::string escape_str(const char *text) { return text; }
std::string sql_format(const char *format, ...)
{
	char out[1024];
	va_list args;
	va_start(args, format);
	vsnprintf(out, sizeof out, format, args);
	va_end(args);
	return out;
}
static std::vector<std::string> sql_save_ship_statements(P_ship ship)
{
	if (ship->db_id == -1)
		ship->db_id = next_ship_id++; // a ship never stored before takes its id from memory
	return { sql_format("SHIP id=%d owner=%s", ship->db_id, ship->ownername) };
}
static unsigned int apply(const std::string &statement, Rows *rows)
{
	char name[64];
	int pid;
	if (sscanf(statement.c_str(), "UPDATE player_data SET name='%63[^']' WHERE pid=%d", name,
		   &pid) == 2)
	{
		assert(pid == PID);
		rows->player = name;
		return fail_player_update;
	}
	if (sscanf(statement.c_str(), "SHIP id=%d owner=%63s", &pid, name) == 2)
	{
		rows->ship = name;
		rows->ship_id = pid;
		return fail_ship_save;
	}
	// The references: the account mapping stands for all of them.
	if (sscanf(statement.c_str(), "UPDATE account_characters SET char_name='%63[^']' WHERE pid=%d",
		   name, &pid) == 2)
	{
		assert(pid == PID);
		rows->references = name;
	}
	return fail_references && statement.find("locker_access SET owner") != std::string::npos;
}
static Rows staged;
unsigned int sql_execute(MYSQL *, const std::string &statement)
{
	statements.push_back(statement);
	return apply(statement, &staged);
}
// The writer holds the job until the next pulse, then runs it in one transaction: its rows
// are stored only if every statement succeeded, before its reply runs.
#define sql_read_work(...) queue_job(__VA_ARGS__)
static bool queue_job(std::function<unsigned int(MYSQL *, sql_rows *)> work,
		      std::function<void(bool, const sql_rows &)> done)
{
	if (refuse_queue)
		return false;
	assert(!pending);
	++jobs;
	pending = [work, done]()
	{
		staged = durable;
		statements.clear();
		sql_rows rows;
		const bool ok = work(nullptr, &rows) == 0;
		if (ok)
			durable = staged;
		done(ok, rows);
	};
	return true;
}
static void pulse()
{
	assert(pending);
	auto job = pending;
	pending = nullptr;
	job();
}

// --- the ship registry, keyed by the live ship's owner -------------------------
static ShipData ships[2];
static obj_data hulls[2];
static std::string invalidated, guild_renamed, indexed, held;

P_ship get_ship_from_owner(char *name)
{
	for (auto &ship : ships)
		if (ship.ownername && !strcasecmp(ship.ownername, name))
			return &ship;
	return nullptr;
}
void name_ship(const char *name, P_ship ship) { ship->name = strdup(name); }
void redis_invalidate_ship_snapshot(const char *owner) { invalidated = owner; }
void rename_guild_member(const char *from, const char *to)
{
	assert(durable.player == to);
	guild_renamed = std::string(from) + ">" + to;
}
void sql_player_names_set(int pid, const char *name)
{
	assert(pid == PID && durable.player == name && held == name);
	indexed = name;
}
// The new name is held from the moment the rename is queued until it is stored or refused.
void sql_player_names_hold(int pid, const char *name)
{
	assert(pid == PID && held.empty() && !pending);
	held = name;
}
void sql_player_names_release(int pid, const char *name)
{
	assert(pid == PID && held == name && durable.player != name);
	held.clear();
}
// --- the rest of the rename ----------------------------------------------------
static bool locker_open = false;
static int charged = 0, saves = 0;
static std::string told;

bool personal_locker_in_use(const char *name)
{
	assert(!strcmp(name, "Oldname"));
	return locker_open;
}
bool sql_player_exists(const char *) { return false; }
bool pfile_exists(const char *, char *) { return false; }
int writeCharacter(P_char, int, int)
{
	++saves;
	return TRUE;
}
void deny_name(char *) {}
void moveToBackup(char *) {}
static acct_chars listed;
struct acct_chars *find_char_in_list(struct acct_chars *list, const char *name)
{
	return list && !strcasecmp(list->charname, name) ? list : nullptr;
}

bool _parse_name(char *arg, char *name, bool)
{
	for (char *p = arg; *p; p++)
		name[p - arg] = tolower(*p);
	name[strlen(arg)] = '\0';
	return false;
}

static char_data people[3];
static bool owner_left = false, immortal_left = false;
P_char get_char_vis(P_char, const char *name)
{
	for (auto &person : people)
		if (person.player.name && !strcasecmp(person.player.name, name))
			return &person;
	return nullptr;
}
P_char find_character_by_runtime_id(uint64_t id)
{
	for (auto &person : people)
		if (person.runtime_id == id && !(owner_left && &person == &people[1]) &&
		    !(immortal_left && &person == &people[0]))
			return &person;
	return nullptr;
}
static descriptor_data owner_desc;
P_desc descriptor_list = &owner_desc;

char *str_dup(const char *text) { return strdup(text); }
void str_free(const char *text) { free(const_cast<char *>(text)); }
void CAP(char *text) { *text = toupper(*text); }
void __free(void *p, const char *, int) { free(p); }
void send_to_char(const char *text, P_char) { told += text; }
void send_to_char_f(P_char, const char *format, ...)
{
	char out[512];
	va_list args;
	va_start(args, format);
	vsnprintf(out, sizeof out, format, args);
	va_end(args);
	told += out;
}
void wizlog(int, const char *, ...) {}
void logit(const char *, const char *, ...) {}
void statuslog(int, const char *, ...) {}
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
static acct_entry owner_account;
static pc_only_data owner_pc;
static bool replied = false, replied_renamed = false;

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
	immortal.runtime_id = 1;
	owner.player.name = strdup("Oldname");
	owner.player.level = 50;
	owner.runtime_id = 2;
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
	banker.runtime_id = 3;
	SET_BIT(banker.specials.act, ACT_ISNPC);

	for (int i = 0; i < 2; i++)
	{
		ships[i] = ShipData{};
		ships[i].shipobj = &hulls[i];
		ships[i].db_id = 3 + i;
	}
	ships[0].ownername = strdup(owns_ship ? "Oldname" : "Someoneelse");
	ships[0].name = strdup("Brine");
	ships[1].ownername = strdup("Stranger");
	ships[1].name = strdup("Gull");

	durable = { "Oldname", owns_ship ? "Oldname" : "Someoneelse", "Oldname", 3 };
	fail_player_update = fail_ship_save = fail_references = refuse_queue = false;
	pending = nullptr;
	jobs = charged = saves = 0;
	next_ship_id = 7;
	locker_open = owner_left = immortal_left = replied = replied_renamed = false;
	statements.clear();
	invalidated.clear();
	guild_renamed.clear();
	indexed.clear();
	held.clear();
	told.clear();
}

static bool rename_by_immortal()
{
	char old_name[64] = "oldname", new_name[64] = "newname";
	return rename_character(&immortal, old_name, new_name, [](P_char staff, bool renamed)
				{
					assert(staff == &immortal);
					replied = true;
					replied_renamed = renamed;
				});
}

// The player row, the ship row and the references are always stored under one name,
// and memory carries the name the store has.
static void check_owned_by(const char *name)
{
	assert(durable.player == name && durable.ship == name && durable.references == name);
	assert(!strcmp(GET_NAME(&owner), name) && !strcmp(ships[0].ownername, name));
	assert(!strcmp(listed.charname, name));
	assert(!strcmp(ships[0].name, "Brine") && !strcmp(ships[1].ownername, "Stranger"));
	assert(!pending);
}

int main()
{
	// An immortal renames an owner who is ashore.  Nothing changes until the writer
	// has stored the player row, the ship and every name reference in one job; then
	// memory follows: the character, their ship, guild roster, name index and account
	// list, and the immortal is told.
	reset();
	assert(rename_by_immortal());
	assert(jobs == 1 && !replied && !strcmp(ships[0].ownername, "Oldname") && held == "Newname");
	assert(!strcmp(GET_NAME(&owner), "Oldname") && durable.player == "Oldname");
	pulse();
	check_owned_by("Newname");
	assert(replied && replied_renamed && saves == 1);
	assert(invalidated == "Oldname" && guild_renamed == "Oldname>Newname" && indexed == "Newname");

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
	pulse();
	assert(durable.player == "Newname" && durable.references == "Newname");
	assert(!strcmp(GET_NAME(&owner), "Newname") && durable.ship == "Someoneelse");
	assert(!strcmp(ships[0].ownername, "Someoneelse"));

	// An open personal locker would save under the old name: nothing is queued.
	reset();
	locker_open = true;
	assert(!rename_by_immortal());
	assert(told.find("currently using that locker") != std::string::npos);
	assert(jobs == 0);
	check_owned_by("Oldname");

	// A failed statement, player row, reference or ship, rolls the whole job back;
	// memory keeps the old name everywhere and the immortal is told.
	for (bool *fault : { &fail_player_update, &fail_references, &fail_ship_save })
	{
		reset();
		*fault = true;
		assert(rename_by_immortal());
		pulse();
		check_owned_by("Oldname");
		assert(replied && !replied_renamed && guild_renamed.empty() && indexed.empty());
		assert(held.empty());
		assert(told.find("Failed to rename character in DB!") != std::string::npos);
	}

	// A job the writer will not take: refused at once, the ship's owner put back.
	reset();
	refuse_queue = true;
	assert(!rename_by_immortal() && held.empty());
	assert(told.find("Failed to rename character in DB!") != std::string::npos);
	check_owned_by("Oldname");

	// The owner logs out before the reply: the stored rename still reaches the ship,
	// guild roster, name index and account list; their next login reads the new name.
	reset();
	assert(rename_by_immortal());
	owner_left = true;
	pulse();
	assert(durable.player == "Newname" && durable.ship == "Newname");
	assert(!strcmp(ships[0].ownername, "Newname") && !strcmp(listed.charname, "Newname"));
	assert(indexed == "Newname" && guild_renamed == "Oldname>Newname" && saves == 0);
	assert(replied && replied_renamed);

	// The immortal logs out before the reply: the rename completes, nobody is told.
	reset();
	assert(rename_by_immortal());
	immortal_left = true;
	pulse();
	check_owned_by("Newname");
	assert(!replied);

	// A ship that was never stored takes its row id from memory when the job is built,
	// and keeps it if the job fails: its next save inserts or updates its row by it.
	reset();
	ships[0].db_id = -1;
	fail_references = true;
	assert(rename_by_immortal());
	pulse();
	check_owned_by("Oldname");
	assert(ships[0].db_id == 7);

	// A linkdead character has no descriptor: the rename completes, and the account
	// list of every live session of the account follows.
	reset();
	owner.desc = nullptr;
	assert(rename_by_immortal());
	pulse();
	check_owned_by("Newname");

	// A paid rename charges an owner once, only when it is stored, and moves the ship.
	reset();
	char arg[64] = "banker rename newname";
	assert(mob_do_rename_hook(&banker, &owner, CMD_ASK, arg) == TRUE);
	assert(charged == 0);
	pulse();
	assert(charged == PRICE);
	check_owned_by("Newname");
	assert(told.find("Congratulations! From now on you will be known as Newname") !=
	       std::string::npos);

	// A paid rename charges a character with no ship too.
	reset(false);
	strcpy(arg, "banker rename newname");
	assert(mob_do_rename_hook(&banker, &owner, CMD_ASK, arg) == TRUE);
	pulse();
	assert(charged == PRICE && !strcmp(GET_NAME(&owner), "Newname"));

	// A paid rename that fails costs nothing.
	reset();
	fail_ship_save = true;
	strcpy(arg, "banker rename newname");
	assert(mob_do_rename_hook(&banker, &owner, CMD_ASK, arg) == TRUE);
	pulse();
	assert(charged == 0);
	check_owned_by("Oldname");

	puts("character renames store the player, their references and their ship in one writer job");
	return 0;
}
'''

# The guild roster follows in memory and each guild it changed is saved again: a save
# queued while the rename ran still holds the old name, and this one lands after it.
assert "if (renamed)\n\t\t\tguild->save();" in extract_function("assocs.c",
                                                              "void rename_guild_member(")

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
