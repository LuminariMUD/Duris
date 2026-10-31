#include "core/prototypes.h"
#include "core/utils.h"
#include "magic/spells.h"
#include "ships/ships.h"
#include "sql/sql_async.h"
#include "world/hardcore_config.h"
#include "world/zone_story_quest_runtime.h"

#include <cassert>
#include <climits>
#include <cstdarg>
#include <cstring>
#include <iostream>
#include <unistd.h>

static MYSQL *connection;
static sql_rows standings;
static std::string output;

void logit(const char *, const char *, ...) {}
int panic_corruption_int(const char *, const char *, ...)
{
	std::abort();
}
void send_to_char(const char *text, P_char)
{
	output += text;
}
void send_to_char_f(P_char, const char *format, ...)
{
	char text[4096];
	va_list args;
	va_start(args, format);
	const int length = vsnprintf(text, sizeof(text), format, args);
	va_end(args);
	assert(length >= 0 && (size_t)length < sizeof(text));
	output += text;
}
void page_string(P_desc, char *text, int)
{
	output += text;
}
bool affected_by_spell(P_char ch, int type)
{
	for (affected_type *affect = ch->affected; affect; affect = affect->next)
		if (affect->type == type)
			return true;
	return false;
}
char *one_argument(const char *text, char *word)
{
	while (*text == ' ')
		++text;
	while (*text && *text != ' ')
		*word++ = *text++;
	*word = '\0';
	return const_cast<char *>(text);
}
bool is_abbrev(const char *word, const char *full)
{
	return *word && !strncasecmp(word, full, strlen(word));
}
namespace zone_story_quest_runtime
{
zone_story_quest_feature::service *service()
{
	return nullptr;
}
uint32_t current_season_id()
{
	return 1;
}
bool remember_character(P_char, std::string *)
{
	return true;
}
}
std::string zone_story_quest_feature::service::render_leaderboard(uint32_t, int32_t, uint64_t,
								  uint64_t, uint32_t, bool,
								  int64_t) const
{
	return {};
}

std::string sql_format(const char *format, ...)
{
	char text[8192];
	va_list args;
	va_start(args, format);
	const int length = vsnprintf(text, sizeof(text), format, args);
	va_end(args);
	assert(length >= 0 && (size_t)length < sizeof(text));
	return text;
}
static void execute(const std::string &query)
{
	if (mysql_query(connection, query.c_str()))
	{
		std::cerr << query << "\n" << mysql_error(connection) << '\n';
		std::abort();
	}
}
bool sql_read_for_at(persistence_query_site, P_char ch, std::string query,
		     std::function<void(P_char, const sql_rows &)> done)
{
	standings.clear();
	if (connection)
	{
		execute(query);
		MYSQL_RES *result = mysql_store_result(connection);
		assert(result);
		while (MYSQL_ROW values = mysql_fetch_row(result))
		{
			sql_row row;
			for (unsigned int i = 0; i < mysql_num_fields(result); ++i)
				row.fields.emplace_back(
					values[i] ? std::optional<std::string>(values[i]) :
						    std::nullopt);
			standings.push_back(std::move(row));
		}
		mysql_free_result(result);
	}
	done(ch, standings);
	return true;
}

struct fixture
{
	const char *name;
	int level, experience;
	long frags;
	int ship_frags, earned;
	unsigned long deaths;
	long expected;
};
static const fixture players[] = {
	{ "Adventurer", 50, 1234567, 125, 37, 240, 12, 90023 },
	{ "Debtor", 1, 0, -200, 0, 0, 1000, -44000 },
	{ "Veteran", 56, 0, 0, 50000000, 0, 100000000, 2500056000L },
	{ "Epicmaster", 50, 0, 0, 0, 2000000001, 0, 200000050100L },
	{ "Wideearner", 50, 0, 0, INT_MAX, INT_MAX, 0, 429496779400L },
	{ "Badfrags", 10, 0, 100000, 0, 10, 0, 11000 },
	{ "Badlosses", 10, 0, -100000, 0, 10, 0, 11000 },
	{ "Alphatie", 10, 9999, 0, 0, 0, 0, 10000 },
	{ "Betatie", 10, 0, 0, 0, 0, 0, 10000 },
	{ "Experience", 10, 10000, 0, 0, 0, 0, 10001 },
	{ "Avatarstaff", AVATAR, 0, 99999, 99999999, 2000000001, 0, 0 },
	{ "Overlordstaff", OVERLORD, 0, 99999, 99999999, 2000000001, 0, 0 },
	{ "Uncreated", 0, 0, 99999, 99999999, 2000000001, 0, 0 },
};

static void check_live_scores()
{
	char_data ch = {};
	pc_only_data pc = {};
	affected_type earned = {};
	ch.only.pc = &pc;
	ch.affected = &earned;
	earned.type = TAG_EPICS_GAINED;
	for (const fixture &player : players)
	{
		ch.player.level = player.level;
		ch.points.curr_exp = player.experience;
		pc.frags = player.frags;
		pc.numb_deaths = player.deaths;
		pc.epics = 999999999; // Spendable balance never determines earned credit.
		earned.modifier = player.earned;
		assert(getLeaderBoardPtsWithShipFrags(&ch, player.ship_frags) == player.expected);
		pc.epics = 0;
		assert(getLeaderBoardPtsWithShipFrags(&ch, player.ship_frags) == player.expected);
		// A stale duplicate cannot make the private score differ from SQL's MAX tag.
		affected_type duplicate = earned;
		duplicate.modifier = player.earned - 1;
		duplicate.next = &earned;
		ch.affected = &duplicate;
		assert(getLeaderBoardPtsWithShipFrags(&ch, player.ship_frags) == player.expected);
		earned.next = &duplicate;
		duplicate.next = nullptr;
		ch.affected = &earned;
		assert(getLeaderBoardPtsWithShipFrags(&ch, player.ship_frags) == player.expected);
		earned.next = nullptr;
	}
	ch.player.level = 10;
	ch.points.curr_exp = -1;
	pc.frags = pc.numb_deaths = 0;
	earned.modifier = -1;
	assert(getLeaderBoardPtsWithShipFrags(&ch, -100) == 10000);
	ch.affected = nullptr;
	assert(getLeaderBoardPtsWithShipFrags(&ch, 0) == 10000);
	ch.specials.act = ACT_ISNPC;
	assert(getLeaderBoardPtsWithShipFrags(&ch, 0) == 0);
	assert(getLeaderBoardPtsWithShipFrags(nullptr, 0) == 0);

	// An owned ship below 24 stronger ships still counts, with exact case-insensitive ownership.
	ch.specials.act = 0;
	char owner[] = "Captain";
	char ship_owner[] = "cAPTAIN";
	char other_owner[] = "Other";
	ch.player.name = owner;
	ShipData ships[25] = {};
	for (ShipData &ship : ships)
	{
		ship.ownername = other_owner;
		ship.frags = 1000;
		assert(shipObjHash.add(&ship));
	}
	ships[0].ownername = ship_owner;
	ships[0].frags = 37;
	assert(calculate_shipfrags(&ch) == 37);
	assert(getLeaderBoardPts(&ch) == 13700);
	// Widened scores must stay wide through both manual and periodic feudal updates.
	ch.specials.position = STAT_NORMAL | POS_STANDING;
	ch.affected = &earned;
	earned.modifier = INT_MAX;
	ships[0].frags = INT_MAX;
	set_surname(&ch, 1);
	assert(GET_SURNAME((&ch)) == SURNAME_KING);
	CLEAR_SURNAME((&ch));
	SET_SURNAME((&ch), SURNAME_SERF);
	set_surname(&ch, 0);
	assert(GET_SURNAME((&ch)) == SURNAME_KING);
	ch.affected = nullptr;
	ships[0].frags = -37;
	assert(calculate_shipfrags(&ch) == 0);
	ships[0].frags = 37;
	ships[0].race = NPCSHIP;
	assert(calculate_shipfrags(&ch) == 0);
	ships[0].race = 0;
	char prefix[] = "Cap";
	ch.player.name = prefix;
	assert(calculate_shipfrags(&ch) == 0);
	for (ShipData &ship : ships)
		assert(shipObjHash.erase(&ship));
}

static void check_database_scores(P_char viewer)
{
	execute("CREATE TABLE player_data (pid INT PRIMARY KEY AUTO_INCREMENT, "
		"name VARCHAR(64) COLLATE utf8mb4_unicode_ci, level TINYINT UNSIGNED, "
		"exp BIGINT, frags BIGINT, epics BIGINT DEFAULT 0, numb_deaths BIGINT UNSIGNED)");
	execute("CREATE TABLE ships (owner_name VARCHAR(64) COLLATE utf8mb4_unicode_ci UNIQUE, frags INT)");
	execute("CREATE TABLE player_affects (pid INT, type SMALLINT, modifier INT)");
	int pid = 0;
	for (const fixture &player : players)
	{
		++pid;
		execute(sql_format(
			"INSERT INTO player_data VALUES (%d,'%s',%d,%d,%ld,99999999,%lu)", pid,
			player.name, player.level, player.experience, player.frags, player.deaths));
		execute(sql_format("INSERT INTO ships VALUES (LOWER('%s'),%d)", player.name,
				   player.ship_frags));
		// Unequal duplicate tags and unrelated affects must not duplicate characters or add credit.
		execute(sql_format(
			"INSERT INTO player_affects VALUES (%d,%d,%d),(%d,%d,%d),(%d,1,99999999)",
			pid, TAG_EPICS_GAINED, player.earned, pid, TAG_EPICS_GAINED,
			player.earned - 1, pid));
	}
	output.clear();
	displayLeader(viewer, nullptr, 0);
	const std::vector<std::string> expected_order = { "Wideearner", "Epicmaster", "Veteran",
							  "Adventurer", "Badfrags",   "Badlosses",
							  "Experience", "Alphatie",   "Betatie",
							  "Debtor" };
	assert(standings.size() == expected_order.size());
	for (size_t i = 0; i < standings.size(); ++i)
	{
		assert(standings[i][0] == expected_order[i]);
		for (const fixture &player : players)
			if (player.name == expected_order[i])
				assert(std::stol(standings[i][1]) == player.expected);
	}
	assert(output.find("2000000501.00") != std::string::npos);
	assert(output.find("900.23") != std::string::npos);
	assert(output.find("-440.00") != std::string::npos);
	assert(output.find("1.25") != std::string::npos);
	assert(output.find("Rank") != std::string::npos &&
	       output.find("Deaths") != std::string::npos);
	assert(output.find("Avatarstaff") == std::string::npos);
	assert(output.find("Overlordstaff") == std::string::npos);
	const std::string before_spending = output;
	execute("UPDATE player_data SET epics=0");
	output.clear();
	displayLeader(viewer, nullptr, 0);
	assert(output == before_spending);

	// Legacy NULLs and missing ships/tags are zero contributions.
	execute("INSERT INTO player_data (name,level) VALUES ('Newcomer',1)");
	displayLeader(viewer, nullptr, 0);
	assert(standings[standings.size() - 2][0] == std::string("Newcomer"));
	assert(std::stol(standings[standings.size() - 2][1]) == 1000);
	for (int i = 0; i < 25; ++i)
		execute(sql_format("INSERT INTO player_data (name,level) VALUES ('Filler%02d',2)",
				   i));
	displayLeader(viewer, nullptr, 0);
	assert(standings.size() == 20);
	execute("DELETE FROM player_data WHERE level < 57");
	output.clear();
	displayLeader(viewer, nullptr, 0);
	assert(standings.empty() && output.find("No players are ranked yet") != std::string::npos);
}

int main()
{
	boot_hardcore_config();
	check_live_scores();
	char_data viewer = {};
	displayLeader(nullptr, nullptr, 0);
	displayLeader(&viewer, nullptr, 0);
	assert(output.find("No players are ranked yet") != std::string::npos);
	if (const char *host = getenv("TEST_DB_HOST"))
	{
		assert(!strcmp(host, "127.0.0.1"));
		connection = mysql_init(nullptr);
		assert(mysql_real_connect(connection, host, getenv("TEST_DB_USER"),
					  getenv("TEST_DB_PASSWORD"), nullptr,
					  std::stoul(getenv("TEST_DB_PORT")), nullptr, 0));
		const std::string database = "leaderboard_regression_" + std::to_string(getpid());
		execute("CREATE DATABASE " + database +
			" CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");
		execute("USE " + database);
		check_database_scores(&viewer);
		execute("DROP DATABASE " + database);
		mysql_close(connection);
		std::cout
			<< "PASS: command SQL, ranking, staff exclusion, signed penalties, epic spending and live score parity\n";
	}
	std::cout
		<< "PASS: live scoring, arithmetic width, earned epics and ship ownership outside top 20\n";
}
