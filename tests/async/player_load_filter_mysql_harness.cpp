// A load takes an item row only when item_current_owner has no row for its uid or
// names the loading character. A stale copy another owner holds is skipped and
// logged to the dupe log. This drives the real save and load repositories against
// a real server: the first player saves holding an item, the second player's save
// claims it, and the first player's next load leaves the stale row behind.
#include "persistence/dupe_log.h"
#include "persistence/persistence_observability.h"
#include "player/player_load_repository.h"
#include "player/player_save_worker.h"
#include "player/player_snapshot_repository.h"
#include "sql/sql_pool.h"

#include <algorithm>
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

void execute(const std::string &sql)
{
	require(mysql_query(test_connection, sql.c_str()) == 0,
		"query failed: " + sql + ": " + mysql_error(test_connection));
}

player_item_snapshot item(uint64_t uid, int32_t vnum, int32_t parent)
{
	player_item_snapshot snapshot = {};
	snapshot.parent_index = parent;
	snapshot.object_uid = uid;
	snapshot.vnum = vnum;
	snapshot.type = 12;
	return snapshot;
}

player_snapshot save_holding(int pid, player_revision_t revision,
			     std::vector<player_item_snapshot> items)
{
	player_snapshot snapshot = {};
	snapshot.schema_version = PLAYER_SNAPSHOT_SCHEMA_VERSION;
	snapshot.pid = pid;
	snapshot.revision = revision;
	snapshot.components = PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY;
	snapshot.encoded_size_bound = 4096;
	snapshot.items = std::move(items);
	return snapshot;
}

std::vector<uint64_t> loaded_uids(const player_load_result &result)
{
	std::vector<uint64_t> uids;
	for (const player_item_snapshot &entry : result.snapshot.items)
		uids.push_back(entry.object_uid);
	std::sort(uids.begin(), uids.end());
	return uids;
}

player_load_result load(int pid, uint64_t request_id)
{
	player_load_request request = {};
	request.request_id = request_id;
	request.pid = pid;
	request.account_name = "claim_probe";
	request.include_items = true;
	request.include_pets = true;
	request.deadline_usec = persistence_observability_now_usec() + PLAYER_LOAD_TIMEOUT_USEC;
	return player_load_repository_execute(test_connection, request);
}
} // namespace

MYSQL *sql_pool_acquire(void)
{
	return test_connection;
}
void sql_pool_release(MYSQL *) {}
MYSQL *sql_pool_replace_connection(MYSQL *)
{
	return nullptr;
}
char *sql_escape_string(const char *)
{
	std::abort();
}

int main()
{
	require(!mysql_library_init(0, nullptr, nullptr), "could not initialize the MySQL client");
	test_connection = mysql_init(nullptr);
	require(test_connection != nullptr, "could not allocate a MySQL connection");
	const unsigned int port = static_cast<unsigned int>(
		std::strtoul(environment("DB_PORT", "3306").c_str(), nullptr, 10));
	require(mysql_real_connect(test_connection, environment("DB_HOST", "127.0.0.1").c_str(),
				   environment("DB_USER", "root").c_str(),
				   environment("DB_PASSWD", "").c_str(),
				   environment("DB_NAME", "player_save_claim_test").c_str(), port,
				   nullptr, 0) != nullptr,
		std::string("could not connect: ") + mysql_error(test_connection));
	execute("SET SESSION sql_mode='STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,"
		"NO_ENGINE_SUBSTITUTION'");
	const std::string dupe_log = environment("DUPE_LOG_PATH_FOR_TEST", "/tmp/dupes");
	dupe_log_set_path_for_tests(dupe_log.c_str());
	execute("INSERT INTO player_data(pid,name,account_name) VALUES "
		"(11,'Giver','claim_probe'),(12,'Taker','claim_probe')");

	// The giver saves holding a bag with a gem in it, and a sword.
	require(player_snapshot_repository_apply(
			test_connection,
			save_holding(11, 1,
				     { item(2001, 601, PLAYER_SNAPSHOT_NO_PARENT),
				       item(2002, 602, 0),
				       item(2003, 603, PLAYER_SNAPSHOT_NO_PARENT) }))
				.outcome == player_save_apply_outcome::applied,
		"the giver's save");
	// The sword changes hands; the taker's save lands before the giver's next one.
	require(player_snapshot_repository_apply(
			test_connection,
			save_holding(12, 1, { item(2003, 603, PLAYER_SNAPSHOT_NO_PARENT) }))
				.outcome == player_save_apply_outcome::applied,
		"the taker's save");
	// A payload row nobody ever recorded, and one of the giver's own items whose
	// ownership row was quarantined by an old death.
	execute("INSERT INTO player_items (pid,vnum,equip_slot,container_id,quantity,item_type,"
		"obj_uid) VALUES (11,604,0,NULL,1,0,2004),(11,605,0,NULL,1,0,2005)");
	execute("INSERT INTO item_current_owner (item_uid,root_item_uid,parent_item_uid,owner_type,"
		"owner_id,owner_context_id,item_revision,vnum,state) VALUES "
		"(2005,2005,NULL,1,11,0,1,605,3)");

	const player_load_result giver = load(11, 1);
	require(giver.outcome == player_load_outcome::applied,
		"the giver's load must succeed: outcome=" +
			std::to_string(static_cast<int>(giver.outcome)) +
			" component=" + (giver.failed_component ? giver.failed_component : "none"));
	require((loaded_uids(giver) == std::vector<uint64_t>{ 2001, 2002, 2004, 2005 }),
		"the giver loads its own items, the unrecorded one and the quarantined one, "
		"but not the sword the taker now holds");
	require(giver.stale_item_rows == 1, "the stale sword row is counted");
	for (size_t index = 0; index < giver.snapshot.items.size(); ++index)
		if (giver.snapshot.items[index].object_uid == 2002)
			require(giver.snapshot.items[index].parent_index >= 0 &&
					giver.snapshot.items[giver.snapshot.items[index].parent_index]
							.object_uid == 2001,
				"the gem stays in the bag");

	const player_load_result taker = load(12, 2);
	require(taker.outcome == player_load_outcome::applied &&
			(loaded_uids(taker) == std::vector<uint64_t>{ 2003 }),
		"the taker loads the sword");

	std::ifstream log(dupe_log);
	std::stringstream lines;
	lines << log.rdbuf();
	require(lines.str().find("load_skipped uid=2003 vnum=603 lost_by=player:11:0 "
				 "held_by=player:12:0") != std::string::npos,
		"the dupe log names the skipped sword: " + lines.str());

	// The giver's next save removes the stale row for good.
	require(player_snapshot_repository_apply(
			test_connection, save_holding(11, 2,
						      { item(2001, 601, PLAYER_SNAPSHOT_NO_PARENT),
							item(2002, 602, 0) }))
				.outcome == player_save_apply_outcome::applied,
		"the giver's next save");
	const player_load_result again = load(11, 3);
	require(again.outcome == player_load_outcome::applied && again.stale_item_rows == 0 &&
			(loaded_uids(again) == std::vector<uint64_t>{ 2001, 2002 }),
		"after its next save the giver has no stale rows left");

	mysql_close(test_connection);
	mysql_library_end();
	std::cout << "player load filter MariaDB leg passed\n";
	return 0;
}
