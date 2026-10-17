#include "guild/artifact_population_repository.h"

#include "economy/collector_codec.h"
#include "core/files.h"
#include "core/defines.h"
#include "player/player_snapshot_codec.h"

#include <algorithm>
#include <array>
#include <cassert>
#include <cerrno>
#include <chrono>
#include <cstring>
#include <thread>
#include <cstdlib>
#include <iostream>
#include <string>
#include <unistd.h>

static MYSQL *connect()
{
	assert(std::string(getenv("TEST_DB_HOST")) == "127.0.0.1");
	MYSQL *connection = mysql_init(nullptr);
	assert(connection && mysql_real_connect(connection, getenv("TEST_DB_HOST"),
						getenv("TEST_DB_USER"), getenv("TEST_DB_PASSWORD"),
						nullptr, atoi(getenv("TEST_DB_PORT")), nullptr, 0));
	return connection;
}

static void query(MYSQL *connection, const std::string &sql)
{
	if (mysql_real_query(connection, sql.data(), sql.size()))
	{
		std::cerr << mysql_error(connection) << '\n';
		std::abort();
	}
}

static void blob_checks(MYSQL *connection, const std::string &database);

int main(int argc, char **argv)
{
	MYSQL *connection = connect();
	if (argc == 2)
	{
		const std::string database = argv[1];
		assert(database.starts_with("duris_artifact_population_"));
		assert(mysql_select_db(connection, database.c_str()) == 0);
		for (unsigned int domain = 0;
		     domain <= static_cast<unsigned>(artifact_payload_domain::siege); ++domain)
		{
			artifact_population_sql_page page;
			assert(!artifact_population_read_sql_page(
				connection, static_cast<artifact_payload_domain>(domain), 0,
				&page));
			assert(page.complete && page.rows.empty());
		}
		blob_checks(connection, database);
		mysql_close(connection);
		std::cout
			<< "numeric and blob population readers accept the actual current schema\n";
		return 0;
	}
	assert(argc == 1);
	const std::string database = "duris_artifact_population_" + std::to_string(getpid());
	query(connection, "CREATE DATABASE " + database);
	assert(mysql_select_db(connection, database.c_str()) == 0);
	query(connection,
	      "CREATE TABLE item_current_owner(item_uid BIGINT UNSIGNED PRIMARY KEY,"
	      "root_item_uid BIGINT UNSIGNED,parent_item_uid BIGINT UNSIGNED,"
	      "owner_type TINYINT UNSIGNED,owner_id BIGINT UNSIGNED,"
	      "owner_context_id BIGINT UNSIGNED,item_revision BIGINT UNSIGNED,vnum INT,state TINYINT UNSIGNED) ENGINE=InnoDB");
	query(connection,
	      "CREATE TABLE item_ownership_quarantine(item_uid BIGINT UNSIGNED,source_table VARCHAR(64),source_row_id BIGINT UNSIGNED,repaired_at TIMESTAMP NULL)");
	query(connection,
	      "CREATE TABLE item_owner_revision(owner_type TINYINT UNSIGNED,"
	      "owner_id BIGINT UNSIGNED,owner_context_id BIGINT UNSIGNED,revision BIGINT UNSIGNED,"
	      "PRIMARY KEY(owner_type,owner_id,owner_context_id)) ENGINE=InnoDB");
	query(connection,
	      "CREATE TABLE player_pets(id INT PRIMARY KEY,pet_uid BIGINT UNSIGNED,owner_pid INT)");
	query(connection, "INSERT INTO player_pets VALUES(42,420042,77)");
	query(connection,
	      "CREATE TABLE corpses(id INT PRIMARY KEY,player_name VARCHAR(50),save_id BIGINT,value3 INT)");
	query(connection, "CREATE TABLE player_data(pid INT PRIMARY KEY,name VARCHAR(50))");
	query(connection, "INSERT INTO corpses VALUES(42,'Fixture',9,77)");
	query(connection, "INSERT INTO player_data VALUES(77,'Fixture')");
	query(connection,
	      "CREATE TABLE private_chests(id INT PRIMARY KEY,locker_id INT,is_public TINYINT)");
	query(connection, "INSERT INTO private_chests VALUES(1042,42,1)");
	query(connection, "CREATE TABLE shopkeepers(id INT PRIMARY KEY,shop_id INT)");
	query(connection, "INSERT INTO shopkeepers VALUES(42,123)");
	struct source
	{
		artifact_payload_domain domain;
		const char *table;
		const char *owner;
	};
	const source sources[] = {
		{ artifact_payload_domain::player, "player_items", "pid" },
		{ artifact_payload_domain::pet, "player_pet_items", "pet_id" },
		{ artifact_payload_domain::locker, "locker_items", "locker_id" },
		{ artifact_payload_domain::account_locker, "account_locker_items", "chest_id" },
		{ artifact_payload_domain::corpse, "corpse_items", "corpse_id" },
		{ artifact_payload_domain::room, "saved_items", "room_vnum" },
		{ artifact_payload_domain::shopkeeper, "shopkeeper_items", "shopkeeper_id" },
		{ artifact_payload_domain::siege, "siege_items", "room_vnum" },
	};
	for (const source &entry : sources)
	{
		query(connection,
		      "CREATE TABLE " + std::string(entry.table) +
			      "(id BIGINT UNSIGNED PRIMARY KEY,obj_uid BIGINT UNSIGNED NULL,"
			      "container_id BIGINT UNSIGNED NULL,vnum INT,extra_flags BIGINT UNSIGNED," +
			      entry.owner + " INT" +
			      (entry.domain == artifact_payload_domain::pet ? "" :
									      ",quantity INT") +
			      (entry.domain == artifact_payload_domain::locker ? ",chest_id INT" :
										 "") +
			      (entry.domain == artifact_payload_domain::room ?
				       ",item_key VARCHAR(64) NOT NULL DEFAULT 'fixture'" :
				       "") +
			      ") ENGINE=InnoDB");
		query(connection, "INSERT INTO " + std::string(entry.table) +
					  "(id,obj_uid,container_id,vnum,extra_flags," +
					  entry.owner +
					  ") VALUES(1,18446744073709551615,NULL,900,268435456,42),"
					  "(2,NULL,1,901,268435456,43)");
		artifact_population_sql_page page;
		assert(!artifact_population_read_sql_page(connection, entry.domain, 0, &page));
		assert(page.complete && page.next_row_id == 2 && page.rows.size() == 2 &&
		       page.rows[0].custody_examined && page.rows[1].custody_examined);
		assert(page.rows[0].item_uid == UINT64_MAX && page.rows[0].owner_reference == 42);
		assert(page.rows[1].extra_flags == (1U << 28) && page.rows[1].extra_flags_present &&
		       !page.rows[1].item_uid && page.rows[1].parent_row_id == 1 &&
		       page.rows[1].parent_item_uid == UINT64_MAX &&
		       page.rows[1].parent_owner_disagrees && !page.rows[1].custody_found);
		if (entry.domain == artifact_payload_domain::pet)
		{
			assert(page.rows[0].quantity == 1); // pet rows have no quantity column
			assert(page.rows[0].payload_owner.type == item_owner_type::pet &&
			       page.rows[0].payload_owner.id == 420042 &&
			       page.rows[0].payload_owner.context_id == 77 &&
			       page.rows[1].payload_owner.id == 0);
		}
		if (entry.domain == artifact_payload_domain::corpse)
			assert(page.rows[0].payload_owner.type == item_owner_type::corpse &&
			       page.rows[0].payload_owner.id == ((77ULL << 32) | 9) &&
			       page.rows[1].payload_owner.id == 0);
		if (entry.domain == artifact_payload_domain::locker)
			assert(page.rows[0].payload_owner.type == item_owner_type::locker &&
			       page.rows[0].payload_owner.id == 42 &&
			       page.rows[0].payload_owner.context_id == 1042);
		if (entry.domain == artifact_payload_domain::shopkeeper)
			assert(page.rows[0].payload_owner.type == item_owner_type::shopkeeper &&
			       page.rows[0].payload_owner.id == 124);
		if (entry.domain == artifact_payload_domain::account_locker ||
		    entry.domain == artifact_payload_domain::siege)
			assert(page.rows[0].payload_owner.type == item_owner_type::unknown);
	}
	query(connection, "UPDATE player_pet_items SET obj_uid=0 WHERE id=2");
	query(connection, "UPDATE shopkeeper_items SET obj_uid=0 WHERE id=2");
	query(connection,
	      "INSERT INTO item_ownership_quarantine(item_uid,source_table,source_row_id) VALUES(0,'player_pet_items',2)");
	artifact_population_sql_page zero_uid_page;
	assert(!artifact_population_read_sql_page(connection, artifact_payload_domain::pet, 0,
						  &zero_uid_page));
	assert(zero_uid_page.rows[1].source_quarantined);
	assert(!artifact_population_read_sql_page(connection, artifact_payload_domain::shopkeeper,
						  0, &zero_uid_page));
	assert(!zero_uid_page.rows[1].source_quarantined &&
	       "zero UID quarantine leaked across sources");
	query(connection, "DELETE FROM item_ownership_quarantine WHERE item_uid=0");

	query(connection, "INSERT INTO player_pets VALUES(44,NULL,78)");
	query(connection,
	      "INSERT INTO player_pet_items(id,obj_uid,vnum,extra_flags,pet_id) VALUES(3,444,900,268435456,44)");
	artifact_population_sql_page legacy_pet;
	assert(!artifact_population_read_sql_page(connection, artifact_payload_domain::pet, 0,
						  &legacy_pet));
	assert(legacy_pet.rows.size() == 3 &&
	       legacy_pet.rows[2].payload_owner.type == item_owner_type::player &&
	       legacy_pet.rows[2].payload_owner.id == 78 &&
	       legacy_pet.rows[2].payload_owner.context_id == 0);
	query(connection,
	      "UPDATE saved_items SET room_vnum=42,item_key='different-source' WHERE id=2");
	artifact_population_sql_page room_keys;
	assert(!artifact_population_read_sql_page(connection, artifact_payload_domain::room, 0,
						  &room_keys));
	assert(room_keys.rows[1].parent_owner_disagrees &&
	       "saved-room parent from another item key was treated as the same source");
	query(connection, "UPDATE saved_items SET item_key='fixture' WHERE id=2");
	assert(!artifact_population_read_sql_page(connection, artifact_payload_domain::room, 0,
						  &room_keys));
	assert(!room_keys.rows[1].parent_owner_disagrees);
	query(connection, "UPDATE saved_items SET room_vnum=43 WHERE id=2");
	// A corpse's stable owner survives both a display-name change and character deletion.
	for (const char *change : { "UPDATE player_data SET name='Renamed' WHERE pid=77",
				    "DELETE FROM player_data WHERE pid=77" })
	{
		query(connection, change);
		artifact_population_sql_page corpses;
		assert(!artifact_population_read_sql_page(
			connection, artifact_payload_domain::corpse, 0, &corpses));
		assert(corpses.rows[0].payload_owner.id == ((77ULL << 32) | 9) &&
		       "corpse owner identity depended on the current player display name");
	}
	query(connection,
	      "INSERT INTO saved_items(id,obj_uid,container_id,vnum,extra_flags,room_vnum) "
	      "VALUES(3,333,999,900,NULL,42)");
	artifact_population_sql_page page;
	assert(!artifact_population_read_sql_page(connection, artifact_payload_domain::room, 0,
						  &page));
	assert(page.rows.size() == 3 && page.rows[2].parent_missing &&
	       page.rows[2].parent_row_id == 999 && !page.rows[2].parent_item_uid &&
	       !page.rows[2].extra_flags_present);
	query(connection, "UPDATE locker_items SET locker_id=42,chest_id=id+100");
	assert(!artifact_population_read_sql_page(connection, artifact_payload_domain::locker, 0,
						  &page));
	assert(page.rows[1].parent_owner_disagrees && page.rows[1].owner_context == 102);
	for (const auto &contexts :
	     { std::pair{ "101", "NULL" }, std::pair{ "NULL", "102" }, std::pair{ "NULL", "NULL" },
	       std::pair{ "1042", "NULL" }, std::pair{ "NULL", "1042" } })
	{
		query(connection, std::string("UPDATE locker_items SET chest_id=") +
					  contexts.first + " WHERE id=1");
		query(connection, std::string("UPDATE locker_items SET chest_id=") +
					  contexts.second + " WHERE id=2");
		assert(!artifact_population_read_sql_page(
			connection, artifact_payload_domain::locker, 0, &page));
		const bool conflict = std::string(contexts.first) == "101" ||
				      std::string(contexts.second) == "102";
		assert(page.rows[1].parent_owner_disagrees == conflict &&
		       "legacy NULL chest context was not normalized before parent comparison");
	}
	query(connection, "INSERT INTO item_current_owner VALUES"
			  "(18446744073709551615,18446744073709551615,NULL,1,77,0,9,902,3),"
			  "(999999,999999,NULL,1,42,0,1,900,1)");
	query(connection, "INSERT INTO item_owner_revision VALUES(1,77,0,12)");
	assert(!artifact_population_read_sql_page(connection, artifact_payload_domain::player, 0,
						  &page));
	assert(page.rows.size() == 2 && page.rows[0].custody_found &&
	       page.rows[0].custody.item_uid == UINT64_MAX && page.rows[0].custody.owner.id == 77 &&
	       page.rows[0].custody.item_revision == 9 &&
	       page.rows[0].custody.owner_revision == 12 &&
	       page.rows[0].custody_owner_revision_found && page.rows[0].custody.vnum == 902 &&
	       page.rows[0].custody.state == item_custody_state::quarantined);
	query(connection, "UPDATE item_owner_revision SET revision=0 WHERE owner_id=77");
	assert(!artifact_population_read_sql_page(connection, artifact_payload_domain::player, 0,
						  &page));
	assert(page.rows[0].custody_found && page.rows[0].custody_owner_revision_found &&
	       page.rows[0].custody.owner_revision == 0);
	query(connection, "DELETE FROM item_owner_revision WHERE owner_id=77");
	assert(!artifact_population_read_sql_page(connection, artifact_payload_domain::player, 0,
						  &page));
	assert(page.rows[0].custody_found && !page.rows[0].custody_owner_revision_found &&
	       page.rows[0].custody.owner_revision == 0);
	query(connection, "INSERT INTO item_owner_revision VALUES(1,77,0,12)");
	for (size_t id = 3; id <= ARTIFACT_POPULATION_SQL_PAGE_SIZE + 1; ++id)
		query(connection,
		      "INSERT INTO player_items(id,obj_uid,vnum,extra_flags,pid) VALUES(" +
			      std::to_string(id) + "," + std::to_string(id + 1000) + ",900,0,42)");
	query(connection, "START TRANSACTION WITH CONSISTENT SNAPSHOT");
	assert(!artifact_population_read_sql_page(connection, artifact_payload_domain::player, 0,
						  &page));
	assert(!page.complete && page.rows.size() == ARTIFACT_POPULATION_SQL_PAGE_SIZE &&
	       page.next_row_id == ARTIFACT_POPULATION_SQL_PAGE_SIZE);
	MYSQL *other = connect();
	assert(mysql_select_db(other, database.c_str()) == 0);
	query(other,
	      "INSERT INTO player_items(id,obj_uid,vnum,extra_flags,pid) VALUES(1000,1000,900,0,42)");
	assert(!artifact_population_read_sql_page(connection, artifact_payload_domain::player,
						  page.next_row_id, &page));
	assert(page.complete && page.rows.size() == 1 &&
	       page.next_row_id == ARTIFACT_POPULATION_SQL_PAGE_SIZE + 1);
	query(connection, "ROLLBACK");
	assert(!artifact_population_read_sql_page(connection, artifact_payload_domain::player,
						  page.next_row_id, &page));
	assert(page.complete && page.rows.size() == 1 && page.next_row_id == 1000);
	for (size_t id = 3; id <= ARTIFACT_POPULATION_SQL_PAGE_SIZE; ++id)
		query(connection,
		      "INSERT INTO locker_items(id,obj_uid,vnum,extra_flags,locker_id) VALUES(" +
			      std::to_string(id) + "," + std::to_string(id + 2000) +
			      ",900,268435456," +
			      (id == ARTIFACT_POPULATION_SQL_PAGE_SIZE ? "88)" : "77)"));
	query(connection, "INSERT INTO private_chests VALUES(1088,88,1),(2088,88,1)");
	const auto *before_ambiguous = page.rows.data();
	assert(artifact_population_read_sql_page(connection, artifact_payload_domain::locker, 0,
						 &page) == EINVAL);
	assert(page.rows.data() == before_ambiguous && page.next_row_id == 1000);
	query(connection, "DROP TABLE siege_items");
	const auto *retained = page.rows.data();
	assert(artifact_population_read_sql_page(connection, artifact_payload_domain::siege, 0,
						 &page));
	assert(page.rows.data() == retained && page.rows.size() == 1 && page.next_row_id == 1000);
	assert(artifact_population_read_sql_page(
		       connection, static_cast<artifact_payload_domain>(255), 0, &page) == EINVAL);
	mysql_close(other);
	query(connection, "DROP DATABASE " + database);
	mysql_close(connection);
	std::cout << "SQL physical payload pages preserve all eight sources, legacy/unknown UIDs, "
		     "custody conflicts, stable continuations and failed-read atomicity\n";
}

static std::string hex(const uint8_t *data, size_t size)
{
	std::string result = "X'";
	for (size_t index = 0; index < size; ++index)
	{
		result += "0123456789abcdef"[data[index] >> 4];
		result += "0123456789abcdef"[data[index] & 15];
	}
	return result + "'";
}

static std::string legacy_blob(uint64_t uid)
{
	std::vector<uint8_t> data;
	auto native = [&]<typename T>(T value)
	{
		const auto *first = reinterpret_cast<const uint8_t *>(&value);
		data.insert(data.end(), first, first + sizeof(value));
	};
	native(uint8_t{ SAV_ITEMVERS });
	native(uint32_t{ 1 });
	native(static_cast<uint8_t>(O_F_UNIQUE | (uid ? O_F_UID : 0))); // UNIQUE, optional UID
	native(int32_t{ 900 });
	native(int16_t{ 0 });
	native(int16_t{ 100 });
	if (uid)
		native(uid);
	native(uint32_t{ O_U_EXTRA }); // explicit EXTRA override
	native(uint32_t{ 1U << 28 });
	native(uint8_t{ O_F_EOL }); // EOL
	return hex(data.data(), data.size());
}

static std::string modern_blob(uint64_t uid, bool money = false, int negative_value = -1,
			       int slot = 0)
{
	player_item_snapshot item = {};
	item.parent_index = PLAYER_SNAPSHOT_NO_PARENT;
	item.equipment_slot = slot;
	item.vnum = 900;
	item.object_uid = uid;
	item.extra_flags = 0; // explicit zero must override an artifact prototype
	if (money)
	{
		item.type = ITEM_MONEY;
		item.values.fill(0);
	}
	if (negative_value >= 0)
		item.values[negative_value] = -1;
	std::vector<uint8_t> bytes;
	assert(player_item_snapshot_list_encode({ item }, &bytes) ==
	       player_snapshot_codec_result::ok);
	return hex(bytes.data(), bytes.size());
}

static void blob_checks(MYSQL *connection, const std::string &database)
{
	std::vector<artifact_payload_projection> population;
	assert(!artifact_population_read_sql_payloads(connection, &population) &&
	       population.empty());
	const auto legacy = legacy_blob(7), uidless = legacy_blob(0);
	query(connection,
	      "INSERT INTO saved_items(id,item_key,room_vnum,vnum,obj_uid,extra_flags) VALUES"
	      "(1,'population-root',100,901,10001,0),(2,'population-child',100,900,801,NULL)");
	query(connection, "UPDATE saved_items SET container_id=1 WHERE id=2");
	query(connection,
	      "INSERT INTO item_current_owner(item_uid,root_item_uid,owner_type,owner_id,"
	      "item_revision,vnum,state) VALUES(101,101,6,1,3,900,1),(102,102,1,99,4,901,3),"
	      "(18446744073709551615,18446744073709551615,6,1,1,900,1),"
	      "(903,903,1,77,1,900,1),(904,904,8,1,1,900,2),(999999,999999,1,77,1,900,1)");
	query(connection,
	      "INSERT INTO item_owner_revision(owner_type,owner_id,revision) VALUES(1,99,12)");
	query(connection,
	      "INSERT INTO item_ownership_quarantine(item_uid,source_table,source_row_id,conflict_code,evidence) "
	      "VALUES(101,'auction_item_custody',1,1,'fixture'),(801,'collector_listings',2001,1,'orphan fixture')");
	query(connection,
	      "INSERT INTO auctions(id,obj_vnum,quantity,obj_blob_str,custody_state) VALUES"
	      "(1,900,3," +
		      legacy + ",1),(2,900,2," + uidless + ",0)");
	query(connection,
	      "UPDATE auctions SET listing_operation_id=UNHEX('fedcba9876543210fedcba9876543210') WHERE id=1");
	query(connection,
	      "INSERT INTO auction_item_custody(auction_id,slot,item_uid,item_revision,vnum,obj_blob) VALUES"
	      "(1,0,101,3,900," +
		      legacy + "),(1,1,102,4,900," + legacy +
		      "),"
		      "(1,65535,18446744073709551615,1,900," +
		      legacy + ")");
	query(connection,
	      "UPDATE auction_item_custody SET claim_pid=77,claimed_at=CURRENT_TIMESTAMP(6),"
	      "claim_operation_id=UNHEX('0123456789abcdef0123456789abcdef') WHERE slot=1");
	query(connection,
	      "INSERT INTO auction_item_pickups(id,pid,quantity,retrieved,obj_blob_str) VALUES"
	      "(1,77,3,0," +
		      uidless + "),(2,77,1,1," + legacy_blob(101) + ")");
	query(connection,
	      "INSERT INTO collector_deaths(death_operation_id,beneficiary_pid,death_time) "
	      "VALUES(UNHEX('123456789abcdef0123456789abcdef0'),77,1000)");
	for (uint64_t index = 1; index <= 3; ++index)
	{
		collector::rules rules;
		rules.enabled = true;
		collector::record record;
		assert(collector::enroll(2000 + index, "123456789abcdef0123456789abcdef0", 77,
					 800 + index, 1, 1000, rules,
					 &record) == collector::outcome::applied);
		if (index != 3)
		{
			assert(collector::collect(&record, record.revision, record.item_revision,
						  record.item_revision, true, 100,
						  record.collect_at) ==
			       collector::outcome::applied);
			if (index == 2)
			{
				assert(collector::activate(&record, record.revision,
							   record.sale_at) ==
				       collector::outcome::applied);
				assert(collector::expire(&record, record.revision,
							 record.expires_at) ==
				       collector::outcome::applied);
			}
		}
		std::array<uint8_t, collector::encoded_record_bytes> encoded;
		assert(collector::record_encode(record, &encoded) == collector::codec_result::ok);
		query(connection,
		      "INSERT INTO collector_listings(listing_id,death_operation_id,beneficiary_pid,item_uid,"
		      "status,listing_revision,item_revision,record_blob,item_blob) VALUES(" +
			      std::to_string(record.listing) +
			      ",UNHEX('123456789abcdef0123456789abcdef0'),77," +
			      std::to_string(record.uid) + "," +
			      std::to_string(static_cast<unsigned>(record.status)) + "," +
			      std::to_string(record.revision) + "," +
			      std::to_string(record.item_revision) + "," +
			      hex(encoded.data(), encoded.size()) + "," +
			      (index == 3 ? "NULL" : modern_blob(record.uid)) + ")");
	}
	query(connection, "UPDATE item_current_owner SET coin_payload=" + modern_blob(903, true) +
				  " WHERE item_uid=903");
	query(connection, "UPDATE item_current_owner SET coin_payload=" + modern_blob(904, true) +
				  " WHERE item_uid=904");
	artifact_population_sql_page page;
	assert(!artifact_population_read_sql_blob_page(connection, artifact_payload_domain::auction,
						       0, &page));
	assert(page.complete && page.rows.size() == 3 &&
	       page.next_row_id == ((1ULL << 16) | 65535));
	assert(page.rows[0].item_uid == 101 && page.rows[0].custody_found &&
	       page.rows[0].source_quarantined);
	assert(page.rows[1].item_uid == 102 &&
	       page.rows[1].role == artifact_payload_role::history &&
	       page.rows[1].payload_owner.id == 77 && page.rows[1].custody.owner.id == 99 &&
	       page.rows[1].custody.vnum == 901 && page.rows[1].custody.owner_revision == 12);
	assert(page.rows[2].item_uid == UINT64_MAX && page.rows[2].extra_flags_present);
	assert(page.rows[1].custody_owner_revision_found);
	query(connection, "UPDATE item_owner_revision SET revision=0 WHERE owner_id=99");
	assert(!artifact_population_read_sql_blob_page(connection, artifact_payload_domain::auction,
						       0, &page));
	assert(page.rows[1].custody_owner_revision_found &&
	       page.rows[1].custody.owner_revision == 0);
	query(connection, "DELETE FROM item_owner_revision WHERE owner_id=99");
	assert(!artifact_population_read_sql_blob_page(connection, artifact_payload_domain::auction,
						       0, &page));
	assert(!page.rows[1].custody_owner_revision_found &&
	       page.rows[1].custody.owner_revision == 0);
	query(connection,
	      "INSERT INTO item_owner_revision(owner_type,owner_id,revision) VALUES(1,99,12)");

	assert(!artifact_population_read_sql_blob_page(
		connection, artifact_payload_domain::auction_legacy, 0, &page));
	assert(page.rows.size() == 2 && page.rows[0].role == artifact_payload_role::history &&
	       page.rows[1].role == artifact_payload_role::stored &&
	       page.rows[1].source_quarantined && !page.rows[1].item_uid &&
	       page.rows[1].quantity == 2);
	query(connection,
	      "INSERT INTO item_ownership_quarantine(item_uid,source_table,source_row_id,conflict_code,evidence) VALUES(0,'auctions',1,1,'legacy template')");
	assert(!artifact_population_read_sql_blob_page(
		connection, artifact_payload_domain::auction_legacy, 0, &page));
	assert(page.rows[0].source_quarantined);
	query(connection,
	      "UPDATE item_ownership_quarantine SET repaired_at=CURRENT_TIMESTAMP(6) WHERE item_uid=0 AND source_table='auctions'");
	assert(!artifact_population_read_sql_blob_page(
		connection, artifact_payload_domain::auction_legacy, 0, &page));
	assert(!page.rows[0].source_quarantined);
	assert(!artifact_population_read_sql_blob_page(
		connection, artifact_payload_domain::auction_pickup, 0, &page));
	assert(page.rows.size() == 2 && page.rows[0].custody_examined &&
	       page.rows[1].custody_examined && !page.rows[0].item_uid &&
	       page.rows[0].quantity == 3 &&
	       page.rows[0].payload_owner.type == item_owner_type::player &&
	       page.rows[0].payload_owner.id == 77 &&
	       page.rows[1].role == artifact_payload_role::history && page.rows[1].custody_found);
	query(connection,
	      "INSERT INTO item_ownership_quarantine(item_uid,source_table,source_row_id,conflict_code,evidence) VALUES(0,'auction_item_pickups',1,1,'uidless pickup')");
	assert(!artifact_population_read_sql_blob_page(
		connection, artifact_payload_domain::auction_pickup, 0, &page));
	assert(page.rows[0].source_quarantined &&
	       page.rows[1].source_quarantined); // UID 101 already quarantined.
	query(connection,
	      "UPDATE auction_item_pickups SET obj_blob_str=" + legacy_blob(777) + " WHERE id=1");
	assert(!artifact_population_read_sql_blob_page(
		connection, artifact_payload_domain::auction_pickup, 0, &page));
	assert(page.rows[0].item_uid == 777 && page.rows[0].source_quarantined);
	query(connection,
	      "UPDATE auction_item_pickups SET obj_blob_str=" + uidless + " WHERE id=1");

	assert(!artifact_population_read_sql_blob_page(
		connection, artifact_payload_domain::collector, 0, &page));
	assert(page.complete && page.next_row_id == 2003 && page.source_rows == 3 &&
	       page.rows.size() == 2 && page.rows[0].role == artifact_payload_role::stored &&
	       page.rows[0].item_uid == 801 && !page.rows[0].custody_found &&
	       page.rows[0].source_quarantined && page.rows[0].extra_flags_present &&
	       !page.rows[0].extra_flags && page.rows[1].role == artifact_payload_role::history);
	assert(!page.rows[1].source_quarantined);
	query(connection,
	      "INSERT INTO collector_reconciliation_quarantine(listing_id,item_uid,conflict_code,evidence) VALUES(2002,802,1,'collector-only fixture')");
	assert(!artifact_population_read_sql_blob_page(
		connection, artifact_payload_domain::collector, 0, &page));
	assert(page.rows[1].source_quarantined &&
	       "collector quarantine was lost without an item-level quarantine row");
	query(connection,
	      "UPDATE collector_reconciliation_quarantine SET repaired_at=CURRENT_TIMESTAMP(6) WHERE listing_id=2002");
	assert(!artifact_population_read_sql_blob_page(
		connection, artifact_payload_domain::collector, 0, &page));
	assert(!page.rows[1].source_quarantined);
	assert(!artifact_population_read_sql_blob_page(
		connection, artifact_payload_domain::embedded, 0, &page));
	assert(page.rows.size() == 2 && page.rows[0].role == artifact_payload_role::history &&
	       page.rows[0].payload_owner.type == item_owner_type::unknown &&
	       page.rows[0].custody.state == item_custody_state::active &&
	       page.rows[1].custody.state == item_custody_state::destroyed);
	assert(!artifact_population_read_sql_payloads(connection, &population));
	assert(population.size() == 13);
	assert(std::any_of(population.begin(), population.end(),
			   [](const auto &item)
			   {
				   return item.domain == artifact_payload_domain::room &&
					  item.item_uid == 801 && item.parent_item_uid == 10001 &&
					  !item.extra_flags_present && item.source_quarantined;
			   }));
	std::vector<artifact_payload_projection> recovery(300);
	for (size_t index = 0; index < recovery.size(); ++index)
	{
		recovery[index].domain = artifact_payload_domain::redis_generation;
		recovery[index].row_id = index + 1;
		recovery[index].item_uid = 100000 + index;
		recovery[index].vnum = 900;
	}
	recovery.front().item_uid = 102;
	recovery[1].custody_found = recovery[1].custody_owner_revision_found = true;
	recovery[1].custody.owner_revision = 99;
	recovery.back().item_uid = 801; // open quarantine without a custody row
	std::vector<artifact_payload_projection> combined;
	assert(!artifact_population_read_sql_payloads(connection, &combined, &recovery) &&
	       combined.size() == population.size() + recovery.size());
	assert(combined.front().custody_examined && combined.front().custody_found &&
	       combined.front().custody.owner.id == 99 && combined.front().custody.vnum == 901 &&
	       combined.front().custody_owner_revision_found);
	assert(combined[1].custody_examined && !combined[1].custody_found &&
	       !combined[1].custody_owner_revision_found && !combined[1].custody.owner_revision);
	assert(combined[299].custody_examined && !combined[299].custody_found &&
	       combined[299].source_quarantined);
	assert(!recovery.front().custody_examined); // caller's pinned input remains immutable
	const auto *retained = population.data();
	query(connection, "START TRANSACTION");
	assert(artifact_population_read_sql_payloads(connection, &population) == EBUSY);
	assert(connection->server_status & SERVER_STATUS_IN_TRANS);
	query(connection, "ROLLBACK");
	query(connection, "SET autocommit=0");
	assert(artifact_population_read_sql_payloads(connection, &population) == EBUSY);
	query(connection, "SET autocommit=1");
	for (const auto &fault : std::array<std::pair<std::string, std::string>, 12>{ {
		     { "UPDATE auction_item_custody SET obj_blob=X'00' WHERE item_uid=101",
		       "UPDATE auction_item_custody SET obj_blob=" + legacy +
			       " WHERE item_uid=101" },
		     { "UPDATE auctions SET obj_blob_str=REPEAT('x',32769) WHERE id=2",
		       "UPDATE auctions SET obj_blob_str=" + uidless + " WHERE id=2" },
		     { "UPDATE auction_item_pickups SET obj_blob_str=X'2400000000' WHERE id=1",
		       "UPDATE auction_item_pickups SET obj_blob_str=" + uidless + " WHERE id=1" },
		     { "UPDATE collector_listings SET item_blob=" + modern_blob(888) +
			       " WHERE listing_id=2001",
		       "UPDATE collector_listings SET item_blob=" + modern_blob(801) +
			       " WHERE listing_id=2001" },
		     { "UPDATE collector_listings SET item_blob=" +
			       modern_blob(801, false, -1, -1) + " WHERE listing_id=2001",
		       "UPDATE collector_listings SET item_blob=" + modern_blob(801) +
			       " WHERE listing_id=2001" },
		     { "UPDATE auction_item_custody SET claim_pid=NULL WHERE slot=1",
		       "UPDATE auction_item_custody SET claim_pid=77 WHERE slot=1" },
		     { "UPDATE auction_item_custody SET claim_operation_id=NULL WHERE slot=1",
		       "UPDATE auction_item_custody SET claim_operation_id=UNHEX('0123456789abcdef0123456789abcdef') WHERE slot=1" },
		     { "UPDATE auction_item_custody SET claimed_at=NULL WHERE slot=1",
		       "UPDATE auction_item_custody SET claimed_at=CURRENT_TIMESTAMP(6) WHERE slot=1" },

		     { "UPDATE auctions SET listing_operation_id=NULL WHERE id=1",
		       "UPDATE auctions SET listing_operation_id=UNHEX('fedcba9876543210fedcba9876543210') WHERE id=1" },
		     { "UPDATE collector_listings SET listing_revision=listing_revision+1 WHERE listing_id=2001",
		       "UPDATE collector_listings SET listing_revision=listing_revision-1 WHERE listing_id=2001" },
		     { "UPDATE collector_listings SET item_revision=item_revision+1 WHERE listing_id=2001",
		       "UPDATE collector_listings SET item_revision=item_revision-1 WHERE listing_id=2001" },

		     { "UPDATE item_current_owner SET coin_payload=X'00' WHERE item_uid=904",
		       "UPDATE item_current_owner SET coin_payload=" + modern_blob(904, true) +
			       " WHERE item_uid=904" },
	     } })
	{
		query(connection, fault.first);
		assert(artifact_population_read_sql_payloads(connection, &population));
		assert(population.data() == retained && population.size() == 13);
		assert(!(connection->server_status & SERVER_STATUS_IN_TRANS));
		query(connection, fault.second);
	}
	query(connection, "UPDATE auction_item_custody SET claim_pid=77 WHERE slot=0");
	assert(!artifact_population_read_sql_blob_page(connection, artifact_payload_domain::auction,
						       0, &page));
	assert(page.rows[0].role == artifact_payload_role::stored &&
	       page.rows[0].payload_owner.type == item_owner_type::auction);
	query(connection, "UPDATE auction_item_custody SET claim_pid=NULL WHERE slot=0");

	for (int invalid = -1; invalid < 4; ++invalid)
	{
		query(connection, "UPDATE item_current_owner SET coin_payload=" +
					  modern_blob(904, invalid >= 0, invalid) +
					  " WHERE item_uid=904");
		assert(artifact_population_read_sql_payloads(connection, &population) == EINVAL &&
		       "embedded history accepted a non-money type or negative coin value");
		assert(population.data() == retained && population.size() == 13 &&
		       !(connection->server_status & SERVER_STATUS_IN_TRANS));
	}
	query(connection, "UPDATE item_current_owner SET coin_payload=" + modern_blob(904, true) +
				  " WHERE item_uid=904");
	query(connection, "RENAME TABLE collector_listings TO collector_listings_held");
	assert(artifact_population_read_sql_payloads(connection, &population));
	assert(population.data() == retained && population.size() == 13);
	query(connection, "RENAME TABLE collector_listings_held TO collector_listings");
	for (uint64_t id = 3; id <= ARTIFACT_POPULATION_SQL_PAGE_SIZE + 1; ++id)
		query(connection, "INSERT INTO auction_item_pickups(id,pid,obj_blob_str) VALUES(" +
					  std::to_string(id) + ",77," + legacy_blob(id + 10000) +
					  ")");
	assert(!artifact_population_read_sql_blob_page(
		connection, artifact_payload_domain::auction_pickup, 0, &page));
	assert(!page.complete && page.rows.size() == ARTIFACT_POPULATION_SQL_PAGE_SIZE &&
	       page.next_row_id == 256);
	assert(!artifact_population_read_sql_blob_page(
		connection, artifact_payload_domain::auction_pickup, page.next_row_id, &page));
	assert(page.complete && page.rows.size() == 1 && page.next_row_id == 257);

	// Block a later source after the aggregate has opened its consistent cut.
	// Insert into a source it has not yet read, then release it. No test hook.
	MYSQL *reader = connect(), *writer = connect();
	assert(!mysql_select_db(reader, database.c_str()) &&
	       !mysql_select_db(writer, database.c_str()));
	query(reader, "SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED");
	query(connection, "LOCK TABLES auction_item_custody WRITE");
	unsigned int aggregate_result = EIO;
	std::thread aggregate(
		[&]
		{ aggregate_result = artifact_population_read_sql_payloads(reader, &population); });
	bool waiting = false;
	for (int attempt = 0; attempt < 500 && !waiting; ++attempt)
	{
		query(writer, "SELECT COUNT(*) FROM information_schema.PROCESSLIST WHERE ID=" +
				      std::to_string(mysql_thread_id(reader)) +
				      " AND INFO LIKE '%FROM auction_item_custody i LEFT%' ");
		MYSQL_RES *result = mysql_store_result(writer);
		assert(result);
		MYSQL_ROW row = mysql_fetch_row(result);
		waiting = row && std::string(row[0]) == "1";
		mysql_free_result(result);
		if (!waiting)
			std::this_thread::sleep_for(std::chrono::milliseconds(10));
	}
	assert(waiting);
	query(writer, "INSERT INTO auction_item_pickups(id,pid,obj_blob_str) VALUES(1000,77," +
			      legacy_blob(888) + ")");
	query(connection, "UNLOCK TABLES");
	aggregate.join();
	assert(!aggregate_result &&
	       std::none_of(population.begin(), population.end(),
			    [](const auto &item) { return item.item_uid == 888; }));
	assert(!artifact_population_read_sql_payloads(reader, &population));
	assert(std::any_of(population.begin(), population.end(),
			   [](const auto &item) { return item.item_uid == 888; }));
	mysql_close(reader);
	mysql_close(writer);
	std::cout
		<< "SQL blob evidence and aggregate preserve bindings, legacy/history, quarantine, "
		   "continuations, snapshot isolation and failure atomicity on the actual schema\n";
}
