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

	// Raw UID collisions must retain both roots regardless of which payload
	// parses first, while unrelated inventory remains writable.
	for (const int pid : { 31, 32 })
	{
		execute("INSERT INTO player_data(pid,name,account_name) VALUES(" +
			std::to_string(pid) + ",'Duplicate" + std::to_string(pid) +
			"','claim_probe')");
		const uint64_t stable_uid = 30000 + pid, duplicate_uid = 40000 + pid;
		require(player_snapshot_repository_apply(
				test_connection,
				save_holding(pid, 1,
					     { item(stable_uid, 601, PLAYER_SNAPSHOT_NO_PARENT) }))
					.outcome == player_save_apply_outcome::applied,
			"duplicate fixture seed");
		for (const int quantity : (pid == 31 ? std::vector{ 7, 1 } : std::vector{ 1, 7 }))
			execute("INSERT INTO player_items(pid,vnum,obj_uid,quantity) VALUES(" +
				std::to_string(pid) + ",900," + std::to_string(duplicate_uid) +
				"," + std::to_string(quantity) + ")");
		const auto duplicate_load = load(pid, pid);
		require(duplicate_load.outcome == player_load_outcome::applied &&
				loaded_uids(duplicate_load) ==
					std::vector<uint64_t>{ stable_uid } &&
				duplicate_load.snapshot.retained_items.rows.size() == 2,
			"valid/unreadable duplicate roots were not both retained");
		auto independent = save_holding(pid, 2, duplicate_load.snapshot.items);
		independent.retained_items = duplicate_load.snapshot.retained_items;
		independent.items[0].values[0] = 37;
		require(player_snapshot_repository_apply(test_connection, independent).outcome ==
				player_save_apply_outcome::applied,
			"duplicate evidence blocked unrelated inventory save");
		const auto reloaded = load(pid, 1000 + pid);
		require(reloaded.outcome == player_load_outcome::applied &&
				reloaded.snapshot.retained_items.rows.size() == 2 &&
				loaded_uids(reloaded) == std::vector<uint64_t>{ stable_uid } &&
				reloaded.snapshot.items[0].values[0] == 37,
			"duplicate evidence or unrelated update lost on reload");
	}

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

	// A legacy artifact without an identity cannot be decoded/materialized, but
	// its original row and metadata must survive an unrelated successful save.
	execute("INSERT INTO player_items(pid,vnum,obj_uid,quantity,weight,wear_flags,extra_flags,short_descr) "
		"VALUES(11,900,NULL,7,123,NULL,268435456,'retained legacy evidence')");
	const auto legacy_id = mysql_insert_id(test_connection);
	for (const auto &quantity : { std::string("NULL"), std::string("0") })
	{
		execute("UPDATE player_items SET quantity=" + quantity +
			" WHERE id=" + std::to_string(legacy_id));
		const auto raw_load = load(11, 9009);
		const auto raw = std::find_if(raw_load.item_sources.begin(),
					      raw_load.item_sources.end(), [&](const auto &source)
					      { return source.row_id == legacy_id; });
		require(raw_load.outcome == player_load_outcome::applied &&
				raw != raw_load.item_sources.end() &&
				raw->quantity_present == (quantity == "0") && raw->quantity == 0,
			"raw quantity presence was lost or fabricated");
	}
	execute("UPDATE player_items SET quantity=7 WHERE id=" + std::to_string(legacy_id));
	execute("INSERT INTO player_items(pid,vnum,obj_uid,container_id,quantity) VALUES(11,901,2099," +
		std::to_string(legacy_id) + ",1)");
	execute("INSERT INTO player_item_affects(item_id,location,modifier) VALUES(" +
		std::to_string(legacy_id) + ",1,77)");
	execute("INSERT INTO player_item_extra_descr(item_id,keyword,description) VALUES(" +
		std::to_string(legacy_id) + ",'legacy','unchanged details')");
	const player_load_result giver = load(11, 1);
	require(giver.gameplay_items && !giver.item_sources.empty(),
		"gameplay source cut was not retained");
	bool inactive_source_seen = false;
	for (const auto &source : giver.item_sources)
		if (source.item_uid == 2005)
			inactive_source_seen = source.custody_found &&
					       source.custody.state != item_custody_state::active;
	require(inactive_source_seen, "load normalization hid the raw inactive custody state");
	bool raw_legacy_seen = false, foreign_seen = false;
	for (const auto &source : giver.item_sources)
	{
		if (source.row_id == legacy_id)
			raw_legacy_seen = source.vnum == 900 && !source.item_uid &&
					  source.quantity == 7 && source.extra_flags_present &&
					  source.extra_flags == 268435456;
		if (source.item_uid == 2003)
			foreign_seen = source.vnum == 603 && source.custody_found &&
				       source.custody.owner.id == 12;
	}
	require(raw_legacy_seen && foreign_seen,
		"inspection lost unreadable or foreign raw source metadata");
	require(giver.outcome == player_load_outcome::applied,
		"the giver's load must succeed: outcome=" +
			std::to_string(static_cast<int>(giver.outcome)) +
			" component=" + (giver.failed_component ? giver.failed_component : "none"));
	require((loaded_uids(giver) == std::vector<uint64_t>{ 2001, 2002, 2004, 2005 }),
		"the giver loads its own items, the unrecorded one and the quarantined one, "
		"but not the sword the taker now holds");
	require(giver.stale_item_rows == 2, "the stale sword row is counted");
	const auto foreign_source = std::find_if(giver.item_sources.begin(),
						 giver.item_sources.end(), [](const auto &source)
						 { return source.item_uid == 2003; });
	require(foreign_source != giver.item_sources.end() && foreign_source->vnum == 603 &&
			foreign_source->quantity_present && foreign_source->quantity == 1 &&
			foreign_source->extra_flags_present && foreign_source->custody_found &&
			foreign_source->custody_owner_revision_found &&
			foreign_source->custody.owner.id == 12,
		"filtered foreign source lost payload or revision evidence");
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
	auto next_save = giver.snapshot;
	next_save.revision = 2;
	next_save.components = PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY;
	next_save.encoded_size_bound = 4096;
	next_save.items = { item(2001, 601, PLAYER_SNAPSHOT_NO_PARENT), item(2002, 602, 0) };
	require(player_snapshot_repository_apply(test_connection, next_save).outcome ==
			player_save_apply_outcome::applied,
		"the giver's next save");
	const std::string retention_query =
		"SELECT p.id FROM player_items p JOIN player_item_affects a ON a.item_id=p.id AND a.location=1 AND a.modifier=77 "
		"JOIN player_item_extra_descr d ON d.item_id=p.id AND d.keyword='legacy' AND d.description='unchanged details' "
		"JOIN player_items child ON child.container_id=p.id AND child.obj_uid=2099 "
		"LEFT JOIN item_current_owner held ON held.item_uid=2099 WHERE p.id=" +
		std::to_string(legacy_id) +
		" AND p.obj_uid IS NULL AND p.quantity=7 AND p.weight=123 AND p.wear_flags IS NULL AND p.extra_flags=268435456 "
		"AND p.short_descr='retained legacy evidence' AND held.item_uid IS NULL";
	execute(retention_query);
	MYSQL_RES *retained = mysql_store_result(test_connection);
	require(retained && mysql_num_rows(retained) == 1,
		"a successful unrelated save erased the undecodable legacy payload");
	mysql_free_result(retained);
	// A pet graph is also active payload; it cannot claim a UID retained in
	// inventory while leaving the original source row intact.
	auto pet_overlap = next_save;
	pet_overlap.revision = 3;
	pet_overlap.components |= PLAYER_COMPONENT_PETS;
	player_pet_snapshot conflicting_pet = {};
	conflicting_pet.pet_uid = 22001;
	conflicting_pet.mob_vnum = 700;
	conflicting_pet.items = { item(2099, 901, PLAYER_SNAPSHOT_NO_PARENT) };
	pet_overlap.pets = { conflicting_pet };
	const auto pet_refused = player_snapshot_repository_apply(test_connection, pet_overlap);
	require(pet_refused.outcome == player_save_apply_outcome::terminal_failure &&
			pet_refused.error_code == ESTALE,
		"active pet/retained inventory overlap was accepted");
	execute("SELECT item_uid FROM item_current_owner WHERE item_uid=2099");
	MYSQL_RES *unclaimed = mysql_store_result(test_connection);
	require(unclaimed && mysql_num_rows(unclaimed) == 0,
		"refused pet save claimed retained UID");
	mysql_free_result(unclaimed);
	// A stale/overlapping capture must fail before it can claim held descendants.
	auto overlapping = next_save;
	overlapping.revision = 3;
	overlapping.items.push_back(item(2099, 901, PLAYER_SNAPSHOT_NO_PARENT));
	require(player_snapshot_repository_apply(test_connection, overlapping).outcome ==
			player_save_apply_outcome::terminal_failure,
		"active/held overlap was accepted");
	execute("INSERT INTO player_items(pid,vnum,obj_uid,container_id,quantity) VALUES(11,902,NULL," +
		std::to_string(legacy_id) + ",1)");
	const auto new_child = mysql_insert_id(test_connection);
	auto stale_source = next_save;
	stale_source.revision = 3;
	require(player_snapshot_repository_apply(test_connection, stale_source).outcome ==
			player_save_apply_outcome::terminal_failure,
		"a changed retained component was silently overwritten");
	execute("DELETE FROM player_items WHERE id=" + std::to_string(new_child));
	execute(retention_query);
	retained = mysql_store_result(test_connection);
	require(retained && mysql_num_rows(retained) == 1,
		"failed saves changed retained evidence or custody");
	mysql_free_result(retained);
	const player_load_result again = load(11, 3);
	require(again.outcome == player_load_outcome::applied && again.stale_item_rows == 1 &&
			(loaded_uids(again) == std::vector<uint64_t>{ 2001, 2002 }),
		"after its next save the giver has no stale rows left");

	// Discoveries and their EXP are one status checkpoint, scoped to the character.
	const auto progress = [&](int pid)
	{
		const auto result = load(pid, 100 + pid);
		require(result.outcome == player_load_outcome::applied,
			"flight status load failed");
		uint64_t stops = 0;
		int64_t experience = 0;
		bool found = false;
		for (const auto &field : result.snapshot.status_integers)
		{
			if (field.field == player_status_field::learned_flight_stops)
			{
				require(field.is_unsigned, "flight mask was loaded as signed");
				stops = field.unsigned_value;
				found = true;
			}
			if (field.field == player_status_field::experience)
				experience = field.signed_value;
		}
		require(found, "flight status field is missing");
		return std::pair(stops, experience);
	};
	require(progress(11).first == 0 && progress(12).first == 0,
		"new SQL characters must start without discoveries");
	player_snapshot discovery = {};
	discovery.schema_version = PLAYER_SNAPSHOT_SCHEMA_VERSION;
	discovery.pid = 11;
	discovery.revision = 3;
	discovery.components = PLAYER_COMPONENT_STATUS;
	discovery.encoded_size_bound = 4096;
	discovery.status_integers = {
		{ player_status_field::learned_flight_stops, 0, (uint64_t{ 1 } << 26) | 1, true },
		{ player_status_field::experience, 12345, 0, false },
	};
	require(player_snapshot_repository_apply(test_connection, discovery).outcome ==
			player_save_apply_outcome::applied,
		"discovery checkpoint failed");
	const auto saved_progress = progress(11);
	require(saved_progress == std::pair((uint64_t{ 1 } << 26) | 1, int64_t{ 12345 }) &&
			progress(12).first == 0,
		"discovery checkpoint mixed account siblings");
	discovery.components = PLAYER_COMPONENT_LANGUAGES;
	discovery.revision++;
	require(player_snapshot_repository_apply(test_connection, discovery).outcome ==
				player_save_apply_outcome::applied &&
			progress(11) == saved_progress,
		"unrelated SQL component save changed flight progress");
	execute("CREATE TRIGGER reject_flight_save BEFORE UPDATE ON player_data FOR EACH ROW "
		"SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='synthetic save failure'");
	discovery.components = PLAYER_COMPONENT_STATUS;
	discovery.revision++;
	discovery.status_integers[0].unsigned_value = 7;
	discovery.status_integers[1].signed_value = 54321;
	require(player_snapshot_repository_apply(test_connection, discovery).outcome ==
				player_save_apply_outcome::terminal_failure &&
			progress(11) == saved_progress,
		"failed save retained only one half of discovery progress");
	execute("DROP TRIGGER reject_flight_save");
	require(player_snapshot_repository_apply(test_connection, discovery).outcome ==
				player_save_apply_outcome::applied &&
			progress(11) == std::pair(uint64_t{ 7 }, int64_t{ 54321 }),
		"discovery checkpoint retry failed");

	mysql_close(test_connection);
	mysql_library_end();
	std::cout << "player load filter MariaDB leg passed\n";
	return 0;
}
