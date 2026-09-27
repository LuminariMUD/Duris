#!/usr/bin/env python3
"""Character renames move the ship the character owns, and fail cleanly.

rename_character() used to decide whether to move ship ownership with
get_ship_from_char(), which asks whether the character is standing aboard any
ship.  It did so after the database and locker renames had already happened, and
the paid rename hook then moved ownership again unconditionally.  So:

- an immortal renaming an owner who was ashore left the ship under the old name;
- a character without a ship standing aboard someone else's ship was renamed in
  the database but not in the game;
- a paid rename was free for a character without a ship, or one aboard their own
  ship, who was told "Ship ownership update failed".

This runs the real rename_character() and mob_do_rename_hook() against a fake
ship registry and player store.  The ship now moves by ownership, before the
database rename, and is handed back (with the database name) when a later step
fails.  get_ship_from_char() is deliberately not defined here.
"""

from pathlib import Path
import os
import subprocess
import tempfile

from _paths import ROOT, extract_function

MODIFY = "modify.c"
FUNCTIONS = "\n\n".join(
    extract_function(MODIFY, signature)
    for signature in (
        "static void return_renamed_ship(",
        "bool rename_character(P_char ch, char *old_name, char *new_name)\n{",
        "int mob_do_rename_hook(P_char npc, P_char ch, int cmd, char *arg)",
    )
)

HARNESS = r'''
#include "core/prototypes.h"
#include "core/structs.h"
#include "cmd/interp.h"
#include "core/utility.h"
#include "core/utils.h"
#include "ships/ships.h"
#include "sql/sql.h"
#include "sql/sql_player.h"

#include <cassert>
#include <cctype>
#include <cstdlib>
#include <cstring>
#include <strings.h>
#include <string>
#include <vector>

bool rename_character(P_char ch, char *old_name, char *new_name);

// --- a fake ship registry, keyed by owner name --------------------------------
static ShipData ships[2];
static std::string ship_owner[2];
static bool fail_ship_write = false;
static int ship_moves = 0;

P_ship get_ship_from_owner(char *name)
{
	for (int i = 0; i < 2; i++)
		if (!strcasecmp(ship_owner[i].c_str(), name))
			return &ships[i];
	return nullptr;
}

bool rename_ship_owner(char *old_name, char *new_name)
{
	P_ship ship = get_ship_from_owner(old_name);
	if (!ship || !*new_name || fail_ship_write)
		return FALSE;
	CAP(new_name);
	ship_owner[ship - ships] = new_name;
	++ship_moves;
	return TRUE;
}

// --- a fake player store -------------------------------------------------------
static std::string db_name;
static bool fail_db_rename = false, fail_locker = false;
static int db_renames = 0, lockers = 0;
static int charged = 0;
static std::string told;

bool sql_player_rename(P_char, const char *new_name)
{
	++db_renames;
	if (fail_db_rename)
		return false;
	db_name = new_name;
	db_name[0] = toupper(db_name[0]);
	return true;
}
bool rename_locker(P_char, char *, char *)
{
	++lockers;
	return !fail_locker;
}
bool sql_player_exists(const char *) { return false; }
bool pfile_exists(const char *, char *) { return false; }
int sql_save_player_core(P_char) { return TRUE; }
int writeCharacter(P_char, int, int) { return TRUE; }
void deny_name(char *) {}
void moveToBackup(char *) {}
struct acct_chars *find_char_in_list(struct acct_chars *, char *) { return nullptr; }
int write_account(P_acct) { return 0; }

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
void CAP(char *text) { *text = toupper(*text); }
void __free(void *, const char *, int) { abort(); } // only for an account entry, and there is none
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

static void reset()
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
	owner.only.pc = &owner_pc;
	owner.desc = &owner_desc;
	owner_desc.account = &owner_account;
	owner.points.cash[3] = PRICE / 1000;
	banker.player.name = strdup("banker");
	banker.player.race = RACE_HUMAN;
	SET_BIT(banker.specials.act, ACT_ISNPC);

	ships[0] = ShipData{};
	ships[1] = ShipData{};
	ship_owner[0] = "Oldname";
	ship_owner[1] = "Stranger";
	db_name = "Oldname";
	fail_ship_write = fail_db_rename = fail_locker = false;
	ship_moves = db_renames = lockers = charged = 0;
	told.clear();
}

static bool rename_by_immortal(const char *to)
{
	char old_name[64] = "oldname", new_name[64];
	strcpy(new_name, to);
	return rename_character(&immortal, old_name, new_name);
}

static int ask_banker(const char *to)
{
	char arg[64];
	snprintf(arg, sizeof arg, "banker rename %s", to);
	return mob_do_rename_hook(&banker, &owner, CMD_ASK, arg);
}

int main()
{
	// An immortal renames an owner who is ashore: the ship moves with them.
	reset();
	assert(rename_by_immortal("newname"));
	assert(!strcmp(GET_NAME(&owner), "Newname") && db_name == "Newname");
	assert(ship_owner[0] == "Newname" && ship_owner[1] == "Stranger");

	// A character with no ship is renamed without touching anyone's ship.
	reset();
	ship_owner[0] = "Someoneelse";
	assert(rename_by_immortal("newname"));
	assert(!strcmp(GET_NAME(&owner), "Newname") && ship_moves == 0);
	assert(ship_owner[0] == "Someoneelse" && ship_owner[1] == "Stranger");

	// A failed ship move stops the rename before anything else changes.
	reset();
	fail_ship_write = true;
	assert(!rename_by_immortal("newname"));
	assert(told.find("Ship ownership update failed.") != std::string::npos);
	assert(db_renames == 0 && lockers == 0);
	assert(!strcmp(GET_NAME(&owner), "Oldname") && ship_owner[0] == "Oldname");

	// A failed database rename hands the ship back.
	reset();
	fail_db_rename = true;
	assert(!rename_by_immortal("newname"));
	assert(ship_moves == 2 && ship_owner[0] == "Oldname" && lockers == 0);
	assert(!strcmp(GET_NAME(&owner), "Oldname") && db_name == "Oldname");

	// A failed locker rename puts the database name and the ship back.
	reset();
	fail_locker = true;
	assert(!rename_by_immortal("newname"));
	assert(db_renames == 2 && db_name == "Oldname");
	assert(ship_moves == 2 && ship_owner[0] == "Oldname");
	assert(!strcmp(GET_NAME(&owner), "Oldname"));

	// A paid rename charges an owner once, and moves the ship once.
	reset();
	assert(ask_banker("newname") == TRUE);
	assert(charged == PRICE && ship_moves == 1);
	assert(!strcmp(GET_NAME(&owner), "Newname") && ship_owner[0] == "Newname");

	// A paid rename charges a character with no ship too.
	reset();
	ship_owner[0] = "Someoneelse";
	assert(ask_banker("newname") == TRUE);
	assert(charged == PRICE && ship_moves == 0);
	assert(!strcmp(GET_NAME(&owner), "Newname"));
	assert(told.find("Ship ownership update failed.") == std::string::npos);

	// A paid rename that fails costs nothing.
	reset();
	fail_ship_write = true;
	assert(ask_banker("newname") == TRUE);
	assert(charged == 0 && !strcmp(GET_NAME(&owner), "Oldname"));

	puts("character renames move owned ships, charge once, and roll back on failure");
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
    subprocess.run([str(path / "test")], check=True,
                   env={**os.environ, "ASAN_OPTIONS": "detect_leaks=0"})
