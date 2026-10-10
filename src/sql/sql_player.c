// sql_player.c
// MariaDB storage for players, accounts, lockers, corpses, shopkeepers and saved items

#include "core/prototypes.h"
#include "core/structs.h"
#include "net/comm.h"
#include "net/output_preference_codec.h"
#include "world/db.h"
#include "core/utils.h"
#include "sql/sql_player.h"
#include "player/player_playtime.h"
#include "sql/item_extra_descr_codec.h"
#include <errno.h>
#include <limits.h>
#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <openssl/sha.h>
#include <sys/time.h>
#include <time.h>
#include <algorithm>
#include <chrono>
#include <functional>
#include <map>
#include <memory>
#include <set>
#include <new>
#include <string>
#include <thread>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include "account/account.h"
#include "guild/assocs.h"
#include "core/files.h"
#include "flatfile/flatfile_identity_adapter.h"
#include "flatfile/flatfile_identity_repository.h"
#include "flatfile/flatfile_locker_repository.h"
#include "flatfile/flatfile_recipe_repository.h"
#include "flatfile/flatfile_spellbook_repository.h"
#include "world/world_singletons.h"
#include "core/mm.h"
#include "classes/necromancy.h"
#include "ships/ships.h"
#include "redis/redis_ship_legacy.h"
#include "magic/spells.h"
#include "sql/sql.h"
#include "sql/sql_async.h"
#include "player/player_name.h"
#include "account/password_hash.h"
#include "player/player_revision_state.h"
#include "player/player_save_worker.h"
#include "persistence/persistence_mode.h"
#include "item/item_transfer_command.h"
#include "item/item_transfer_repository.h"
#include "item/item_claim_repository.h"

// external tables
extern P_index obj_index;
extern struct index_data *mob_index;
extern int top_of_world;
extern struct room_data *world;
extern P_char character_list;
extern P_acct account_list;
extern struct mm_ds *dead_mob_pool;
extern struct mm_ds *dead_pconly_pool;
extern struct mm_ds *dead_obj_pool;
extern P_obj object_list;
extern unsigned long next_obj_uid;
extern P_Guild guild_list;
extern Skill skills[];
void ensure_pconly_pool(void);

#ifdef __NO_MYSQL__

// stubs when mysql is disabled
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-parameter"

bool sql_begin_transaction(void)
{
	return false;
}
bool sql_commit(void)
{
	return false;
}
bool sql_rollback(void)
{
	return false;
}
bool sql_in_transaction(void)
{
	return false;
}

bool sql_add_player_recipe(int pid, int recipe_vnum)
{
	const char *root = persistence_mode_flatfile_root();
	std::string error;
	const auto result = root ? flatfile_recipe_add(root, pid, recipe_vnum, &error) :
				   flatfile_recipe_result::invalid;
	if (result == flatfile_recipe_result::ok)
		return true;
	persistence_alert(AVATAR, "recipes", "redacted", "none", "none", "add", "flat_write_failed",
			  "pid=%d recipe=%d error=%s", pid, recipe_vnum, error.c_str());
	return false;
}
bool sql_delete_player_recipes(int pid)
{
	const char *root = persistence_mode_flatfile_root();
	std::string error;
	const auto result = root ? flatfile_recipe_clear(root, pid, &error) :
				   flatfile_recipe_result::invalid;
	if (result == flatfile_recipe_result::ok)
		return true;
	persistence_alert(AVATAR, "recipes", "redacted", "none", "none", "clear",
			  "flat_write_failed", "pid=%d error=%s", pid, error.c_str());
	return false;
}
bool sql_has_player_recipe(int pid, int recipe_vnum)
{
	const char *root = persistence_mode_flatfile_root();
	std::string error;
	bool contains = false;
	const auto result =
		root ? flatfile_recipe_contains(root, pid, recipe_vnum, &contains, &error) :
		       flatfile_recipe_result::invalid;
	if (result == flatfile_recipe_result::ok)
		return contains;
	persistence_alert(AVATAR, "recipes", "redacted", "none", "none", "contains",
			  "flat_read_failed", "pid=%d recipe=%d error=%s", pid, recipe_vnum,
			  error.c_str());
	return false;
}
int *sql_get_player_recipes(int pid, int *count)
{
	if (!count)
		return NULL;
	*count = 0;
	const char *root = persistence_mode_flatfile_root();
	std::string error;
	std::vector<int32_t> recipes;
	const auto result = root ? flatfile_recipe_list(root, pid, &recipes, &error) :
				   flatfile_recipe_result::invalid;
	if (result != flatfile_recipe_result::ok)
	{
		persistence_alert(AVATAR, "recipes", "redacted", "none", "none", "list",
				  "flat_read_failed", "pid=%d error=%s", pid, error.c_str());
		return NULL;
	}
	if (recipes.empty())
		return NULL;
	int *result_recipes = static_cast<int *>(malloc(recipes.size() * sizeof(int)));
	if (!result_recipes)
	{
		persistence_alert(AVATAR, "recipes", "redacted", "none", "none", "list",
				  "allocation_failed", "pid=%d recipes=%zu", pid, recipes.size());
		return NULL;
	}
	std::copy(recipes.begin(), recipes.end(), result_recipes);
	*count = static_cast<int>(recipes.size());
	return result_recipes;
}

bool sql_player_exists(const char *name)
{
	bool exists = true;
	std::string error;
	if (!flatfile_player_identity_exists(name, &exists, &error))
		return true;
	return exists;
}
int sql_get_player_pid(const char *name)
{
	int32_t pid = -1;
	std::string error;
	if (!flatfile_player_identity_pid(name, &pid, &error))
		return -1;
	return pid;
}
bool sql_player_names_load(void)
{
	return true;
}
void sql_player_names_set(int, const char *) {}
void sql_player_names_forget(int) {}
void sql_player_names_hold(int, const char *) {}
void sql_player_names_release(int, const char *) {}
const char *sql_get_player_name(int)
{
	return nullptr;
}
int sql_highest_player_pid(void)
{
	return 0;
}

bool sql_load_player_shapechanges(P_char ch)
{
	return false;
}

bool sql_save_account(struct acct_entry *acc)
{
	return false;
}

char *sql_escape_string(const char *str)
{
	return NULL;
}
void sql_player_error(const char *site) {}

bool sql_load_all_corpses(void)
{
	return false;
}

bool sql_save_shopkeeper(P_char ch, int shop_nr)
{
	return false;
}
bool sql_restore_shopkeepers(void)
{
	return true;
}
bool sql_save_dirty_shopkeepers(bool force)
{
	(void)force;
	return true;
}

void sql_restore_saved_items(void) {}
bool sql_save_ship(P_ship ship)
{
	return false;
}
P_ship sql_place_ship(const char * /*owner_name*/, bool *unplaced)
{
	if (unplaced)
		*unplaced = false;
	return NULL;
}
bool sql_ship_stored(const char * /*owner_name*/)
{
	return false;
}
bool sql_load_all_ships(void)
{
	return false;
}
bool sql_delete_ship(const char *owner_name)
{
	return false;
}

bool sql_save_guild(Guild *guild)
{
	return false;
}
Guild *sql_load_guild(unsigned int guild_id)
{
	return NULL;
}
bool sql_load_all_guilds(void)
{
	return false;
}

std::vector<std::string> sql_rename_character_statements(int, const char *, const char *, P_ship)
{
	return {};
}

bool sql_log_chest_activity(int /*locker_id*/, int /*chest_id*/, const char * /*char_name*/,
			    int /*action_type*/, const char * /*item_short*/)
{
	return false;
}
bool sql_save_private_chest_items(int /*locker_id*/, int /*chest_id*/, P_obj /*chest_obj*/)
{
	return false;
}
P_obj sql_locker_items_from_rows(const sql_rows & /*rows*/, int /*locker_id*/, int /*chest_id*/,
				 P_obj /*chest_obj*/)
{
	return NULL;
}

bool sql_add_spellbook_mob(int pid, int mob_vnum)
{
	const char *root = persistence_mode_flatfile_root();
	std::string error;
	const auto result = root ? flatfile_spellbook_add(root, pid, mob_vnum, &error) :
				   flatfile_spellbook_result::invalid;
	if (result == flatfile_spellbook_result::ok)
		return true;
	persistence_alert(AVATAR, "spellbooks", "redacted", "none", "none", "add",
			  "flat_write_failed", "pid=%d mob=%d error=%s", pid, mob_vnum,
			  error.c_str());
	return false;
}
bool sql_remove_spellbook_mob(int pid, int mob_vnum)
{
	const char *root = persistence_mode_flatfile_root();
	std::string error;
	const auto result = root ? flatfile_spellbook_remove(root, pid, mob_vnum, &error) :
				   flatfile_spellbook_result::invalid;
	if (result == flatfile_spellbook_result::ok)
		return true;
	persistence_alert(AVATAR, "spellbooks", "redacted", "none", "none", "remove",
			  "flat_write_failed", "pid=%d mob=%d error=%s", pid, mob_vnum,
			  error.c_str());
	return false;
}
bool sql_has_spellbook_mob(int pid, int mob_vnum)
{
	const char *root = persistence_mode_flatfile_root();
	std::string error;
	bool contains = false;
	const auto result =
		root ? flatfile_spellbook_contains(root, pid, mob_vnum, &contains, &error) :
		       flatfile_spellbook_result::invalid;
	if (result == flatfile_spellbook_result::ok)
		return contains;
	persistence_alert(AVATAR, "spellbooks", "redacted", "none", "none", "contains",
			  "flat_read_failed", "pid=%d mob=%d error=%s", pid, mob_vnum,
			  error.c_str());
	return false;
}
int *sql_get_spellbook_mobs(int pid, int *count)
{
	if (!count)
		return NULL;
	*count = 0;
	const char *root = persistence_mode_flatfile_root();
	std::string error;
	std::vector<int32_t> mobs;
	const auto loaded = root ? flatfile_spellbook_list(root, pid, &mobs, &error) :
				   flatfile_spellbook_result::invalid;
	if (loaded != flatfile_spellbook_result::ok)
	{
		persistence_alert(AVATAR, "spellbooks", "redacted", "none", "none", "list",
				  "flat_read_failed", "pid=%d error=%s", pid, error.c_str());
		return NULL;
	}
	if (mobs.empty())
		return NULL;
	int *result = static_cast<int *>(malloc(mobs.size() * sizeof(int)));
	if (!result)
	{
		persistence_alert(AVATAR, "spellbooks", "redacted", "none", "none", "list",
				  "allocation_failed", "pid=%d mobs=%zu", pid, mobs.size());
		return NULL;
	}
	std::copy(mobs.begin(), mobs.end(), result);
	*count = static_cast<int>(mobs.size());
	return result;
}

#pragma GCC diagnostic pop

#else

#include "flatfile/flatfile_shopkeeper_capture.h"
#include "player/player_snapshot_capture.h"
#include "player/player_snapshot_codec.h"
#include "player/player_snapshot_repository.h"

// globals

extern MYSQL *DB;

// track transaction state
static bool in_transaction = false;

// transaction helpers

bool sql_begin_transaction(void)
{
	if (!DB)
	{
		logit(LOG_DEBUG, "sql_begin_transaction: db not initialized");
		return false;
	}

	if (in_transaction)
	{
		logit(LOG_DEBUG, "sql_begin_transaction: already in transaction");
		return false;
	}

	sql_clear_results();
	if (!sql_trace_exec("sql_begin_transaction", "START TRANSACTION", 17, false, false))
	{
		logit(LOG_DEBUG, "sql_begin_transaction: failed");
		return false;
	}

	in_transaction = true;
	return true;
}

bool sql_commit(void)
{
	if (!DB)
	{
		logit(LOG_DEBUG, "sql_commit: db not initialized");
		return false;
	}

	if (!in_transaction)
	{
		logit(LOG_DEBUG, "sql_commit: not in transaction");
		return false;
	}

	if (!sql_trace_exec("sql_commit", "COMMIT", 6, false, false))
	{
		logit(LOG_DEBUG, "sql_commit: failed");
		/* Keep transaction ownership intact so the caller can attempt an
		 * explicit rollback.  A failed COMMIT leaves server-side durability
		 * uncertain; claiming the transaction ended here would make that
		 * recovery path impossible. */
		return false;
	}

	in_transaction = false;
	return true;
}

bool sql_rollback(void)
{
	if (!DB)
	{
		logit(LOG_DEBUG, "sql_rollback: db not initialized");
		return false;
	}

	if (!in_transaction)
	{
		logit(LOG_DEBUG, "sql_rollback: not in transaction");
		return false;
	}

	if (!sql_trace_exec("sql_rollback", "ROLLBACK", 8, false, false))
	{
		logit(LOG_DEBUG, "sql_rollback: failed");
		in_transaction = false;
		return false;
	}

	in_transaction = false;
	return true;
}

bool sql_in_transaction(void)
{
	return in_transaction;
}

// Shared helper: for an item being saved, fill the
// wear_str, type_str, and bv1-5_str output buffers with the
// item's wear_flags, type, and bitvectors.  Each buffer must be
// at least 32 bytes (16 for type_str).  The bitvector buffers
// are set to the numeric value if it differs from the prototype,
// or to the literal "NULL" otherwise (load code uses NULL to
// mean "use prototype value").
//
// SIDE EFFECT: the prototype object loaded internally is freed
// (extract_obj) before returning.  The function name makes this
// explicit so callers can't accidentally skip the cleanup.
static int sql_validate_loaded_item_type(P_obj obj, int saved_type, const char *context)
{
	if (!obj)
		return saved_type;

	if (saved_type <= 0)
		return obj->type;

	if (saved_type > ITEM_LAST)
	{
		logit(LOG_DEBUG,
		      "sql item repair: ignoring out-of-range item_type for vnum=%d saved_type=%d proto_type=%d context=%s",
		      OBJ_VNUM(obj), saved_type, obj->type, context ? context : "(null)");
		return obj->type;
	}

	if (saved_type == ITEM_CORPSE && obj->type != ITEM_CORPSE)
	{
		logit(LOG_DEBUG,
		      "sql item repair: ignoring corpse item_type for vnum=%d saved_type=%d proto_type=%d context=%s",
		      OBJ_VNUM(obj), saved_type, obj->type, context ? context : "(null)");
		return obj->type;
	}

	return saved_type;
}

static void sql_format_item_diff_fields_and_free_proto(P_obj obj, char *wear_str, char *type_str,
						       char *material_str, char *bv1_str,
						       char *bv2_str, char *bv3_str, char *bv4_str,
						       char *bv5_str)
{
	P_obj proto = read_object(obj->R_num, REAL);

	if (proto)
	{
		if (obj->wear_flags != proto->wear_flags)
			snprintf(wear_str, 32, "%d", obj->wear_flags);
		else
			strcpy(wear_str, "NULL");

		if (obj->type != proto->type)
			snprintf(type_str, 16, "%d", obj->type);
		else
			strcpy(type_str, "NULL");

		if (obj->material != proto->material)
			snprintf(material_str, 16, "%d", obj->material);
		else
			strcpy(material_str, "NULL");

		if (obj->bitvector != proto->bitvector)
			snprintf(bv1_str, 32, "%lu", obj->bitvector);
		else
			strcpy(bv1_str, "NULL");
		if (obj->bitvector2 != proto->bitvector2)
			snprintf(bv2_str, 32, "%lu", obj->bitvector2);
		else
			strcpy(bv2_str, "NULL");
		if (obj->bitvector3 != proto->bitvector3)
			snprintf(bv3_str, 32, "%lu", obj->bitvector3);
		else
			strcpy(bv3_str, "NULL");
		if (obj->bitvector4 != proto->bitvector4)
			snprintf(bv4_str, 32, "%lu", obj->bitvector4);
		else
			strcpy(bv4_str, "NULL");
		if (obj->bitvector5 != proto->bitvector5)
			snprintf(bv5_str, 32, "%lu", obj->bitvector5);
		else
			strcpy(bv5_str, "NULL");
	}
	else
	{
		snprintf(wear_str, 32, "%d", obj->wear_flags);
		snprintf(type_str, 16, "%d", obj->type);
		snprintf(material_str, 16, "%d", obj->material);
		snprintf(bv1_str, 32, "%lu", obj->bitvector);
		snprintf(bv2_str, 32, "%lu", obj->bitvector2);
		snprintf(bv3_str, 32, "%lu", obj->bitvector3);
		snprintf(bv4_str, 32, "%lu", obj->bitvector4);
		snprintf(bv5_str, 32, "%lu", obj->bitvector5);
	}

	if (proto)
		extract_obj(proto);
}

// utility functions

// escape string for sql, caller must free
char *sql_escape_string(const char *str)
{
	if (!str || !DB)
		return NULL;

	size_t len = strlen(str);
	// mysql_real_escape_string needs at most len*2+1 bytes
	char *escaped = (char *)malloc(len * 2 + 1);
	if (!escaped)
		return NULL;

	mysql_real_escape_string(DB, escaped, str, len);
	return escaped;
}

// log SQL failure by stable call-site label only
void sql_player_error(const char *site)
{
	if (!DB)
	{
		logit(LOG_DEBUG, "sql_player: site=%s outcome=unavailable", site);
		return;
	}
	logit(LOG_DEBUG, "sql_player: site=%s outcome=failure error_code=%u sqlstate=%.5s", site,
	      (unsigned int)mysql_errno(DB), mysql_sqlstate(DB));
}

// helper to run query and free result
static bool sql_run_query(const char *query)
{
	if (!DB || !query)
		return false;

	if (!sql_trace_exec("sql_run_query", query, strlen(query), false, false))
	{
		sql_player_error("sql_run_query");
		return false;
	}

	// consume any result set
	MYSQL_RES *result = mysql_store_result(DB);
	if (result)
		mysql_free_result(result);

	return true;
}

static void sql_load_item_extra_descr_values(const char *db_keyword, const char *db_description,
					     struct extra_descr_data *ed, const char *table,
					     int item_id)
{
	const bool stored_spellbook = (db_keyword && strcmp(db_keyword, "SPELLBOOK") == 0) ||
				      sql_item_extra_descr_is_spellbook_marker(db_keyword);

	if (stored_spellbook)
	{
		const size_t buflen = (MAX_SKILLS + 1) / 8 + 1;
		char decoded_bits[(MAX_SKILLS + 1) / 8 + 1];
		const sql_spellbook_decode_status status = sql_decode_stored_spellbook(
			db_keyword, db_description, decoded_bits, sizeof(decoded_bits));
		if (status == sql_spellbook_decode_status::invalid)
		{
			// Keep malformed canonical data visible instead of silently replacing it
			// with an empty native bitmap. It cannot be used as a spellbook until
			// repaired, but a later save must not erase the evidence we need to recover.
			ed->keyword = db_keyword ? str_dup(db_keyword) : str_dup("");
			ed->description = db_description ? str_dup(db_description) : NULL;
			persistence_alert(
				AVATAR, "item_extra_descr", table ? table : "unknown", "none",
				"none", "invalid_spellbook_encoding",
				"item_id=%d had a malformed canonical spellbook description; preserved it for repair",
				item_id);
			return;
		}

		CREATE(ed->keyword, char, 4, MEM_TAG_STRING);
		ed->keyword[0] = 3;
		ed->keyword[1] = 1;
		ed->keyword[2] = 3;
		ed->keyword[3] = '\0';

		CREATE(ed->description, char, buflen, MEM_TAG_STRING);
		memcpy(ed->description, decoded_bits, buflen);
		if (status == sql_spellbook_decode_status::legacy_corrupt)
		{
			persistence_alert(
				AVATAR, "item_extra_descr", table ? table : "unknown", "none",
				"none", "legacy_spellbook_corrupt",
				"item_id=%d had a raw truncated spellbook marker; loaded an empty safe bitmap",
				item_id);
		}
		return;
	}

	ed->keyword = db_keyword ? str_dup(db_keyword) : str_dup("");
	ed->description = db_description ? str_dup(db_description) : NULL;
}

// player existence check

namespace
{
// Every player_data row's pid, name and active flag, read at boot and kept current by the
// game's own writes (entry, renames, deletion), so a lookup never waits on the database.
struct player_name
{
	std::string name;
	bool active;
};
std::unordered_map<int, player_name> names_by_pid;
int highest_pid = 0;
// The lowercase name to the pid a lookup gives: the active character of that name.
std::unordered_map<std::string, int> pids_by_name;

std::string lowercase(const char *name)
{
	std::string lower = name;
	for (char &letter : lower)
		letter = LOWER(letter);
	return lower;
}
} // namespace

bool sql_player_names_load(void)
{
	MYSQL_RES *result = db_query("SELECT pid, name, active FROM player_data");
	if (!result)
		return false;
	names_by_pid.clear();
	pids_by_name.clear();
	while (MYSQL_ROW row = mysql_fetch_row(result))
	{
		if (!row[0] || !row[1])
			continue;
		const int pid = atoi(row[0]);
		const bool active = row[2] && atoi(row[2]);
		names_by_pid[pid] = { row[1], active };
		highest_pid = std::max(highest_pid, pid);
		auto [named, added] = pids_by_name.try_emplace(lowercase(row[1]), pid);
		if (!added && active)
			named->second = pid;
	}
	mysql_free_result(result);
	// Never a deleted character's pid again: rows keyed by pid outlive the character.
	highest_pid =
		std::max(highest_pid, static_cast<int>(sql_next_auto_increment("player_data")) - 1);
	return true;
}

void sql_player_names_set(int pid, const char *name)
{
	if (pid <= 0 || !name)
		return;
	sql_player_names_forget(pid);
	const std::string lower = lowercase(name);
	// As at entry in the database: any other character of that name is inactive.
	for (auto &[other, entry] : names_by_pid)
		if (lowercase(entry.name.c_str()) == lower)
			entry.active = false;
	names_by_pid[pid] = { name, true };
	pids_by_name[lower] = pid;
	highest_pid = std::max(highest_pid, pid);
}

int sql_highest_player_pid(void)
{
	return highest_pid;
}

void sql_player_names_forget(int pid)
{
	auto found = names_by_pid.find(pid);
	if (found == names_by_pid.end())
		return;
	auto named = pids_by_name.find(lowercase(found->second.name.c_str()));
	if (named != pids_by_name.end() && named->second == pid)
		pids_by_name.erase(named);
	names_by_pid.erase(found);
}

void sql_player_names_hold(int pid, const char *name)
{
	pids_by_name.try_emplace(lowercase(name), pid);
}

void sql_player_names_release(int pid, const char *name)
{
	auto named = pids_by_name.find(lowercase(name));
	if (named != pids_by_name.end() && named->second == pid)
		pids_by_name.erase(named);
}

const char *sql_get_player_name(int pid)
{
	auto found = names_by_pid.find(pid);
	return found != names_by_pid.end() && found->second.active ? found->second.name.c_str() :
								     nullptr;
}

bool sql_player_exists(const char *name)
{
	return name && pids_by_name.count(lowercase(name));
}

/*
 * What else the character's name keys, besides the player row and the ship: the
 * account mapping that login reads, a personal locker and its access list, the
 * character's own grants on other lockers, their guild roster row and top-fragger
 * credit, and their leaderboard name.  Corpses keep the name they were made under,
 * which the corpse objects in the world also carry, and logs keep their history.
 *
 * A grant naming an account as well as the character is ambiguous, and stays
 * with the account.  If the new name already holds a grant on a locker, the
 * old one is dropped.
 */
static std::vector<std::string> sql_rename_character_references(int pid, const char *old_name,
								const char *new_name)
{
	const std::string old_escaped = escape_str(old_name);
	const std::string new_escaped = escape_str(new_name);
	const char *esc_old = old_escaped.c_str();
	const char *esc_new = new_escaped.c_str();
	return {
		/* Earlier renames could leave a second active mapping for the pid; keep
		 * the oldest, so the one rename below cannot collide with itself. */
		sql_format(
			"DELETE stale FROM account_characters stale JOIN account_characters keeper "
			"ON keeper.pid=stale.pid AND keeper.id<stale.id AND keeper.deleted_at IS NULL "
			"WHERE stale.pid=%d AND stale.deleted_at IS NULL",
			pid),
		sql_format("UPDATE account_characters SET char_name='%s' "
			   "WHERE pid=%d AND deleted_at IS NULL",
			   esc_new, pid),
		sql_format(
			"UPDATE lockers SET locker_name=CONCAT('%s','.locker') "
			"WHERE locker_name=CONCAT('%s','.locker') AND (owner_pid=%d OR owner_pid IS NULL)",
			esc_new, esc_old, pid),
		sql_format("UPDATE locker_access SET owner=CONCAT('%s','.locker') "
			   "WHERE owner=CONCAT('%s','.locker')",
			   esc_new, esc_old),
		sql_format("UPDATE IGNORE locker_access SET visitor='%s' WHERE visitor='%s' "
			   "AND NOT EXISTS (SELECT 1 FROM accounts WHERE account_name='%s')",
			   esc_new, esc_old, esc_old),
		sql_format("DELETE FROM locker_access WHERE visitor='%s' "
			   "AND NOT EXISTS (SELECT 1 FROM accounts WHERE account_name='%s')",
			   esc_old, esc_old),
		sql_format("UPDATE guild_members SET player_name='%s' "
			   "WHERE player_pid=%d OR (player_pid IS NULL AND player_name='%s')",
			   esc_new, pid, esc_old),
		sql_format("UPDATE guilds SET topfragger='%s' WHERE topfragger='%s'", esc_new,
			   esc_old),
		sql_format("UPDATE frag_leaderboard SET char_name='%s' WHERE pid=%d", esc_new, pid),
	};
}

static std::vector<std::string> sql_save_ship_statements(P_ship ship);

std::vector<std::string> sql_rename_character_statements(int pid, const char *old_name,
							 const char *new_name, P_ship ship)
{
	char stored_name[MAX_STRING_LENGTH];
	strlcpy(stored_name, new_name, sizeof(stored_name));
	normalize_player_name_case(stored_name);
	std::vector<std::string> statements = { sql_format(
		"UPDATE player_data SET name='%s' WHERE pid=%d", escape_str(stored_name).c_str(),
		pid) };
	for (std::string &statement : sql_rename_character_references(pid, old_name, stored_name))
		statements.push_back(std::move(statement));
	if (ship)
		for (std::string &statement : sql_save_ship_statements(ship))
			statements.push_back(std::move(statement));
	return statements;
}

int sql_get_player_pid(const char *name)
{
	if (!name)
		return -1;
	auto named = pids_by_name.find(lowercase(name));
	return named != pids_by_name.end() ? named->second : -1;
}

static bool sql_merge_duplicate_spellbook(struct extra_descr_data *existing,
					  struct extra_descr_data *candidate);

// Attach one stored extra description to obj. A second native spellbook row of the
// same item is merged into the first (*loaded_spellbook) instead of attached.
static void sql_add_item_extra_descr(P_obj obj, const char *keyword, const char *description,
				     const char *table, int item_id,
				     struct extra_descr_data **loaded_spellbook)
{
	struct extra_descr_data *ed;
	CREATE(ed, extra_descr_data, 1, MEM_TAG_EXDESCD);

	sql_load_item_extra_descr_values(keyword, description, ed, table, item_id);

	if (sql_item_extra_descr_is_spellbook_marker(ed->keyword))
	{
		if (*loaded_spellbook && sql_merge_duplicate_spellbook(*loaded_spellbook, ed))
		{
			persistence_alert(
				AVATAR, "item_extra_descr", table ? table : "unknown", "none",
				"none", "duplicate_spellbook_rows",
				"item_id=%d had duplicate native spellbook rows; merged their bitmaps",
				item_id);
			return;
		}
		*loaded_spellbook = ed;
	}
	ed->next = obj->ex_description;
	obj->ex_description = ed;
	obj->str_mask |= STRUNG_EDESC;
}

static bool sql_load_item_extra_descr_from_table(int item_id, P_obj obj, const char *table)
{
	char query[256];
	if (!obj || !DB)
		return true;

	// TABLE is the base item table name; this helper appends _extra_descr.
	// Keep callers on the base name so locker_item does not become
	// locker_item_extra_descr_extra_descr.
	snprintf(query, sizeof(query),
		 "SELECT keyword, description "
		 "FROM %s_extra_descr "
		 "WHERE item_id=%d",
		 table, item_id);

	MYSQL_RES *result = db_query("%s", query);
	if (!result)
		return false;
	struct extra_descr_data *loaded_spellbook = NULL;
	MYSQL_ROW row;
	while ((row = mysql_fetch_row(result)))
		sql_add_item_extra_descr(obj, row[0], row[1], table, item_id, &loaded_spellbook);
	mysql_free_result(result);
	return true;
}

// A legacy save can leave both a raw-marker row (which decodes to an empty
// safe bitmap) and a later canonical row for the same item. Never let row
// order decide which one find_spell_description() sees; merge duplicate native
// bitmaps before attaching the candidate to the object. The caller supplies
// only rows loaded from this table, so a native marker from the object
// prototype is not accidentally merged into persisted state.
static bool sql_merge_duplicate_spellbook(struct extra_descr_data *existing,
					  struct extra_descr_data *candidate)
{
	if (!existing || !candidate ||
	    !sql_item_extra_descr_is_spellbook_marker(existing->keyword) ||
	    !sql_item_extra_descr_is_spellbook_marker(candidate->keyword))
		return false;

	const size_t byte_count = (MAX_SKILLS + 1) / 8 + 1;
	if (existing->description && candidate->description)
		for (size_t offset = 0; offset < byte_count; ++offset)
			existing->description[offset] = static_cast<char>(
				static_cast<unsigned char>(existing->description[offset]) |
				static_cast<unsigned char>(candidate->description[offset]));
	else if (!existing->description && candidate->description)
	{
		existing->description = candidate->description;
		candidate->description = NULL;
	}
	if (candidate->keyword)
		str_free(candidate->keyword);
	if (candidate->description)
		str_free(candidate->description);
	FREE(candidate);
	return true;
}

// Set obj's affects to its stored (location, modifier) rows. Any stored row replaces
// the prototype's affects; duplicates are dropped.
static void sql_set_item_affects(P_obj obj, const std::vector<std::pair<int, int>> &affects)
{
	if (affects.empty())
		return;
	for (int a = 0; a < MAX_OBJ_AFFECT; a++)
	{
		obj->affected[a].location = 0;
		obj->affected[a].modifier = 0;
	}
	int aff_idx = 0;
	for (const auto &[loc, mod] : affects)
	{
		if (aff_idx >= MAX_OBJ_AFFECT)
			break;
		bool is_dup = false;
		for (int d = 0; d < aff_idx; d++)
			if (obj->affected[d].location == loc && obj->affected[d].modifier == mod)
			{
				is_dup = true;
				break;
			}
		if (!is_dup)
		{
			obj->affected[aff_idx].location = loc;
			obj->affected[aff_idx].modifier = mod;
			aff_idx++;
		}
	}
}

static bool sql_save_item_extra_descr(int item_id, P_obj obj, const char *table)
{
	if (!obj || !DB)
		return true;

	// The incremental and equipment-only save paths update item rows in place, so the
	// FK cascade from a full inventory delete never runs. Without clearing the rows
	// first every save appends another exact copy of each description until the load
	// path rejects the whole character as a corrupt snapshot.
	char del_query[256];
	snprintf(del_query, sizeof(del_query), "DELETE FROM %s WHERE item_id = %d", table, item_id);
	if (!sql_run_query(del_query))
		return false;

	if (!obj->ex_description)
		return true;

	const size_t spellbook_bytes = (MAX_SKILLS + 1) / 8 + 1;
	char spellbook_bits[(MAX_SKILLS + 1) / 8 + 1] = {};
	static const char spellbook_marker[] = { 3, 1, 3, 0 };
	for (struct extra_descr_data *source = obj->ex_description; source; source = source->next)
	{
		if (!sql_item_extra_descr_is_spellbook_marker(source->keyword) ||
		    !source->description)
			continue;
		for (size_t offset = 0; offset < spellbook_bytes; ++offset)
			spellbook_bits[offset] = static_cast<char>(
				static_cast<unsigned char>(spellbook_bits[offset]) |
				static_cast<unsigned char>(source->description[offset]));
	}

	bool spellbook_emitted = false;
	std::unordered_set<std::string> description_keys;
	struct extra_descr_data *ed;
	for (ed = obj->ex_description; ed; ed = ed->next)
	{
		if (!ed->keyword)
			continue;

		const char *source_keyword = ed->keyword;
		const char *source_description = ed->description;
		if (sql_item_extra_descr_is_spellbook_marker(ed->keyword))
		{
			if (spellbook_emitted)
				continue;
			spellbook_emitted = true;
			source_keyword = spellbook_marker;
			source_description = spellbook_bits;
		}

		char *db_keyword = NULL;
		char *db_desc = NULL;

		if (!sql_encode_item_extra_descr(source_keyword, source_description, &db_keyword,
						 &db_desc))
			return false;
		std::string description_key = db_keyword;
		description_key.push_back('\0');
		if (db_desc)
			description_key += db_desc;
		if (!description_keys.insert(std::move(description_key)).second)
		{
			free(db_keyword);
			if (db_desc)
				free(db_desc);
			continue;
		}

		char query[32768];
		int written;
		if (db_desc)
		{
			written = snprintf(
				query, sizeof(query),
				"INSERT INTO %s (item_id, keyword, description) VALUES (%d, '%s', '%s')",
				table, item_id, db_keyword, db_desc);
		}
		else
		{
			written = snprintf(
				query, sizeof(query),
				"INSERT INTO %s (item_id, keyword, description) VALUES (%d, '%s', NULL)",
				table, item_id, db_keyword);
		}
		if (written < 0 || static_cast<size_t>(written) >= sizeof(query))
		{
			free(db_keyword);
			if (db_desc)
				free(db_desc);
			return false;
		}

		free(db_keyword);
		if (db_desc)
			free(db_desc);

		if (!sql_run_query(query))
			return false;
	}
	return true;
}

// shapechange save/load

bool sql_load_player_shapechanges(P_char ch)
{
	if (!ch || !IS_PC(ch) || !DB)
		return false;

	int pid = GET_PID(ch);
	if (pid <= 0)
		return false;

	// only load if character has shapechange innate
	if (!has_innate(ch, INNATE_SHAPECHANGE))
		return true;

	// clear existing shapes (defined in files.c)
	extern void delete_knownShapes(P_char ch);
	if (ch->only.pc->knownShapes)
		delete_knownShapes(ch);

	char query[256];
	snprintf(
		query, sizeof(query),
		"SELECT mob_vnum, times_researched, UNIX_TIMESTAMP(last_researched), UNIX_TIMESTAMP(last_shapechanged) "
		"FROM player_shapechanges WHERE pid=%d ORDER BY id",
		pid);

	MYSQL_RES *result = db_query("%s", query);
	if (!result)
		return false;

	struct char_shapechange_data **ppShape = &(ch->only.pc->knownShapes);
	MYSQL_ROW row;

	while ((row = mysql_fetch_row(result)))
	{
		int vnum = atoi(row[0]);

		// ensure vnum exists
		if (!real_mobile(vnum))
			continue;

		struct char_shapechange_data *shape;
		CREATE(shape, char_shapechange_data, 1, MEM_TAG_SHPCHNG);
		shape->mobVnum = vnum;
		shape->timesResearched = atoi(row[1]);
		shape->lastResearched = atol(row[2]);
		shape->lastShapechanged = atol(row[3]);
		shape->next = NULL;

		*ppShape = shape;
		ppShape = &(shape->next);
	}

	mysql_free_result(result);
	return true;
}

// recipe save/load

namespace
{
// Every character's recipes, in the order learned: read at boot, changed here at once, and
// written on the writer. Only the game writes player_recipes.
std::unordered_map<int, std::vector<int>> recipes_by_pid;
} // namespace

bool sql_player_recipes_load(void)
{
	MYSQL_RES *result = db_query("SELECT pid, recipe_vnum FROM player_recipes ORDER BY id");
	if (!result)
		return false;
	recipes_by_pid.clear();
	while (MYSQL_ROW row = mysql_fetch_row(result))
		if (row[0] && row[1])
			recipes_by_pid[atoi(row[0])].push_back(atoi(row[1]));
	mysql_free_result(result);
	return true;
}

bool sql_add_player_recipe(int pid, int recipe_vnum)
{
	if (!DB || pid <= 0)
		return false;
	std::vector<int> &recipes = recipes_by_pid[pid];
	if (std::find(recipes.begin(), recipes.end(), recipe_vnum) != recipes.end())
		return true;
	recipes.push_back(recipe_vnum);
	return sql_queue("INSERT IGNORE INTO player_recipes (pid, recipe_vnum) VALUES (%d, %d)",
			 pid, recipe_vnum);
}

bool sql_delete_player_recipes(int pid)
{
	if (!DB || pid <= 0)
		return false;
	recipes_by_pid.erase(pid);
	return sql_queue("DELETE FROM player_recipes WHERE pid=%d", pid);
}

bool sql_has_player_recipe(int pid, int recipe_vnum)
{
	const auto found = recipes_by_pid.find(pid);
	return found != recipes_by_pid.end() &&
	       std::find(found->second.begin(), found->second.end(), recipe_vnum) !=
		       found->second.end();
}

// returns array of recipe vnums, sets count. caller must free array
int *sql_get_player_recipes(int pid, int *count)
{
	*count = 0;
	const auto found = recipes_by_pid.find(pid);
	if (found == recipes_by_pid.end() || found->second.empty())
		return NULL;
	int *recipes = (int *)malloc(found->second.size() * sizeof(int));
	if (!recipes)
		return NULL;
	std::copy(found->second.begin(), found->second.end(), recipes);
	*count = static_cast<int>(found->second.size());
	return recipes;
}

bool sql_save_account(struct acct_entry *acc)
{
	if (!DB || !acc || !acc->acct_name)
		return false;

	const std::string name = escape_str(acc->acct_name);
	const std::string email = escape_str(acc->acct_email ? acc->acct_email : "");
	const std::string password = escape_str(acc->acct_password ? acc->acct_password : "");
	const std::string confirmation =
		escape_str(acc->acct_confirmation ? acc->acct_confirmation : "");
	std::vector<std::string> statements;
	statements.push_back(sql_format(
		"insert into accounts (account_name, email, password, confirmation_code, "
		"confirmed, confirmation_sent, blocked, last_login, last_good_char, last_evil_char, "
		"flags1, flags2, flags3, flags4) values ('%s', '%s', '%s', '%s', %d, %d, %d, FROM_UNIXTIME(NULLIF(%ld,0)), FROM_UNIXTIME(NULLIF(%ld,0)), FROM_UNIXTIME(NULLIF(%ld,0)), %lu, %lu, %lu, %lu) "
		"on duplicate key update email='%s', password='%s', confirmation_code='%s', "
		"confirmed=%d, confirmation_sent=%d, blocked=%d, last_login=FROM_UNIXTIME(NULLIF(%ld,0)), last_good_char=FROM_UNIXTIME(NULLIF(%ld,0)), last_evil_char=FROM_UNIXTIME(NULLIF(%ld,0)), "
		"flags1=%lu, flags2=%lu, flags3=%lu, flags4=%lu",
		name.c_str(), email.c_str(), password.c_str(), confirmation.c_str(),
		acc->acct_confirmed, acc->acct_confirmation_sent, acc->acct_blocked, acc->acct_last,
		acc->acct_good, acc->acct_evil, acc->acct_flags1, acc->acct_flags2,
		acc->acct_flags3, acc->acct_flags4, email.c_str(), password.c_str(),
		confirmation.c_str(), acc->acct_confirmed, acc->acct_confirmation_sent,
		acc->acct_blocked, acc->acct_last, acc->acct_good, acc->acct_evil, acc->acct_flags1,
		acc->acct_flags2, acc->acct_flags3, acc->acct_flags4));
	statements.push_back(
		sql_format("DELETE FROM account_ips WHERE account_name='%s'", name.c_str()));
	for (struct acct_ip *ip = acc->acct_unique_ips; ip; ip = ip->next)
		statements.push_back(sql_format(
			"INSERT INTO account_ips (account_name, hostname, ip_address, count, updated_at) "
			"VALUES ('%s', '%s', '%s', %lu, FROM_UNIXTIME(%ld))",
			name.c_str(), escape_str(ip->hostname ? ip->hostname : "").c_str(),
			escape_str(ip->ip_address ? ip->ip_address : "").c_str(), ip->count,
			(long)ip->last_seen));

	struct mapping
	{
		std::string name;
		unsigned long count;
		long last;
		int blocked;
		int racewar;
	};
	std::vector<mapping> characters;
	for (struct acct_chars *ch = acc->acct_character_list; ch; ch = ch->next)
		if (ch->charname)
			characters.push_back({ escape_str(ch->charname), ch->count, ch->last,
					       ch->blocked, ch->racewar });

	// Each character's mapping is resolved on the writer, just before the write it
	// decides.
	return sql_queue_work(
		[name, statements = std::move(statements),
		 characters = std::move(characters)](MYSQL *connection) -> unsigned int
		{
			for (const std::string &statement : statements)
				if (const unsigned int error_code =
					    sql_execute(connection, statement))
					return error_code;
			for (const mapping &character : characters)
			{
				sql_rows rows;
				if (const unsigned int error_code = sql_select(
					    connection,
					    sql_format("SELECT pid FROM player_data "
						       "WHERE LOWER(name)=LOWER('%s') LIMIT 1",
						       character.name.c_str()),
					    &rows))
					return error_code;
				/* A brand new character has no player_data row yet, and
				   account_characters.pid is NOT NULL. Its first save writes the
				   mapping (sql_update_account_character()). */
				const long pid = !rows.empty() && rows[0][0] ? atol(rows[0][0]) : 0;
				if (pid <= 0)
					continue;
				/* Update an existing mapping in place. MySQL consumes an
				   account_characters identity value on every INSERT ... ON DUPLICATE
				   KEY UPDATE attempt, so projecting the same character on each account
				   save advanced the signed INT counter without adding a row. */
				long mapping_id = 0;
				if (const unsigned int error_code = sql_find_account_character_id(
					    connection, pid, character.name, &mapping_id))
					return error_code;
				if (const unsigned int error_code = sql_execute(
					    connection,
					    mapping_id > 0 ?
						    sql_format(
							    "update account_characters set login_count=%lu, last_login=FROM_UNIXTIME(NULLIF(%ld,0)), blocked=%d, racewar=%d, deleted_at=NULL, pid=%ld, account_name='%s', char_name='%s' where id=%ld",
							    character.count, character.last,
							    character.blocked, character.racewar,
							    pid, name.c_str(),
							    character.name.c_str(), mapping_id) :
						    /* A genuinely new mapping must allocate once; the
						       duplicate-key branch still converges against a
						       concurrent insert of the same unique char_name. */
						    sql_format(
							    "insert into account_characters (account_name, char_name, pid, login_count, last_login, blocked, racewar) "
							    "values ('%s', '%s', %ld, %lu, FROM_UNIXTIME(NULLIF(%ld,0)), %d, %d) "
							    "on duplicate key update login_count=%lu, last_login=FROM_UNIXTIME(NULLIF(%ld,0)), blocked=%d, racewar=%d, deleted_at=NULL, pid=VALUES(pid), account_name=VALUES(account_name), char_name=VALUES(char_name)",
							    name.c_str(), character.name.c_str(),
							    pid, character.count, character.last,
							    character.blocked, character.racewar,
							    character.count, character.last,
							    character.blocked, character.racewar)))
					return error_code;
			}
			return 0;
		});
}

/* Repair selectable account mappings only after safe opening baselines exist.
 * Returns 0 or the MySQL error; *repaired counts the mappings it changed. */
static unsigned int sql_repair_account_character_projection(MYSQL *connection,
							    const std::string &escaped_account,
							    int *repaired)
{
	const std::string eligibility = sql_format(
		"pd.active=1 AND LOWER(pd.account_name)=LOWER('%s') AND NOT EXISTS ("
		"SELECT 1 FROM account_characters tombstone WHERE tombstone.deleted_at IS NOT NULL "
		"AND (tombstone.pid=pd.pid OR LOWER(tombstone.char_name)=LOWER(pd.name)))",
		escaped_account.c_str());
	const std::string baselines[] = {
		sql_format(
			"INSERT INTO currency_wallet_baseline(pid,opening_copper,opening_silver,"
			"opening_gold,opening_platinum,opening_revision) "
			"SELECT pd.pid,pd.copper,pd.silver,pd.gold,pd.platinum,pd.wallet_revision "
			"FROM player_data pd WHERE %s AND pd.wallet_revision=0 "
			"AND NOT EXISTS (SELECT 1 FROM currency_ledger ledger WHERE ledger.pid=pd.pid) "
			"AND NOT EXISTS (SELECT 1 FROM currency_wallet_baseline baseline "
			"WHERE baseline.pid=pd.pid)",
			eligibility.c_str()),
		sql_format(
			"INSERT INTO epic_balance_baseline(pid,opening_balance,opening_revision) "
			"SELECT pd.pid,pd.epics,pd.epic_revision FROM player_data pd WHERE %s "
			"AND pd.epic_revision=0 AND NOT EXISTS (SELECT 1 FROM epic_ledger ledger "
			"WHERE ledger.pid=pd.pid) AND NOT EXISTS (SELECT 1 FROM epic_balance_baseline "
			"baseline WHERE baseline.pid=pd.pid)",
			eligibility.c_str()),
		sql_format(
			"INSERT INTO combat_frag_baseline(pid,opening_frags,opening_revision) "
			"SELECT pd.pid,pd.frags,pd.frag_revision FROM player_data pd WHERE %s "
			"AND pd.frag_revision=0 AND NOT EXISTS (SELECT 1 FROM combat_frag_ledger ledger "
			"WHERE ledger.pid=pd.pid) AND NOT EXISTS (SELECT 1 FROM combat_frag_baseline "
			"baseline WHERE baseline.pid=pd.pid)",
			eligibility.c_str())
	};
	for (const std::string &statement : baselines)
		if (const unsigned int error_code = sql_execute(connection, statement))
			return error_code;

	/* A character renamed before renames carried their mapping along has two
	 * active mappings, and the repair below would then give both the same
	 * unique name.  Keep the one with the current name, or else the oldest. */
	if (const unsigned int error_code = sql_execute(
		    connection,
		    sql_format("DELETE stale FROM account_characters stale "
			       "JOIN player_data pd ON pd.pid=stale.pid "
			       "JOIN account_characters keeper ON keeper.pid=stale.pid "
			       "AND keeper.id<>stale.id AND keeper.deleted_at IS NULL "
			       "AND (LOWER(keeper.char_name)=LOWER(pd.name) OR keeper.id<stale.id) "
			       "WHERE stale.deleted_at IS NULL "
			       "AND LOWER(stale.char_name)<>LOWER(pd.name) "
			       "AND LOWER(pd.account_name)=LOWER('%s')",
			       escaped_account.c_str())))
		return error_code;
	const my_ulonglong duplicates = mysql_affected_rows(connection);

	if (const unsigned int error_code = sql_execute(
		    connection,
		    sql_format("INSERT INTO account_characters "
			       "(id, account_name, pid, char_name, created_at, deleted_at) "
			       "SELECT active_mapping.id, pd.account_name, pd.pid, pd.name, NOW(), "
			       "NULL FROM player_data pd "
			       "LEFT JOIN account_characters active_mapping "
			       "ON active_mapping.pid=pd.pid AND active_mapping.deleted_at IS NULL "
			       "JOIN currency_wallet_baseline wallet ON wallet.pid=pd.pid "
			       "JOIN epic_balance_baseline epic ON epic.pid=pd.pid "
			       "JOIN combat_frag_baseline combat ON combat.pid=pd.pid "
			       "WHERE pd.active=1 AND LOWER(pd.account_name)=LOWER('%s') "
			       "AND NOT EXISTS ("
			       "SELECT 1 FROM account_characters tombstone "
			       "WHERE tombstone.deleted_at IS NOT NULL "
			       "AND (tombstone.pid=pd.pid "
			       "OR LOWER(tombstone.char_name)=LOWER(pd.name))) "
			       "ON DUPLICATE KEY UPDATE "
			       "account_name=VALUES(account_name), pid=VALUES(pid), "
			       "char_name=VALUES(char_name), deleted_at=NULL",
			       escaped_account.c_str())))
		return error_code;

	const my_ulonglong affected = mysql_affected_rows(connection) + duplicates;
	*repaired = affected > static_cast<my_ulonglong>(INT_MAX) ? INT_MAX :
								    static_cast<int>(affected);
	return 0;
}

namespace
{
// An account's rows, read on the writer.
struct account_rows
{
	int repaired = 0;
	sql_rows account;
	sql_rows ips;
	sql_rows characters;
};

P_acct account_from_rows(const account_rows &rows)
{
	if (rows.account.empty())
		return nullptr;
	const sql_row &row = rows.account[0];
	P_acct acc = allocate_account();
	acc->acct_name = str_dup(row[0] ? row[0] : "");
	acc->acct_email = str_dup(row[1] ? row[1] : "");
	acc->acct_password = str_dup(row[2] ? row[2] : "");
	acc->acct_confirmation = str_dup(row[3] ? row[3] : "");
	acc->acct_confirmed = row[4] ? atoi(row[4]) : 0;
	acc->acct_confirmation_sent = row[5] ? atoi(row[5]) : 0;
	acc->acct_blocked = row[6] ? atoi(row[6]) : 0;
	acc->acct_last = row[7] ? atol(row[7]) : 0;
	acc->acct_good = row[8] ? atol(row[8]) : 0;
	acc->acct_evil = row[9] ? atol(row[9]) : 0;
	acc->acct_flags1 = row[10] ? strtoul(row[10], NULL, 10) : 0;
	acc->acct_flags2 = row[11] ? strtoul(row[11], NULL, 10) : 0;
	acc->acct_flags3 = row[12] ? strtoul(row[12], NULL, 10) : 0;
	acc->acct_flags4 = row[13] ? strtoul(row[13], NULL, 10) : 0;

	struct acct_ip **ip_tail = &acc->acct_unique_ips;
	for (const sql_row &ip_row : rows.ips)
	{
		struct acct_ip *ip;
		CREATE(ip, struct acct_ip, 1, MEM_TAG_OTHER);
		ip->hostname = str_dup(ip_row[0] ? ip_row[0] : "");
		ip->ip_address = str_dup(ip_row[1] ? ip_row[1] : "");
		ip->count = ip_row[2] ? strtoul(ip_row[2], NULL, 10) : 0;
		ip->last_seen = ip_row[3] ? atol(ip_row[3]) : 0;
		*ip_tail = ip;
		ip_tail = &ip->next;
		acc->num_ips++;
	}

	struct acct_chars **character_tail = &acc->acct_character_list;
	for (const sql_row &character_row : rows.characters)
	{
		struct acct_chars *ch;
		CREATE(ch, struct acct_chars, 1, MEM_TAG_OTHER);
		ch->pid = character_row[0] ? atoi(character_row[0]) : 0;
		ch->charname = str_dup(character_row[1] ? character_row[1] : "");
		ch->count = character_row[2] ? strtoul(character_row[2], NULL, 10) : 0;
		ch->last = character_row[3] ? atol(character_row[3]) : 0;
		ch->blocked = character_row[4] ? atoi(character_row[4]) : 0;
		ch->racewar = character_row[5] ? atoi(character_row[5]) : 0;
		ch->level = character_row[6] ? atoi(character_row[6]) : 0;
		ch->race = character_row[7] ? atoi(character_row[7]) : 0;
		ch->m_class = character_row[8] ? (unsigned int)strtoul(character_row[8], NULL, 10) :
						 0;
		ch->secondary_class =
			character_row[9] ? (unsigned int)strtoul(character_row[9], NULL, 10) : 0;
		ch->last_room = character_row[10] ? atoi(character_row[10]) : 0;
		ch->last_save = character_row[11] ? atol(character_row[11]) : 0;
		ch->spec = character_row[12] ? atoi(character_row[12]) : 0;
		ch->played = character_row[13] ? atol(character_row[13]) : 0;
		*character_tail = ch;
		character_tail = &ch->next;
		acc->num_chars++;
	}
	return acc;
}
} // namespace

bool sql_load_account(const char *name, std::function<void(bool ok, P_acct loaded)> done)
{
	if (!DB || !name || !done)
		return false;
	const std::string account = escape_str(name);
	auto rows = std::make_shared<account_rows>();
	return sql_read_work(
		[account, rows](MYSQL *connection, sql_rows *) -> unsigned int
		{
			// A retried read starts over.
			*rows = account_rows();
			if (const unsigned int error_code = sql_repair_account_character_projection(
				    connection, account, &rows->repaired))
				return error_code;
			if (const unsigned int error_code = sql_select(
				    connection,
				    sql_format(
					    "select account_name, email, password, confirmation_code, confirmed, confirmation_sent, "
					    "blocked, UNIX_TIMESTAMP(last_login), UNIX_TIMESTAMP(last_good_char), "
					    "UNIX_TIMESTAMP(last_evil_char), flags1, flags2, flags3, flags4 "
					    "from accounts where account_name='%s'",
					    account.c_str()),
				    &rows->account))
				return error_code;
			if (const unsigned int error_code = sql_select(
				    connection,
				    sql_format(
					    "SELECT hostname, ip_address, count, UNIX_TIMESTAMP(updated_at) "
					    "FROM account_ips WHERE account_name='%s' AND "
					    "updated_at >= NOW() - INTERVAL 30 DAY",
					    account.c_str()),
				    &rows->ips))
				return error_code;
			return sql_select(
				connection,
				sql_format(
					"select ac.pid, ac.char_name, ac.login_count, UNIX_TIMESTAMP(ac.last_login), "
					"ac.blocked, ac.racewar, pd.level, pd.race, pd.m_class, pd.secondary_class, "
					"pd.last_room, UNIX_TIMESTAMP(pd.last_save), pd.spec, pd.played_time "
					"from account_characters ac "
					"left join player_data pd on ac.pid = pd.pid "
					"where LOWER(ac.account_name)=LOWER('%s') and ac.deleted_at is null",
					account.c_str()),
				&rows->characters);
		},
		[rows, done = std::move(done)](bool ok, const sql_rows &)
		{
			if (ok && rows->repaired > 0)
				statuslog(56, "account character projection repaired (affected=%d)",
					  rows->repaired);
			done(ok, ok ? account_from_rows(*rows) : nullptr);
		});
}

constexpr unsigned int ACCOUNT_LOCKER_SLOT_COUNT = 5;

static bool sql_format_account_locker_name_list(char *output, size_t output_size,
						const char *escaped_account)
{
	if (!output || !output_size || !escaped_account)
		return false;
	size_t used = 0;
	for (unsigned int slot = 0; slot < ACCOUNT_LOCKER_SLOT_COUNT; ++slot)
	{
		const int written = snprintf(output + used, output_size - used,
					     "%sLOWER(CONCAT('account.','%s','.%u.locker'))",
					     slot ? "," : "", escaped_account, slot);
		if (written < 0 || static_cast<size_t>(written) >= output_size - used)
			return false;
		used += static_cast<size_t>(written);
	}
	return true;
}

bool sql_delete_account(const char *name, std::function<void(bool deleted)> done)
{
	if (!DB || !name || !name[0] || !done)
		return false;

	const std::string account = escape_str(name);
	char locker_names_buffer[2048];
	if (!sql_format_account_locker_name_list(locker_names_buffer, sizeof(locker_names_buffer),
						 account.c_str()))
		return false;
	const std::string locker_names = locker_names_buffer;
	// Refusals the database raises no error for: the transaction rolls back.
	constexpr unsigned int refused = EPERM;

	return sql_read_work(
		[account, locker_names](MYSQL *connection, sql_rows *) -> unsigned int
		{
			sql_rows rows;
			if (const unsigned int error_code = sql_select(
				    connection,
				    sql_format("SELECT blocked FROM accounts WHERE "
					       "LOWER(account_name)=LOWER('%s') FOR UPDATE",
					       account.c_str()),
				    &rows))
				return error_code;
			if (rows.empty())
			{
				// Already gone: nothing of it may be left anywhere.
				sql_rows left;
				if (const unsigned int error_code = sql_select(
					    connection,
					    sql_format(
						    "SELECT (SELECT COUNT(*) FROM accounts WHERE LOWER(account_name)=LOWER('%s'))+"
						    "(SELECT COUNT(*) FROM player_data WHERE LOWER(account_name)=LOWER('%s'))+"
						    "(SELECT COUNT(*) FROM account_characters WHERE LOWER(account_name)=LOWER('%s'))",
						    account.c_str(), account.c_str(),
						    account.c_str()),
					    &left))
					return error_code;
				return left.size() == 1 && left[0][0] &&
						       strtoull(left[0][0], NULL, 10) == 0 ?
					       0 :
					       refused;
			}
			if (rows.size() != 1 || !rows[0][0] ||
			    atoi(rows[0][0]) != ACCOUNT_BLOCK_DELETION)
				return refused;

			/* player_data is the durable ownership source, while account_characters can
			 * retain a still-active projection after an interrupted legacy deletion. */
			rows.clear();
			if (const unsigned int error_code = sql_select(
				    connection,
				    sql_format(
					    "SELECT pd.pid,pd.name FROM player_data pd "
					    "WHERE LOWER(pd.account_name)=LOWER('%s') "
					    "UNION SELECT ac.pid,COALESCE(pd.name,ac.char_name) "
					    "FROM account_characters ac LEFT JOIN player_data pd ON pd.pid=ac.pid "
					    "WHERE LOWER(ac.account_name)=LOWER('%s') AND ac.deleted_at IS NULL",
					    account.c_str(), account.c_str()),
				    &rows))
				return error_code;
			std::vector<std::pair<int, std::string>> identities;
			for (const sql_row &row : rows)
			{
				const int pid = row[0] ? atoi(row[0]) : 0;
				if (pid <= 0 || !row[1] || !row[1][0] || identities.size() >= 1024)
					return refused;
				const auto duplicate =
					std::find_if(identities.begin(), identities.end(),
						     [pid](const auto &identity)
						     { return identity.first == pid; });
				if (duplicate == identities.end())
					identities.emplace_back(pid, row[1]);
				else if (strcasecmp(duplicate->second.c_str(), row[1]))
					return refused;
			}

			{
				/* Snapshot persistence never writes custody authority. Resolve the exact
				 * player, corpse, and locker owners here, then let the item repository move
				 * their complete topology to ledgered destruction inside this transaction. */
				std::vector<item_owner_identity> item_owners;
				const auto collect_item_owners = [&](const sql_rows &owner_rows)
				{
					for (const sql_row &owner_row : owner_rows)
					{
						if (!owner_row[0] || !owner_row[1] ||
						    !owner_row[2] || item_owners.size() >= 4096)
							return false;
						const unsigned long owner_type =
							strtoul(owner_row[0], NULL, 10);
						item_owner_identity owner = {
							static_cast<item_owner_type>(owner_type),
							strtoull(owner_row[1], NULL, 10),
							strtoull(owner_row[2], NULL, 10),
						};
						if (owner_type > UINT8_MAX ||
						    !item_owner_identity_valid(owner))
							return false;
						const auto duplicate = std::find_if(
							item_owners.begin(), item_owners.end(),
							[&](const auto &candidate) {
								return item_owner_identity_equal(
									candidate, owner);
							});
						if (duplicate == item_owners.end())
							item_owners.push_back(owner);
					}
					return true;
				};
				for (const auto &[pid, character_name] : identities)
				{
					(void)character_name;
					sql_rows owners;
					if (const unsigned int error_code = sql_select(
						    connection,
						    sql_format(
							    "SELECT DISTINCT owner_type,owner_id,owner_context_id "
							    "FROM item_current_owner WHERE "
							    "(owner_type=1 AND owner_id=%d) OR "
							    "(owner_type=4 AND (owner_id >> 32)=%d) OR "
							    "(owner_type=5 AND owner_id IN "
							    "(SELECT id FROM lockers WHERE owner_pid=%d))",
							    pid, pid, pid),
						    &owners))
						return error_code;
					if (!collect_item_owners(owners))
						return refused;
				}
				sql_rows owners;
				if (const unsigned int error_code = sql_select(
					    connection,
					    sql_format(
						    "SELECT DISTINCT ico.owner_type,ico.owner_id,ico.owner_context_id "
						    "FROM item_current_owner ico JOIN lockers l ON l.id=ico.owner_id "
						    "WHERE ico.owner_type=5 AND LOWER(l.locker_name) IN (%s)",
						    locker_names.c_str()),
					    &owners))
					return error_code;
				if (!collect_item_owners(owners))
					return refused;
				if (!item_transfer_repository_destroy_owners(
					    connection, item_owners.data(), item_owners.size()))
					return mysql_errno(connection) ? mysql_errno(connection) :
									 refused;
			}

			for (const auto &[pid, character_name] : identities)
			{
				std::string character(character_name.size() * 2 + 1, '\0');
				character.resize(mysql_real_escape_string(
					connection, character.data(), character_name.c_str(),
					character_name.size()));

				/* Auction custody can belong to another player. Refuse to erase through
				 * an unsettled listing instead of silently destroying shared value. */
				sql_rows unsettled;
				if (const unsigned int error_code = sql_select(
					    connection,
					    sql_format(
						    "SELECT 1 FROM auctions WHERE status=1 AND "
						    "(seller_pid=%d OR winning_bidder_pid=%d) LIMIT 1 FOR UPDATE",
						    pid, pid),
					    &unsettled))
					return error_code;
				if (!unsettled.empty())
					return refused;

				std::vector<std::string> statements = {
					/* Release current artifact ownership before deleting the identity. The
					 * legacy and revisioned representations must move together. */
					sql_format(
						"UPDATE artifacts SET owned='N',location=0,timer=NULL,locType=1,"
						"lastUpdate=NOW() WHERE location=%d AND locType IN (3,5)",
						pid),
					sql_format(
						"UPDATE artifacts_mortal SET owned='N',location=0,timer=NULL,locType=1,"
						"lastUpdate=NOW() WHERE location=%d AND locType IN (3,5)",
						pid),
					sql_format(
						"UPDATE artifact_bind SET owner_pid=-1,timer=0 WHERE owner_pid=%d",
						pid),
					sql_format(
						"UPDATE artifact_domain_state SET owned=0,loc_type=1,location=0,"
						"bind_timer_epoch=IF(bind_owner_pid=%d,0,bind_timer_epoch),"
						"bind_owner_pid=IF(bind_owner_pid=%d,-1,bind_owner_pid),timer_epoch=0,"
						"revision=revision+1 WHERE (location=%d AND loc_type IN (3,5)) OR "
						"bind_owner_pid=%d",
						pid, pid, pid, pid),
				};
				static const char *const pid_deletes[][2] = {
					{ "account_bound_reward_summons", "pid" },
					{ "auction_item_pickups", "pid" },
					{ "auction_money_pickups", "pid" },
					{ "boons_progress", "pid" },
					{ "boons_shop", "pid" },
					{ "ctf_data", "pid" },
					{ "epic_bonus", "pid" },
					{ "epic_gain", "pid" },
					{ "ip_info", "pid" },
					{ "lockers", "owner_pid" },
					{ "offline_messages", "pid" },
					{ "pkill_info", "pid" },
					{ "player_recipes", "pid" },
					{ "player_shapechanges", "pid" },
					{ "progress", "pid" },
					{ "quest_trophy", "pid" },
					{ "shop_trophy", "seller" },
					{ "zone_trophy", "pid" },
				};
				for (const auto &spec : pid_deletes)
					statements.push_back(
						sql_format("DELETE FROM %s WHERE %s=%d", spec[0],
							   spec[1], pid));
				statements.push_back(sql_format(
					"UPDATE boons SET pid=0,active=0 WHERE pid=%d", pid));
				statements.push_back(sql_format(
					"UPDATE frag_leaderboard SET deleted_at=COALESCE(deleted_at,NOW()),"
					"last_updated=NOW() WHERE pid=%d",
					pid));
				statements.push_back(sql_format(
					"UPDATE guilds g JOIN guild_members gm ON gm.guild_id=g.id SET "
					"g.top_frags=IF(LOWER(g.topfragger)=LOWER('%s'),0,g.top_frags),"
					"g.topfragger=IF(LOWER(g.topfragger)=LOWER('%s'),'',g.topfragger) "
					"WHERE gm.player_pid=%d OR LOWER(gm.player_name)=LOWER('%s')",
					character.c_str(), character.c_str(), pid,
					character.c_str()));
				statements.push_back(sql_format(
					"DELETE FROM guild_members WHERE player_pid=%d OR "
					"LOWER(player_name)=LOWER('%s')",
					pid, character.c_str()));
				statements.push_back(sql_format(
					"DELETE FROM locker_access WHERE LOWER(visitor)=LOWER('%s')",
					character.c_str()));
				statements.push_back(sql_format(
					"DELETE FROM locker_access WHERE LOWER(owner)=LOWER(CONCAT('%s','.locker'))",
					character.c_str()));
				/* A corpse keeps the name it was made under, so one from before a
				 * rename is found by its owner pid. */
				statements.push_back(sql_format(
					"DELETE FROM corpses WHERE LOWER(player_name)=LOWER('%s') "
					"OR (value3=%d AND (value1 & %u)<>0)",
					character.c_str(), pid, PC_CORPSE));
				statements.push_back(sql_format(
					"DELETE FROM world_quest_accomplished WHERE pid='%d' OR "
					"LOWER(player_name)=LOWER('%s')",
					pid, character.c_str()));
				statements.push_back(sql_format(
					"DELETE FROM ships WHERE LOWER(owner_name)=LOWER('%s')",
					character.c_str()));
				statements.push_back(
					sql_format("DELETE FROM player_data WHERE pid=%d", pid));
				for (const std::string &statement : statements)
					if (const unsigned int error_code =
						    sql_execute(connection, statement))
						return error_code;
			}

			/* Account lockers in the live locker subsystem are keyed by this exact
			 * finite set of names and do not carry an account foreign key. */
			std::vector<std::string> statements = {
				sql_format("DELETE FROM locker_access WHERE LOWER(owner) IN (%s)",
					   locker_names.c_str()),
				sql_format("DELETE FROM lockers WHERE LOWER(locker_name) IN (%s)",
					   locker_names.c_str()),
			};
			static const char *const account_deletes[][2] = {
				{ "account_locker_access", "visitor_account" },
				{ "locker_kickouts", "account_name" },
				{ "locker_session_state", "account_name" },
				{ "poll_votes", "account_name" },
				{ "account_characters", "account_name" },
			};
			for (const auto &spec : account_deletes)
				statements.push_back(
					sql_format("DELETE FROM %s WHERE LOWER(%s)=LOWER('%s')",
						   spec[0], spec[1], account.c_str()));
			for (const std::string &statement : statements)
				if (const unsigned int error_code =
					    sql_execute(connection, statement))
					return error_code;

			/* ON DELETE CASCADE removes banks, IPs, account lockers, and account-bound
			 * rewards. The credential is intentionally the last destructive write. */
			if (const unsigned int error_code = sql_execute(
				    connection,
				    sql_format(
					    "DELETE FROM accounts WHERE LOWER(account_name)=LOWER('%s')",
					    account.c_str())))
				return error_code;
			if (mysql_affected_rows(connection) != 1)
				return refused;

			sql_rows left;
			if (const unsigned int error_code = sql_select(
				    connection,
				    sql_format(
					    "SELECT (SELECT COUNT(*) FROM accounts WHERE LOWER(account_name)=LOWER('%s'))+"
					    "(SELECT COUNT(*) FROM player_data WHERE LOWER(account_name)=LOWER('%s'))+"
					    "(SELECT COUNT(*) FROM account_characters WHERE LOWER(account_name)=LOWER('%s'))",
					    account.c_str(), account.c_str(), account.c_str()),
				    &left))
				return error_code;
			return left.size() == 1 && left[0][0] &&
					       strtoull(left[0][0], NULL, 10) == 0 ?
				       0 :
				       refused;
		},
		[done = std::move(done)](bool ok, const sql_rows &) { done(ok); });
}

// locker functions

#define MAX_CONTAINER_LOAD_DEPTH 64

// Append a loaded object chain to the end of a list being built.
static void append_loaded_objects(P_obj *first, P_obj *last, P_obj chain)
{
	while (chain)
	{
		P_obj next = chain->next_content;
		if (!*first)
			*first = chain;
		else
			(*last)->next_content = chain;
		*last = chain;
		chain->next_content = NULL;
		chain = next;
	}
}

// The item rows of a locker entry read, by (chest, container), and their affect and
// extra description rows by item.
struct locker_row_index
{
	std::map<std::pair<int, int>, std::vector<const sql_row *>> items;
	std::map<int, std::vector<const sql_row *>> affects, extras;
};

// Build the items of one chest level: its rows in order, each with its contents. An
// item another owner holds is left out and what it contains moves up a level. With
// chest_obj (a private chest) each item goes into the chest before its contents are
// attached, so a full container is not refused by the chest's fit check.
static P_obj locker_items_from_index(const locker_row_index &index, int locker_id, int chest_id,
				     int container_id, int depth, P_obj chest_obj)
{
	if (depth > MAX_CONTAINER_LOAD_DEPTH)
	{
		logit(LOG_DEBUG,
		      "sql_locker_items_from_rows: component=container outcome=depth_limit");
		return NULL;
	}
	const auto level = index.items.find({ chest_id, container_id });
	if (level == index.items.end())
		return NULL;

	P_obj first_obj = NULL;
	P_obj last_obj = NULL;
	for (const sql_row *item : level->second)
	{
		const sql_row &row = *item;
		const int item_id = atoi(row[1]);
		const int rnum = real_object(atoi(row[2]));
		if (rnum < 0)
		{
			logit(LOG_DEBUG,
			      "sql_locker_items_from_rows: skip unknown vnum item_id=%d vnum=%s locker_id=%d chest_id=%d",
			      item_id, row[2], locker_id, chest_id);
			continue;
		}
		P_obj obj = read_object(rnum, REAL);
		if (!obj)
			continue;

		if (row[3])
			obj->weight = atoi(row[3]);
		if (row[4])
			obj->cost = atoi(row[4]);
		if (row[5])
			obj->timer[0] = atol(row[5]);
		if (row[6])
			obj->extra_flags = strtoul(row[6], NULL, 10);
		if (row[7])
			obj->wear_flags = atoi(row[7]);
		if (row[8])
			obj->type = sql_validate_loaded_item_type(obj, atoi(row[8]),
								  "sql_load_locker_items");
		for (int v = 0; v < 8; v++)
			if (row[9 + v])
				obj->value[v] = atoi(row[9 + v]);
		if (row[17] && *row[17])
		{
			obj->name = str_dup(row[17]);
			obj->str_mask |= STRUNG_KEYS;
		}
		if (row[18] && *row[18])
		{
			obj->short_description = str_dup(row[18]);
			obj->str_mask |= STRUNG_DESC2;
		}
		if (row[19] && *row[19])
		{
			obj->description = str_dup(row[19]);
			obj->str_mask |= STRUNG_DESC1;
		}
		if (row[20] && *row[20])
		{
			obj->action_description = str_dup(row[20]);
			obj->str_mask |= STRUNG_DESC3;
		}
		if (row[23])
			obj->bitvector = strtoul(row[23], NULL, 10);
		if (row[24])
			obj->bitvector2 = strtoul(row[24], NULL, 10);
		if (row[25])
			obj->bitvector3 = strtoul(row[25], NULL, 10);
		if (row[26])
			obj->bitvector4 = strtoul(row[26], NULL, 10);
		if (row[27])
			obj->bitvector5 = strtoul(row[27], NULL, 10);
		if (row[28])
			obj->material = atoi(row[28]);
		if (row[21] && strtoul(row[21], NULL, 10) > 0)
			obj->obj_uid = strtoul(row[21], NULL, 10);

		const char *const owner[] = { row[31], row[32], row[33], row[34], row[35],
					      row[36], row[37], row[38], row[39] };
		if (!sql_persistence_item_owner_fields_match(
			    obj->obj_uid, "locker", static_cast<unsigned long long>(locker_id),
			    static_cast<unsigned long long>(chest_id), row[31] ? owner : NULL))
		{
			// A stale copy another owner holds is left out, and what it contains
			// moves up a level.
			extract_obj(obj, FALSE);
			P_obj orphans = locker_items_from_index(index, locker_id, chest_id, item_id,
								depth + 1, NULL);
			if (!chest_obj)
				append_loaded_objects(&first_obj, &last_obj, orphans);
			while (chest_obj && orphans)
			{
				P_obj next = orphans->next_content;
				orphans->next_content = NULL;
				obj_to_obj(orphans, chest_obj);
				orphans = next;
			}
			continue;
		}
		if (row[22] && *row[22])
			obj->condition = atoi(row[22]);
		obj->db_item_id = item_id;

		const auto affects = index.affects.find(item_id);
		if (affects != index.affects.end())
		{
			std::vector<std::pair<int, int>> stored;
			for (const sql_row *affect : affects->second)
				stored.emplace_back(atoi((*affect)[2]), atoi((*affect)[3]));
			sql_set_item_affects(obj, stored);
		}
		const auto extras = index.extras.find(item_id);
		if (extras != index.extras.end())
		{
			struct extra_descr_data *loaded_spellbook = NULL;
			for (const sql_row *extra : extras->second)
				sql_add_item_extra_descr(obj, (*extra)[2], (*extra)[3],
							 "locker_item", item_id, &loaded_spellbook);
		}

		if (chest_obj)
			obj_to_obj(obj, chest_obj);
		obj->contains = locker_items_from_index(index, locker_id, chest_id, item_id,
							depth + 1, NULL);
		for (P_obj c = obj->contains; c; c = c->next_content)
		{
			if (!obj_can_nest(c, obj))
			{
				logit(LOG_DEBUG,
				      "sql_locker_items_from_rows: component=container_link outcome=malformed");
				continue;
			}
			c->loc_p = LOC_INSIDE;
			c->loc.inside = obj;
		}

		if (!chest_obj)
			append_loaded_objects(&first_obj, &last_obj, obj);
	}
	return first_obj;
}

P_obj sql_locker_items_from_rows(const sql_rows &rows, int locker_id, int chest_id, P_obj chest_obj)
{
	locker_row_index index;
	for (const sql_row &row : rows)
	{
		if (!row[0] || !row[1])
			continue;
		if (!strcmp(row[0], "item"))
			index.items[{ row[29] ? atoi(row[29]) : 0, row[30] ? atoi(row[30]) : 0 }]
				.push_back(&row);
		else if (!strcmp(row[0], "affect"))
			index.affects[atoi(row[1])].push_back(&row);
		else if (!strcmp(row[0], "extra"))
			index.extras[atoi(row[1])].push_back(&row);
	}
	return locker_items_from_index(index, locker_id, chest_id, 0, 0, chest_obj);
}

/* The statement that deletes the personal or association locker selected by its
 * stable owner key (its chests and items cascade); empty without a key. */
std::string sql_delete_locker_statement(int owner_pid, int owner_assoc_id)
{
	if (owner_pid > 0)
		return sql_format("DELETE FROM lockers WHERE owner_pid=%d", owner_pid);
	if (owner_assoc_id > 0)
		return sql_format("DELETE FROM lockers WHERE owner_assoc_id=%d", owner_assoc_id);
	return {};
}

// ============================================================================
// private chest functions
// ============================================================================

bool sql_log_chest_activity(int locker_id, int chest_id, const char *char_name, int action_type,
			    const char *item_short)
{
	if (!DB || locker_id <= 0 || !char_name || action_type < 1)
		return false;
	return sql_queue(
		"INSERT INTO private_chest_log (locker_id, chest_id, char_name, action_type, item_short) "
		"VALUES (%d, %s, '%s', %d, %s)",
		locker_id, chest_id > 0 ? std::to_string(chest_id).c_str() : "NULL",
		escape_str(char_name).c_str(), action_type,
		item_short ? ("'" + escape_str(item_short) + "'").c_str() : "NULL");
}

bool sql_save_private_chest_items(int locker_id, int chest_id, P_obj chest_obj)
{
	if (locker_id <= 0 || chest_id <= 0 || !chest_obj)
		return false;

	// The chest save goes to the one writer, behind any save still queued; a job it
	// refuses is the caller's failure to report.
	locker_chest_snapshot snapshot;
	snapshot.locker_id = locker_id;
	snapshot.chest_id = chest_id;
	if (player_item_snapshot_contents_capture(chest_obj, &snapshot.items) !=
	    player_snapshot_capture_result::ok)
		return false;
	// A private chest's key never matches its locker's public job.
	const uint64_t owner = (static_cast<uint64_t>(chest_id) << 32) |
			       static_cast<uint32_t>(locker_id);
	const size_t bytes =
		sizeof(snapshot) + snapshot.items.size() * sizeof(player_item_snapshot);
	const player_save_submit_result submitted = persistence_writer_submit(
		persistence_job_kind::locker, owner, bytes, [snapshot]()
		{ return locker_chest_snapshot_repository_apply_from_pool(snapshot); });
	return submitted == player_save_submit_result::accepted ||
	       submitted == player_save_submit_result::replaced;
}

// single query corpse loading - all data in one query
#define MAX_CORPSE_ITEMS 512

extern int skip_corpse_save;

enum corpse_load_column
{
	CORPSE_COL_ID,
	CORPSE_COL_PLAYER_NAME,
	CORPSE_COL_SAVE_ID,
	CORPSE_COL_ROOM_VNUM,
	CORPSE_COL_OWNER_PID,
	CORPSE_COL_ITEM_ID,
	CORPSE_COL_ITEM_CONTAINER_ID,
	CORPSE_COL_ITEM_VNUM,
	CORPSE_COL_ITEM_TYPE_COALESCED,
	CORPSE_COL_ITEM_WEIGHT,
	CORPSE_COL_ITEM_COST,
	CORPSE_COL_ITEM_TIMER,
	CORPSE_COL_ITEM_EXTRA_FLAGS,
	CORPSE_COL_ITEM_VALUE0,
	CORPSE_COL_ITEM_VALUE1,
	CORPSE_COL_ITEM_VALUE2,
	CORPSE_COL_ITEM_VALUE3,
	CORPSE_COL_ITEM_VALUE4,
	CORPSE_COL_ITEM_VALUE5,
	CORPSE_COL_ITEM_VALUE6,
	CORPSE_COL_ITEM_VALUE7,
	CORPSE_COL_ITEM_NAME,
	CORPSE_COL_ITEM_SHORT_DESCRIPTION,
	CORPSE_COL_ITEM_DESCRIPTION,
	CORPSE_COL_ITEM_ACTION_DESCRIPTION,
	CORPSE_COL_ITEM_AFFECT_LOCATION,
	CORPSE_COL_ITEM_AFFECT_MODIFIER,
	CORPSE_COL_ITEM_UID,
	CORPSE_COL_ITEM_CONDITION,
	CORPSE_COL_SHORT_DESCRIPTION,
	CORPSE_COL_DESCRIPTION,
	CORPSE_COL_NAME,
	CORPSE_COL_WEIGHT,
	CORPSE_COL_VALUE0,
	CORPSE_COL_VALUE1,
	CORPSE_COL_VALUE2,
	CORPSE_COL_VALUE3,
	CORPSE_COL_VALUE4,
	CORPSE_COL_VALUE5,
	CORPSE_COL_VALUE7,
	CORPSE_COL_ITEM_WEAR_FLAGS,
	CORPSE_COL_ITEM_TYPE,
	CORPSE_COL_ITEM_MATERIAL,
	CORPSE_COL_ITEM_BITVECTOR1,
	CORPSE_COL_ITEM_BITVECTOR2,
	CORPSE_COL_ITEM_BITVECTOR3,
	CORPSE_COL_ITEM_BITVECTOR4,
	CORPSE_COL_ITEM_BITVECTOR5,
	CORPSE_COL_COUNT
};

static void sql_restore_corpse_identity(P_obj corpse, const char *player_name, const char *name,
					const char *short_description, const char *description)
{
	char keywords[MAX_STRING_LENGTH];

	if (name && *name)
		set_keywords(corpse, name);
	else
	{
		checked_snprintf(keywords, sizeof(keywords), "%s corpse _pcorpse_", player_name);
		set_keywords(corpse, keywords);
	}

	if (short_description && *short_description)
		set_short_description(corpse, short_description);
	if (description && *description)
		set_long_description(corpse, description);

	if ((corpse->str_mask & STRUNG_DESC3) && corpse->action_description)
		FREE(corpse->action_description);
	corpse->str_mask |= STRUNG_DESC3;
	corpse->action_description = str_dup(player_name);
}

bool sql_load_all_corpses(void)
{
	if (!DB)
		return false;

	skip_corpse_save = 1; // don't write corpses back during load

	bool ok = false;
	MYSQL_RES *result = NULL;
	int cur_corpse_id = -1;
	P_obj cur_corpse = NULL;
	int cur_room = 0;
	uint32_t cur_owner_pid = 0;
	uint32_t cur_save_id = 0;
	uint64_t cur_corpse_owner_id = 0;
	P_obj obj_map[MAX_CORPSE_ITEMS];
	int id_map[MAX_CORPSE_ITEMS];
	int container_map[MAX_CORPSE_ITEMS];
	int num_objs = 0;
	int last_item_id = -1;
	// true only when last_item_id names the object now at obj_map[num_objs - 1];
	// a row whose item failed to load must not have its affects applied to the
	// previous, unrelated object.
	bool last_item_stored = false;
	int loaded = 0;
	MYSQL_ROW row;

	// one query gets everything: corpses + items + affects
	result = db_query(
		"SELECT c.id, c.player_name, c.save_id, c.room_vnum, "
		"COALESCE(c.value3,0), "
		"ci.id, COALESCE(ci.container_id, 0), ci.vnum, COALESCE(ci.item_type, 0), "
		"ci.weight, ci.cost, ci.timer, "
		"ci.extra_flags, ci.value0, ci.value1, ci.value2, ci.value3, ci.value4, "
		"ci.value5, ci.value6, ci.value7, ci.name, ci.short_descr, ci.description, "
		"ci.action_descr, COALESCE(cia.location, -1), COALESCE(cia.modifier, 0), "
		"ci.obj_uid, ci.item_condition, "
		"c.short_descr, c.description, c.name, c.weight, "
		"c.value0, c.value1, c.value2, c.value3, c.value4, c.value5, c.value7, "
		"ci.wear_flags, ci.item_type, ci.item_material, "
		"ci.bitvector1, ci.bitvector2, ci.bitvector3, ci.bitvector4, ci.bitvector5 "
		"FROM corpses c "
		"LEFT JOIN corpse_items ci ON ci.corpse_id = c.id "
		"LEFT JOIN corpse_item_affects cia ON cia.item_id = ci.id "
		"ORDER BY c.id, ci.id, cia.id");
	if (!result)
		goto cleanup;
	if (mysql_num_fields(result) != CORPSE_COL_COUNT)
	{
		logit(LOG_DEBUG, "sql_load_all_corpses: expected %d result columns, got %u",
		      CORPSE_COL_COUNT, mysql_num_fields(result));
		goto cleanup;
	}

	// tracking for current corpse being built
	while ((row = mysql_fetch_row(result)))
	{
		int corpse_id = atoi(row[CORPSE_COL_ID]);
		int item_id = row[CORPSE_COL_ITEM_ID] ? atoi(row[CORPSE_COL_ITEM_ID]) : 0;

		// new corpse - finalize previous one first
		if (corpse_id != cur_corpse_id)
		{
			// finalize previous corpse if exists
			if (cur_corpse && num_objs > 0)
			{
// link containers using hash
#define HASH_SIZE 1024
				int hash_id[HASH_SIZE];
				int hash_idx[HASH_SIZE];
				for (int i = 0; i < HASH_SIZE; i++)
					hash_id[i] = -1;

				for (int i = 0; i < num_objs; i++)
				{
					int h = id_map[i] % HASH_SIZE;
					while (hash_id[h] != -1)
						h = (h + 1) % HASH_SIZE;
					hash_id[h] = id_map[i];
					hash_idx[h] = i;
				}

				for (int i = 0; i < num_objs; i++)
				{
					if (container_map[i] == 0)
						continue;
					int h = container_map[i] % HASH_SIZE;
					while (hash_id[h] != -1 && hash_id[h] != container_map[i])
						h = (h + 1) % HASH_SIZE;
					if (hash_id[h] == container_map[i])
					{
						int j = hash_idx[h];
						if (!obj_can_nest(obj_map[i], obj_map[j]))
						{
							logit(LOG_DEBUG,
							      "sql_restore_saved_items: skipping malformed container link %d -> %d",
							      obj_map[i]->db_item_id,
							      obj_map[j]->db_item_id);
							continue;
						}
						obj_map[i]->next_content = obj_map[j]->contains;
						obj_map[j]->contains = obj_map[i];
						obj_map[i]->loc_p = LOC_INSIDE;
						obj_map[i]->loc.inside = obj_map[j];
						container_map[i] = -1;
					}
				}
#undef HASH_SIZE

				// build top-level list; an item whose container was skipped
				// or cannot hold it lies loose in the corpse
				P_obj first = NULL;
				P_obj last_obj = NULL;
				for (int i = 0; i < num_objs; i++)
				{
					if (container_map[i] != -1)
					{
						if (!first)
							first = obj_map[i];
						else
							last_obj->next_content = obj_map[i];
						last_obj = obj_map[i];
						last_obj->next_content = NULL;
					}
				}
				cur_corpse->contains = first;
				for (P_obj o = cur_corpse->contains; o; o = o->next_content)
				{
					o->loc_p = LOC_INSIDE;
					o->loc.inside = cur_corpse;
				}
				obj_to_room(cur_corpse, cur_room);
				persistence_refresh_restored_corpse(cur_corpse,
								    "sql_load_all_corpses");
				loaded++;
			}
			else if (cur_corpse)
			{
				// corpse with no items
				obj_to_room(cur_corpse, cur_room);
				persistence_refresh_restored_corpse(cur_corpse,
								    "sql_load_all_corpses");
				loaded++;
			}

			// start new corpse
			num_objs = 0;
			last_item_id = -1;
			last_item_stored = false;
			cur_corpse_id = corpse_id;

			const char *player_name =
				row[CORPSE_COL_PLAYER_NAME] ? row[CORPSE_COL_PLAYER_NAME] : "";
			const unsigned long parsed_save_id =
				strtoul(row[CORPSE_COL_SAVE_ID], NULL, 10);
			const unsigned long parsed_owner_pid =
				strtoul(row[CORPSE_COL_OWNER_PID], NULL, 10);
			if (!parsed_save_id || parsed_save_id > INT32_MAX || !parsed_owner_pid ||
			    parsed_owner_pid > INT32_MAX)
				goto cleanup;
			int save_id = static_cast<int>(parsed_save_id);
			cur_save_id = static_cast<uint32_t>(parsed_save_id);
			cur_owner_pid = static_cast<uint32_t>(parsed_owner_pid);
			int room_vnum = atoi(row[CORPSE_COL_ROOM_VNUM]);
			cur_corpse_owner_id = item_corpse_owner_id(cur_owner_pid, cur_save_id);

			cur_room = real_room(room_vnum);
			if (cur_room == NOWHERE)
				cur_room = 0;

			int corpse_rnum = real_object(2); // vnum 2 is the corpse prototype
			if (corpse_rnum < 0)
			{
				cur_corpse = NULL;
				continue;
			}

			cur_corpse = read_object(corpse_rnum, REAL);
			if (!cur_corpse)
				continue;

			cur_corpse->type = ITEM_CORPSE;
			if (row[CORPSE_COL_WEIGHT])
				cur_corpse->weight = atoi(row[CORPSE_COL_WEIGHT]);
			for (int value_index = 0; value_index <= CORPSE_RACEWAR; value_index++)
			{
				if (row[CORPSE_COL_VALUE0 + value_index])
					cur_corpse->value[value_index] =
						atoi(row[CORPSE_COL_VALUE0 + value_index]);
			}
			if (row[CORPSE_COL_VALUE7])
				cur_corpse->value[CORPSE_RACE] = atoi(row[CORPSE_COL_VALUE7]);
			SET_BIT(cur_corpse->value[CORPSE_FLAGS], PC_CORPSE);
			cur_corpse->value[CORPSE_SAVEID] = save_id;

			sql_restore_corpse_identity(cur_corpse, player_name, row[CORPSE_COL_NAME],
						    row[CORPSE_COL_SHORT_DESCRIPTION],
						    row[CORPSE_COL_DESCRIPTION]);
		}

		// no item in this row (corpse with no items)
		if (!row[CORPSE_COL_ITEM_ID] || !cur_corpse)
			continue;

		// same item, just another affect
		if (item_id == last_item_id && last_item_stored && num_objs > 0)
		{
			int aff_loc = atoi(row[CORPSE_COL_ITEM_AFFECT_LOCATION]);
			if (aff_loc >= 0)
			{
				P_obj obj = obj_map[num_objs - 1];
				for (int i = 0; i < MAX_OBJ_AFFECT; i++)
				{
					if (obj->affected[i].location == 0 &&
					    obj->affected[i].modifier == 0)
					{
						obj->affected[i].location = aff_loc;
						obj->affected[i].modifier =
							atoi(row[CORPSE_COL_ITEM_AFFECT_MODIFIER]);
						break;
					}
				}
			}
			continue;
		}

		// new item
		if (num_objs >= MAX_CORPSE_ITEMS)
			continue;

		int vnum = atoi(row[CORPSE_COL_ITEM_VNUM]);
		int rnum = real_object(vnum);
		if (rnum < 0)
		{
			last_item_id = item_id;
			last_item_stored = false;
			continue;
		}

		P_obj obj = read_object(rnum, REAL);
		if (!obj)
		{
			last_item_id = item_id;
			last_item_stored = false;
			continue;
		}

		if (row[CORPSE_COL_ITEM_WEIGHT])
			obj->weight = atoi(row[CORPSE_COL_ITEM_WEIGHT]);
		if (row[CORPSE_COL_ITEM_COST])
			obj->cost = atoi(row[CORPSE_COL_ITEM_COST]);
		if (row[CORPSE_COL_ITEM_TIMER])
			obj->timer[0] = atol(row[CORPSE_COL_ITEM_TIMER]);
		if (row[CORPSE_COL_ITEM_EXTRA_FLAGS])
			obj->extra_flags = strtoul(row[CORPSE_COL_ITEM_EXTRA_FLAGS], NULL, 10);
		for (int v = 0; v < 8; v++)
			obj->value[v] = row[CORPSE_COL_ITEM_VALUE0 + v] ?
						atoi(row[CORPSE_COL_ITEM_VALUE0 + v]) :
						0;

		if (row[CORPSE_COL_ITEM_NAME] && row[CORPSE_COL_ITEM_NAME][0])
		{
			obj->name = str_dup(row[CORPSE_COL_ITEM_NAME]);
			obj->str_mask |= STRUNG_KEYS;
		}
		if (row[CORPSE_COL_ITEM_SHORT_DESCRIPTION] &&
		    row[CORPSE_COL_ITEM_SHORT_DESCRIPTION][0])
		{
			obj->short_description = str_dup(row[CORPSE_COL_ITEM_SHORT_DESCRIPTION]);
			obj->str_mask |= STRUNG_DESC2;
		}
		if (row[CORPSE_COL_ITEM_DESCRIPTION] && row[CORPSE_COL_ITEM_DESCRIPTION][0])
		{
			obj->description = str_dup(row[CORPSE_COL_ITEM_DESCRIPTION]);
			obj->str_mask |= STRUNG_DESC1;
		}
		if (row[CORPSE_COL_ITEM_ACTION_DESCRIPTION] &&
		    row[CORPSE_COL_ITEM_ACTION_DESCRIPTION][0])
		{
			obj->action_description = str_dup(row[CORPSE_COL_ITEM_ACTION_DESCRIPTION]);
			obj->str_mask |= STRUNG_DESC3;
		}

		unsigned long saved_uid =
			row[CORPSE_COL_ITEM_UID] ? strtoul(row[CORPSE_COL_ITEM_UID], NULL, 10) : 0;
		if (saved_uid > 0)
		{
			obj->obj_uid = saved_uid;
			if (obj->obj_uid >= next_obj_uid)
				next_obj_uid = obj->obj_uid + 1;
		}
		if (row[CORPSE_COL_ITEM_CONDITION])
			obj->condition = atoi(row[CORPSE_COL_ITEM_CONDITION]);

		// v19 diff columns - NULL means use prototype value from read_object()
		if (row[CORPSE_COL_ITEM_WEAR_FLAGS])
			obj->wear_flags = atoi(row[CORPSE_COL_ITEM_WEAR_FLAGS]);
		if (row[CORPSE_COL_ITEM_TYPE])
			obj->type = sql_validate_loaded_item_type(
				obj, atoi(row[CORPSE_COL_ITEM_TYPE]), "sql_load_all_corpses");
		if (row[CORPSE_COL_ITEM_MATERIAL])
			obj->material = atoi(row[CORPSE_COL_ITEM_MATERIAL]);
		if (row[CORPSE_COL_ITEM_BITVECTOR1])
			obj->bitvector = strtoul(row[CORPSE_COL_ITEM_BITVECTOR1], NULL, 10);
		if (row[CORPSE_COL_ITEM_BITVECTOR2])
			obj->bitvector2 = strtoul(row[CORPSE_COL_ITEM_BITVECTOR2], NULL, 10);
		if (row[CORPSE_COL_ITEM_BITVECTOR3])
			obj->bitvector3 = strtoul(row[CORPSE_COL_ITEM_BITVECTOR3], NULL, 10);
		if (row[CORPSE_COL_ITEM_BITVECTOR4])
			obj->bitvector4 = strtoul(row[CORPSE_COL_ITEM_BITVECTOR4], NULL, 10);
		if (row[CORPSE_COL_ITEM_BITVECTOR5])
			obj->bitvector5 = strtoul(row[CORPSE_COL_ITEM_BITVECTOR5], NULL, 10);

		char owner_ref[32];
		snprintf(owner_ref, sizeof(owner_ref), "%llu",
			 (unsigned long long)cur_corpse_owner_id);
		if (!sql_persistence_item_owner_matches(saved_uid, "corpse", owner_ref,
							"sql_load_all_corpses"))
		{
			extract_obj(obj, FALSE);
			last_item_id = item_id;
			last_item_stored = false;
			continue;
		}

		int aff_loc = atoi(row[CORPSE_COL_ITEM_AFFECT_LOCATION]);
		if (aff_loc >= 0)
		{
			obj->affected[0].location = aff_loc;
			obj->affected[0].modifier = atoi(row[CORPSE_COL_ITEM_AFFECT_MODIFIER]);
		}

		sql_load_item_extra_descr_from_table(item_id, obj, "corpse_item");

		obj_map[num_objs] = obj;
		id_map[num_objs] = item_id;
		container_map[num_objs] = atoi(row[CORPSE_COL_ITEM_CONTAINER_ID]);
		num_objs++;
		last_item_id = item_id;
		last_item_stored = true;
	}

	// finalize last corpse
	if (cur_corpse && num_objs > 0)
	{
#define HASH_SIZE 1024
		int hash_id[HASH_SIZE];
		int hash_idx[HASH_SIZE];
		for (int i = 0; i < HASH_SIZE; i++)
			hash_id[i] = -1;

		for (int i = 0; i < num_objs; i++)
		{
			int h = id_map[i] % HASH_SIZE;
			while (hash_id[h] != -1)
				h = (h + 1) % HASH_SIZE;
			hash_id[h] = id_map[i];
			hash_idx[h] = i;
		}

		for (int i = 0; i < num_objs; i++)
		{
			if (container_map[i] == 0)
				continue;
			int h = container_map[i] % HASH_SIZE;
			while (hash_id[h] != -1 && hash_id[h] != container_map[i])
				h = (h + 1) % HASH_SIZE;
			if (hash_id[h] == container_map[i])
			{
				int j = hash_idx[h];
				if (!obj_can_nest(obj_map[i], obj_map[j]))
				{
					logit(LOG_DEBUG,
					      "sql_restore_saved_items: skipping malformed container link %d -> %d",
					      obj_map[i]->db_item_id, obj_map[j]->db_item_id);
					continue;
				}
				obj_map[i]->next_content = obj_map[j]->contains;
				obj_map[j]->contains = obj_map[i];
				obj_map[i]->loc_p = LOC_INSIDE;
				obj_map[i]->loc.inside = obj_map[j];
				container_map[i] = -1;
			}
		}
#undef HASH_SIZE

		// An item whose container was skipped or cannot hold it lies loose in the corpse.
		P_obj first = NULL;
		P_obj last_obj = NULL;
		for (int i = 0; i < num_objs; i++)
		{
			if (container_map[i] != -1)
			{
				if (!first)
					first = obj_map[i];
				else
					last_obj->next_content = obj_map[i];
				last_obj = obj_map[i];
				last_obj->next_content = NULL;
			}
		}
		cur_corpse->contains = first;
		for (P_obj o = cur_corpse->contains; o; o = o->next_content)
		{
			o->loc_p = LOC_INSIDE;
			o->loc.inside = cur_corpse;
		}
		obj_to_room(cur_corpse, cur_room);
		persistence_refresh_restored_corpse(cur_corpse, "sql_load_all_corpses");
		loaded++;
	}
	else if (cur_corpse)
	{
		obj_to_room(cur_corpse, cur_room);
		persistence_refresh_restored_corpse(cur_corpse, "sql_load_all_corpses");
		loaded++;
	}

	ok = true;

cleanup:
	if (result)
		mysql_free_result(result);
	skip_corpse_save = 0; // re-enable corpse saves
	return ok;
}

extern struct shop_data *shop_index;
extern int number_of_shops;
extern int top_of_mobt;

namespace
{
enum class shopkeeper_save_reason
{
	ok,
	database_unavailable,
	null_keeper,
	invalid_shop,
	invalid_keeper,
	invalid_shop_room,
	keeper_not_npc,
	keeper_rnum_mismatch,
	keeper_room_invalid,
	keeper_room_mismatch,
	keeper_not_found,
	keeper_ambiguous,
	keeper_not_shopkeeper,
	save_failed,
};

const char *shopkeeper_save_reason_name(shopkeeper_save_reason reason)
{
	switch (reason)
	{
	case shopkeeper_save_reason::ok:
		return "ok";
	case shopkeeper_save_reason::database_unavailable:
		return "database_unavailable";
	case shopkeeper_save_reason::null_keeper:
		return "null_keeper";
	case shopkeeper_save_reason::invalid_shop:
		return "invalid_shop";
	case shopkeeper_save_reason::invalid_keeper:
		return "invalid_keeper";
	case shopkeeper_save_reason::invalid_shop_room:
		return "invalid_shop_room";
	case shopkeeper_save_reason::keeper_not_npc:
		return "keeper_not_npc";
	case shopkeeper_save_reason::keeper_rnum_mismatch:
		return "keeper_rnum_mismatch";
	case shopkeeper_save_reason::keeper_room_invalid:
		return "keeper_room_invalid";
	case shopkeeper_save_reason::keeper_room_mismatch:
		return "keeper_room_mismatch";
	case shopkeeper_save_reason::keeper_not_found:
		return "keeper_not_found";
	case shopkeeper_save_reason::keeper_ambiguous:
		return "keeper_ambiguous";
	case shopkeeper_save_reason::keeper_not_shopkeeper:
		return "keeper_not_shopkeeper";
	case shopkeeper_save_reason::save_failed:
		return "save_failed";
	}
	return "unknown";
}

int shopkeeper_expected_room_rnum(int shop_nr)
{
	if (!shop_index || shop_nr < 0 || shop_nr >= number_of_shops)
		return NOWHERE;
	return real_room(shop_index[shop_nr].in_room);
}

bool shopkeeper_save_matches_room(P_char ch, int shop_nr)
{
	if (!ch || !shop_index || shop_nr < 0 || shop_nr >= number_of_shops)
		return false;
	if (ch->only.npc && ch->only.npc->shopkeeper_shop_id >= 0)
		return ch->only.npc->shopkeeper_shop_id == shop_nr;
	const int room = shopkeeper_expected_room_rnum(shop_nr);
	if (shop_index[shop_nr].shop_is_roaming)
		return singleton_shop_id(ch) == shop_nr;
	return ch->in_room == room;
}

shopkeeper_save_reason validate_shopkeeper_save(P_char ch, int shop_nr)
{
	if (!DB)
		return shopkeeper_save_reason::database_unavailable;
	if (!ch)
		return shopkeeper_save_reason::null_keeper;
	if (!shop_index || shop_nr < 0 || shop_nr >= number_of_shops)
		return shopkeeper_save_reason::invalid_shop;
	if (shop_index[shop_nr].keeper < 0 || shop_index[shop_nr].keeper > top_of_mobt)
		return shopkeeper_save_reason::invalid_keeper;
	const int shop_room = shopkeeper_expected_room_rnum(shop_nr);
	if (!shop_index[shop_nr].shop_is_roaming && (shop_room < 0 || shop_room > top_of_world))
		return shopkeeper_save_reason::invalid_shop_room;
	if (!IS_NPC(ch) || GET_MASTER(ch))
		return shopkeeper_save_reason::keeper_not_npc;
	if (GET_RNUM(ch) != shop_index[shop_nr].keeper)
		return shopkeeper_save_reason::keeper_rnum_mismatch;
	if (ch->in_room < 0 || ch->in_room > top_of_world)
		return shopkeeper_save_reason::keeper_room_invalid;
	if (!shopkeeper_save_matches_room(ch, shop_nr))
		return shopkeeper_save_reason::keeper_room_mismatch;
	// Persistence identity is the configured shop/binding, not its command
	// procedure: quest and tradeskill keepers deliberately use other procs.
	bind_shopkeeper(ch, shop_nr);
	return shopkeeper_save_reason::ok;
}

// The NPCs that could be a dirty shop's keeper.
struct shopkeeper_candidates
{
	P_char keeper = NULL;
	int same_rnum = 0;
	int matches = 0;
};

// Finds the keepers of all the shops in `shops` (keeper template to shop) in one walk of
// the character list. A boot leaves every shop dirty, and a walk per shop held the game
// loop for over a second at the first hourly save.
std::vector<shopkeeper_candidates>
find_shopkeepers_for_dirty_save(const std::unordered_multimap<int, int> &shops)
{
	std::vector<shopkeeper_candidates> found(number_of_shops);
	if (shops.empty())
		return found;
	for (P_char ch = character_list; ch; ch = ch->next)
	{
		if (!IS_NPC(ch) || GET_MASTER(ch))
			continue;
		const auto same_rnum = shops.equal_range(GET_RNUM(ch));
		for (auto shop = same_rnum.first; shop != same_rnum.second; ++shop)
		{
			shopkeeper_candidates &candidates = found[shop->second];
			++candidates.same_rnum;
			if (ch->in_room < 0 || ch->in_room > top_of_world ||
			    !shopkeeper_save_matches_room(ch, shop->second))
				continue;
			candidates.keeper = ch;
			++candidates.matches;
		}
	}
	return found;
}

shopkeeper_save_reason choose_shopkeeper_for_dirty_save(int shop_nr,
							const shopkeeper_candidates &candidates,
							P_char *keeper_out)
{
	if (shop_index[shop_nr].keeper < 0 || shop_index[shop_nr].keeper > top_of_mobt)
		return shopkeeper_save_reason::invalid_keeper;
	const int shop_room = shopkeeper_expected_room_rnum(shop_nr);
	if (!shop_index[shop_nr].shop_is_roaming && (shop_room < 0 || shop_room > top_of_world))
		return shopkeeper_save_reason::invalid_shop_room;
	if (candidates.matches == 0)
		return candidates.same_rnum > 0 ? shopkeeper_save_reason::keeper_room_mismatch :
						  shopkeeper_save_reason::keeper_not_found;
	if (candidates.matches > 1)
		return shopkeeper_save_reason::keeper_ambiguous;
	*keeper_out = candidates.keeper;
	return validate_shopkeeper_save(candidates.keeper, shop_nr);
}

void log_shopkeeper_save_guard(P_char ch, int shop_nr, shopkeeper_save_reason reason)
{
	int expected_rnum = -1;
	int expected_room = NOWHERE;
	if (shop_index && shop_nr >= 0 && shop_nr < number_of_shops)
	{
		expected_rnum = shop_index[shop_nr].keeper;
		expected_room = shopkeeper_expected_room_rnum(shop_nr);
	}
	const int actual_rnum = ch && IS_NPC(ch) ? GET_RNUM(ch) : -1;
	const int actual_room = ch ? ch->in_room : NOWHERE;
	logit(LOG_DEBUG,
	      "sql_save_shopkeeper: phase=pretransaction outcome=retry shop=%d reason=%s "
	      "expected_keeper_rnum=%d actual_keeper_rnum=%d expected_room_rnum=%d actual_room_rnum=%d",
	      shop_nr, shopkeeper_save_reason_name(reason), expected_rnum, actual_rnum,
	      expected_room, actual_room);
}

void log_shopkeeper_dirty_retry(int shop_nr, shopkeeper_save_reason reason, P_char keeper,
				time_t now, bool force)
{
	const int expected_rnum = shop_index[shop_nr].keeper;
	const int expected_room = shopkeeper_expected_room_rnum(shop_nr);
	const int actual_rnum = keeper && IS_NPC(keeper) ? GET_RNUM(keeper) : -1;
	const int actual_room = keeper ? keeper->in_room : NOWHERE;
	const shopkeeper_save_retry_state &retry = shop_index[shop_nr].dirty_save_retry;
	logit(LOG_DEBUG,
	      "sql_save_dirty_shopkeepers: shop=%d outcome=retry reason=%s leaving_dirty=1 "
	      "attempt=%u next_retry=%lld now=%lld force=%d expected_keeper_rnum=%d "
	      "actual_keeper_rnum=%d expected_room_rnum=%d actual_room_rnum=%d",
	      shop_nr, shopkeeper_save_reason_name(reason), retry.failure_count,
	      static_cast<long long>(retry.next_retry_at), static_cast<long long>(now),
	      force ? 1 : 0, expected_rnum, actual_rnum, expected_room, actual_room);
}
}

bool sql_save_shopkeeper(P_char ch, int shop_nr)
{
	const shopkeeper_save_reason guard = validate_shopkeeper_save(ch, shop_nr);
	if (guard != shopkeeper_save_reason::ok)
	{
		log_shopkeeper_save_guard(ch, shop_nr, guard);
		return false;
	}
	// The stock is captured now and written by the one persistence writer, in order
	// with the saves around it.
	flatfile_shopkeeper_record shop;
	const player_snapshot_capture_result captured =
		flatfile_shopkeeper_capture(ch, static_cast<uint32_t>(shop_nr), 1, time(0), &shop);
	if (captured != player_snapshot_capture_result::ok)
	{
		logit(LOG_DEBUG, "sql_save_shopkeeper: shop=%d capture_result=%d", shop_nr,
		      static_cast<int>(captured));
		return false;
	}
	// Fixed shops can be moved by game mechanics after binding. Their stock remains
	// owned by that shop and cold-restores at its configured home; only roaming shops
	// persist a changing location.
	if (!shop_index[shop_nr].shop_is_roaming)
		shop.room_vnum = shop_index[shop_nr].in_room;
	// Producing stock is regenerated from the shop's definition, not saved.
	for (P_obj obj = ch->carrying; obj; obj = obj->next_content)
		if (shop_producing(obj, shop_nr))
		{
			std::vector<player_item_snapshot> produced, rest;
			const player_snapshot_codec_result extracted =
				player_item_snapshot_extract_subtree(shop.items, obj->obj_uid,
								     &produced, &rest);
			if (extracted != player_snapshot_codec_result::ok)
			{
				logit(LOG_DEBUG,
				      "sql_save_shopkeeper: shop=%d produced_uid=%lu extract_result=%d",
				      shop_nr, obj->obj_uid, static_cast<int>(extracted));
				return false;
			}
			shop.items = std::move(rest);
		}
	const size_t bytes = sizeof(shop) + shop.items.size() * sizeof(player_item_snapshot);
	// The writer's owners are nonzero; shop numbers start at 0.
	const player_save_submit_result submitted = persistence_writer_submit(
		persistence_job_kind::shopkeeper, static_cast<uint64_t>(shop_nr) + 1, bytes,
		[shop]() { return shopkeeper_snapshot_repository_apply_from_pool(shop); });
	return submitted == player_save_submit_result::accepted ||
	       submitted == player_save_submit_result::replaced;
}

static bool sql_save_saved_item_affects(int item_id, P_obj obj)
{
	if (!obj || !DB || item_id <= 0)
		return false;

	for (int i = 0; i < MAX_OBJ_AFFECT; i++)
	{
		if (obj->affected[i].location != 0 || obj->affected[i].modifier != 0)
		{
			char query[256];
			snprintf(
				query, sizeof(query),
				"INSERT INTO saved_item_affects (item_id, location, modifier) VALUES (%d, %d, %d)",
				item_id, obj->affected[i].location, obj->affected[i].modifier);
			if (!sql_run_query(query))
				return false;
		}
	}
	return true;
}

static int sql_save_saved_item_recursive(const char *item_key, int room_vnum, P_obj obj,
					 int container_id)
{
	if (!obj || !DB)
		return 0;

	int vnum = obj_index[obj->R_num].virtual_number;

	char *esc_name = NULL;
	char *esc_short = NULL;
	char *esc_desc = NULL;
	char *esc_action = NULL;

	if (obj->str_mask & STRUNG_KEYS)
		esc_name = sql_escape_string(obj->name ? obj->name : "");
	if (obj->str_mask & STRUNG_DESC2)
		esc_short = sql_escape_string(obj->short_description ? obj->short_description : "");
	if (obj->str_mask & STRUNG_DESC1)
		esc_desc = sql_escape_string(obj->description ? obj->description : "");
	if (obj->str_mask & STRUNG_DESC3)
		esc_action =
			sql_escape_string(obj->action_description ? obj->action_description : "");

	char container_str[32];
	if (container_id > 0)
		snprintf(container_str, sizeof(container_str), "%d", container_id);
	else
		strcpy(container_str, "NULL");

	char name_str[1024], short_str[1024], desc_str[2048], action_str[2048];
	if (esc_name)
		snprintf(name_str, sizeof(name_str), "'%s'", esc_name);
	else
		strcpy(name_str, "NULL");
	if (esc_short)
		snprintf(short_str, sizeof(short_str), "'%s'", esc_short);
	else
		strcpy(short_str, "NULL");
	if (esc_desc)
		snprintf(desc_str, sizeof(desc_str), "'%s'", esc_desc);
	else
		strcpy(desc_str, "NULL");
	if (esc_action)
		snprintf(action_str, sizeof(action_str), "'%s'", esc_action);
	else
		strcpy(action_str, "NULL");

	char *esc_key = sql_escape_string(item_key);

	char query[8192];
	// Shared helper formats wear_str, type_str, and bv1-5_str
	// (NULL when matching the prototype) and frees the loaded prototype.
	// See sql_format_item_diff_fields_and_free_proto().
	char wear_str[32];
	char type_str[16];
	char material_str[16];
	char bv1_str[32], bv2_str[32], bv3_str[32], bv4_str[32], bv5_str[32];
	sql_format_item_diff_fields_and_free_proto(obj, wear_str, type_str, material_str, bv1_str,
						   bv2_str, bv3_str, bv4_str, bv5_str);

	snprintf(
		query, sizeof(query),
		"INSERT INTO saved_items ("
		"item_key, room_vnum, vnum, container_id, quantity, "
		"weight, cost, timer, extra_flags, "
		"value0, value1, value2, value3, value4, value5, value6, value7, "
		"name, short_descr, description, action_descr, wear_flags, item_type, bitvector1, bitvector2, bitvector3, bitvector4, bitvector5, "
		"item_material, obj_uid"
		") VALUES ("
		"'%s', %d, %d, %s, 1, "
		"%d, %d, %ld, %lu, "
		"%d, %d, %d, %d, %d, %d, %d, %d, "
		"%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
		"%s, %lu"
		")",
		esc_key ? esc_key : "", room_vnum, vnum, container_str, obj->weight, obj->cost,
		(long)obj->timer[0], (unsigned long)obj->extra_flags, obj->value[0], obj->value[1],
		obj->value[2], obj->value[3], obj->value[4], obj->value[5], obj->value[6],
		obj->value[7], name_str, short_str, desc_str, action_str, wear_str, type_str,
		bv1_str, bv2_str, bv3_str, bv4_str, bv5_str, material_str, obj->obj_uid);

	if (esc_key)
		free(esc_key);
	if (esc_name)
		free(esc_name);
	if (esc_short)
		free(esc_short);
	if (esc_desc)
		free(esc_desc);
	if (esc_action)
		free(esc_action);

	if (!sql_run_query(query))
		return 0;

	int item_id = (int)mysql_insert_id(DB);

	if (!sql_save_saved_item_affects(item_id, obj))
		return 0;
	if (!sql_save_item_extra_descr(item_id, obj, "saved_item_extra_descr"))
		return 0;

	if (obj->contains)
	{
		for (P_obj content = obj->contains; content; content = content->next_content)
		{
			if (sql_save_saved_item_recursive(item_key, room_vnum, content, item_id) <=
			    0)
				return 0;
		}
	}

	return item_id;
}

struct shopkeeper_temp
{
	int shop_nr;
	int shopkeeper_id;
	int mob_vnum;
	int room_vnum;
	P_char mob;
	P_obj equipment[MAX_WEAR];
	P_obj inventory;
	struct shopkeeper_temp *next;
};

// temp struct for batched item loading across all shopkeepers
struct all_items_temp
{
	int item_id;
	int shopkeeper_id;
	int container_id;
	int equip_slot;
	int affect_count;
	P_obj obj;
	struct all_items_temp *next;
};

void discard_shopkeeper_restore_stage(struct shopkeeper_temp *keepers,
				      struct all_items_temp *all_items, bool items_attached)
{
	/* Once items have been attached to staged NPCs, extract_char owns their
	 * complete object graph.  Before that point every materialized item is an
	 * unlinked root and must be explicitly discarded. */
	if (items_attached)
	{
		// Trees are linked in the staging records, not yet equipped/carried.
		for (struct shopkeeper_temp *k = keepers; k; k = k->next)
		{
			for (P_obj obj : k->equipment)
				if (obj)
					extract_obj(obj);
			while (k->inventory)
			{
				P_obj obj = k->inventory;
				k->inventory = obj->next_content;
				obj->next_content = nullptr;
				extract_obj(obj);
			}
			if (k->mob)
				extract_char(k->mob);
		}
	}
	else
	{
		for (struct all_items_temp *item = all_items; item; item = item->next)
			if (item->obj)
				extract_obj(item->obj);
		for (struct shopkeeper_temp *k = keepers; k; k = k->next)
			if (k->mob)
				extract_char(k->mob);
	}
	while (keepers)
	{
		struct shopkeeper_temp *next = keepers->next;
		free(keepers);
		keepers = next;
	}
	while (all_items)
	{
		struct all_items_temp *next = all_items->next;
		free(all_items);
		all_items = next;
	}
}

static bool sql_restore_shopkeeper_catalog(int only_shop, P_char *restored)
{
	if (!DB)
		return false;

	// query 1: load all shopkeepers
	MYSQL_RES *result =
		db_query("SELECT shop_id, id, mob_vnum, room_vnum FROM shopkeepers "
			 "WHERE (%d < 0 OR shop_id=%d) ORDER BY save_time DESC, id DESC",
			 only_shop, only_shop);
	if (!result)
		return false;

	struct shopkeeper_temp *keepers = NULL;
	struct all_items_temp *all_items = NULL;
	struct all_items_temp *last_item = NULL;
	int keeper_count = 0;
	MYSQL_ROW row;

	while ((row = mysql_fetch_row(result)))
	{
		int shop_nr = atoi(row[0]);
		int shopkeeper_id = atoi(row[1]);
		int mob_vnum = atoi(row[2]);
		int room_vnum = atoi(row[3]);

		const int mob_rnum = real_mobile(mob_vnum);
		if (shop_nr < 0 || shop_nr >= number_of_shops || mob_rnum < 0 ||
		    shop_index[shop_nr].keeper != mob_rnum || room_vnum <= 0 ||
		    real_room(room_vnum) == NOWHERE ||
		    (!shop_index[shop_nr].shop_is_roaming &&
		     room_vnum != shop_index[shop_nr].in_room))
		{
			logit(LOG_DEBUG,
			      "sql_restore_shopkeepers: skipping invalid shop %d vnum %d room %d",
			      shop_nr, mob_vnum, room_vnum);
			mysql_free_result(result);
			discard_shopkeeper_restore_stage(keepers, all_items, false);
			return false;
		}
		bool duplicate = false;
		for (struct shopkeeper_temp *existing = keepers; existing;
		     existing = existing->next)
			if (existing->shop_nr == shop_nr)
			{
				duplicate = true;
				break;
			}
		if (duplicate)
		{
			logit(LOG_DEBUG,
			      "sql_restore_shopkeepers: skipping duplicate shop %d vnum %d room %d",
			      shop_nr, mob_vnum, room_vnum);
			continue;
		}

		P_char mob = read_mobile(mob_vnum, VIRTUAL);
		if (!mob)
		{
			logit(LOG_DEBUG, "sql_restore_shopkeeper: mob vnum %d not found", mob_vnum);
			mysql_free_result(result);
			discard_shopkeeper_restore_stage(keepers, all_items, false);
			return false;
		}

		struct shopkeeper_temp *k =
			(struct shopkeeper_temp *)malloc(sizeof(struct shopkeeper_temp));
		if (!k)
		{
			extract_char(mob);
			mysql_free_result(result);
			discard_shopkeeper_restore_stage(keepers, all_items, false);
			return false;
		}
		k->shop_nr = shop_nr;
		k->shopkeeper_id = shopkeeper_id;
		k->mob_vnum = mob_vnum;
		k->room_vnum = room_vnum;
		k->mob = mob;
		memset(k->equipment, 0, sizeof(k->equipment));
		k->inventory = NULL;

		GET_BIRTHPLACE(mob) = room_vnum;
		bind_shopkeeper(mob, shop_nr);

		k->next = keepers;
		keepers = k;
		keeper_count++;
	}
	mysql_free_result(result);

	if (keeper_count == 0)
		return true;

	// query 2: load all shopkeeper affects
	result = db_query(
		"SELECT sa.shopkeeper_id, sa.type, sa.duration, sa.modifier, sa.location, "
		"sa.bitvector1, sa.bitvector2, sa.bitvector3, sa.bitvector4, sa.bitvector5 "
		"FROM shopkeeper_affects sa "
		"INNER JOIN shopkeepers s ON sa.shopkeeper_id = s.id WHERE (%d < 0 OR s.shop_id=%d)",
		only_shop, only_shop);
	if (!result)
	{
		discard_shopkeeper_restore_stage(keepers, all_items, false);
		return false;
	}
	{
		while ((row = mysql_fetch_row(result)))
		{
			int shopkeeper_id = atoi(row[0]);
			bool matched = false;
			for (struct shopkeeper_temp *k = keepers; k; k = k->next)
			{
				if (k->shopkeeper_id == shopkeeper_id)
				{
					matched = true;
					struct affected_type af;
					memset(&af, 0, sizeof(af));
					af.type = atoi(row[1]);
					af.duration = atoi(row[2]);
					af.modifier = atoi(row[3]);
					af.location = atoi(row[4]);
					af.bitvector = strtoul(row[5], NULL, 10);
					af.bitvector2 = strtoul(row[6], NULL, 10);
					af.bitvector3 = strtoul(row[7], NULL, 10);
					af.bitvector4 = strtoul(row[8], NULL, 10);
					af.bitvector5 = strtoul(row[9], NULL, 10);
					affect_to_char(k->mob, &af);
					break;
				}
			}
			if (!matched)
			{
				mysql_free_result(result);
				discard_shopkeeper_restore_stage(keepers, all_items, false);
				return false;
			}
		}
		mysql_free_result(result);
	}

	// query 3: load all items for all shopkeepers
	result = db_query(
		"SELECT si.id, si.shopkeeper_id, si.vnum, si.equip_slot, si.weight, si.cost, si.timer, "
		"si.extra_flags, si.value0, si.value1, si.value2, si.value3, si.value4, si.value5, "
		"si.value6, si.value7, si.name, si.short_descr, si.description, si.action_descr, si.container_id, "
		"si.wear_flags, si.item_type, si.item_material, si.bitvector1, si.bitvector2, si.bitvector3, si.bitvector4, si.bitvector5 "
		"FROM shopkeeper_items si "
		"INNER JOIN shopkeepers s ON si.shopkeeper_id = s.id "
		"WHERE (%d < 0 OR s.shop_id=%d) ORDER BY si.shopkeeper_id, si.id",
		only_shop, only_shop);
	if (!result)
	{
		discard_shopkeeper_restore_stage(keepers, all_items, false);
		return false;
	}
	{
		while ((row = mysql_fetch_row(result)))
		{
			int item_id = atoi(row[0]);
			int shopkeeper_id = atoi(row[1]);
			bool accepted_keeper = false;
			for (struct shopkeeper_temp *k = keepers; k; k = k->next)
				if (k->shopkeeper_id == shopkeeper_id)
				{
					accepted_keeper = true;
					break;
				}
			if (!accepted_keeper)
			{
				mysql_free_result(result);
				discard_shopkeeper_restore_stage(keepers, all_items, false);
				return false;
			}
			int vnum = atoi(row[2]);
			int rnum = real_object(vnum);
			if (rnum < 0)
			{
				mysql_free_result(result);
				discard_shopkeeper_restore_stage(keepers, all_items, false);
				return false;
			}

			P_obj obj = read_object(rnum, REAL);
			if (!obj)
			{
				mysql_free_result(result);
				discard_shopkeeper_restore_stage(keepers, all_items, false);
				return false;
			}

			int equip_slot = atoi(row[3]);
			int container_id = row[20] ? atoi(row[20]) : 0;
			if (equip_slot < 0 || equip_slot > MAX_WEAR || container_id < 0)
			{
				extract_obj(obj);
				mysql_free_result(result);
				discard_shopkeeper_restore_stage(keepers, all_items, false);
				return false;
			}

			if (row[4])
				obj->weight = atoi(row[4]);
			if (row[5])
				obj->cost = atoi(row[5]);
			if (row[6])
				obj->timer[0] = atol(row[6]);
			if (row[7])
				obj->extra_flags = strtoul(row[7], NULL, 10);

			obj->value[0] = row[8] ? atoi(row[8]) : 0;
			obj->value[1] = row[9] ? atoi(row[9]) : 0;
			obj->value[2] = row[10] ? atoi(row[10]) : 0;
			obj->value[3] = row[11] ? atoi(row[11]) : 0;
			obj->value[4] = row[12] ? atoi(row[12]) : 0;
			obj->value[5] = row[13] ? atoi(row[13]) : 0;
			obj->value[6] = row[14] ? atoi(row[14]) : 0;
			obj->value[7] = row[15] ? atoi(row[15]) : 0;

			if (row[16] && strlen(row[16]) > 0)
			{
				obj->name = str_dup(row[16]);
				obj->str_mask |= STRUNG_KEYS;
			}
			if (row[17] && strlen(row[17]) > 0)
			{
				obj->short_description = str_dup(row[17]);
				obj->str_mask |= STRUNG_DESC2;
			}
			if (row[18] && strlen(row[18]) > 0)
			{
				obj->description = str_dup(row[18]);
				obj->str_mask |= STRUNG_DESC1;
			}
			if (row[19] && strlen(row[19]) > 0)
			{
				obj->action_description = str_dup(row[19]);
				obj->str_mask |= STRUNG_DESC3;
			}

			if (row[21])
				obj->wear_flags = atoi(row[21]);
			if (row[22])
				obj->type = sql_validate_loaded_item_type(
					obj, atoi(row[22]), "sql_restore_shopkeepers");
			if (row[23])
				obj->material = atoi(row[23]);
			if (row[24])
				obj->bitvector = strtoul(row[24], NULL, 10);
			if (row[25])
				obj->bitvector2 = strtoul(row[25], NULL, 10);
			if (row[26])
				obj->bitvector3 = strtoul(row[26], NULL, 10);
			if (row[27])
				obj->bitvector4 = strtoul(row[27], NULL, 10);
			if (row[28])
				obj->bitvector5 = strtoul(row[28], NULL, 10);
			obj->db_item_id = item_id;
			if (!sql_load_item_extra_descr_from_table(item_id, obj, "shopkeeper_item"))
			{
				extract_obj(obj);
				mysql_free_result(result);
				discard_shopkeeper_restore_stage(keepers, all_items, false);
				return false;
			}

			struct all_items_temp *t =
				(struct all_items_temp *)malloc(sizeof(struct all_items_temp));
			if (!t)
			{
				extract_obj(obj);
				mysql_free_result(result);
				discard_shopkeeper_restore_stage(keepers, all_items, false);
				return false;
			}
			for (struct all_items_temp *existing = all_items; existing;
			     existing = existing->next)
				if (existing->item_id == item_id)
				{
					extract_obj(obj);
					free(t);
					mysql_free_result(result);
					discard_shopkeeper_restore_stage(keepers, all_items, false);
					return false;
				}
			t->item_id = item_id;
			t->shopkeeper_id = shopkeeper_id;
			t->container_id = container_id;
			t->equip_slot = equip_slot;
			t->affect_count = 0;
			t->obj = obj;
			t->next = NULL;

			if (!all_items)
				all_items = t;
			else
				last_item->next = t;
			last_item = t;
		}
		mysql_free_result(result);
	}

	// query 4: load all item affects
	result = db_query("SELECT sia.item_id, sia.location, sia.modifier "
			  "FROM shopkeeper_item_affects sia "
			  "INNER JOIN shopkeeper_items si ON sia.item_id = si.id "
			  "INNER JOIN shopkeepers s ON si.shopkeeper_id = s.id "
			  "WHERE (%d < 0 OR s.shop_id=%d) ORDER BY sia.item_id",
			  only_shop, only_shop);
	if (!result)
	{
		discard_shopkeeper_restore_stage(keepers, all_items, false);
		return false;
	}
	{
		while ((row = mysql_fetch_row(result)))
		{
			int aff_item_id = atoi(row[0]);
			int location = atoi(row[1]);
			int modifier = atoi(row[2]);
			bool matched = false;
			bool placed = false;

			for (struct all_items_temp *t = all_items; t; t = t->next)
			{
				if (t->item_id != aff_item_id)
					continue;
				matched = true;
				if (t->affect_count == 0)
					memset(t->obj->affected, 0, sizeof(t->obj->affected));
				if (t->affect_count < MAX_OBJ_AFFECT)
				{
					t->obj->affected[t->affect_count].location = location;
					t->obj->affected[t->affect_count++].modifier = modifier;
					placed = true;
				}
				break;
			}
			if (!matched || !placed)
			{
				mysql_free_result(result);
				discard_shopkeeper_restore_stage(keepers, all_items, false);
				return false;
			}
		}
		mysql_free_result(result);
	}

	// link container contents
	int item_count = 0;
	for (struct all_items_temp *item = all_items; item; item = item->next)
		++item_count;
	for (struct all_items_temp *t = all_items; t; t = t->next)
	{
		if (t->equip_slot > 0)
			for (struct all_items_temp *other = t->next; other; other = other->next)
				if (other->shopkeeper_id == t->shopkeeper_id &&
				    other->equip_slot == t->equip_slot)
				{
					discard_shopkeeper_restore_stage(keepers, all_items, false);
					return false;
				}
		if (t->container_id > 0)
		{
			struct all_items_temp *parent = NULL;
			for (struct all_items_temp *p = all_items; p; p = p->next)
				if (p->item_id == t->container_id)
				{
					parent = p;
					break;
				}
			if (!parent || parent->shopkeeper_id != t->shopkeeper_id ||
			    t->equip_slot != 0 || !obj_can_nest(t->obj, parent->obj))
			{
				discard_shopkeeper_restore_stage(keepers, all_items, false);
				return false;
			}
			int hops = 0;
			for (struct all_items_temp *cursor = t; cursor && cursor->container_id > 0;
			     ++hops)
			{
				if (hops >= item_count)
				{
					discard_shopkeeper_restore_stage(keepers, all_items, false);
					return false;
				}
				const int parent_id = cursor->container_id;
				cursor = NULL;
				for (struct all_items_temp *candidate = all_items; candidate;
				     candidate = candidate->next)
					if (candidate->item_id == parent_id)
					{
						cursor = candidate;
						break;
					}
				if (!cursor)
					break;
				if (cursor == t)
				{
					discard_shopkeeper_restore_stage(keepers, all_items, false);
					return false;
				}
			}
		}
	}
	for (struct all_items_temp *t = all_items; t; t = t->next)
	{
		if (t->container_id <= 0)
			continue;
		for (struct all_items_temp *p = all_items; p; p = p->next)
			if (p->item_id == t->container_id)
			{
				t->obj->next_content = p->obj->contains;
				p->obj->contains = t->obj;
				t->obj->loc_p = LOC_INSIDE;
				t->obj->loc.inside = p->obj;
				break;
			}
	}

	// assign items to shopkeepers
	for (struct all_items_temp *t = all_items; t; t = t->next)
	{
		if (t->container_id > 0)
			continue;

		for (struct shopkeeper_temp *k = keepers; k; k = k->next)
		{
			if (k->shopkeeper_id == t->shopkeeper_id)
			{
				if (t->equip_slot > 0 && t->equip_slot <= MAX_WEAR)
					k->equipment[t->equip_slot - 1] = t->obj;
				else
				{
					t->obj->next_content = k->inventory;
					k->inventory = t->obj;
				}
				break;
			}
		}
	}

	/* Materialize derived stock while the restore is still staged.  A failed
	 * prototype read must discard the complete stage, not publish a partial
	 * snapshot and mark the durable row dirty. */
	for (struct shopkeeper_temp *k = keepers; k; k = k->next)
	{
		for (int i = 0; i < shop_index[k->shop_nr].number_items_produced; ++i)
		{
			const int rnum = shop_index[k->shop_nr].producing[i];
			if (rnum < 0)
				continue;
			bool found = false;
			for (P_obj obj = k->inventory; obj; obj = obj->next_content)
				if (obj->R_num == rnum)
				{
					found = true;
					break;
				}
			for (int slot = 0; !found && slot < MAX_WEAR; ++slot)
				if (k->equipment[slot] && k->equipment[slot]->R_num == rnum)
					found = true;
			if (!found)
			{
				P_obj obj = read_object(rnum, REAL);
				if (!obj)
				{
					discard_shopkeeper_restore_stage(keepers, all_items, true);
					return false;
				}
				obj->next_content = k->inventory;
				k->inventory = obj;
			}
		}
	}

	// free item temp structs
	struct all_items_temp *ti = all_items;
	while (ti)
	{
		struct all_items_temp *next = ti->next;
		free(ti);
		ti = next;
	}

	// process each shopkeeper
	int loaded = 0;
	for (struct shopkeeper_temp *k = keepers; k; k = k->next)
	{
		int load_room = real_room(k->room_vnum);
		if (load_room == NOWHERE)
		{
			logit(LOG_DEBUG, "sql_restore_shopkeepers: bad room %d for shop %d",
			      k->room_vnum, k->shop_nr);
			extract_char(k->mob);
			continue;
		}

		// equip and set inventory
		for (int slot = 0; slot < MAX_WEAR; slot++)
		{
			if (k->equipment[slot])
				equip_char(k->mob, k->equipment[slot], slot, 0);
		}
		k->mob->carrying = k->inventory;
		for (P_obj obj = k->mob->carrying; obj; obj = obj->next_content)
		{
			obj->loc_p = LOC_CARRIED;
			obj->loc.carrying = k->mob;
		}

		const int shop_idx = k->shop_nr;

		// Replace only one incumbent already proven to belong to this exact
		// shop.  A controlled NPC, a different bound shop, or an ambiguous
		// same-template population is never destructive restore authority.
		std::vector<P_char> incumbents;
		for (P_char keeper2 : live_shopkeepers(k->shop_nr))
			if (keeper2 != k->mob &&
			    (shop_index[k->shop_nr].shop_is_roaming ||
			     keeper2->in_room == load_room) &&
			    mob_index[GET_RNUM(keeper2)].virtual_number == k->mob_vnum)
				incumbents.push_back(keeper2);
		const int incumbent_matches = static_cast<int>(incumbents.size());
		int extracted = 0;
		if (!restored && incumbent_matches == 1)
		{
			extract_char(incumbents[0]);
			extracted = 1;
		}
		if (persistence_trace_enabled())
			logit(LOG_DEBUG,
			      "sql_restore_shopkeepers: shop %d vnum %d incumbent_matches=%d extracted=%d",
			      k->shop_nr, k->mob_vnum, incumbent_matches, extracted);

		if (restored)
			*restored = k->mob;
		else
			char_to_room(k->mob, load_room, 0);

		// Derived stock was materialized before publication. Only a complete
		// catalog restore schedules a replacement snapshot.
		if (!restored)
		{
			shop_index[shop_idx].dirty = 1;
			shopkeeper_save_retry_reset(&shop_index[shop_idx].dirty_save_retry);
		}
		loaded++;
	}

	// Keep the durable snapshot through restore and failed dirty retries.
	// sql_save_shopkeeper replaces only this shop, inside its transaction.
	// Invalid/unloaded rows require operator reconciliation, never a blanket delete.

	// free keeper temp structs
	struct shopkeeper_temp *tk = keepers;
	while (tk)
	{
		struct shopkeeper_temp *next = tk->next;
		free(tk);
		tk = next;
	}

	logit(LOG_DEBUG, "sql_restore_shopkeepers: loaded %d shopkeepers", loaded);
	return true;
}

bool sql_restore_shopkeepers(void)
{
	return sql_restore_shopkeeper_catalog(-1, nullptr);
}

// True while the periodic save's next pulse is scheduled.
static bool shopkeeper_save_continues = false;

// The shops the writer had no room for a pulse ago.
static void event_save_dirty_shopkeepers(P_char /*ch*/, P_char /*victim*/, P_obj /*obj*/,
					 void * /*data*/)
{
	shopkeeper_save_continues = false;
	sql_save_dirty_shopkeepers();
}

bool sql_save_dirty_shopkeepers(bool force)
{
	if (!shop_index || number_of_shops <= 0)
		return true;

	// The one writer takes these saves in order with the players', and a boot leaves
	// every shop dirty: queued at once, 544 shop saves stood ahead of every player save
	// and relog. The periodic save fills the writer's queue to SHOPKEEPER_SAVE_QUEUE
	// jobs and takes the remaining shops on the following pulses, as the writer takes
	// them. A forced save (shutdown, copyover) queues every shop.
	constexpr uint64_t SHOPKEEPER_SAVE_QUEUE = 16;
	uint64_t room = UINT64_MAX;
	if (!force)
	{
		const uint64_t queued = player_save_worker_health_copy().queued_jobs;
		room = queued < SHOPKEEPER_SAVE_QUEUE ? SHOPKEEPER_SAVE_QUEUE - queued : 0;
	}
	bool waiting = false;
	const time_t now = time(NULL);
	std::vector<int> due;
	std::unordered_multimap<int, int> due_by_keeper;
	for (int i = 0; i < number_of_shops; i++)
	{
		if (!shop_index[i].dirty)
		{
			shopkeeper_save_retry_reset(&shop_index[i].dirty_save_retry);
			continue;
		}
		shopkeeper_save_retry_state *retry = &shop_index[i].dirty_save_retry;
		if (!DB || !shopkeeper_save_retry_due(retry, now, force))
		{
			if (!DB)
				shopkeeper_save_retry_record_failure(retry, now);
			continue;
		}
		if (due.size() >= room)
		{
			waiting = true;
			continue;
		}
		due.push_back(i);
		due_by_keeper.emplace(shop_index[i].keeper, i);
	}
	if (waiting && !shopkeeper_save_continues)
		shopkeeper_save_continues =
			add_event(event_save_dirty_shopkeepers, 1, NULL, NULL, NULL, 0, NULL, 0)
				.was_scheduled();

	const std::vector<shopkeeper_candidates> found =
		find_shopkeepers_for_dirty_save(due_by_keeper);
	int saved = 0;
	for (int i : due)
	{
		shopkeeper_save_retry_state *retry = &shop_index[i].dirty_save_retry;
		P_char keeper = NULL;
		shopkeeper_save_reason reason =
			choose_shopkeeper_for_dirty_save(i, found[i], &keeper);
		if (reason == shopkeeper_save_reason::ok && sql_save_shopkeeper(keeper, i))
		{
			shop_index[i].dirty = 0;
			shopkeeper_save_retry_reset(retry);
			saved++;
			continue;
		}
		if (reason == shopkeeper_save_reason::ok)
			reason = shopkeeper_save_reason::save_failed;
		shopkeeper_save_retry_record_failure(retry, now);
		log_shopkeeper_dirty_retry(i, reason, keeper, now, force);
	}

	if (saved > 0 && persistence_trace_enabled())
		logit(LOG_DEBUG, "sql_save_dirty_shopkeepers: saved %d shopkeepers", saved);
	for (int i = 0; i < number_of_shops; ++i)
		if (shop_index[i].dirty)
			return false;
	return true;
}

static P_obj sql_load_saved_item_contents(const char *item_key, int room_vnum, int container_id,
					  int depth, std::vector<int> *source_ids, bool *valid)
{
	if (!DB || !item_key || !source_ids || !valid)
		return NULL;

	if (depth > MAX_CONTAINER_LOAD_DEPTH)
	{
		*valid = false;
		logit(LOG_DEBUG,
		      "sql_load_saved_item_contents: component=container outcome=depth_limit");
		return NULL;
	}

	char *esc_key = sql_escape_string(item_key);
	if (!esc_key)
	{
		*valid = false;
		return NULL;
	}

	char query[512];
	snprintf(query, sizeof(query),
		 "SELECT id, vnum, weight, cost, timer, extra_flags, "
		 "value0, value1, value2, value3, value4, value5, value6, value7, "
		 "name, short_descr, description, action_descr, "
		 "wear_flags, item_type, item_material, "
		 "bitvector1, bitvector2, bitvector3, bitvector4, bitvector5, "
		 "obj_uid "
		 "FROM saved_items WHERE item_key='%s' AND container_id=%d",
		 esc_key, container_id);
	free(esc_key);

	MYSQL_RES *result = db_query("%s", query);
	if (!result)
	{
		*valid = false;
		return NULL;
	}

	P_obj first_obj = NULL;
	P_obj last_obj = NULL;
	MYSQL_ROW row;

	while ((row = mysql_fetch_row(result)))
	{
		int item_id = atoi(row[0]);
		source_ids->push_back(item_id);
		int vnum = atoi(row[1]);
		int rnum = real_object(vnum);
		if (rnum < 0)
		{
			*valid = false;
			continue;
		}

		P_obj obj = read_object(rnum, REAL);
		if (!obj)
		{
			*valid = false;
			continue;
		}

		if (row[2])
			obj->weight = atoi(row[2]);
		if (row[3])
			obj->cost = atoi(row[3]);
		if (row[4])
			obj->timer[0] = atol(row[4]);
		if (row[5])
			obj->extra_flags = strtoul(row[5], NULL, 10);

		obj->value[0] = row[6] ? atoi(row[6]) : obj->value[0];
		obj->value[1] = row[7] ? atoi(row[7]) : obj->value[1];
		obj->value[2] = row[8] ? atoi(row[8]) : obj->value[2];
		obj->value[3] = row[9] ? atoi(row[9]) : obj->value[3];
		obj->value[4] = row[10] ? atoi(row[10]) : obj->value[4];
		obj->value[5] = row[11] ? atoi(row[11]) : obj->value[5];
		obj->value[6] = row[12] ? atoi(row[12]) : obj->value[6];
		obj->value[7] = row[13] ? atoi(row[13]) : obj->value[7];

		if (row[14] && strlen(row[14]) > 0)
		{
			obj->name = str_dup(row[14]);
			obj->str_mask |= STRUNG_KEYS;
		}
		if (row[15] && strlen(row[15]) > 0)
		{
			obj->short_description = str_dup(row[15]);
			obj->str_mask |= STRUNG_DESC2;
		}
		if (row[16] && strlen(row[16]) > 0)
		{
			obj->description = str_dup(row[16]);
			obj->str_mask |= STRUNG_DESC1;
		}
		if (row[17] && strlen(row[17]) > 0)
		{
			obj->action_description = str_dup(row[17]);
			obj->str_mask |= STRUNG_DESC3;
		}
		// v19 diff columns - NULL means use prototype value from read_object()
		if (row[18])
			obj->wear_flags = atoi(row[18]);
		if (row[19])
			obj->type = sql_validate_loaded_item_type(obj, atoi(row[19]),
								  "sql_load_saved_item_contents");
		if (row[20])
			obj->material = atoi(row[20]);
		if (row[21])
			obj->bitvector = strtoul(row[21], NULL, 10);
		if (row[22])
			obj->bitvector2 = strtoul(row[22], NULL, 10);
		if (row[23])
			obj->bitvector3 = strtoul(row[23], NULL, 10);
		if (row[24])
			obj->bitvector4 = strtoul(row[24], NULL, 10);
		if (row[25])
			obj->bitvector5 = strtoul(row[25], NULL, 10);
		const unsigned long saved_uid = row[26] ? strtoul(row[26], NULL, 10) : 0;
		if (saved_uid)
			obj->obj_uid = saved_uid;
		char owner_ref[32];
		snprintf(owner_ref, sizeof(owner_ref), "%d", room_vnum);
		if (!sql_persistence_item_owner_matches(obj->obj_uid, "room", owner_ref,
							"sql_load_saved_item_contents"))
		{
			// A stale copy another owner holds is left out, and what it contains
			// moves up a level; the rest of the container still loads.
			extract_obj(obj, FALSE);
			append_loaded_objects(&first_obj, &last_obj,
					      sql_load_saved_item_contents(item_key, room_vnum,
									   item_id, depth + 1,
									   source_ids, valid));
			continue;
		}
		obj->db_item_id = item_id;
		if (!sql_load_item_extra_descr_from_table(item_id, obj, "saved_item"))
			*valid = false;

		char aff_query[128];
		snprintf(aff_query, sizeof(aff_query),
			 "SELECT location, modifier FROM saved_item_affects WHERE item_id=%d",
			 item_id);
		MYSQL_RES *aff_result = db_query("%s", aff_query);
		if (aff_result)
		{
			MYSQL_ROW aff_row;
			int aff_idx = 0;
			while ((aff_row = mysql_fetch_row(aff_result)) && aff_idx < MAX_OBJ_AFFECT)
			{
				obj->affected[aff_idx].location = atoi(aff_row[0]);
				obj->affected[aff_idx].modifier = atoi(aff_row[1]);
				aff_idx++;
			}
			mysql_free_result(aff_result);
		}
		else
			*valid = false;

		obj->contains = sql_load_saved_item_contents(item_key, room_vnum, item_id,
							     depth + 1, source_ids, valid);
		for (P_obj c = obj->contains; c; c = c->next_content)
		{
			if (!obj_can_nest(c, obj))
			{
				*valid = false;
				logit(LOG_DEBUG,
				      "sql_load_saved_item_contents: skipping malformed container link %d -> %d",
				      c->db_item_id, obj->db_item_id);
				continue;
			}
			c->loc_p = LOC_INSIDE;
			c->loc.inside = obj;
		}

		if (!first_obj)
			first_obj = obj;
		else
			last_obj->next_content = obj;
		last_obj = obj;
		obj->next_content = NULL;
	}

	mysql_free_result(result);
	return first_obj;
}

static void sql_saved_item_restore_fault(const char *stage)
{
	const char *environment = getenv("ENVIRONMENT");
	const char *selected = getenv("DURIS_SAVED_ITEM_RESTORE_FAULT_STAGE");
	const char *pause = getenv("DURIS_SAVED_ITEM_RESTORE_PAUSE_STAGE");
	if (environment && strcmp(environment, "local") == 0 && pause && strcmp(pause, stage) == 0)
	{
		logit(LOG_SYS, "sql_restore_saved_items: injected pause stage=%s", stage);
		std::this_thread::sleep_for(std::chrono::seconds(5));
	}
	if (environment && strcmp(environment, "local") == 0 && selected &&
	    strcmp(selected, stage) == 0)
	{
		logit(LOG_SYS, "sql_restore_saved_items: injected stop stage=%s", stage);
		fflush(NULL);
		_Exit(80);
	}
}

static bool sql_saved_item_uid_key(uint64_t uid, char *buffer, size_t size)
{
	if (!uid || !buffer || size < sizeof "item.uid.18446744073709551615")
		return false;
	const int length =
		snprintf(buffer, size, "item.uid.%llu", static_cast<unsigned long long>(uid));
	return length > 0 && static_cast<size_t>(length) < size;
}

static uint64_t sql_saved_item_season_epoch()
{
	MYSQL_RES *result =
		db_query("SELECT season_epoch FROM season_reset_state WHERE state_id=1");
	if (!result)
		return 0;
	MYSQL_ROW row = mysql_fetch_row(result);
	const uint64_t epoch = row && row[0] ? strtoull(row[0], NULL, 10) : 0;
	mysql_free_result(result);
	return epoch;
}

static bool sql_saved_item_source_rows_match(const char *item_key, const std::vector<int> &expected,
					     bool lock)
{
	if (!item_key || expected.empty())
		return false;
	char *escaped = sql_escape_string(item_key);
	if (!escaped)
		return false;
	char query[512];
	snprintf(query, sizeof(query),
		 "SELECT id, container_id FROM saved_items WHERE item_key='%s' ORDER BY id%s",
		 escaped, lock ? " FOR UPDATE" : "");
	MYSQL_RES *result = db_query("%s", query);
	if (!result)
	{
		free(escaped);
		return false;
	}
	std::vector<int> observed;
	bool graph_valid = true;
	int roots = 0;
	MYSQL_ROW row;
	while ((row = mysql_fetch_row(result)))
	{
		const int id = atoi(row[0]);
		observed.push_back(id);
		if (!row[1])
		{
			++roots;
			if (id != expected[0])
				graph_valid = false;
		}
		else if (std::find(expected.begin(), expected.end(), atoi(row[1])) ==
			 expected.end())
			graph_valid = false;
	}
	mysql_free_result(result);
	std::vector<int> sorted = expected;
	std::sort(sorted.begin(), sorted.end());
	graph_valid = graph_valid && roots == 1 && observed == sorted;
	for (int id : expected)
	{
		snprintf(
			query, sizeof(query),
			"SELECT COUNT(*) FROM saved_items WHERE container_id=%d AND item_key<>'%s'%s",
			id, escaped, lock ? " FOR UPDATE" : "");
		result = db_query("%s", query);
		if (!result)
		{
			graph_valid = false;
			break;
		}
		row = mysql_fetch_row(result);
		if (!row || !row[0] || atoi(row[0]) != 0)
			graph_valid = false;
		mysql_free_result(result);
		if (!graph_valid)
			break;
	}
	free(escaped);
	return graph_valid;
}

static bool sql_saved_item_source_ids(const char *item_key, std::vector<int> *ids)
{
	if (!item_key || !ids)
		return false;
	char *escaped = sql_escape_string(item_key);
	if (!escaped)
		return false;
	char query[512];
	snprintf(query, sizeof(query), "SELECT id FROM saved_items WHERE item_key='%s'", escaped);
	free(escaped);
	MYSQL_RES *result = db_query("%s", query);
	if (!result)
		return false;
	ids->clear();
	MYSQL_ROW row;
	while ((row = mysql_fetch_row(result)))
		ids->push_back(atoi(row[0]));
	mysql_free_result(result);
	return true;
}

static std::string sql_saved_item_source_id_digest(const std::vector<int> &ids)
{
	std::vector<int> ordered = ids;
	std::sort(ordered.begin(), ordered.end());
	std::string serialized;
	for (int id : ordered)
	{
		serialized += std::to_string(id);
		serialized += ',';
	}
	unsigned char digest[SHA256_DIGEST_LENGTH];
	SHA256(reinterpret_cast<const unsigned char *>(serialized.data()), serialized.size(),
	       digest);
	static const char digits[] = "0123456789ABCDEF";
	std::string hex;
	hex.reserve(SHA256_DIGEST_LENGTH * 2);
	for (unsigned char byte : digest)
	{
		hex += digits[byte >> 4];
		hex += digits[byte & 15];
	}
	return hex;
}

static bool sql_saved_item_collect_uids(P_obj obj, std::unordered_set<uint64_t> *uids)
{
	if (!obj || !uids || !obj->obj_uid || !uids->insert(obj->obj_uid).second)
		return false;
	for (P_obj child = obj->contains; child; child = child->next_content)
		if (!sql_saved_item_collect_uids(child, uids))
			return false;
	return true;
}

static bool sql_saved_item_handoff_receipt(uint64_t epoch, int source_root_id,
					   int *destination_root_id, int *source_count,
					   bool *retired, std::string *source_digest = NULL)
{
	char query[256];
	snprintf(query, sizeof(query),
		 "SELECT destination_root_id, source_row_count, retired_at, HEX(source_id_digest) "
		 "FROM saved_item_recovery_handoff "
		 "WHERE season_epoch=%llu AND source_root_id=%d",
		 static_cast<unsigned long long>(epoch), source_root_id);
	MYSQL_RES *result = db_query("%s", query);
	if (!result)
		return false;
	MYSQL_ROW row = mysql_fetch_row(result);
	const bool found = row != NULL;
	if (found)
	{
		if (destination_root_id)
			*destination_root_id = atoi(row[0]);
		if (source_count)
			*source_count = atoi(row[1]);
		if (retired)
			*retired = row[2] != NULL;
		if (source_digest)
			*source_digest = row[3] ? row[3] : "";
	}
	mysql_free_result(result);
	return found;
}

static bool sql_retire_saved_item_source(uint64_t epoch, int source_root_id, const char *source_key,
					 int source_count)
{
	if (!sql_begin_transaction())
		return false;
	bool ok = false;
	int destination_root_id = 0;
	bool retired = false;
	std::string source_digest;
	if (!sql_saved_item_handoff_receipt(epoch, source_root_id, &destination_root_id, NULL,
					    &retired, &source_digest) ||
	    !destination_root_id)
		goto done;
	if (retired)
	{
		ok = true;
		goto done;
	}
	{
		std::vector<int> source_ids;
		if (!sql_saved_item_source_ids(source_key, &source_ids) ||
		    static_cast<int>(source_ids.size()) != source_count ||
		    std::find(source_ids.begin(), source_ids.end(), source_root_id) ==
			    source_ids.end() ||
		    sql_saved_item_source_id_digest(source_ids) != source_digest ||
		    !sql_saved_item_source_rows_match(source_key, source_ids, true))
			goto done;
	}
	sql_saved_item_restore_fault("before_retirement");
	{
		char query[512];
		char *escaped = sql_escape_string(source_key);
		if (!escaped)
			goto done;
		snprintf(query, sizeof(query),
			 "DELETE FROM saved_items WHERE id=%d AND item_key='%s'", source_root_id,
			 escaped);
		free(escaped);
		if (!sql_run_query(query) || mysql_affected_rows(DB) != 1)
			goto done;
		sql_saved_item_restore_fault("after_retirement");
		snprintf(query, sizeof(query),
			 "UPDATE saved_item_recovery_handoff SET retired_at=CURRENT_TIMESTAMP(6) "
			 "WHERE season_epoch=%llu AND source_root_id=%d AND retired_at IS NULL",
			 static_cast<unsigned long long>(epoch), source_root_id);
		if (!sql_run_query(query) || mysql_affected_rows(DB) != 1)
			goto done;
	}
	ok = true;
done:
	if (!ok || !sql_commit())
	{
		sql_rollback();
		return false;
	}
	sql_saved_item_restore_fault("after_retirement_commit");
	return true;
}

static bool sql_acknowledge_saved_item_handoff(uint64_t epoch, const char *source_key,
					       const std::vector<int> &source_ids, P_obj item,
					       int room_vnum, const char *destination_key)
{
	if (!epoch || !source_key || source_ids.empty() || !item || !destination_key ||
	    sql_in_transaction() || !sql_begin_transaction())
		return false;
	bool ok = false;
	int destination_root_id = 0;
	char *escaped_source = NULL;
	char *escaped_destination = NULL;
	if (!sql_saved_item_source_rows_match(source_key, source_ids, true))
		goto done;
	escaped_destination = sql_escape_string(destination_key);
	if (!escaped_destination)
		goto done;
	{
		char query[512];
		snprintf(query, sizeof(query),
			 "SELECT id FROM saved_items WHERE item_key='%s' FOR UPDATE",
			 escaped_destination);
		MYSQL_RES *existing = db_query("%s", query);
		if (!existing)
			goto done;
		const bool occupied = mysql_num_rows(existing) > 0;
		mysql_free_result(existing);
		if (occupied)
			goto done;
	}
	sql_saved_item_restore_fault("before_acknowledgment");
	destination_root_id = sql_save_saved_item_recursive(destination_key, room_vnum, item, 0);
	if (destination_root_id <= 0)
		goto done;
	escaped_source = sql_escape_string(source_key);
	if (!escaped_source)
		goto done;
	{
		char query[1024];
		snprintf(query, sizeof(query),
			 "INSERT INTO saved_item_recovery_handoff "
			 "(season_epoch,source_root_id,source_key,source_uid,source_room_vnum,"
			 "source_row_count,source_id_digest,destination_root_id,destination_key) "
			 "VALUES (%llu,%d,'%s',%llu,%d,%u,UNHEX('%s'),%d,'%s')",
			 static_cast<unsigned long long>(epoch), source_ids[0], escaped_source,
			 static_cast<unsigned long long>(item->obj_uid), room_vnum,
			 static_cast<unsigned int>(source_ids.size()),
			 sql_saved_item_source_id_digest(source_ids).c_str(), destination_root_id,
			 escaped_destination);
		if (!sql_run_query(query))
			goto done;
	}
	ok = true;
done:
	if (escaped_source)
		free(escaped_source);
	if (escaped_destination)
		free(escaped_destination);
	if (!ok || !sql_commit())
	{
		sql_rollback();
		return false;
	}
	sql_saved_item_restore_fault("after_acknowledgment");
	return true;
}

void sql_restore_saved_items(void)
{
	if (!DB)
		return;

	const uint64_t season_epoch = sql_saved_item_season_epoch();
	if (!season_epoch)
	{
		logit(LOG_SYS,
		      "sql_restore_saved_items: season epoch unavailable; source rows retained");
		return;
	}
	std::unordered_set<uint64_t> published_uids;

	MYSQL_RES *result =
		db_query("SELECT item_key, room_vnum, id, vnum, weight, cost, timer, extra_flags, "
			 "value0, value1, value2, value3, value4, value5, value6, value7, "
			 "name, short_descr, description, action_descr, "
			 "wear_flags, item_type, item_material, "
			 "bitvector1, bitvector2, bitvector3, bitvector4, bitvector5, "
			 "obj_uid "
			 "FROM saved_items WHERE container_id IS NULL ORDER BY id DESC");
	if (!result)
	{
		logit(LOG_SYS,
		      "sql_restore_saved_items: root restore query failed; saved ground items were not loaded");
		return;
	}

	int loaded = 0;
	MYSQL_ROW row;

	while ((row = mysql_fetch_row(result)))
	{
		const char *item_key = row[0];
		int room_vnum = atoi(row[1]);
		int item_id = atoi(row[2]);
		int vnum = atoi(row[3]);
		const uint64_t saved_uid = row[28] ? strtoull(row[28], NULL, 10) : 0;
		int destination_root_id = 0;
		int source_count = 0;
		bool retired = false;
		if (sql_saved_item_handoff_receipt(season_epoch, item_id, &destination_root_id,
						   &source_count, &retired))
		{
			char query[128];
			snprintf(query, sizeof(query), "SELECT id FROM saved_items WHERE id=%d",
				 destination_root_id);
			MYSQL_RES *destination = db_query("%s", query);
			const bool acknowledged_payload = destination &&
							  mysql_num_rows(destination) == 1;
			if (destination)
				mysql_free_result(destination);
			if (acknowledged_payload)
			{
				if (!retired &&
				    !sql_retire_saved_item_source(season_epoch, item_id, item_key,
								  source_count))
					logit(LOG_SYS,
					      "sql_restore_saved_items: acknowledged source retirement deferred");
				continue;
			}
		}
		if (saved_uid && published_uids.find(saved_uid) != published_uids.end())
		{
			logit(LOG_SYS,
			      "sql_restore_saved_items: duplicate source UID deferred for reconciliation");
			continue;
		}

		int room = real_room(room_vnum);
		if (room == NOWHERE)
		{
			logit(LOG_DEBUG, "sql_restore_saved_items: location=room outcome=invalid");
			continue;
		}

		int rnum = real_object(vnum);
		if (rnum < 0)
			continue;

		sql_saved_item_restore_fault("before_materialization");
		P_obj obj = read_object(rnum, REAL);
		if (!obj)
			continue;
		bool valid = true;
		std::vector<int> source_ids = { item_id };

		if (row[4])
			obj->weight = atoi(row[4]);
		if (row[5])
			obj->cost = atoi(row[5]);
		if (row[6])
			obj->timer[0] = atol(row[6]);
		if (row[7])
			obj->extra_flags = strtoul(row[7], NULL, 10);

		obj->value[0] = row[8] ? atoi(row[8]) : 0;
		obj->value[1] = row[9] ? atoi(row[9]) : 0;
		obj->value[2] = row[10] ? atoi(row[10]) : 0;
		obj->value[3] = row[11] ? atoi(row[11]) : 0;
		obj->value[4] = row[12] ? atoi(row[12]) : 0;
		obj->value[5] = row[13] ? atoi(row[13]) : 0;
		obj->value[6] = row[14] ? atoi(row[14]) : 0;
		obj->value[7] = row[15] ? atoi(row[15]) : 0;

		if (row[16] && strlen(row[16]) > 0)
		{
			obj->name = str_dup(row[16]);
			obj->str_mask |= STRUNG_KEYS;
		}
		if (row[17] && strlen(row[17]) > 0)
		{
			obj->short_description = str_dup(row[17]);
			obj->str_mask |= STRUNG_DESC2;
		}
		if (row[18] && strlen(row[18]) > 0)
		{
			obj->description = str_dup(row[18]);
			obj->str_mask |= STRUNG_DESC1;
		}
		if (row[19] && strlen(row[19]) > 0)
		{
			obj->action_description = str_dup(row[19]);
			obj->str_mask |= STRUNG_DESC3;
		}
		// v19 diff columns - NULL means use prototype value from read_object()
		if (row[20])
			obj->wear_flags = atoi(row[20]);
		if (row[21])
			obj->type = sql_validate_loaded_item_type(obj, atoi(row[21]),
								  "sql_restore_saved_items");
		if (row[22])
			obj->material = atoi(row[22]);
		if (row[23])
			obj->bitvector = strtoul(row[23], NULL, 10);
		if (row[24])
			obj->bitvector2 = strtoul(row[24], NULL, 10);
		if (row[25])
			obj->bitvector3 = strtoul(row[25], NULL, 10);
		if (row[26])
			obj->bitvector4 = strtoul(row[26], NULL, 10);
		if (row[27])
			obj->bitvector5 = strtoul(row[27], NULL, 10);
		if (saved_uid)
			obj->obj_uid = saved_uid;
		char owner_ref[32];
		snprintf(owner_ref, sizeof(owner_ref), "%d", room_vnum);
		if (!sql_persistence_item_owner_matches(obj->obj_uid, "room", owner_ref,
							"sql_restore_saved_items"))
		{
			extract_obj(obj, FALSE);
			continue;
		}
		obj->db_item_id = item_id;
		if (!sql_load_item_extra_descr_from_table(item_id, obj, "saved_item"))
			valid = false;

		char aff_query[128];
		snprintf(aff_query, sizeof(aff_query),
			 "SELECT location, modifier FROM saved_item_affects WHERE item_id=%d",
			 item_id);
		MYSQL_RES *aff_result = db_query("%s", aff_query);
		if (aff_result)
		{
			MYSQL_ROW aff_row;
			int aff_idx = 0;
			while ((aff_row = mysql_fetch_row(aff_result)) && aff_idx < MAX_OBJ_AFFECT)
			{
				obj->affected[aff_idx].location = atoi(aff_row[0]);
				obj->affected[aff_idx].modifier = atoi(aff_row[1]);
				aff_idx++;
			}
			mysql_free_result(aff_result);
		}
		else
			valid = false;

		obj->contains = sql_load_saved_item_contents(item_key, room_vnum, item_id, 0,
							     &source_ids, &valid);
		for (P_obj c = obj->contains; c; c = c->next_content)
		{
			if (!obj_can_nest(c, obj))
			{
				valid = false;
				logit(LOG_DEBUG,
				      "sql_load_saved_item_contents: skipping malformed container link %d -> %d",
				      c->db_item_id, obj->db_item_id);
				continue;
			}
			c->loc_p = LOC_INSIDE;
			c->loc.inside = obj;
		}
		if (!valid || !sql_saved_item_source_rows_match(item_key, source_ids, false))
		{
			logit(LOG_SYS,
			      "sql_restore_saved_items: incomplete source graph retained without publication");
			extract_obj(obj, FALSE);
			continue;
		}
		std::unordered_set<uint64_t> tree_uids;
		if (!sql_saved_item_collect_uids(obj, &tree_uids) ||
		    std::any_of(tree_uids.begin(), tree_uids.end(), [&published_uids](uint64_t uid)
				{ return published_uids.find(uid) != published_uids.end(); }))
		{
			extract_obj(obj, FALSE);
			continue;
		}
		char destination_key[128];
		if (!sql_saved_item_uid_key(obj->obj_uid, destination_key, sizeof destination_key))
		{
			extract_obj(obj, FALSE);
			continue;
		}
		sql_saved_item_restore_fault("after_materialization");

		obj_to_room(obj, room);
		if (!OBJ_ROOM(obj) || obj->loc.room != room)
		{
			extract_obj(obj, FALSE);
			continue;
		}
		published_uids.insert(tree_uids.begin(), tree_uids.end());
		sql_saved_item_restore_fault("after_publication");

		if (strcmp(item_key, destination_key) != 0)
		{
			if (!sql_acknowledge_saved_item_handoff(season_epoch, item_key, source_ids,
								obj, room_vnum, destination_key))
				logit(LOG_SYS,
				      "sql_restore_saved_items: handoff deferred; original source retained");
			else if (!sql_retire_saved_item_source(season_epoch, item_id, item_key,
							       static_cast<int>(source_ids.size())))
				logit(LOG_SYS,
				      "sql_restore_saved_items: acknowledged source retirement deferred");
		}
		loaded++;
	}

	mysql_free_result(result);

	logit(LOG_DEBUG, "sql_restore_saved_items: loaded %d items", loaded);
}

/* The next ships row id: the boot load reads the highest stored one, and -1 means it
 * could not, so no new ship is saved over a stored one. */
static int ship_next_db_id = -1;

/* A ship's statements: its row (inserted or updated by its id), then its armor, crew
 * and slots. A new ship takes its id from memory here. Empty when no id can be given. */
static std::vector<std::string> sql_save_ship_statements(P_ship ship)
{
	if (ship->db_id == -1)
	{
		if (ship_next_db_id < 0)
			return {};
		ship->db_id = ++ship_next_db_id;
	}
	const std::string owner = escape_str(ship->ownername);
	const std::string name = escape_str(ship->name ? ship->name : "");
	std::vector<std::string> statements;
	statements.push_back(sql_format(
		"insert into ships (id, owner_name, ship_name, ship_class, frags, anchor_room, time_played, mainsail, race, money, flags) "
		"values (%d, '%s', '%s', %d, %d, %d, %d, %d, %d, %d, %lu) "
		"on duplicate key update owner_name=values(owner_name), ship_name=values(ship_name), "
		"ship_class=values(ship_class), frags=values(frags), anchor_room=values(anchor_room), "
		"time_played=values(time_played), mainsail=values(mainsail), race=values(race), "
		"money=values(money), flags=values(flags)",
		ship->db_id, owner.c_str(), name.c_str(), ship->m_class, ship->frags, ship->anchor,
		ship->time, ship->mainsail, ship->race, ship->money, ship->flags));
	for (int i = 0; i < 4; i++)
		statements.push_back(
			sql_format("insert into ship_armor (ship_id, side, armor, internal) "
				   "values (%d, %d, %d, %d) "
				   "on duplicate key update armor=%d, internal=%d",
				   ship->db_id, i, ship->armor[i], ship->internal[i],
				   ship->armor[i], ship->internal[i]));
	statements.push_back(sql_format(
		"insert into ship_crew (ship_id, crew_index, sail_skill, guns_skill, rpar_skill, "
		"sail_chief, guns_chief, rpar_chief) "
		"values (%d, %d, %d, %d, %d, %d, %d, %d) "
		"on duplicate key update crew_index=%d, sail_skill=%d, guns_skill=%d, rpar_skill=%d, "
		"sail_chief=%d, guns_chief=%d, rpar_chief=%d",
		ship->db_id, ship->crew.index, (int)(ship->crew.sail_skill * 1000),
		(int)(ship->crew.guns_skill * 1000), (int)(ship->crew.rpar_skill * 1000),
		ship->crew.sail_chief, ship->crew.guns_chief, ship->crew.rpar_chief,
		ship->crew.index, (int)(ship->crew.sail_skill * 1000),
		(int)(ship->crew.guns_skill * 1000), (int)(ship->crew.rpar_skill * 1000),
		ship->crew.sail_chief, ship->crew.guns_chief, ship->crew.rpar_chief));
	for (int i = 0; i < MAXSLOTS; i++)
		statements.push_back(sql_format(
			"insert into ship_slots (ship_id, slot_index, slot_type, item_index, position, "
			"timer, val0, val1, val2, val3, val4) "
			"values (%d, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d) "
			"on duplicate key update slot_type=%d, item_index=%d, position=%d, "
			"timer=%d, val0=%d, val1=%d, val2=%d, val3=%d, val4=%d",
			ship->db_id, i, ship->slot[i].type, ship->slot[i].index,
			ship->slot[i].position, ship->slot[i].timer, ship->slot[i].val0,
			ship->slot[i].val1, ship->slot[i].val2, ship->slot[i].val3,
			ship->slot[i].val4, ship->slot[i].type, ship->slot[i].index,
			ship->slot[i].position, ship->slot[i].timer, ship->slot[i].val0,
			ship->slot[i].val1, ship->slot[i].val2, ship->slot[i].val3,
			ship->slot[i].val4));
	return statements;
}

/* Save one ship: its statements are one writer job. */
bool sql_save_ship(P_ship ship)
{
	if (!ship || !ship->ownername)
		return false;
	const std::vector<std::string> statements = sql_save_ship_statements(ship);
	return !statements.empty() && sql_queue_statements(statements);
}

/* The stored rows of one ship: its ships row, then its armor, crew and slot rows. */
struct ship_rows
{
	sql_rows ship, armor, crew, slots;
};

/* Stored ships that are not in the world: the room pool could not hold them at boot, or
 * their rows could not be read. place_stored_ship() tries them again from here. */
static std::vector<std::pair<std::string, ship_rows>> stored_ships;

static std::vector<std::pair<std::string, ship_rows>>::iterator stored_ship(const char *owner_name)
{
	return std::find_if(stored_ships.begin(), stored_ships.end(),
			    [owner_name](const auto &stored)
			    { return !strcasecmp(stored.first.c_str(), owner_name); });
}

/* Boot only: read one ship's rows. */
static bool sql_read_ship_rows(const char *owner_name, ship_rows *rows)
{
	if (sql_select(
		    DB,
		    "select id, ship_name, ship_class, frags, anchor_room, time_played, mainsail, "
		    "race, money, flags from ships where owner_name='" +
			    escape_str(owner_name) + "'",
		    &rows->ship) ||
	    rows->ship.empty() || !rows->ship[0][0])
		return false;
	const std::string where = std::string(" where ship_id=") + rows->ship[0][0];
	return !sql_select(DB, "select side, armor, internal from ship_armor" + where,
			   &rows->armor) &&
	       !sql_select(DB,
			   "select crew_index, sail_skill, guns_skill, rpar_skill, sail_chief, "
			   "guns_chief, rpar_chief from ship_crew" +
				   where,
			   &rows->crew) &&
	       !sql_select(DB,
			   "select slot_index, slot_type, item_index, position, timer, val0, val1, "
			   "val2, val3, val4 from ship_slots" +
				   where,
			   &rows->slots);
}

static P_ship sql_ship_from_rows(const char *owner_name, const ship_rows &rows)
{
	if (rows.ship.empty())
		return NULL;
	const sql_row &row = rows.ship[0];
	P_ship ship = new_ship(atoi(row[2]));
	if (!ship)
		return NULL;

	ship->db_id = atoi(row[0]);
	ship->ownername = str_dup(owner_name);
	ship->name = str_dup(row[1] ? row[1] : "");
	ship->frags = atoi(row[3]);
	ship->anchor = atoi(row[4]);
	ship->time = atoi(row[5]);
	ship->mainsail = atoi(row[6]);
	ship->race = atoi(row[7]);
	ship->money = atoi(row[8]);
	ship->flags = row[9] ? strtoul(row[9], NULL, 10) : 0;

	for (const sql_row &armor : rows.armor)
	{
		int side = atoi(armor[0]);
		if (side >= 0 && side < 4)
		{
			ship->armor[side] = atoi(armor[1]);
			ship->internal[side] = atoi(armor[2]);
		}
	}
	if (!rows.crew.empty())
	{
		const sql_row &crew = rows.crew[0];
		ship->crew.index = atoi(crew[0]);
		ship->crew.sail_skill = (float)atoi(crew[1]) / 1000.0f;
		ship->crew.guns_skill = (float)atoi(crew[2]) / 1000.0f;
		ship->crew.rpar_skill = (float)atoi(crew[3]) / 1000.0f;
		ship->crew.sail_chief = atoi(crew[4]);
		ship->crew.guns_chief = atoi(crew[5]);
		ship->crew.rpar_chief = atoi(crew[6]);
	}
	for (const sql_row &slot : rows.slots)
	{
		int idx = atoi(slot[0]);
		if (idx >= 0 && idx < MAXSLOTS)
		{
			ship->slot[idx].type = atoi(slot[1]);
			ship->slot[idx].index = atoi(slot[2]);
			ship->slot[idx].position = atoi(slot[3]);
			ship->slot[idx].timer = atoi(slot[4]);
			ship->slot[idx].val0 = atoi(slot[5]);
			ship->slot[idx].val1 = atoi(slot[6]);
			ship->slot[idx].val2 = atoi(slot[7]);
			ship->slot[idx].val3 = atoi(slot[8]);
			ship->slot[idx].val4 = atoi(slot[9]);
		}
	}
	ship->save_pending = false;
	ship->save_retry_after = 0;
	ship->save_saved_signature = ship_save_signature(ship);

	return ship;
}

/*
 * Put `owner_name`'s stored ship in the world at its anchor, from the rows the boot
 * read.  Returns the ship, or NULL with any part-built ship destroyed and its rows kept.
 * `unplaced` says whether it was built but could not be placed, usually because the
 * ship-room pool is full.
 */
P_ship sql_place_ship(const char *owner_name, bool *unplaced)
{
	*unplaced = false;
	const auto stored = stored_ship(owner_name);
	P_ship ship = stored == stored_ships.end() ? NULL :
						     sql_ship_from_rows(owner_name, stored->second);
	if (!ship)
	{
		logit(LOG_FILE, "sql_place_ship: component=rows outcome=failure");
		return NULL;
	}

	name_ship(ship->name, ship);
	if (!load_ship(ship, real_room0(ship->anchor)))
	{
		/* An unplaced ship must not stay registered; its rows are kept. */
		logit(LOG_FILE, "sql_place_ship: component=ship outcome=failure");
		shipObjHash.erase(ship);
		delete_ship(ship, true);
		*unplaced = true;
		return NULL;
	}

	ship->mainsail = BOUNDED(0, ship->mainsail, SHIP_MAX_SAIL(ship));
	update_crew(ship);
	reset_crew_stamina(ship);
	set_ship_armor(ship, false);
	update_ship_status(ship);
	stored_ships.erase(stored);
	return ship;
}

/* Whether `owner_name` has a stored ship that is not in the world. */
bool sql_ship_stored(const char *owner_name)
{
	return stored_ship(owner_name) != stored_ships.end();
}

/* Boot: read every ship, place the ones the room pool can hold, and keep the rows of
 * the rest for place_stored_ship(). */
bool sql_load_all_ships()
{
	if (!DB)
		return false;

	MYSQL_RES *result = db_query("select owner_name, id from ships");
	if (!result)
		return false;

	ship_next_db_id = 0;
	std::vector<std::string> owner_names;
	MYSQL_ROW row;
	while ((row = mysql_fetch_row(result)))
	{
		ship_next_db_id = std::max(ship_next_db_id, atoi(row[1]));
		if (row[0])
			owner_names.emplace_back(row[0]);
	}
	mysql_free_result(result);

	for (const std::string &owner_name : owner_names)
	{
		ship_rows rows;
		if (!sql_read_ship_rows(owner_name.c_str(), &rows))
			rows = {};
		stored_ships.emplace_back(owner_name, std::move(rows));
		bool unplaced = false;
		if (!sql_place_ship(owner_name.c_str(), &unplaced) && unplaced)
			note_unplaced_ship(owner_name.c_str());
	}

	return true;
}

/* The statement that deletes `owner_name`'s ship; its armor, crew and slots go with it. */
std::string sql_delete_ship_statement(const char *owner_name)
{
	return "delete from ships where owner_name='" + escape_str(owner_name) + "'";
}

/* Delete a ship's rows on the writer, and forget its stored rows and snapshot. */
bool sql_delete_ship(const char *owner_name)
{
	if (!owner_name || !sql_queue("%s", sql_delete_ship_statement(owner_name).c_str()))
		return false;

	const auto stored = stored_ship(owner_name);
	if (stored != stored_ships.end())
		stored_ships.erase(stored);
	redis_invalidate_ship_snapshot(owner_name);
	return true;
}

/* One guild's statements: its row, then its ranks and members, which are replaced
 * wholesale (the DELETEs before the INSERTs), so they must run in one transaction. */
std::vector<std::string> sql_save_guild_statements(Guild *guild)
{
	const unsigned int gid = guild->get_id();
	const std::string name = escape_str(guild->name);
	const std::string fragger = escape_str(guild->frags.topfragger);
	std::vector<std::string> statements;
	statements.push_back(sql_format(
		"insert into guilds (id, name, racewar, bits, prestige, construction, "
		"platinum, gold, silver, copper, frags, top_frags, topfragger) "
		"values (%u, '%s', %u, %u, %lu, %lu, %u, %u, %u, %u, %ld, %ld, '%s') "
		"on duplicate key update name='%s', racewar=%u, bits=%u, prestige=prestige, "
		"construction=construction, platinum=%u, gold=%u, silver=%u, copper=%u, "
		"frags=%ld, top_frags=%ld, topfragger='%s'",
		gid, name.c_str(), guild->racewar, guild->bits, guild->prestige,
		guild->construction, guild->platinum, guild->gold, guild->silver, guild->copper,
		guild->frags.frags, guild->frags.top_frags, fragger.c_str(), name.c_str(),
		guild->racewar, guild->bits, guild->platinum, guild->gold, guild->silver,
		guild->copper, guild->frags.frags, guild->frags.top_frags, fragger.c_str()));

	statements.push_back(sql_format("delete from guild_ranks where guild_id=%u", gid));
	for (int i = 0; i < ASC_NUM_RANKS; i++)
		statements.push_back(sql_format(
			"insert into guild_ranks (guild_id, rank_index, title) values (%u, %d, '%s')",
			gid, i, escape_str(guild->titles[i]).c_str()));

	statements.push_back(sql_format("delete from guild_members where guild_id=%u", gid));
	for (P_member mem = guild->members; mem; mem = mem->next)
	{
		const int pid = sql_get_player_pid(mem->name);
		statements.push_back(sql_format(
			"insert into guild_members (guild_id, player_name, player_pid, bits, debt) "
			"values (%u, '%s', %s, %u, %u)",
			gid, escape_str(mem->name).c_str(),
			pid > 0 ? std::to_string(pid).c_str() : "NULL", mem->bits, mem->debt));
	}
	return statements;
}

/* Save one guild: its statements are one writer job. */
bool sql_save_guild(Guild *guild)
{
	return guild && sql_queue_statements(sql_save_guild_statements(guild));
}

Guild *sql_load_guild(unsigned int guild_id)
{
	if (!DB || guild_id == 0)
		return NULL;

	char query[256];
	snprintf(query, sizeof(query),
		 "select id, name, racewar, bits, prestige, construction, "
		 "platinum, gold, silver, copper, frags, top_frags, topfragger "
		 "from guilds where id=%u",
		 guild_id);

	MYSQL_RES *result = db_query("%s", query);
	if (!result)
		return NULL;

	MYSQL_ROW row = mysql_fetch_row(result);
	if (!row)
	{
		mysql_free_result(result);
		return NULL;
	}

	Guild *guild = new Guild();
	guild->id_number = atoi(row[0]);
	strlcpy(guild->name, row[1] ? row[1] : "", sizeof guild->name);
	guild->racewar = row[2] ? atoi(row[2]) : 0;
	guild->bits = row[3] ? atoi(row[3]) : 0;
	guild->prestige = row[4] ? strtoul(row[4], NULL, 10) : 0;
	guild->construction = row[5] ? strtoul(row[5], NULL, 10) : 0;
	guild->platinum = row[6] ? atoi(row[6]) : 0;
	guild->gold = row[7] ? atoi(row[7]) : 0;
	guild->silver = row[8] ? atoi(row[8]) : 0;
	guild->copper = row[9] ? atoi(row[9]) : 0;
	guild->frags.frags = row[10] ? atol(row[10]) : 0;
	guild->frags.top_frags = row[11] ? atol(row[11]) : 0;
	strlcpy(guild->frags.topfragger, row[12] ? row[12] : "", sizeof guild->frags.topfragger);
	mysql_free_result(result);

	// load ranks
	snprintf(query, sizeof(query),
		 "select rank_index, title from guild_ranks where guild_id=%u order by rank_index",
		 guild_id);
	result = db_query("%s", query);
	if (!result)
	{
		logit(LOG_DEBUG, "sql_load_guild: failed to load ranks for guild %u", guild_id);
		delete guild;
		return NULL;
	}
	while ((row = mysql_fetch_row(result)))
	{
		int idx = atoi(row[0]);
		if (idx >= 0 && idx < ASC_NUM_RANKS)
			strlcpy(guild->titles[idx], row[1] ? row[1] : "", ASC_MAX_STR_RANK);
	}
	mysql_free_result(result);

	// load members
	snprintf(query, sizeof(query),
		 "select player_name, bits, debt from guild_members where guild_id=%u", guild_id);
	result = db_query("%s", query);
	if (!result)
	{
		logit(LOG_DEBUG, "sql_load_guild: failed to load members for guild %u", guild_id);
		delete guild;
		return NULL;
	}
	P_member tail = NULL;
	while ((row = mysql_fetch_row(result)))
	{
		P_member mem = new guild_member();
		strlcpy(mem->name, row[0] ? row[0] : "", sizeof mem->name);
		mem->bits = row[1] ? atoi(row[1]) : 0;
		mem->debt = row[2] ? atoi(row[2]) : 0;
		mem->online_status = GSTAT_OFFLINE;
		mem->next = NULL;

		if (!guild->members)
			guild->members = mem;
		else
			tail->next = mem;
		tail = mem;
		guild->member_count++;
	}
	mysql_free_result(result);

	return guild;
}

bool sql_load_all_guilds()
{
	if (!DB)
		return false;

	MYSQL_RES *result = db_query("select id from guilds");
	if (!result)
		return false;

	// collect all guild IDs first (can't run queries while fetching unbuffered results)
	unsigned int guild_ids[256];
	int num_guilds = 0;
	MYSQL_ROW row;
	while ((row = mysql_fetch_row(result)) && num_guilds < 256)
	{
		guild_ids[num_guilds++] = atoi(row[0]);
	}
	mysql_free_result(result);

	// now load each guild
	for (int i = 0; i < num_guilds; i++)
	{
		Guild *guild = sql_load_guild(guild_ids[i]);
		if (!guild)
		{
			logit(LOG_FILE, "sql_load_all_guilds: failed to load guild rows for %u",
			      guild_ids[i]);
			continue;
		}
		guild->next_guild = guild_list;
		guild_list = guild;
	}

	return true;
}

// ============================================================================
// spellbook (conjurable mobs) functions
// ============================================================================

// Every character's spellbook, read at boot and kept current by the game's own writes,
// which are queued on the writer: only the game writes the spellbooks.
static std::unordered_map<int, std::set<int>> spellbooks;

bool sql_spellbooks_load(void)
{
	MYSQL_RES *result = db_query("select pid, mob_vnum from player_spellbooks");
	if (!result)
		return false;
	spellbooks.clear();
	while (MYSQL_ROW row = mysql_fetch_row(result))
		if (row[0] && row[1])
			spellbooks[atoi(row[0])].insert(atoi(row[1]));
	mysql_free_result(result);
	return true;
}

bool sql_add_spellbook_mob(int pid, int mob_vnum)
{
	if (!DB || pid <= 0 ||
	    !sql_queue("insert ignore into player_spellbooks (pid, mob_vnum) values (%d, %d)", pid,
		       mob_vnum))
		return false;
	spellbooks[pid].insert(mob_vnum);
	return true;
}

bool sql_remove_spellbook_mob(int pid, int mob_vnum)
{
	if (!DB || pid <= 0 || mob_vnum <= 0 ||
	    !sql_queue("delete from player_spellbooks where pid=%d and mob_vnum=%d", pid, mob_vnum))
		return false;
	spellbooks[pid].erase(mob_vnum);
	return true;
}

bool sql_has_spellbook_mob(int pid, int mob_vnum)
{
	const auto book = spellbooks.find(pid);
	return book != spellbooks.end() && book->second.count(mob_vnum);
}

// returns array of mob vnums, sets count. caller must free array.
int *sql_get_spellbook_mobs(int pid, int *count)
{
	*count = 0;
	const auto book = spellbooks.find(pid);
	if (book == spellbooks.end() || book->second.empty())
		return NULL;

	int *mobs = (int *)malloc(sizeof(int) * book->second.size());
	if (!mobs)
		return NULL;
	for (int mob_vnum : book->second)
		mobs[(*count)++] = mob_vnum;
	return mobs;
}

// account bank

#endif // __NO_MYSQL__
