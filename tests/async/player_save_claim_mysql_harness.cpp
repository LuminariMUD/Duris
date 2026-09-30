// A save never refuses. It writes what its owner holds in memory and makes
// item_current_owner agree: an item the table gives to a corpse, a locker, a room,
// another player or a pet is taken, with an audit row per change; an item an
// auction holds, or one the table says was destroyed, is left out with its contents
// and logged to the dupe log; the rest of the save commits. This drives
// player_snapshot_repository_apply() against a real server.
#include "persistence/dupe_log.h"
#include "player/player_save_worker.h"
#include "player/player_snapshot_repository.h"
#include "sql/sql_pool.h"

#include <cstdlib>
#include <fstream>
#include <iostream>
#include <mysql/mysql.h>
#include <sstream>
#include <string>
#include <vector>

namespace
{
MYSQL *test_connection = nullptr;

void require(bool condition, const std::string &message)
{
	if (!condition)
	{
		std::cerr << "FAILED: " << message << '\n';
		exit(1);
	}
}

std::string environment(const char *name, const char *fallback)
{
	const char *value = getenv(name);
	return value && *value ? value : fallback;
}

void execute(MYSQL *connection, const std::string &sql)
{
	require(mysql_query(connection, sql.c_str()) == 0,
		"query failed: " + sql + ": " + mysql_error(connection));
}

std::string scalar(MYSQL *connection, const std::string &sql)
{
	execute(connection, sql);
	MYSQL_RES *result = mysql_store_result(connection);
	require(result != nullptr, "no result: " + sql);
	MYSQL_ROW row = mysql_fetch_row(result);
	const std::string value = row && row[0] ? row[0] : "<null>";
	mysql_free_result(result);
	return value;
}

player_item_snapshot item(uint64_t uid, int32_t vnum, int32_t parent)
{
	player_item_snapshot snapshot = {};
	snapshot.parent_index = parent;
	snapshot.equipment_slot = 0;
	snapshot.object_uid = uid;
	snapshot.vnum = vnum;
	snapshot.type = 12;
	return snapshot;
}

player_snapshot snapshot_for(int pid, player_revision_t revision, const char *name)
{
	player_snapshot snapshot = {};
	snapshot.schema_version = PLAYER_SNAPSHOT_SCHEMA_VERSION;
	snapshot.pid = pid;
	snapshot.revision = revision;
	snapshot.components = PLAYER_CHECKPOINT_COMPONENT_ALL;
	snapshot.save_intent = 1;
	snapshot.room_vnum = 3001;
	snapshot.encoded_size_bound = 8192;
	snapshot.status_integers.push_back({ player_status_field::level, 20, 0, false });
	snapshot.status_strings.push_back({ player_status_string_field::name, name });
	snapshot.recipes_are_external = true;
	return snapshot;
}

std::string owner_of(uint64_t uid)
{
	return scalar(test_connection,
		      "SELECT CONCAT(owner_type,':',owner_id,':',owner_context_id,':',state,':',"
		      "root_item_uid,':',COALESCE(parent_item_uid,0)) FROM item_current_owner "
		      "WHERE item_uid=" +
			      std::to_string(uid));
}
} // namespace

// The pooled entry point runs on the harness's own connection.
MYSQL *sql_pool_acquire(void)
{
	return test_connection;
}
void sql_pool_release(MYSQL *) {}
MYSQL *sql_pool_replace_connection(MYSQL *)
{
	return nullptr;
}
// The fixture has no extra descriptions.
char *sql_escape_string(const char *)
{
	std::abort();
}

int main()
{
	require(!mysql_library_init(0, nullptr, nullptr), "could not initialize the MySQL client");
	test_connection = mysql_init(nullptr);
	require(test_connection != nullptr, "could not allocate a MySQL connection");
	const std::string host = environment("DB_HOST", "127.0.0.1");
	const std::string user = environment("DB_USER", "root");
	const std::string password = environment("DB_PASSWD", "");
	const std::string database = environment("DB_NAME", "player_save_claim_test");
	const std::string dupe_log = environment("DUPE_LOG_PATH_FOR_TEST", "/tmp/dupes");
	const unsigned int port = static_cast<unsigned int>(
		std::strtoul(environment("DB_PORT", "3306").c_str(), nullptr, 10));
	require(mysql_real_connect(test_connection, host.c_str(), user.c_str(), password.c_str(),
				   database.c_str(), port, nullptr, 0) != nullptr,
		std::string("could not connect: ") + mysql_error(test_connection));
	execute(test_connection, "SET SESSION sql_mode='STRICT_TRANS_TABLES,"
				 "ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'");
	dupe_log_set_path_for_tests(dupe_log.c_str());

	// The ownership table disagrees with memory about almost everything pid 1 holds.
	execute(test_connection,
		"INSERT INTO item_current_owner (item_uid,root_item_uid,parent_item_uid,owner_type,"
		"owner_id,owner_context_id,item_revision,vnum,state) VALUES "
		"(1001,1001,NULL,4,9001,0,3,501,1)," // a corpse
		"(1002,1002,NULL,5,77,0,2,502,1)," // a locker
		"(1003,1003,NULL,3,3001,0,1,503,1)," // a room
		"(1004,1004,NULL,1,2,0,4,504,1)," // another player
		"(1005,1005,NULL,11,88,2,1,505,1)," // another player's pet
		"(1006,1006,NULL,6,12,0,1,506,1)," // an auction
		"(1007,1006,1006,6,12,0,1,507,1)," // inside the auctioned container
		"(1009,1009,NULL,1,1,0,5,509,1)," // already pid 1's
		"(1011,1011,NULL,1,1,0,5,511,3)," // pid 1's, but quarantined
		"(1050,1050,NULL,8,0,0,2,550,2)," // sold to a shop and destroyed
		"(1051,1050,1050,8,0,0,2,551,2)," // destroyed with the bag it was in
		"(1053,1053,NULL,1,1,0,2,553,1)"); // taken out of that bag before the sale
	// A stale payload row for an item pid 1 no longer holds.
	execute(test_connection, "INSERT INTO player_items (pid,vnum,equip_slot,container_id,"
				 "quantity,item_type,obj_uid) VALUES (1,599,0,NULL,1,0,1099)");

	player_snapshot save = snapshot_for(1, 5, "Claimer");
	save.items = {
		item(1010, 510, PLAYER_SNAPSHOT_NO_PARENT), // 0: a bag nobody has recorded
		item(1003, 503, 0), // 1: the room item, in the bag
		item(1001, 501, PLAYER_SNAPSHOT_NO_PARENT),
		item(1002, 502, PLAYER_SNAPSHOT_NO_PARENT),
		item(1004, 504, PLAYER_SNAPSHOT_NO_PARENT),
		item(1005, 505, PLAYER_SNAPSHOT_NO_PARENT),
		item(1006, 506, PLAYER_SNAPSHOT_NO_PARENT), // 6: held by an auction
		item(1007, 507, 6),
		item(1008, 508, PLAYER_SNAPSHOT_NO_PARENT), // no row at all
		item(1009, 509, PLAYER_SNAPSHOT_NO_PARENT),
		item(1011, 511, PLAYER_SNAPSHOT_NO_PARENT),
		// 11: captured before the sale destroyed it, with what it held then.
		item(1050, 550, PLAYER_SNAPSHOT_NO_PARENT),
		item(1051, 551, 11),
		item(1053, 553, 11),
	};
	player_save_apply_result applied = player_snapshot_repository_apply(test_connection, save);
	require(applied.outcome == player_save_apply_outcome::applied,
		"a save whose items other owners hold must still commit");

	for (const uint64_t uid : { 1001, 1002, 1004, 1005, 1008, 1009, 1010, 1011 })
		require(owner_of(uid) == "1:1:0:1:" + std::to_string(uid) + ":0",
			"item " + std::to_string(uid) + " must now be pid 1's: " + owner_of(uid));
	require(owner_of(1003) == "1:1:0:1:1010:1010",
		"the room item must be pid 1's, inside the bag: " + owner_of(1003));
	require(owner_of(1006) == "6:12:0:1:1006:0" && owner_of(1007) == "6:12:0:1:1006:1006",
		"the auction keeps what it holds");
	require(owner_of(1050) == "8:0:0:2:1050:0" && owner_of(1051) == "8:0:0:2:1050:1050" &&
			owner_of(1053) == "1:1:0:1:1053:0",
		"a destroyed item stays destroyed, and what it held is not moved: " +
			owner_of(1050) + " " + owner_of(1051) + " " + owner_of(1053));

	require(scalar(test_connection, "SELECT COUNT(*) FROM item_owner_audit") == "5",
		"one audit row per item taken from another owner");
	require(scalar(test_connection,
		       "SELECT GROUP_CONCAT(CONCAT(item_uid,'=',old_owner_type,':',old_owner_id,':',"
		       "old_owner_context_id,'>',new_owner_type,':',new_owner_id,':',"
		       "new_owner_context_id,'@',vnum) ORDER BY item_uid) FROM item_owner_audit") ==
			"1001=4:9001:0>1:1:0@501,1002=5:77:0>1:1:0@502,1003=3:3001:0>1:1:0@503,"
			"1004=1:2:0>1:1:0@504,1005=11:88:2>1:1:0@505",
		"the audit names each item, its vnum, the old owner and the new one");

	require(scalar(test_connection, "SELECT COUNT(*) FROM player_items WHERE pid=1") == "9",
		"every held item except the auction's and the destroyed graphs is written");
	require(scalar(test_connection, "SELECT COUNT(*) FROM player_items WHERE pid=1 AND obj_uid "
					"IN (1006,1007,1050,1051,1053,1099)") == "0",
		"the save leaves out the auction's and the destroyed items and drops the stale row");
	require(scalar(test_connection,
		       "SELECT COUNT(*) FROM player_items child JOIN player_items bag ON "
		       "bag.id=child.container_id WHERE child.obj_uid=1003 AND bag.obj_uid=1010") ==
			"1",
		"the room item is written inside the bag");
	require(scalar(test_connection, "SELECT save_revision FROM player_data WHERE pid=1") == "5",
		"the save revision is recorded");
	require(scalar(test_connection, "SELECT COUNT(*) FROM item_owner_revision WHERE "
					"owner_type=1 AND owner_id=1") == "1",
		"the claimer has an owner revision row");

	std::ifstream log(dupe_log);
	std::stringstream lines;
	lines << log.rdbuf();
	const std::string text = lines.str();
	for (const char *line :
	     { "save_left_out uid=1006 vnum=506 lost_by=player:1:0 held_by=auction:12:0",
	       "save_left_out uid=1007 vnum=507 lost_by=player:1:0 held_by=auction:12:0",
	       "save_left_out uid=1050 vnum=550 lost_by=player:1:0 held_by=destruction:0:0",
	       "save_left_out uid=1051 vnum=551 lost_by=player:1:0 held_by=destruction:0:0",
	       "save_left_out uid=1053 vnum=553 lost_by=player:1:0 held_by=player:1:0" })
		require(text.find(line) != std::string::npos,
			std::string("the dupe log names each left-out item: ") + line + "\n" +
				text);

	// Saving the same state again changes nothing and audits nothing.
	save.revision = 6;
	applied = player_snapshot_repository_apply(test_connection, save);
	require(applied.outcome == player_save_apply_outcome::applied, "a repeat save commits");
	require(scalar(test_connection, "SELECT COUNT(*) FROM item_owner_audit") == "5",
		"a repeat save writes no audit rows");

	// No revision fence: an ordinary save with a lower revision is still written.
	player_snapshot older = snapshot_for(1, 4, "Claimer");
	applied = player_snapshot_repository_apply(test_connection, older);
	require(applied.outcome == player_save_apply_outcome::applied &&
			scalar(test_connection, "SELECT COUNT(*) FROM player_items WHERE pid=1") ==
				"0",
		"an ordinary save is never fenced by revision");
	// Only the one-time replay of an older server's journal keeps the fence.
	execute(test_connection, "UPDATE player_data SET save_revision=10 WHERE pid=1");
	player_snapshot replayed = snapshot_for(1, 9, "Claimer");
	replayed.items = { item(1001, 501, PLAYER_SNAPSHOT_NO_PARENT) };
	applied = player_snapshot_repository_apply_from_pool(replayed, PLAYER_SAVE_LEGACY_REPLAY);
	require(applied.outcome == player_save_apply_outcome::stale_revision &&
			scalar(test_connection, "SELECT COUNT(*) FROM player_items WHERE pid=1") ==
				"0",
		"a legacy replay older than the database is skipped");
	replayed.revision = 11;
	applied = player_snapshot_repository_apply_from_pool(replayed, PLAYER_SAVE_LEGACY_REPLAY);
	require(applied.outcome == player_save_apply_outcome::applied &&
			scalar(test_connection, "SELECT COUNT(*) FROM player_items WHERE pid=1") ==
				"1",
		"a newer legacy replay is applied");

	// A character with no player_data row yet gets one instead of failing.
	player_snapshot unbased = snapshot_for(3, 1, "Newcomer");
	unbased.items = { item(1012, 512, PLAYER_SNAPSHOT_NO_PARENT) };
	applied = player_snapshot_repository_apply(test_connection, unbased);
	require(applied.outcome == player_save_apply_outcome::applied,
		"a save for a character without a row must commit");
	require(scalar(test_connection,
		       "SELECT CONCAT(name,':',level) FROM player_data WHERE pid=3") ==
			"Newcomer:20",
		"the missing row is created and filled in");
	require(owner_of(1012) == "1:3:0:1:1012:0", "the newcomer's item is claimed");

	// A corpse save claims what the corpse holds and replaces its rows; a remove deletes
	// them (persistence reset step 6).
	const uint64_t corpse_owner = (static_cast<uint64_t>(3) << 32) | 555;
	const std::string corpse_prefix = "4:" + std::to_string(corpse_owner) + ":0:1:";
	corpse_snapshot corpse;
	corpse.owner = { item_owner_type::corpse, corpse_owner, 0 };
	corpse.save_id = 555;
	corpse.player_name = "Newcomer";
	corpse.room_vnum = 3001;
	corpse.short_description = "the corpse of Newcomer";
	corpse.description = "The corpse of Newcomer is lying here.";
	corpse.keywords = "newcomer corpse _pcorpse_";
	corpse.values = { 20, 2, 0, 3, 0, 0, 555, 0 };
	corpse.items = { item(1012, 512, PLAYER_SNAPSHOT_NO_PARENT), item(1020, 520, 0) };
	applied = corpse_snapshot_repository_apply(test_connection, corpse);
	require(applied.outcome == player_save_apply_outcome::applied, "a corpse save commits");
	require(owner_of(1012) == corpse_prefix + "1012:0" &&
			owner_of(1020) == corpse_prefix + "1012:1012",
		"the corpse claims its items: " + owner_of(1012) + " " + owner_of(1020));
	require(scalar(test_connection, "SELECT COUNT(*) FROM item_owner_audit WHERE item_uid=1012 "
					"AND old_owner_type=1 AND new_owner_type=4") == "1",
		"taking the dead player's item is audited");
	require(scalar(test_connection,
		       "SELECT COUNT(*) FROM corpse_items child JOIN corpse_items bag ON "
		       "bag.id=child.container_id WHERE child.obj_uid=1020 AND bag.obj_uid=1012") ==
			"1",
		"the corpse's items are written with their containment");
	corpse.items.resize(1);
	applied = corpse_snapshot_repository_apply(test_connection, corpse);
	require(applied.outcome == player_save_apply_outcome::applied &&
			scalar(test_connection, "SELECT COUNT(*) FROM corpse_items") == "1" &&
			scalar(test_connection, "SELECT corpse_revision FROM corpses WHERE "
						"player_name='Newcomer' AND save_id=555") == "2",
		"a later corpse save replaces the rows");
	corpse.remove = true;
	applied = corpse_snapshot_repository_apply(test_connection, corpse);
	require(applied.outcome == player_save_apply_outcome::applied &&
			scalar(test_connection, "SELECT COUNT(*) FROM corpses") == "0" &&
			scalar(test_connection, "SELECT COUNT(*) FROM corpse_items") == "0",
		"a corpse leaving the world is deleted");

	// A saved room item claims itself and its contents for the room.
	saved_item_snapshot saved;
	saved.owner = { item_owner_type::room, 3001, 0 };
	saved.item_key = "item.uid.1030";
	saved.room_vnum = 3001;
	saved.items = { item(1030, 530, PLAYER_SNAPSHOT_NO_PARENT), item(1020, 520, 0) };
	applied = saved_item_snapshot_repository_apply(test_connection, saved);
	require(applied.outcome == player_save_apply_outcome::applied &&
			owner_of(1030) == "3:3001:0:1:1030:0" &&
			owner_of(1020) == "3:3001:0:1:1030:1030" &&
			scalar(test_connection,
			       "SELECT COUNT(*) FROM saved_items WHERE "
			       "item_key='item.uid.1030' AND room_vnum=3001") == "2",
		"a saved item save claims its graph for the room: " + owner_of(1020));
	saved.remove = true;
	applied = saved_item_snapshot_repository_apply(test_connection, saved);
	require(applied.outcome == player_save_apply_outcome::applied &&
			scalar(test_connection, "SELECT COUNT(*) FROM saved_items") == "0",
		"a saved item leaving the room is deleted");

	// A private locker chest save claims its contents for the chest and replaces its rows.
	execute(test_connection,
		"INSERT INTO lockers (id,locker_name,owner_pid) VALUES (7,'Claimer',1)");
	locker_chest_snapshot chest;
	chest.locker_id = 7;
	chest.chest_id = 2;
	chest.items = { item(1030, 530, PLAYER_SNAPSHOT_NO_PARENT), item(1040, 540, 0) };
	applied = locker_chest_snapshot_repository_apply(test_connection, chest);
	require(applied.outcome == player_save_apply_outcome::applied &&
			owner_of(1030) == "5:7:2:1:1030:0" &&
			owner_of(1040) == "5:7:2:1:1030:1030" &&
			scalar(test_connection,
			       "SELECT COUNT(*) FROM locker_items WHERE locker_id=7 "
			       "AND chest_id=2") == "2",
		"a chest save claims its contents: " + owner_of(1030));
	chest.items.resize(1);
	applied = locker_chest_snapshot_repository_apply(test_connection, chest);
	require(applied.outcome == player_save_apply_outcome::applied &&
			scalar(test_connection,
			       "SELECT COUNT(*) FROM locker_items WHERE locker_id=7 "
			       "AND chest_id=2") == "1",
		"a later chest save replaces the rows");

	// A locker's public chest save runs wholly on the writer: it finds the locker's row
	// and public chest by name, creating them for a new locker, claims what the chest
	// holds and replaces its rows, including one written before public chests existed.
	locker_snapshot locker;
	locker.locker_name = "Claimer.locker";
	locker.owner_name = "Claimer";
	locker.racewar = 1;
	locker.race = 2;
	locker.items = { item(1080, 580, PLAYER_SNAPSHOT_NO_PARENT), item(1081, 581, 0) };
	applied = locker_snapshot_repository_apply(test_connection, locker);
	require(applied.outcome == player_save_apply_outcome::applied,
		"a new locker's save commits");
	const std::string locker_id = scalar(
		test_connection, "SELECT id FROM lockers WHERE locker_name='Claimer.locker'");
	const std::string public_id = scalar(
		test_connection, "SELECT id FROM private_chests WHERE locker_id=" + locker_id +
					 " AND is_public=1 AND chest_name='public'");
	const std::string public_prefix = "5:" + locker_id + ":" + public_id + ":1:";
	require(scalar(test_connection,
		       "SELECT CONCAT(COALESCE(owner_pid,0),':',"
		       "COALESCE(owner_assoc_id,0),':',racewar,':',race) FROM lockers "
		       "WHERE id=" +
			       locker_id) == "1:0:1:2",
		"a new locker's row names its owner, racewar and race");
	require(owner_of(1080) == public_prefix + "1080:0" &&
			owner_of(1081) == public_prefix + "1080:1080" &&
			scalar(test_connection,
			       "SELECT COUNT(*) FROM locker_items WHERE locker_id=" + locker_id +
				       " AND chest_id=" + public_id) == "2",
		"the public chest claims and writes what it holds: " + owner_of(1080));
	execute(test_connection,
		"INSERT INTO locker_items (locker_id,chest_id,vnum,obj_uid) VALUES (" + locker_id +
			",NULL,599,1098)");
	locker.items.resize(1);
	applied = locker_snapshot_repository_apply(test_connection, locker);
	require(applied.outcome == player_save_apply_outcome::applied &&
			scalar(test_connection, "SELECT COUNT(*) FROM lockers WHERE "
						"locker_name='Claimer.locker'") == "1" &&
			scalar(test_connection,
			       "SELECT COUNT(*) FROM private_chests WHERE locker_id=" +
				       locker_id) == "1" &&
			scalar(test_connection,
			       "SELECT GROUP_CONCAT(obj_uid) FROM locker_items WHERE locker_id=" +
				       locker_id) == "1080",
		"a later save finds the same locker and chest and replaces the rows");
	locker_snapshot guild;
	guild.locker_name = "guild.12.locker";
	guild.owner_assoc_id = 12;
	applied = locker_snapshot_repository_apply(test_connection, guild);
	require(applied.outcome == player_save_apply_outcome::applied &&
			scalar(test_connection,
			       "SELECT CONCAT(COALESCE(owner_pid,0),':',owner_assoc_id)"
			       " FROM lockers WHERE locker_name='guild.12.locker'") == "0:12",
		"a guild locker's row names its guild");

	// sql_log() queues its row on the writer: it is written with the time it was logged,
	// and its text is escaped on the writer's connection.
	log_entry_snapshot entry;
	entry.logged_at = 1700000000;
	entry.kind = "CONNECTLOG";
	entry.ip_address = "127.0.0.1";
	entry.pid = 1;
	entry.player_name = "Claimer";
	entry.zone_number = 30;
	entry.room_vnum = 3001;
	entry.message = "Quit Game: it's a \\ test";
	applied = log_entry_repository_apply(test_connection, entry);
	require(applied.outcome == player_save_apply_outcome::applied &&
			scalar(test_connection,
			       "SELECT CONCAT(UNIX_TIMESTAMP(date),'|',kind,'|',ip_address,'|',pid,'|',"
			       "player_name,'|',zone_number,'|',room_vnum,'|',message) FROM "
			       "log_entries") ==
				"1700000000|CONNECTLOG|127.0.0.1|1|Claimer|30|3001|Quit Game: it's a "
				"\\ test",
		"a log row keeps its time and text: " +
			scalar(test_connection, "SELECT message FROM log_entries"));

	// Money lives in memory: the save writes the wallet, and a bank change is a delta
	// added to the account's row, creating it. A debit the row cannot cover fails and
	// leaves the row as it was.
	player_snapshot wallet = snapshot_for(1, 40, "Claimer");
	wallet.status_integers.push_back({ player_status_field::copper, 5, 0, false });
	wallet.status_integers.push_back({ player_status_field::platinum, 2, 0, false });
	wallet.status_integers.push_back({ player_status_field::epics, 77, 0, false });
	wallet.status_integers.push_back({ player_status_field::frags, -12, 0, false });
	wallet.status_integers.push_back({ player_status_field::old_frags, 10, 0, false });
	applied = player_snapshot_repository_apply(test_connection, wallet);
	require(applied.outcome == player_save_apply_outcome::applied &&
			scalar(test_connection,
			       "SELECT CONCAT(copper,':',silver,':',gold,':',platinum,':',epics,':',"
			       "frags,':',oldfrags) FROM player_data WHERE pid=1") ==
				"5:0:0:2:77:-12:10",
		"the save writes the wallet, epics and frags");
	const auto bank = [&]
	{
		return scalar(test_connection,
			      "SELECT CONCAT(bank_copper,':',bank_silver,':',bank_gold,':',"
			      "bank_platinum,'@',bank_revision) FROM account_banks WHERE "
			      "account_name='claim_probe' AND racewar=1");
	};
	require(bank_delta_repository_apply(test_connection, { "claim_probe", 1, { 7, 0, 3, 0 } })
					.outcome == player_save_apply_outcome::applied &&
			bank() == "7:0:3:0@0",
		"a bank credit creates the account's row: " + bank());
	require(bank_delta_repository_apply(test_connection, { "claim_probe", 1, { 1, 0, -3, 4 } })
					.outcome == player_save_apply_outcome::applied &&
			bank() == "8:0:0:4@1",
		"a bank delta adds to the row: " + bank());
	require(bank_delta_repository_apply(test_connection, { "claim_probe", 1, { -9, 0, 0, 0 } })
					.outcome == player_save_apply_outcome::terminal_failure &&
			bank() == "8:0:0:4@1",
		"a debit the row cannot cover fails: " + bank());

	mysql_close(test_connection);
	mysql_library_end();
	std::cout << "player save claim MariaDB leg passed\n";
	return 0;
}
