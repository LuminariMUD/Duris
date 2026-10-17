#include "guild/artifact_population_repository.h"

#include <cassert>
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
		mysql_close(connection);
		std::cout << "all numeric population readers accept the actual current schema\n";
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
			      ") ENGINE=InnoDB");
		query(connection, "INSERT INTO " + std::string(entry.table) +
					  "(id,obj_uid,container_id,vnum,extra_flags," +
					  entry.owner +
					  ") VALUES(1,18446744073709551615,NULL,900,268435456,42),"
					  "(2,NULL,1,901,268435456,43)");
		artifact_population_sql_page page;
		assert(!artifact_population_read_sql_page(connection, entry.domain, 0, &page));
		assert(page.complete && page.next_row_id == 2 && page.rows.size() == 2);
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
