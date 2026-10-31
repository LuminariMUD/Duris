// A save never refuses. It writes what its owner holds in memory and makes
// item_current_owner agree: an item the table gives to a corpse, a locker, a room,
// another player, a pet or an auction is taken, with an audit row per change; an item
// the table says was destroyed is left out with its contents and logged to the dupe
// log; the rest of the save commits. This drives
// player_snapshot_repository_apply() against a real server.
#include "item/item_claim_repository.h"
#include "core/files.h"
#include "persistence/dupe_log.h"
#include "player/player_save_worker.h"
#include "player/player_snapshot_repository.h"
#include "sql/sql_pool.h"

#include <cerrno>
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

	// The boot reap (work item #11): a player's active row whose item is in no payload
	// row at all goes; one a payload row, a legacy pet's payload row, a child row, an
	// auction's custody row or an artifact's row still holds stays, as does a
	// quarantined row and any other owner's. So does one whose item an older copy in
	// another player's payload, a pet's, a locker, a corpse or a saved room item still
	// carries: the row is what makes that copy load as stale (MR !13 review, finding 1).
	// A stale container goes after its stale contents. Pid 2's rows, so the saves below
	// meet the table they expect.
	execute(test_connection,
		"INSERT INTO item_current_owner (item_uid,root_item_uid,parent_item_uid,owner_type,"
		"owner_id,owner_context_id,item_revision,vnum,state) VALUES "
		"(7001,7001,NULL,1,2,0,1,601,1)," // dropped and extracted
		"(7002,7002,NULL,1,2,0,1,602,1)," // a dropped bag...
		"(7003,7002,7002,1,2,0,1,603,1)," // ...with what it held
		"(7004,7004,NULL,1,2,0,1,604,1)," // held
		"(7005,7005,NULL,1,2,0,1,605,1)," // carried by a legacy pet
		"(7006,7006,NULL,1,2,0,1,606,1)," // claimed from an auction, whose row stays
		"(7007,7007,NULL,1,2,0,1,607,1)," // an artifact's row names it
		"(7008,7008,NULL,1,2,0,1,608,3)," // quarantined
		"(7010,7010,NULL,4,9002,0,1,610,1)," // a corpse's, with no payload anywhere
		"(7011,7011,NULL,1,2,0,1,611,1)," // a bag the player no longer holds...
		"(7012,7011,7011,1,2,0,1,612,1)," // ...but its contents are held
		"(7013,7013,NULL,1,2,0,1,613,1)," // handed over; pid 1's payload has a copy
		"(7014,7014,NULL,1,2,0,1,614,1)," // a copy is in a locker
		"(7015,7015,NULL,1,2,0,1,615,1)," // in a corpse
		"(7016,7016,NULL,1,2,0,1,616,1)," // in a saved room item
		"(7017,7017,NULL,1,2,0,1,617,1)"); // with pid 1's pet
	execute(test_connection, "INSERT INTO player_items (pid,vnum,equip_slot,container_id,"
				 "quantity,item_type,obj_uid) VALUES (2,604,0,NULL,1,0,7004),"
				 "(2,612,0,NULL,1,0,7012)");
	execute(test_connection,
		"INSERT INTO player_pets (id,owner_pid,mob_vnum) VALUES (77,2,1201)");
	execute(test_connection, "INSERT INTO player_pet_items (pet_id,vnum,obj_uid) VALUES "
				 "(77,605,7005)");
	execute(test_connection,
		"INSERT INTO auction_item_custody (auction_id,slot,item_uid,"
		"item_revision,vnum,obj_blob,claim_pid) VALUES (79,0,7006,1,606,'',2)");
	execute(test_connection,
		"INSERT INTO artifact_domain_state (vnum,canonical_item_uid,identity_state) VALUES (607,7007,1)");
	execute(test_connection, "INSERT INTO player_items (pid,vnum,equip_slot,container_id,"
				 "quantity,item_type,obj_uid) VALUES (1,613,0,NULL,1,0,7013)");
	execute(test_connection,
		"INSERT INTO lockers (id,locker_name,owner_pid) VALUES (70,'Reaped',2)");
	execute(test_connection,
		"INSERT INTO locker_items (locker_id,vnum,obj_uid) VALUES (70,614,7014)");
	execute(test_connection,
		"INSERT INTO corpses (id,player_name,save_id) VALUES (70,'Other',1)");
	execute(test_connection,
		"INSERT INTO corpse_items (corpse_id,vnum,obj_uid) VALUES (70,615,7015)");
	execute(test_connection, "INSERT INTO saved_items (item_key,room_vnum,vnum,obj_uid) "
				 "VALUES ('item.uid.7016',3001,616,7016)");
	execute(test_connection,
		"INSERT INTO player_pets (id,owner_pid,mob_vnum) VALUES (78,1,1201)");
	execute(test_connection, "INSERT INTO player_pet_items (pet_id,vnum,obj_uid) VALUES "
				 "(78,617,7017)");
	// The reap runs before each check, so the check's message sees its outcome.
	uint64_t reaped = 0;
	unsigned int reap = reap_unheld_player_items(test_connection, &reaped);
	require(reap == 0 && reaped == 3,
		"the reap deletes the three stale rows: " + std::to_string(reaped));
	require(scalar(test_connection, "SELECT GROUP_CONCAT(item_uid ORDER BY item_uid) FROM "
					"item_current_owner") ==
			"7004,7005,7006,7007,7008,7010,7011,7012,7013,7014,7015,7016,7017",
		"the reap keeps every other row: " +
			scalar(test_connection,
			       "SELECT GROUP_CONCAT(item_uid ORDER BY item_uid) FROM "
			       "item_current_owner"));
	reap = reap_unheld_player_items(test_connection, &reaped);
	require(reap == 0 && reaped == 0, "a second reap finds nothing");
	// The older copies go, as their holders' next saves take them out: the rows go at
	// the boot after that.
	execute(test_connection, "DELETE FROM player_items WHERE obj_uid=7013");
	execute(test_connection, "DELETE FROM lockers WHERE id=70");
	execute(test_connection, "DELETE FROM corpses WHERE id=70");
	execute(test_connection, "DELETE FROM saved_items WHERE obj_uid=7016");
	execute(test_connection, "DELETE FROM player_pets WHERE id=78");
	reap = reap_unheld_player_items(test_connection, &reaped);
	require(reap == 0 && reaped == 5,
		"the rows no copy holds any more go: " + std::to_string(reaped));

	// Recovery-only payloads have no row in those legacy joins. Keep their
	// custody across bounded pages, while still deleting unrelated stale rows.
	for (uint64_t uid = 900001; uid <= 900301; ++uid)
		execute(test_connection,
			"INSERT INTO item_current_owner(item_uid,root_item_uid,owner_type,owner_id,owner_context_id,item_revision,vnum,state) VALUES(" +
				std::to_string(uid) + ',' + std::to_string(uid) +
				",1,2,0,1,900,1)");
	execute(test_connection,
		"INSERT INTO item_current_owner(item_uid,root_item_uid,parent_item_uid,owner_type,owner_id,owner_context_id,item_revision,vnum,state) VALUES(900400,900400,NULL,1,2,0,1,900,1),(900500,900400,900400,1,2,0,1,900,1)");
	const std::vector<uint64_t> retained = { 900001, 900129, 900301 };
	reap = reap_unheld_player_items(test_connection, &reaped, &retained);
	require(!reap && reaped == 300,
		"paged reap lost a retained recovery UID or failed to reap stale parent/child");
	require(scalar(test_connection,
		       "SELECT GROUP_CONCAT(item_uid ORDER BY item_uid) FROM item_current_owner WHERE item_uid>=900000") ==
			"900001,900129,900301",
		"recovery-only retained custody did not survive");
	require(!reap_unheld_player_items(test_connection, &reaped, &retained) && !reaped,
		"retained-only pages did not terminate");
	execute(test_connection, "DELETE FROM item_current_owner WHERE item_uid>=900000");

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
		item(1006, 506, PLAYER_SNAPSHOT_NO_PARENT), // 6: an auction's, by the table
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

	for (const uint64_t uid : { 1001, 1002, 1004, 1005, 1006, 1008, 1009, 1010, 1011 })
		require(owner_of(uid) == "1:1:0:1:" + std::to_string(uid) + ":0",
			"item " + std::to_string(uid) + " must now be pid 1's: " + owner_of(uid));
	require(owner_of(1003) == "1:1:0:1:1010:1010",
		"the room item must be pid 1's, inside the bag: " + owner_of(1003));
	require(owner_of(1007) == "1:1:0:1:1006:1006",
		"the auctioned container's contents must be pid 1's: " + owner_of(1007));
	require(owner_of(1050) == "8:0:0:2:1050:0" && owner_of(1051) == "8:0:0:2:1050:1050" &&
			owner_of(1053) == "1:1:0:1:1053:0",
		"a destroyed item stays destroyed, and what it held is not moved: " +
			owner_of(1050) + " " + owner_of(1051) + " " + owner_of(1053));

	require(scalar(test_connection, "SELECT COUNT(*) FROM item_owner_audit") == "7",
		"one audit row per item taken from another owner");
	require(scalar(test_connection,
		       "SELECT GROUP_CONCAT(CONCAT(item_uid,'=',old_owner_type,':',old_owner_id,':',"
		       "old_owner_context_id,'>',new_owner_type,':',new_owner_id,':',"
		       "new_owner_context_id,'@',vnum) ORDER BY item_uid) FROM item_owner_audit") ==
			"1001=4:9001:0>1:1:0@501,1002=5:77:0>1:1:0@502,1003=3:3001:0>1:1:0@503,"
			"1004=1:2:0>1:1:0@504,1005=11:88:2>1:1:0@505,1006=6:12:0>1:1:0@506,"
			"1007=6:12:0>1:1:0@507",
		"the audit names each item, its vnum, the old owner and the new one");

	require(scalar(test_connection, "SELECT COUNT(*) FROM player_items WHERE pid=1") == "11",
		"every held item except the destroyed graph is written");
	require(scalar(test_connection, "SELECT COUNT(*) FROM player_items WHERE pid=1 AND obj_uid "
					"IN (1050,1051,1053,1099)") == "0",
		"the save leaves out the destroyed items and drops the stale row");
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
	     { "save_left_out uid=1050 vnum=550 lost_by=player:1:0 held_by=destruction:0:0",
	       "save_left_out uid=1051 vnum=551 lost_by=player:1:0 held_by=destruction:0:0",
	       "save_left_out uid=1053 vnum=553 lost_by=player:1:0 held_by=player:1:0" })
		require(text.find(line) != std::string::npos,
			std::string("the dupe log names each left-out item: ") + line + "\n" +
				text);

	// Saving the same state again changes nothing and audits nothing.
	save.revision = 6;
	applied = player_snapshot_repository_apply(test_connection, save);
	require(applied.outcome == player_save_apply_outcome::applied, "a repeat save commits");
	require(scalar(test_connection, "SELECT COUNT(*) FROM item_owner_audit") == "7",
		"a repeat save writes no audit rows");

	// No revision fence: an ordinary save with a lower revision is still written.
	player_snapshot older = snapshot_for(1, 4, "Claimer");
	applied = player_snapshot_repository_apply(test_connection, older);
	require(applied.outcome == player_save_apply_outcome::applied &&
			scalar(test_connection, "SELECT COUNT(*) FROM player_items WHERE pid=1") ==
				"0",
		"an ordinary save is never fenced by revision");

	// A character with no player_data row yet gets one instead of failing.
	player_snapshot unbased = snapshot_for(3, 1, "Newcomer");
	unbased.wallet_revision = 7; // Starter money has already changed in memory.
	unbased.status_integers.push_back({ player_status_field::copper, 35, 0, false });
	unbased.items = { item(1012, 512, PLAYER_SNAPSHOT_NO_PARENT) };
	applied = player_snapshot_repository_apply(test_connection, unbased);
	require(applied.outcome == player_save_apply_outcome::applied,
		"a save for a character without a row must commit");
	require(scalar(test_connection,
		       "SELECT CONCAT(name,':',level) FROM player_data WHERE pid=3") ==
			"Newcomer:20",
		"the missing row is created and filled in");
	require(owner_of(1012) == "1:3:0:1:1012:0", "the newcomer's item is claimed");
	require(scalar(test_connection,
		       "SELECT CONCAT(copper,':',wallet_revision) FROM player_data WHERE pid=3") ==
				"35:7" &&
			scalar(test_connection,
			       "SELECT CONCAT(opening_copper,':',opening_revision) "
			       "FROM currency_wallet_baseline WHERE pid=3") == "35:7",
		"the starter wallet opening baseline must begin at its captured revision");

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
	// and its text is escaped on the writer's connection. An IPv6 address of the longest
	// form (45 characters) is kept whole.
	log_entry_snapshot entry;
	entry.logged_at = 1700000000;
	entry.kind = "CONNECTLOG";
	entry.ip_address = "2001:0db8:85a3:0000:0000:8a2e:192.168.100.200";
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
				"1700000000|CONNECTLOG|2001:0db8:85a3:0000:0000:8a2e:192.168.100.200|1|"
				"Claimer|30|3001|Quit Game: it's a "
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
	// Boot refuses a bank without an opening baseline, so the delta that creates the
	// row writes one from it, and later deltas leave it alone.
	const auto bank_baseline = [&]
	{
		return scalar(
			test_connection,
			"SELECT CONCAT(opening_copper,':',opening_silver,':',opening_gold,':',"
			"opening_platinum,'@',opening_revision) FROM currency_bank_baseline "
			"JOIN account_banks bank ON bank.id=bank_id WHERE "
			"account_name='claim_probe' AND racewar=1");
	};
	applied =
		bank_delta_repository_apply(test_connection, { "claim_probe", 1, { 7, 0, 3, 0 } });
	require(applied.outcome == player_save_apply_outcome::applied && bank() == "7:0:3:0@0" &&
			bank_baseline() == "7:0:3:0@0",
		"a bank credit creates the account's row and its baseline: " + bank() + " " +
			bank_baseline());
	applied =
		bank_delta_repository_apply(test_connection, { "claim_probe", 1, { 1, 0, -3, 4 } });
	require(applied.outcome == player_save_apply_outcome::applied && bank() == "8:0:0:4@1" &&
			bank_baseline() == "7:0:3:0@0",
		"a bank delta adds to the row: " + bank() + " " + bank_baseline());
	require(bank_delta_repository_apply(test_connection, { "claim_probe", 1, { -9, 0, 0, 0 } })
					.outcome == player_save_apply_outcome::terminal_failure &&
			bank() == "8:0:0:4@1",
		"a debit the row cannot cover fails: " + bank());

	// A shopkeeper save replaces the shop's row, affects and stock in one transaction;
	// nested stock keeps its container and every row keeps its uid.
	flatfile_shopkeeper_record shop;
	shop.shop_id = 17;
	shop.mob_vnum = 3001;
	shop.room_vnum = 3002;
	shop.saved_at = 1700000000;
	shop.affects.push_back({ 5, 10, 2, 1, { 1, 0, 0, 0, 0 } });
	player_item_snapshot worn = item(9101, 12, -1);
	worn.equipment_slot = 3;
	shop.items = { item(9102, 13, -1), item(9103, 14, 0), worn };
	shop.items[1].parent_index = 0;
	applied = shopkeeper_snapshot_repository_apply(test_connection, shop);
	require(applied.outcome == player_save_apply_outcome::applied &&
			scalar(test_connection,
			       "SELECT CONCAT(COUNT(*),':',MAX(mob_vnum),':',MAX(room_vnum)) FROM "
			       "shopkeepers WHERE shop_id=17") == "1:3001:3002" &&
			scalar(test_connection, "SELECT COUNT(*) FROM shopkeeper_affects") == "1" &&
			scalar(test_connection,
			       "SELECT COUNT(*) FROM shopkeeper_items child JOIN shopkeeper_items "
			       "bag ON bag.id=child.container_id WHERE child.obj_uid=9103 AND "
			       "bag.obj_uid=9102") == "1" &&
			scalar(test_connection,
			       "SELECT equip_slot FROM shopkeeper_items WHERE obj_uid=9101") == "3",
		"a shopkeeper save did not write its row, affects and stock");
	shop.items = { item(9104, 15, -1) };
	shop.affects.clear();
	applied = shopkeeper_snapshot_repository_apply(test_connection, shop);
	require(applied.outcome == player_save_apply_outcome::applied &&
			scalar(test_connection,
			       "SELECT GROUP_CONCAT(obj_uid) FROM shopkeeper_items") == "9104" &&
			scalar(test_connection, "SELECT COUNT(*) FROM shopkeeper_affects") == "0" &&
			scalar(test_connection,
			       "SELECT COUNT(*) FROM shopkeepers WHERE shop_id=17") == "1",
		"a shopkeeper save did not replace the shop's stock");

	// Game-thread SQL (sql_async.c): a job's work runs in one transaction, so one that
	// fails leaves nothing; a read's rows are copied, NULLs included.
	execute(test_connection, "CREATE TEMPORARY TABLE sql_job_probe (id INT PRIMARY KEY, "
				 "note VARCHAR(8) NULL)");
	applied = sql_work_repository_apply(
		test_connection,
		[](MYSQL *connection) -> unsigned int
		{
			if (const unsigned int error_code = sql_execute(
				    connection, "INSERT INTO sql_job_probe VALUES (1,'one')"))
				return error_code;
			return sql_execute(connection, "INSERT INTO sql_job_probe VALUES (2,NULL)");
		});
	require(applied.outcome == player_save_apply_outcome::applied &&
			scalar(test_connection, "SELECT COUNT(*) FROM sql_job_probe") == "2",
		"queued statements did not apply");
	applied = sql_work_repository_apply(
		test_connection,
		[](MYSQL *connection) -> unsigned int
		{
			if (const unsigned int error_code = sql_execute(
				    connection, "INSERT INTO sql_job_probe VALUES (3,'three')"))
				return error_code;
			return sql_execute(connection,
					   "INSERT INTO sql_job_probe VALUES (1,'again')");
		});
	require(applied.outcome == player_save_apply_outcome::terminal_failure &&
			scalar(test_connection, "SELECT COUNT(*) FROM sql_job_probe") == "2",
		"a failed statement left the others of its job applied");
	sql_rows rows;
	applied = sql_work_repository_apply(
		test_connection,
		[&](MYSQL *connection) {
			return sql_select(connection,
					  "SELECT id,note FROM sql_job_probe ORDER BY id", &rows);
		});
	require(applied.outcome == player_save_apply_outcome::applied && rows.size() == 2 &&
			std::string(rows[0][0]) == "1" && std::string(rows[0][1]) == "one" &&
			std::string(rows[1][0]) == "2" && !rows[1][1],
		"a queued read did not copy its rows");

	// A prepared reward's balance and applied sequence share one status commit.
	player_snapshot paid = {};
	paid.schema_version = PLAYER_SNAPSHOT_SCHEMA_VERSION;
	paid.pid = 1;
	paid.revision = 10000;
	paid.components = PLAYER_COMPONENT_STATUS;
	paid.encoded_size_bound = 4096;
	paid.wallet_revision =
		std::stoull(scalar(test_connection,
				   "SELECT wallet_revision FROM player_data WHERE pid=1")) +
		1;
	paid.status_integers = { { player_status_field::epics, 450, 0, false },
				 { player_status_field::divine_boon_delivery_seq, 0, 3, true } };
	paid.status_integers.insert(paid.status_integers.end(),
				    { { player_status_field::copper, 150, 0, false },
				      { player_status_field::silver, 0, 0, false },
				      { player_status_field::gold, 0, 0, false },
				      { player_status_field::platinum, 0, 0, false } });
	applied = player_snapshot_repository_apply(test_connection, paid);
	require(applied.outcome == player_save_apply_outcome::applied &&
			scalar(test_connection,
			       "SELECT CONCAT(epics,':',divine_boon_delivery_seq) FROM player_data WHERE pid=1") ==
				"450:3",
		"Divine balance and applied marker were not checkpointed together");
	auto stale_delivery = paid;
	stale_delivery.revision = 10001;
	stale_delivery.status_integers[0].signed_value = 1;
	stale_delivery.status_integers[1].unsigned_value = 2;
	applied = player_snapshot_repository_apply(test_connection, stale_delivery);
	require(applied.outcome == player_save_apply_outcome::stale_revision &&
			applied.durable_revision == paid.revision &&
			scalar(test_connection,
			       "SELECT CONCAT(epics,':',divine_boon_delivery_seq) FROM player_data WHERE pid=1") ==
				"450:3",
		"a newer-numbered stale capture erased a delivered Divine award");
	auto mixed_delivery = stale_delivery;
	mixed_delivery.components |= PLAYER_COMPONENT_SKILLS | PLAYER_COMPONENT_LANGUAGES;
	mixed_delivery.skills = { { 9, 73, 2 } };
	mixed_delivery.languages = { { 1, 82, 0 } };
	applied = player_snapshot_repository_apply(test_connection, mixed_delivery);
	require(applied.outcome == player_save_apply_outcome::applied &&
			scalar(test_connection,
			       "SELECT CONCAT(epics,':',divine_boon_delivery_seq,':',save_revision) FROM player_data WHERE pid=1") ==
				"450:3:10001" &&
			scalar(test_connection,
			       "SELECT learned FROM player_skills WHERE pid=1 AND skill_id=9") ==
				"73" &&
			scalar(test_connection,
			       "SELECT proficiency FROM player_languages WHERE pid=1 AND tongue_id=1") ==
				"82",
		"stale status discarded unrelated skill/language changes");
	auto marker_only = paid;
	marker_only.revision = 10002;
	marker_only.status_integers.erase(marker_only.status_integers.begin());
	marker_only.status_integers[0].unsigned_value = 4;
	applied = player_snapshot_repository_apply(test_connection, marker_only);
	require(applied.outcome == player_save_apply_outcome::terminal_failure &&
			scalar(test_connection,
			       "SELECT CONCAT(epics,':',divine_boon_delivery_seq) FROM player_data WHERE pid=1") ==
				"450:3",
		"delivery marker advanced without its epic balance");
	auto malformed_delivery = paid;
	malformed_delivery.status_integers[1].is_unsigned = false;
	require(player_snapshot_repository_apply(test_connection, malformed_delivery).outcome ==
			player_save_apply_outcome::terminal_failure,
		"signed Divine delivery marker was accepted");
	malformed_delivery = paid;
	malformed_delivery.status_integers.push_back(paid.status_integers[1]);
	require(player_snapshot_repository_apply(test_connection, malformed_delivery).outcome ==
			player_save_apply_outcome::terminal_failure,
		"duplicate Divine delivery marker was accepted");

	auto stale_wallet = paid;
	stale_wallet.revision = 99999;
	stale_wallet.wallet_revision = paid.wallet_revision - 1;
	stale_wallet.status_integers[2].signed_value = 1;
	stale_wallet.components |= PLAYER_COMPONENT_TROPHIES;
	stale_wallet.trophies.push_back({ 123456, 77 });
	applied = player_snapshot_repository_apply(test_connection, stale_wallet);
	require(applied.outcome == player_save_apply_outcome::applied &&
			scalar(test_connection,
			       "SELECT CONCAT(copper,':',wallet_revision) FROM player_data WHERE pid=1") ==
				"150:" + std::to_string(paid.wallet_revision) &&
			scalar(test_connection,
			       "SELECT exp FROM zone_trophy WHERE pid=1 AND zone_number=123456") ==
				"77",
		"stale wallet lost unrelated terminal-save state");
	// A later current-wallet capture keeps the same unrelated state.
	auto fresh_wallet = stale_wallet;
	fresh_wallet.revision = 100000;
	fresh_wallet.wallet_revision = paid.wallet_revision;
	fresh_wallet.status_integers[2].signed_value = 150;
	applied = player_snapshot_repository_apply(test_connection, fresh_wallet);
	require(applied.outcome == player_save_apply_outcome::applied &&
			scalar(test_connection,
			       "SELECT exp FROM zone_trophy WHERE pid=1 AND zone_number=123456") ==
				"77" &&
			scalar(test_connection,
			       "SELECT CONCAT(copper,':',wallet_revision) FROM player_data WHERE pid=1") ==
				"150:" + std::to_string(paid.wallet_revision),
		"freshly recaptured unrelated components did not persist with the safe wallet");
	// Partial non-wallet status work must preserve the wallet revision.
	auto non_wallet = paid;
	non_wallet.revision = 100001;
	non_wallet.wallet_revision = 0;
	non_wallet.status_integers.resize(2);
	non_wallet.status_integers[0].signed_value = 500;
	applied = player_snapshot_repository_apply(test_connection, non_wallet);
	require(applied.outcome == player_save_apply_outcome::applied &&
			scalar(test_connection,
			       "SELECT CONCAT(copper,':',wallet_revision) FROM player_data WHERE pid=1") ==
				"150:" + std::to_string(paid.wallet_revision),
		"non-wallet status work reset the committed wallet revision");

	// Inn rent consumes only NORENT keys, in the same transaction as the player.
	for (int scenario = 0; scenario < 6; ++scenario)
	{
		const uint64_t uid = 4040100 + scenario * 10;
		const int place = scenario % 3;
		auto rent = snapshot_for(1, 200000 + scenario * 10, "Claimer");
		rent.items = { item(uid, 100, -1), item(uid + 1, 40401, place == 2 ? 0 : -1),
			       item(uid + 2, 101, 0), item(uid + 3, 102, -1) };
		rent.items[0].type = ITEM_CONTAINER;
		rent.items[1].type = ITEM_KEY;
		rent.items[1].extra_flags = ITEM_NORENT;
		rent.items[1].equipment_slot = place == 1 ? HOLD + 1 : 0;
		rent.items[2].type = ITEM_FOOD;
		rent.items[2].extra_flags = ITEM_NORENT;
		rent.items[3].type = ITEM_KEY;
		if (scenario >= 3)
		{
			auto before_rent = rent;
			if (scenario == 5)
			{
				before_rent.pid = 2;
				before_rent.status_strings[0].value = "Other";
			}
			require(player_snapshot_repository_apply(test_connection, before_rent)
						.outcome == player_save_apply_outcome::applied,
				"owned rent baseline");
		}
		rent.save_intent = RENT_INN;
		const auto apply = [&](const player_snapshot &input)
		{
			require(player_snapshot_repository_apply(test_connection, input).outcome ==
					player_save_apply_outcome::applied,
				"rent save");
		};
		const auto kept = [&]
		{
			require(scalar(test_connection,
				       "SELECT GROUP_CONCAT(obj_uid ORDER BY obj_uid) FROM player_items WHERE pid=1") ==
					std::to_string(uid) + "," + std::to_string(uid + 2) + "," +
						std::to_string(uid + 3),
				"rent lost ordinary items or retained key");
			require(scalar(test_connection,
				       "SELECT bag.obj_uid FROM player_items child JOIN player_items bag ON child.container_id=bag.id WHERE child.obj_uid=" +
					       std::to_string(uid + 2) + " AND child.pid=1") ==
					std::to_string(uid),
				"rent changed sibling topology");
		};
		apply(rent);
		kept();
		require(owner_of(uid + 1) == "8:0:0:2:" + std::to_string(uid + 1) + ":0",
			"rent custody");
		const auto revision =
			scalar(test_connection,
			       "SELECT item_revision FROM item_current_owner WHERE item_uid=" +
				       std::to_string(uid + 1));
		const auto audits = scalar(test_connection,
					   "SELECT COUNT(*) FROM item_owner_audit WHERE item_uid=" +
						   std::to_string(uid + 1));
		apply(rent);
		kept();
		require(scalar(test_connection,
			       "SELECT item_revision FROM item_current_owner WHERE item_uid=" +
				       std::to_string(uid + 1)) == revision &&
				scalar(test_connection,
				       "SELECT COUNT(*) FROM item_owner_audit WHERE item_uid=" +
					       std::to_string(uid + 1)) == audits,
			"rent retry changed custody or audit");
		auto old = rent;
		old.save_intent = RENT_CRASH;
		--old.revision;
		apply(old);
		kept();
		require(owner_of(uid + 1) == "8:0:0:2:" + std::to_string(uid + 1) + ":0",
			"stale save revived key");
		auto invalid = rent;
		invalid.items[1].object_uid = 0;
		invalid.items[0].vnum = 999;
		require(player_snapshot_repository_apply(test_connection, invalid).outcome ==
				player_save_apply_outcome::terminal_failure,
			"UID-less disposal accepted");
		kept();
	}
	auto recovery = snapshot_for(1, 300000, "Claimer");
	// Preserve the delivery sequence established by the preceding reward tests.
	recovery.status_integers.push_back(
		{ player_status_field::divine_boon_delivery_seq, 0, 3, true });
	recovery.status_integers.push_back({ player_status_field::epics, 500, 0, false });
	recovery.items = { item(4040991, 40401, -1) };
	recovery.items[0].type = ITEM_KEY;
	recovery.items[0].extra_flags = ITEM_NORENT;
	for (int intent :
	     { RENT_CRASH, RENT_CRASH2, RENT_QUIT, RENT_LINKDEAD, RENT_CAMPED, RENT_DEATH })
	{
		recovery.save_intent = intent;
		require(player_snapshot_repository_apply(test_connection, recovery).outcome ==
					player_save_apply_outcome::applied &&
				owner_of(4040991) == "1:1:0:1:4040991:0",
			"recovery lost key");
		++recovery.revision;
	}
	auto partial = recovery;
	partial.components = PLAYER_COMPONENT_STATUS;
	partial.save_intent = RENT_INN;
	require(player_snapshot_repository_apply(test_connection, partial).outcome ==
				player_save_apply_outcome::applied &&
			owner_of(4040991) == "1:1:0:1:4040991:0",
		"partial status disposed key");
	partial.components = PLAYER_COMPONENT_PETS;
	player_pet_snapshot pet_key{};
	pet_key.pet_uid = 4040992;
	pet_key.mob_vnum = 1201;
	pet_key.room_vnum = 3001;
	pet_key.items = recovery.items;
	pet_key.items[0].object_uid = 4040993;
	partial.pets = { pet_key };
	require(player_snapshot_repository_apply(test_connection, partial).outcome ==
				player_save_apply_outcome::applied &&
			owner_of(4040993) == "11:4040992:1:1:4040993:0",
		"pet rent disposed key");

	// Fail after the ownership update but before the replacement payload commits.
	recovery.save_intent = RENT_INN;
	execute(test_connection,
		"CREATE TRIGGER reject_rent_items BEFORE DELETE ON player_items FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='rent rollback probe'");
	const auto failed_rent = player_snapshot_repository_apply(test_connection, recovery);
	execute(test_connection, "DROP TRIGGER reject_rent_items");
	require(failed_rent.outcome == player_save_apply_outcome::terminal_failure &&
			owner_of(4040991) == "1:1:0:1:4040991:0" &&
			scalar(test_connection,
			       "SELECT COUNT(*) FROM player_items WHERE pid=1 AND obj_uid=4040991") ==
				"1" &&
			scalar(test_connection,
			       "SELECT COUNT(*) FROM item_owner_audit WHERE item_uid=4040991 AND new_owner_type=8") ==
				"0",
		"rent rollback split custody, audit or inventory");
	require(player_snapshot_repository_apply(test_connection, recovery).outcome ==
				player_save_apply_outcome::applied &&
			owner_of(4040991) == "8:0:0:2:4040991:0",
		"rent after rollback");
	std::cout
		<< "[PASS] rent placements, replay, recovery intents, partial saves and SQL rollback\n";

	// History and its player's quest after-image must be one transaction. A
	// rejected INSERT must not leave the task cleared; replay must not duplicate it.
	execute(test_connection, "INSERT INTO player_data(pid,name,quest_active,quest_mob_vnum) "
				 "VALUES (77777,'QuestProbe',1,15001)");
	auto quest = snapshot_for(77777, 400000, "QuestProbe");
	quest.components = PLAYER_COMPONENT_STATUS;
	quest.pending_world_quest = { true, 15001,	30,	      9000,
				      0,    1800000000, "QuestProbe", "a witness's reward" };
	execute(test_connection,
		"CREATE TRIGGER reject_quest_history BEFORE INSERT ON world_quest_accomplished "
		"FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='quest rollback probe'");
	require(player_snapshot_repository_apply(test_connection, quest).outcome ==
			player_save_apply_outcome::terminal_failure,
		"history refusal accepted the player snapshot");
	require(scalar(test_connection, "SELECT quest_active FROM player_data WHERE pid=77777") ==
				"1" &&
			scalar(test_connection,
			       "SELECT COUNT(*) FROM world_quest_accomplished WHERE pid=77777") ==
				"0",
		"history refusal cleared the quest or inserted a row");
	execute(test_connection, "DROP TRIGGER reject_quest_history");
	require(player_snapshot_repository_apply(test_connection, quest).outcome ==
			player_save_apply_outcome::applied,
		"quest snapshot did not commit after the failure was removed");
	require(player_snapshot_repository_apply(test_connection, quest).outcome ==
				player_save_apply_outcome::applied &&
			scalar(test_connection,
			       "SELECT quest_active FROM player_data WHERE pid=77777") == "0" &&
			scalar(test_connection,
			       "SELECT COUNT(*) FROM world_quest_accomplished WHERE pid=77777 AND quest_target=15001") ==
				"1" &&
			scalar(test_connection,
			       "SELECT reward_desc FROM world_quest_accomplished WHERE pid=77777 AND quest_target=15001") ==
				"a witness's reward",
		"quest snapshot replay lost status, duplicated history or altered its text");
	execute(test_connection, "UPDATE player_data SET quest_active=1 WHERE pid=77777");
	++quest.pending_world_quest.occurred_at;
	++quest.revision;
	require(player_snapshot_repository_apply(test_connection, quest).outcome ==
				player_save_apply_outcome::terminal_failure &&
			scalar(test_connection,
			       "SELECT quest_active FROM player_data WHERE pid=77777") == "1",
		"an unrelated older completion was mistaken for this retry");
	--quest.pending_world_quest.occurred_at;
	execute(test_connection,
		"UPDATE player_data SET wallet_revision=5,quest_active=1 WHERE pid=77777");
	quest.pending_world_quest.target = 15002;
	++quest.revision;
	require(player_snapshot_repository_apply(test_connection, quest).outcome ==
				player_save_apply_outcome::terminal_failure &&
			scalar(test_connection,
			       "SELECT quest_active FROM player_data WHERE pid=77777") == "1" &&
			scalar(test_connection,
			       "SELECT COUNT(*) FROM world_quest_accomplished WHERE pid=77777 AND quest_target=15002") ==
				"0",
		"stale wallet snapshot committed a quest completion");
	std::cout
		<< "[PASS] quest status/history transaction, rejection, replay and stale wallet\n";

	execute(test_connection,
		"UPDATE player_data SET wallet_revision=0,quest_active=1 WHERE pid=77777");
	quest.components = PLAYER_COMPONENT_STATUS | PLAYER_COMPONENT_EQUIPMENT |
			   PLAYER_COMPONENT_INVENTORY;
	quest.quest_values[0] = 1;
	quest.quest_values[1] = 15003;
	quest.quest_values[3] = PLAYER_WORLD_QUEST_REWARD_PENDING;
	quest.pending_world_quest.target = 15003;
	quest.pending_world_quest.awaiting_reward = true;
	quest.pending_world_quest.reward_items = { item(15003001, 1001, -1) };
	quest.pending_world_quest.reward_encoded_size = 1024;
	quest.items = quest.pending_world_quest.reward_items;
	++quest.revision;
	execute(test_connection,
		"CREATE TRIGGER reject_quest_history BEFORE INSERT ON world_quest_accomplished "
		"FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='reward rollback probe'");
	require(player_snapshot_repository_apply(test_connection, quest).outcome ==
				player_save_apply_outcome::terminal_failure &&
			scalar(test_connection,
			       "SELECT COUNT(*) FROM item_current_owner WHERE item_uid=15003001") ==
				"0" &&
			scalar(test_connection,
			       "SELECT COUNT(*) FROM player_items WHERE pid=77777 AND obj_uid=15003001") ==
				"0" &&
			scalar(test_connection,
			       "SELECT COUNT(*) FROM world_quest_accomplished WHERE pid=77777 AND quest_target=15003") ==
				"0",
		"history failure left a reward claim or payload behind");
	execute(test_connection, "DROP TRIGGER reject_quest_history");
	require(player_snapshot_repository_apply(test_connection, quest).outcome ==
				player_save_apply_outcome::applied &&
			player_snapshot_repository_apply(test_connection, quest).outcome ==
				player_save_apply_outcome::applied &&
			scalar(test_connection,
			       "SELECT quest_accomplished FROM player_data WHERE pid=77777") ==
				"2" &&
			scalar(test_connection,
			       "SELECT COUNT(*) FROM player_items WHERE pid=77777 AND obj_uid=15003001") ==
				"1" &&
			owner_of(15003001) == "1:77777:0:1:15003001:0" &&
			scalar(test_connection,
			       "SELECT COUNT(*) FROM world_quest_accomplished WHERE pid=77777 AND quest_target=15003") ==
				"1",
		"reward, history and recoverable quest marker did not commit once");
	execute(test_connection,
		"INSERT INTO item_current_owner (item_uid,root_item_uid,owner_type,owner_id,"
		"owner_context_id,item_revision,vnum,state) VALUES (15004001,15004001,1,2,0,1,1001,1)");
	quest.pending_world_quest.target = 15004;
	quest.pending_world_quest.reward_items = { item(15004001, 1001, -1) };
	quest.items = quest.pending_world_quest.reward_items;
	++quest.revision;
	require(player_snapshot_repository_apply(test_connection, quest).outcome ==
				player_save_apply_outcome::terminal_failure &&
			owner_of(15004001) == "1:2:0:1:15004001:0" &&
			scalar(test_connection,
			       "SELECT COUNT(*) FROM world_quest_accomplished WHERE pid=77777 AND quest_target=15004") ==
				"0",
		"a colliding reward UID stole another owner's item or recorded history");
	std::cout << "[PASS] quest reward custody, history, rollback, replay and UID collision\n";

	mysql_close(test_connection);
	mysql_library_end();
	std::cout << "player save claim MariaDB leg passed\n";
	return 0;
}
