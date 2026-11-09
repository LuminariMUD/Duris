#include "economy/divine_boon_repository.h"
#include "economy/divine_trade_repository.h"
#include <cassert>
#include <cstdlib>
#include <ctime>
#include <iostream>
#include <string>

static int ports[] = { 559633, 635260, 88846, 82669, 66689, 9967, 22441, 49090, 43158, 83786 };
int main(int argc, char **argv)
{
	assert(argc >= 5);
	const std::string action = argv[3], owner = argv[4];
	MYSQL *db = nullptr;
	db = mysql_init(nullptr);
	assert(db && mysql_real_connect(db, getenv("DB_HOST"), getenv("DB_USER"),
					getenv("DB_PASSWD"), getenv("DB_NAME"),
					std::strtoul(getenv("DB_PORT"), nullptr, 10), nullptr, 0));
	auto query = [&](const std::string &sql) { assert(db && !mysql_query(db, sql.c_str())); };
	auto number = [&](const std::string &sql)
	{
		query(sql);
		auto *result = mysql_store_result(db);
		assert(result);
		auto row = mysql_fetch_row(result);
		assert(row && row[0]);
		long long value = std::strtoll(row[0], nullptr, 10);
		mysql_free_result(result);
		return value;
	};
	divine_boon_state state;
	assert(divine_boon_sql_load(db, &state) == divine_boon_store_result::ok);
	auto save = [&](uint64_t expected)
	{ assert(divine_boon_sql_save(db, expected, state) == divine_boon_store_result::ok); };
	if (action == "inspect")
	{
		uint64_t cargo = 0;
		for (const auto &slot : state.slots)
			if (slot.category == divine_boon_category::cargo)
			{
				cargo = slot.id;
				std::cout << "ROUTE " << slot.source_port << " "
					  << slot.destination_port << "\n";
			}
		std::vector<divine_trade_book> books;
		assert(divine_trade_sql_books(db, cargo, &books));
		for (const auto &book : books)
			std::cout << "BOOK " << book.first_full_hold << " " << book.consumed << " "
				  << book.lots.size() << "\n";
	}

	else if (action == "ready")
	{
		const bool ready =
			number("SELECT COUNT(*) FROM ships s JOIN ship_crew c ON c.ship_id=s.id WHERE s.owner_name='" +
			       owner +
			       "' AND c.crew_index=2 AND c.sail_skill>=100000 AND c.guns_skill>=100000 AND c.rpar_skill>=100000") ==
			1;
		std::cout << (ready ? "READY" : "PENDING") << "\n";
	}
	else if (action == "hold")
	{
		query("START TRANSACTION");
		number("SELECT pid FROM player_data WHERE name='" + owner + "' FOR UPDATE");
		std::cout << "LOCKED" << std::endl;
		std::string release;
		std::getline(std::cin, release);
		query("COMMIT");
	}

	else if (action == "fighter")
	{
		query("UPDATE player_data SET level=30,highest_level=30,base_hit=" +
		      std::string(owner == "Boonvictim" ? "1" : "10000") +
		      ",hit_diff=0,exp=1000000 WHERE name='" + owner + "'");
	}
	else if (action == "objectives")
	{
		assert(argc == 7);
		const int side = std::atoi(argv[5]), zone = std::atoi(argv[6]);
		assert(side == 0 || side == 1);
		auto expected = state.revision++;
		for (auto category :
		     { divine_boon_category::experience, divine_boon_category::pvp })
		{
			size_t index = 0;
			while (index < state.slots.size() && state.slots[index].id)
				++index;
			assert(index < state.slots.size());
			auto &slot = state.slots[index];
			slot.id = state.next_id++;
			slot.category = category;
			slot.starts_at = state.last_opportunity -
					 (category == divine_boon_category::experience ? 3 : 2) *
						 DIVINE_BOON_HOUR;
			slot.expires_at = slot.starts_at + divine_boon_duration(category);
			if (category == divine_boon_category::experience)
				slot.zones[side] = zone;
		}
		save(expected);
	}
	else if (action == "player")
	{
		std::cout << "XP "
			  << number("SELECT exp FROM player_data WHERE name='" + owner + "'")
			  << "\n";
	}
	else if (action == "seed" || action == "move")
	{
		assert(argc == 6);
		int port = std::atoi(argv[5]);
		assert(port >= 0 && port < 10);
		if (action == "seed")
		{
			query("UPDATE player_data SET platinum=100000 WHERE name='" + owner + "'");
			query("INSERT INTO ships(owner_name,ship_name,ship_class,frags,anchor_room,mainsail,flags) VALUES ('" +
			      owner + "','Campaign Clipper',2,10000," +
			      std::to_string(ports[port]) + ",90,16)");
			const auto id =
				number("SELECT id FROM ships WHERE owner_name='" + owner + "'");
			query("INSERT INTO ship_crew(ship_id,crew_index) VALUES(" +
			      std::to_string(id) + ",2)");
			for (int side = 0; side < 4; ++side)
				query("INSERT INTO ship_armor(ship_id,side,armor,internal) VALUES(" +
				      std::to_string(id) + "," + std::to_string(side) +
				      ",100,100)");
		}
		else
			query("UPDATE ships SET anchor_room=" + std::to_string(ports[port]) +
			      ",flags=16 WHERE owner_name='" + owner + "'");
	}
	if (db)
		mysql_close(db);
}
