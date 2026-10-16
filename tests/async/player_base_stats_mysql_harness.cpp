// Synthetic signed-short stats round-trip through the production repository.
#include "player/player_snapshot_repository.h"
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>

char *sql_escape_string(const char *text)
{
	return strdup(text);
}

static void execute(MYSQL *db, const std::string &sql)
{
	if (mysql_real_query(db, sql.data(), sql.size()))
	{
		std::cerr << mysql_error(db) << '\n';
		std::abort();
	}
}

int main(int argc, char **argv)
{
	assert(argc == 3);
	MYSQL *db = mysql_init(nullptr);
	assert(db &&
	       mysql_real_connect(db, "localhost", "root", "stats-test", argv[2], 0, argv[1], 0));
	execute(db, "SET SESSION sql_mode='STRICT_TRANS_TABLES'");
	execute(db, "INSERT INTO player_data(pid,name,save_revision) VALUES(7,'Fixture',10)");
	const player_status_field fields[] = {
		player_status_field::base_strength, player_status_field::base_dexterity,
		player_status_field::base_agility,  player_status_field::base_constitution,
		player_status_field::base_power,    player_status_field::base_intelligence,
		player_status_field::base_wisdom,   player_status_field::base_charisma,
		player_status_field::base_karma,    player_status_field::base_luck
	};
	player_snapshot snapshot{};
	snapshot.pid = 7;
	snapshot.schema_version = PLAYER_SNAPSHOT_SCHEMA_VERSION;
	snapshot.components = PLAYER_COMPONENT_STATUS;
	snapshot.revision = 10;
	for (const int value : { 128, 255, -32768, 32767 })
	{
		++snapshot.revision;
		snapshot.status_integers.clear();
		for (const auto field : fields)
			snapshot.status_integers.push_back({ field, value, 0, false });
		const auto result = player_snapshot_repository_apply(db, snapshot);
		assert(result.outcome == player_save_apply_outcome::applied &&
		       result.error_code == 0);
		execute(db,
			"SELECT save_revision,base_str,base_dex,base_agi,base_con,base_pow,"
			"base_int,base_wis,base_cha,base_kar,base_luk FROM player_data WHERE pid=7");
		MYSQL_RES *rows = mysql_store_result(db);
		assert(rows);
		MYSQL_ROW row = mysql_fetch_row(rows);
		assert(row && std::strtoull(row[0], nullptr, 10) == snapshot.revision);
		for (int i = 1; i <= 10; ++i)
			assert(row[i] && std::atoi(row[i]) == value);
		mysql_free_result(rows);
	}
	mysql_close(db);
	std::cout
		<< "All ten stats: values above the former limit and signed-short boundaries persisted\n";
}
