/*
 *  kingdom_db.c
 *  Duris
 *
 *  Persistence for the kingdom realms: the four entry points declared at the
 *  foot of kingdom_internal.h, implemented against MariaDB.
 *
 *  WHAT IS PERSISTED
 *  -----------------
 *  One record per realm, eleven integers wide. THE TERRITORY IS A SINGLE
 *  INTEGER: because the claim order is fixed and a ring completes before the
 *  next opens, a realm owns claims 1..highest_claim and nothing else. So
 *  claiming a square, reverting an outer ring for arrears, and losing the
 *  whole realm are all one small integer write -- there is no per-square
 *  table and no 80-row rewrite anywhere in this file.
 *
 *  The anchor is stored as hall_vnum ONLY. hall_rnum, zone_idx and
 *  hall_x/hall_y are derived state; kingdom_db_load_all() deliberately leaves
 *  them at their "unresolved" defaults (hall_rnum 0, matching real_room0()'s
 *  sentinel) because resolving them needs a loaded world, and this module must
 *  be safe to load from before the world is up. kingdom_initialize() resolves
 *  the anchors and builds the square index after loading, exactly as its
 *  contract in kingdom.h says.
 */

#include "kingdom/kingdom_internal.h"

#include "core/structs.h"

#include "core/utility.h"

#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <new>
#include <string>
#include <vector>

#include "sql/sql.h"
#include "sql/sql_player.h"
#include "sql/sql_async.h"

#include <mysqld_error.h>

/* ------------------------------------------------------------------ *
 * Record limits and validation
 * ------------------------------------------------------------------ */

namespace
{
/* Adding a resource type without adding its column here would silently drop
 * the new counter on every save and zero it on every load. Break the build
 * instead: the queries below enumerate exactly these four. */
static_assert(KRES_MAX == 4, "kingdom_db persists exactly four resource counters");

/* One realm per association at most: a row count read out of a table must
 * never authorise an unbounded allocation. */
constexpr size_t kingdom_realm_maximum = 65536;

/* REJECT a bad record rather than repair it. highest_claim indexes
 * KINGDOM_CLAIM_ORDER in every other file of this module, so a value past
 * KINGDOM_MAX_SQUARES read back from a corrupt store would walk off the end
 * of that table; arrears indexes the ladder.
 *
 * The loader logs a bad row and skips it, per RECORD and never per store.
 * Nothing on the load path deletes or rewrites a row it refused, so the
 * corrupt row is still in kingdom_realms after the boot that rejected it:
 * readable for forensics and repairable by hand, after which the next boot
 * loads it. (Not immortal -- a later upsert for that same assoc_id, or
 * kingdom_on_guild_deleted()'s DELETE, still replaces or removes it. The point
 * is only that the REJECTION itself destroys nothing.)
 *
 * Both save paths (single-record and flush) refuse to write a record that
 * fails this, leaving it dirty in memory. Losing one guild's territory is the
 * outcome in every case, rather than the process. */
bool record_is_sane(const kingdom_realm &realm)
{
	if (realm.assoc_id <= 0 || realm.realm_id < 0)
		return false;
	if (realm.hall_vnum < 0)
		return false;
	if (realm.highest_claim < 0 || realm.highest_claim > KINGDOM_MAX_SQUARES)
		return false;
	if (realm.arrears < KARR_CURRENT || realm.arrears > KARR_LAND_REVERTING)
		return false;
	if (realm.missed_cycles < 0)
		return false;
	if (realm.upkeep_paid_through < 0)
		return false;
	for (int res = 0; res < KRES_MAX; res++)
		if (realm.resources[res] < 0)
			return false;
	return true;
}
} /* namespace */

/* ------------------------------------------------------------------ *
 * MariaDB backend
 * ------------------------------------------------------------------ *
 * Table kingdom_realms, assoc_id PRIMARY KEY. The schema is owned by
 * migrations/, not by this file: nothing in src/ issues CREATE TABLE.
 *
 * NOTHING HERE IS ESCAPED, ON PURPOSE. Every column is an integer and every
 * value is formatted with %d / %ld / %lld from a field of the realm struct,
 * so no player-supplied text can reach a statement and there is nothing for
 * escape_str() (src/sql/sql.c:1107) to do. The realm carries no name -- the
 * guild's name lives in the association record.
 */

/* ER_NO_SUCH_TABLE_IN_ENGINE is MySQL 5.7+; MariaDB's client headers do not
 * define it at all, so referring to it unguarded fails to COMPILE against the
 * default backend rather than failing at runtime. Defined here when absent
 * instead of dropping the test, because the roster's missing-table degradation
 * genuinely wants both codes: 1146 is "no such table" and 1932 is "the table is
 * in the dictionary but its engine has lost it", and a server in the second
 * state should degrade exactly as one in the first. The number is a wire error
 * code and is stable. */
#ifndef ER_NO_SUCH_TABLE_IN_ENGINE
#define ER_NO_SUCH_TABLE_IN_ENGINE 1932
#endif

/* Defined below kingdom_db_load_all(), which calls it: the roster loader reads
 * realms that pass has already filed, so it belongs after them in the file and
 * needs a forward declaration to be reached from before. */
static void kingdom_db_load_rosters(void);

namespace
{
/* ONE list, used by both the SELECT and the INSERT, so the two can never
 * drift apart and the row[] indices below always mean what they say. */
const char *const kingdom_realm_columns = "assoc_id,realm_id,hall_vnum,highest_claim,"
					  "res_mineral,res_wood,res_fibre,res_water,"
					  "upkeep_paid_through,arrears,missed_cycles";
constexpr unsigned int kingdom_realm_column_count = 11;
} /* namespace */

/* Replace kingdom_realms with every row of the kingdom_realms table, anchors
 * unresolved and flags clear. Rows with a NULL column, a record that fails
 * record_is_sane() or a duplicate assoc_id are skipped, each with its own log
 * line naming the row, and then counted in the closing "rejected" total. A
 * skipped row is left in the table -- see the record_is_sane() banner.
 * False when the SELECT fails, the
 * column count is wrong, memory runs out, or the cap truncates the load --
 * never for an empty table. */
bool kingdom_db_load_all(void)
{
	kingdom_realms.clear();

	MYSQL_RES *result =
		db_query("SELECT %s FROM kingdom_realms ORDER BY assoc_id", kingdom_realm_columns);
	if (!result)
	{
		/* db_query_at() returns the stored result set for any statement
		 * that ran, so a SELECT matching nothing still yields a non-NULL
		 * empty set (src/sql/sql.c db_query_at -> mysql_store_result).
		 * NULL therefore means the statement FAILED, never "no kingdoms",
		 * and reporting success here would tell the caller that every
		 * realm had ceased to exist. */
		logit(LOG_KINGDOM, "kingdom_db_load_all: SELECT from kingdom_realms failed; "
				   "no realms loaded");
		return false;
	}

	if (mysql_num_fields(result) != kingdom_realm_column_count)
	{
		/* Schema drift. Without this the row[] reads below would run past
		 * the end of a short row. */
		logit(LOG_KINGDOM,
		      "kingdom_db_load_all: kingdom_realms returned %u columns, expected %u; "
		      "run the kingdom migration",
		      mysql_num_fields(result), kingdom_realm_column_count);
		mysql_free_result(result);
		return false;
	}

	size_t loaded = 0;
	size_t rejected = 0;
	bool complete = true;

	try
	{
		MYSQL_ROW row;
		while ((row = mysql_fetch_row(result)) != NULL)
		{
			if (kingdom_realms.size() >= kingdom_realm_maximum)
			{
				logit(LOG_KINGDOM,
				      "kingdom_db_load_all: stopped at %zu realms, the cap; "
				      "the rest of kingdom_realms was not loaded",
				      kingdom_realm_maximum);
				complete = false;
				break;
			}

			unsigned int null_column = kingdom_realm_column_count;
			for (unsigned int column = 0; column < kingdom_realm_column_count; column++)
				if (!row[column])
				{
					null_column = column;
					break;
				}
			if (null_column != kingdom_realm_column_count)
			{
				/* One line per rejected row, the same shape as the
				 * corrupt-record drop below: the aggregate "rejected"
				 * total at the foot cannot tell an operator WHICH row
				 * to repair. The column is reported as its index into
				 * kingdom_realm_columns, which is printed with it,
				 * rather than as a second name list that could drift
				 * out of step with the SELECT. assoc_id is printed as
				 * the raw string because assoc_id is row[0] and may be
				 * the NULL column itself. */
				logit(LOG_KINGDOM,
				      "kingdom_db_load_all: rejecting a row of kingdom_realms "
				      "(assoc_id %s): column %u of \"%s\", counting from 0, is "
				      "NULL; the row is left in the table for repair",
				      row[0] ? row[0] : "NULL", null_column, kingdom_realm_columns);
				rejected++;
				continue;
			}

			kingdom_realm realm;
			realm.assoc_id = atoi(row[0]);
			realm.realm_id = atoi(row[1]);
			realm.hall_vnum = atoi(row[2]);
			realm.highest_claim = atoi(row[3]);
			for (int res = 0; res < KRES_MAX; res++)
				realm.resources[res] = strtol(row[4 + res], NULL, 10);
			realm.upkeep_paid_through = static_cast<time_t>(strtoll(row[8], NULL, 10));
			realm.arrears = atoi(row[9]);
			realm.missed_cycles = atoi(row[10]);
			/* Anchor left unresolved on purpose -- see the file banner.
			 * dirty and payment_pending are runtime-only and stay at
			 * their defaults: just read, by definition clean. */

			if (!record_is_sane(realm))
			{
				logit(LOG_KINGDOM,
				      "kingdom_db_load_all: rejecting corrupt row for "
				      "association %d (claim %d, arrears %d); the row is left "
				      "in the table for repair",
				      realm.assoc_id, realm.highest_claim, realm.arrears);
				rejected++;
				continue;
			}
			if (!kingdom_realms.emplace(realm.assoc_id, realm).second)
			{
				logit(LOG_KINGDOM,
				      "kingdom_db_load_all: duplicate realm for association %d; "
				      "keeping the first",
				      realm.assoc_id);
				rejected++;
				continue;
			}
			loaded++;
		}
	}
	catch (const std::bad_alloc &)
	{
		logit(LOG_KINGDOM, "kingdom_db_load_all: out of memory after %zu realms", loaded);
		kingdom_realms.clear();
		mysql_free_result(result);
		return false;
	}

	mysql_free_result(result);

	if (rejected)
		logit(LOG_KINGDOM, "kingdom_db_load_all: loaded %zu realms, rejected %zu", loaded,
		      rejected);
	else
		logit(LOG_KINGDOM, "kingdom_db_load_all: loaded %zu realms", loaded);

	/* Rosters AFTER the realms, because each row is filed against a realm
	 * this pass has already put in the map. kingdom_find_realm() skips rows
	 * for realms beyond the cap, so a truncated pass still restores every
	 * roster belonging to a realm it did load. */
	kingdom_db_load_rosters();

	/* A truncated load is a failed load: the caller must not treat the
	 * squares of the realms it never saw as unowned. */
	return complete;
}

/* One realm's write, run on the writer: its row, then its garrison roster (the
 * bought guards and the champion).
 *
 * assoc_id is the primary key, so one upsert covers both create and update and
 * no caller has to know which it is doing. Guild ids are reused by found_asc(),
 * which is exactly why kingdom_on_guild_deleted() must DELETE the row rather
 * than leave it for the next holder of the id to inherit through this statement.
 *
 * The roster is replaced DELETE-THEN-INSERT rather than diffed: it is at most
 * seventeen tiny rows and changes only on a hire, a promotion or a death.
 *
 * A MISSING kingdom_garrison IS NOT AN ERROR HERE, and that is deliberate: the
 * table is outside the runtime contract's table list (see the migration and
 * runtime_compatibility_contract.h), so a database at head 0008 still boots and
 * still runs kingdoms -- it simply cannot keep a roster, and the realm's own row
 * still lands. Only those exact server errors degrade; every other one fails the
 * job. */
static sql_work realm_work(const kingdom_realm &realm)
{
	const std::string upsert = sql_format(
		"INSERT INTO kingdom_realms (%s) VALUES "
		"(%d,%d,%d,%d,%ld,%ld,%ld,%ld,%lld,%d,%d) "
		"ON DUPLICATE KEY UPDATE realm_id=VALUES(realm_id),"
		"hall_vnum=VALUES(hall_vnum),highest_claim=VALUES(highest_claim),"
		"res_mineral=VALUES(res_mineral),res_wood=VALUES(res_wood),"
		"res_fibre=VALUES(res_fibre),res_water=VALUES(res_water),"
		"upkeep_paid_through=VALUES(upkeep_paid_through),"
		"arrears=VALUES(arrears),missed_cycles=VALUES(missed_cycles)",
		kingdom_realm_columns, realm.assoc_id, realm.realm_id, realm.hall_vnum,
		realm.highest_claim, realm.resources[KRES_MINERAL], realm.resources[KRES_WOOD],
		realm.resources[KRES_FIBRE], realm.resources[KRES_WATER],
		static_cast<long long>(realm.upkeep_paid_through), realm.arrears,
		realm.missed_cycles);
	std::vector<std::string> roster = { sql_format(
		"DELETE FROM kingdom_garrison WHERE assoc_id=%d", realm.assoc_id) };
	for (int slot = 0; slot < KINGDOM_GUARD_SLOTS; slot++)
		if (realm.guards[slot].level > 0)
			roster.push_back(sql_format(
				"INSERT INTO kingdom_garrison (assoc_id,slot,guard_class,level) "
				"VALUES (%d,%d,%d,%d)",
				realm.assoc_id, slot, realm.guards[slot].guard_class,
				realm.guards[slot].level));
	if (realm.champion_class)
		roster.push_back(
			sql_format("INSERT INTO kingdom_garrison (assoc_id,slot,guard_class,level) "
				   "VALUES (%d,%d,%d,%d)",
				   realm.assoc_id, KINGDOM_CHAMPION_SLOT, realm.champion_class,
				   KINGDOM_CHAMPION_LEVEL));

	return [upsert, roster](MYSQL *connection) -> unsigned int
	{
		if (const unsigned int error_code = sql_execute(connection, upsert))
			return error_code;
		for (const std::string &statement : roster)
			if (const unsigned int error_code = sql_execute(connection, statement))
				return error_code == ER_NO_SUCH_TABLE ||
						       error_code == ER_NO_SUCH_TABLE_IN_ENGINE ?
					       0 :
					       error_code;
		return 0;
	};
}

/* Queue one realm's row and roster on the writer. False when the record fails
 * record_is_sane() or the job could not be queued; the caller's dirty flag is
 * untouched either way.
 *
 * THIS PRIMITIVE DOES NOT TEST payment_pending. Pending payments use the
 * composed guild/realm writer instead. Every ordinary caller must be guarded by
 * !payment_pending and leave a pending record dirty for
 * kingdom_upkeep_retry_pending() to carry. */
bool kingdom_db_save_realm(const kingdom_realm &realm)
{
	if (!record_is_sane(realm))
	{
		logit(LOG_KINGDOM,
		      "kingdom_db_save_realm: refusing to persist an invalid record for "
		      "association %d (claim %d, arrears %d)",
		      realm.assoc_id, realm.highest_claim, realm.arrears);
		return false;
	}
	return sql_queue_work(realm_work(realm));
}

/* A guild write must carry a still-pending payment's realm image. This also
 * composes with character deletion, whose transaction owns the surrounding work. */
sql_work kingdom_guild_save_work(int assoc_id, std::vector<std::string> guild_statements)
{
	const kingdom_realm *realm = kingdom_find_realm(assoc_id);
	sql_work realm_write;
	if (realm && realm->payment_pending)
	{
		if (!record_is_sane(*realm))
		{
			errno = EINVAL;
			logit(LOG_KINGDOM,
			      "guild snapshot: invalid pending realm for association %d", assoc_id);
			return {};
		}
		realm_write = realm_work(*realm);
	}
	return [guild_statements = std::move(guild_statements),
		realm_write = std::move(realm_write)](MYSQL *connection) -> unsigned int
	{
		for (const std::string &statement : guild_statements)
			if (const unsigned int error = sql_execute(connection, statement))
				return error;
		return realm_write ? realm_write(connection) : 0;
	};
}

bool kingdom_queue_guild_save(int assoc_id, std::vector<std::string> statements,
			      std::shared_ptr<sql_write_receipt> receipt)
{
	kingdom_realm *realm = kingdom_find_realm(assoc_id);
	if (!realm || !realm->payment_pending)
		return sql_queue_statements(std::move(statements), std::move(receipt));
	// An older acknowledgement cannot settle the newer capture, even if this
	// admission fails. Guild dirty-state retry will capture both current images.
	realm->payment_receipt.reset();
	realm->dirty = true;
	sql_work work = kingdom_guild_save_work(assoc_id, std::move(statements));
	if (!work || !sql_queue_work(std::move(work), receipt))
		return false;
	realm->payment_receipt = std::move(receipt);
	realm->dirty = false;
	return true;
}

void kingdom_guild_save_completed(int assoc_id, const std::shared_ptr<sql_write_receipt> &receipt)
{
	kingdom_realm *realm = kingdom_find_realm(assoc_id);
	if (!realm || !receipt || realm->payment_receipt != receipt ||
	    !receipt->finished.load(std::memory_order_acquire))
		return;
	if (receipt->ok)
	{
		realm->payment_pending = false;
		logit(LOG_KINGDOM, "payment for realm %d (association %d) is now durable",
		      realm->realm_id, assoc_id);
	}
	else
		realm->dirty = true;
	realm->payment_receipt.reset();
}

/* Validate persisted class bits against the same curated table commands use.
 * Round-tripping a single value through name -> bit avoids a second whitelist
 * in the persistence layer. A champion is exactly two distinct allowed bits. */
static bool kingdom_db_valid_guard_class(int candidate)
{
	return candidate != 0 &&
	       kingdom_guard_class_by_name(kingdom_guard_class_name(candidate)) == candidate;
}

static bool kingdom_db_valid_champion_class(int candidate)
{
	const unsigned int bits = static_cast<unsigned int>(candidate);
	const unsigned int lower = bits & (~bits + 1u);
	const unsigned int higher = bits & ~lower;

	return lower != 0 && higher != 0 && (higher & (higher - 1u)) == 0 &&
	       kingdom_db_valid_guard_class(static_cast<int>(lower)) &&
	       kingdom_db_valid_guard_class(static_cast<int>(higher));
}

/*
 * Fill in every loaded realm's roster in ONE query rather than one per realm:
 * the table is keyed by association and the whole of it is wanted, so a single
 * ordered scan costs one round trip whatever the number of realms.
 *
 * Rows for a realm that is not loaded are skipped in silence -- they are the
 * normal residue of a guild deleted while the server was down, and
 * kingdom_on_guild_deleted() clears them the next time that id is used. A row
 * with a slot or level outside its range is dropped with a line naming it,
 * because a guard at level 900 would otherwise walk out of the gate.
 */
static void kingdom_db_load_rosters(void)
{
	MYSQL_RES *result = db_query("SELECT assoc_id,slot,guard_class,level FROM "
				     "kingdom_garrison ORDER BY assoc_id,slot");

	if (!result)
	{
		/* Head 0006 has no such table. Kingdoms still run; no realm can
		 * keep a garrison until the database is migrated. */
		logit(LOG_KINGDOM, "kingdom_db_load_rosters: kingdom_garrison could not be read; "
				   "no realm will field guards this boot");
		return;
	}

	if (mysql_num_fields(result) != 4)
	{
		logit(LOG_KINGDOM, "kingdom_db_load_rosters: kingdom_garrison has the wrong shape; "
				   "no rosters loaded");
		mysql_free_result(result);
		return;
	}

	size_t loaded = 0, rejected = 0;
	MYSQL_ROW row;

	while ((row = mysql_fetch_row(result)) != NULL)
	{
		if (!row[0] || !row[1] || !row[2] || !row[3])
		{
			rejected++;
			continue;
		}

		const int assoc_id = atoi(row[0]);
		const int slot = atoi(row[1]);
		const int guard_class = atoi(row[2]);
		const int level = atoi(row[3]);

		kingdom_realm *realm = kingdom_find_realm(assoc_id);

		if (!realm)
			continue;

		if (slot == KINGDOM_CHAMPION_SLOT)
		{
			if (level == KINGDOM_CHAMPION_LEVEL &&
			    kingdom_db_valid_champion_class(guard_class))
				realm->champion_class = guard_class;
			else
				rejected++;
			continue;
		}

		if (slot < 0 || slot >= KINGDOM_GUARD_SLOTS ||
		    !kingdom_db_valid_guard_class(guard_class) ||
		    level < KINGDOM_GUARD_BASE_LEVEL || level > KINGDOM_GUARD_TOP_LEVEL)
		{
			logit(LOG_KINGDOM,
			      "kingdom_db_load_rosters: dropping association %d slot %d class %d "
			      "level %d as out of range",
			      assoc_id, slot, guard_class, level);
			rejected++;
			continue;
		}

		realm->guards[slot].guard_class = guard_class;
		realm->guards[slot].level = level;
		loaded++;
	}

	mysql_free_result(result);

	if (rejected)
		logit(LOG_KINGDOM, "kingdom_db_load_rosters: loaded %zu guard(s), rejected %zu",
		      loaded, rejected);
	else
		logit(LOG_KINGDOM, "kingdom_db_load_rosters: loaded %zu guard(s)", loaded);
}

/* Queue the delete of the row for assoc_id, with its roster. True when queued;
 * false for a non-positive id or a job that could not be queued. */
bool kingdom_db_delete_realm(int assoc_id)
{
	if (assoc_id <= 0)
	{
		logit(LOG_KINGDOM, "kingdom_db_delete_realm: refusing association id %d", assoc_id);
		return false;
	}

	/* Idempotent: a DELETE that matched nothing still succeeded, which is what
	 * kingdom_on_guild_deleted() needs when the guild never had a realm. The
	 * roster goes with the realm, and for the same reason the realm's own row
	 * does: association ids are reused, so a garrison left behind would be
	 * inherited by whoever founds the next guild on that id. Its failure does
	 * NOT fail the delete -- the realm is gone either way, and a database at
	 * head 0008 has no such table to clear. */
	return sql_queue_work(
		[assoc_id](MYSQL *connection) -> unsigned int
		{
			if (const unsigned int error_code = sql_execute(
				    connection,
				    sql_format("DELETE FROM kingdom_realms WHERE assoc_id=%d",
					       assoc_id)))
				return error_code;
			sql_execute(connection,
				    sql_format("DELETE FROM kingdom_garrison WHERE assoc_id=%d",
					       assoc_id));
			return 0;
		});
}

/* Upsert every dirty realm, one statement each, clearing dirty on success. A
 * realm with payment_pending set is HELD BACK -- not written, counted and
 * logged -- because its record carries a paid mark whose guild debit is not
 * yet durable; kingdom_persist_payment() writes that pair. A failed upsert
 * leaves the record dirty for the next flush. Never erases from the map. */
void kingdom_db_flush_dirty(void)
{
	size_t saved = 0;
	size_t failed = 0;
	size_t held = 0;

	for (auto &entry : kingdom_realms)
	{
		if (!entry.second.dirty)
			continue;
		if (entry.second.payment_pending)
		{
			/* Publishing this alone would record a payment the guild has
			 * not durably made. It stays dirty AND pending until the pair
			 * lands through kingdom_upkeep_retry_pending(). */
			held++;
			continue;
		}
		if (kingdom_db_save_realm(entry.second))
		{
			entry.second.dirty = false;
			saved++;
		}
		else
		{
			/* Leave the flag set: the next cycle retries. Clearing it on
			 * failure would drop the write for good. */
			failed++;
		}
	}

	if (failed || held)
		logit(LOG_KINGDOM,
		      "kingdom_db_flush_dirty: saved %zu realms, %zu failed and still dirty, "
		      "%zu held back (payment pending)",
		      saved, failed, held);
}
