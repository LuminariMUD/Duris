// sql_player.h
// player save/load functions for mysql storage
// part of pfile-to-db migration

#ifndef __SQL_PLAYER_H_INCLUDED__
#define __SQL_PLAYER_H_INCLUDED__

#include "core/structs.h"

#include "sql/sql_work.h"

#include <functional>
#include <string>
#include <vector>

// ============================================================================
// transaction helpers
// ============================================================================

// start a transaction, returns true on success
bool sql_begin_transaction(void);

// commit current transaction, returns true on success
bool sql_commit(void);

// rollback current transaction, returns true on success
bool sql_rollback(void);

// check if we're currently in a transaction
bool sql_in_transaction(void);

#ifndef __NO_MYSQL__
#include <mysql.h>

// for forked child - create separate db connection
MYSQL *sql_create_child_connection(void);

// child swaps globals after fork
void sql_reset_for_child(MYSQL *child_conn);
#endif

// ============================================================================
// player save functions
// ============================================================================

// master save function - saves entire player to db atomically
// type: save type (RENT_CAMPED, RENT_RENTED, etc from defines.h)
// room: room vnum to save
// returns true on success
bool sql_save_player(P_char ch, int type, int room);

// individual save functions (called by sql_save_player)
bool sql_save_player_status(P_char ch, int type, int room);
bool sql_save_player_skills(P_char ch);
bool sql_save_player_affects(P_char ch);
bool sql_save_player_items(P_char ch);
bool sql_delete_player_items(int pid);
bool sql_save_player_shapechanges(P_char ch);
bool sql_save_player_recipes(P_char ch);
// Every character's recipes, read at boot and kept in memory (MariaDB).
bool sql_player_recipes_load(void);
bool sql_add_player_recipe(int pid, int recipe_vnum);
bool sql_delete_player_recipes(int pid);
bool sql_has_player_recipe(int pid, int recipe_vnum);
int *sql_get_player_recipes(int pid, int *count);

// ============================================================================
// player load functions
// ============================================================================

// master load function - loads entire player from db
// name: player name to load
// returns char_data pointer or NULL on failure
P_char sql_load_player(const char *name);

// check if player exists in db
bool sql_player_exists(const char *name);

// character rename
bool sql_player_rename(P_char ch, const char *new_name);

// outcome of a transaction whose COMMIT may have been applied even though it failed
enum class sql_commit_outcome
{
	committed,
	rolled_back,
	unknown,
};

// rename the character, everything their name keys, and the ship they own
// (NULL for none, its owner already changed in memory) in one transaction
sql_commit_outcome sql_rename_character(P_char ch, const char *old_name, const char *new_name,
					struct ShipData *ship);

// get player pid by name
int sql_get_player_pid(const char *name);

// individual load functions (called by sql_load_player)
bool sql_load_player_status(P_char ch, int pid);
bool sql_load_player_skills(P_char ch);
bool sql_load_player_affects(P_char ch);
bool sql_load_player_items(P_char ch);
bool sql_load_player_shapechanges(P_char ch);

// pet save/load for crash recovery
bool sql_save_player_pets(P_char ch, int save_type, int save_room_vnum);
bool sql_load_player_pets(P_char ch);

// ============================================================================
// player delete
// ============================================================================

// The characters' pids and names, read at boot and kept current in memory (MariaDB; the
// flat-file lookups read the identity store). sql_get_player_name() gives only an active
// character's name.
bool sql_player_names_load(void);
void sql_player_names_set(int pid, const char *name);
void sql_player_names_forget(int pid);
const char *sql_get_player_name(int pid);
// The highest pid any character has had, for allocating the next one.
int sql_highest_player_pid(void);

// delete player from db (for pwipe, etc)
// Transaction owners defer revision eviction until their commit is confirmed.

// ============================================================================
// account functions
// ============================================================================

// Queues the account's save on the writer.
bool sql_save_account(struct acct_entry *acc);

// Reads the account on the writer, behind every save queued before it: its character
// projection is repaired first, then the account, its IPs and its characters are read.
// done runs on the game thread with the loaded account, which it then owns, or null
// when there is none; ok is false when the read failed.
bool sql_load_account(const char *name, std::function<void(bool ok, P_acct loaded)> done);

// Permanently removes one fenced account and all of its live character state, on the
// writer in one transaction, behind the saves queued before it. done(deleted) runs on
// the game thread; an account already gone counts as deleted. False when not queued.
bool sql_delete_account(const char *name, std::function<void(bool deleted)> done);

// link player to account (updates player_data.account_name)

// ============================================================================
// locker functions
// ============================================================================

// delete locker
std::string sql_delete_locker_statement(int owner_pid, int owner_assoc_id);
bool sql_delete_locker_by_name(const char *locker_name);

// private chest functions
// private_chest_log action_type values
#define CHEST_ACTION_OPEN 1
#define CHEST_ACTION_CLOSE 2
#define CHEST_ACTION_PUT 3
#define CHEST_ACTION_GET 4
#define CHEST_ACTION_FAIL 5

bool sql_log_chest_activity(int locker_id, int chest_id, const char *char_name, int action_type,
			    const char *item_short);
bool sql_save_private_chest_items(int locker_id, int chest_id, P_obj chest_obj);
// A locker's items from the rows its entry read on the writer (storage_lockers.c):
// the chain of chest `chest_id`, or, with chest_obj, placed in that private chest.
P_obj sql_locker_items_from_rows(const sql_rows &rows, int locker_id, int chest_id,
				 P_obj chest_obj);

// account bank
struct AccountBankBalances
{
	int copper;
	int silver;
	int gold;
	int platinum;
};

bool sql_load_account_bank(const char *account_name, int racewar, P_char ch);
long long sql_account_bank_deposit(const char *account_name, int racewar, int coin_type,
				   int amount);
bool sql_account_bank_deposit_balances(const char *account_name, int racewar,
				       const AccountBankBalances *amounts,
				       AccountBankBalances *committed);
long long sql_account_bank_withdraw(const char *account_name, int racewar, int coin_type,
				    int amount);
int sql_account_bank_withdraw_value(const char *account_name, int racewar, int amount,
				    AccountBankBalances *committed, int *change);
bool sql_ensure_account_bank(const char *account_name, int racewar);

// ============================================================================
// migration helpers
// ============================================================================

// migrate single player from pfile to db
// loads from pfile, saves to db, verifies
bool sql_migrate_player(const char *name);

// verify player data matches between pfile and db
bool sql_verify_player(const char *name);

// migrate all players from pfiles to db
// returns count of successfully migrated players
int sql_migrate_all_players(void);

// ============================================================================
// utility
// ============================================================================

// escape string for sql (wrapper around mysql_real_escape_string)
// caller must free returned string
char *sql_escape_string(const char *str);

// log a redacted SQL failure with a stable call-site label
void sql_player_error(const char *site);

// corpses
bool sql_load_all_corpses(void);

// shopkeepers
bool sql_save_shopkeeper(P_char ch, int shop_nr);
bool sql_delete_shopkeeper(int shop_nr);
P_char sql_restore_shopkeeper(int shop_nr);
bool sql_restore_shopkeepers(void);
bool sql_save_dirty_shopkeepers(bool force = false);

// saved items
void sql_restore_saved_items(void);

// ships
struct ShipData;
bool sql_save_ship(struct ShipData *ship);
bool sql_load_all_ships(void);
struct ShipData *sql_place_ship(const char *owner_name, bool *unplaced);
bool sql_ship_stored(const char *owner_name);
std::string sql_delete_ship_statement(const char *owner_name);
bool sql_delete_ship(const char *owner_name);

// guilds
class Guild;
bool sql_save_guild(Guild *guild);
std::vector<std::string> sql_save_guild_statements(Guild *guild);
Guild *sql_load_guild(unsigned int guild_id);
bool sql_load_all_guilds(void);
bool sql_delete_guild(unsigned int guild_id);

// spellbooks (conjurable mobs); on MariaDB read at boot and kept in memory
bool sql_spellbooks_load(void);
bool sql_add_spellbook_mob(int pid, int mob_vnum);
bool sql_remove_spellbook_mob(int pid, int mob_vnum);
bool sql_has_spellbook_mob(int pid, int mob_vnum);
int *sql_get_spellbook_mobs(int pid, int *count);
bool sql_delete_spellbook_mobs(int pid);

#endif // __SQL_PLAYER_H_INCLUDED__
