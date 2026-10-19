#include <array>
#include <cassert>
#include <cstdarg>
#include <iostream>

// PRODUCTION_CODE

static index_data mobs[512] = {};
static index_data objects[512] = {};
static room_data rooms[2] = {};
P_index mob_index = mobs;
P_index obj_index = objects;
P_room world = rooms;
extern const int top_of_world = 1;
static int ship_token;
P_ship cyrics_revenge = reinterpret_cast<P_ship>(&ship_token);
bool nexus_to_cyrics_revenge = true;
static int ship_room = 3003;
static int missing_mobile = -1, missing_object = -1;
static bool fail_mobile = false, fail_object = false, fail_query = false, fail_result = false;
static int freed_results = 0, fatal_errors = 0;
static std::vector<P_obj> live_objects;
static std::vector<P_char> live_mobs;
static std::vector<std::string> log_messages;
using Row = std::array<const char *, 8>;
static std::vector<Row> rows;

void logit(const char *, const char *format, ...)
{
	char buffer[4096];
	va_list arguments;
	va_start(arguments, format);
	vsnprintf(buffer, sizeof(buffer), format, arguments);
	va_end(arguments);
	log_messages.emplace_back(buffer);
}
void fatal_boot_error(const char *, const char *, ...)
{
	++fatal_errors;
}
static int logs_containing(const char *text)
{
	return std::count_if(log_messages.begin(), log_messages.end(), [text](const auto &message)
			     { return message.find(text) != std::string::npos; });
}

// Init assigns these callbacks; command/lifecycle behavior has separate runtime coverage.
int nexus_stone_guardian(P_char, P_char, int, char *)
{
	return 0;
}
int nexus_sage(P_char, P_char, int, char *)
{
	return 0;
}
int nexus_stone(P_obj, P_char, int, char *)
{
	return 0;
}
int nexus_guardian_pwn_mace(P_obj, P_char, int, char *)
{
	return 0;
}
int real_mobile(const int vnum)
{
	return vnum == missing_mobile ? -1 : vnum;
}
int real_object(const int vnum)
{
	return vnum == missing_object ? -1 : vnum;
}
int real_room(const int vnum)
{
	return vnum == 1001 ? 0 : vnum == 3003 ? 1 : -1;
}
int get_cyrics_revenge_nexus_rvnum(P_ship)
{
	return ship_room;
}
std::string strip_ansi(const char *value)
{
	return value;
}
char *str_dup(const char *value)
{
	return strdup(value);
}
P_obj read_object(int rnum, int)
{
	assert(rnum >= 0);
	if (fail_object)
		return nullptr;
	auto object = new obj_data{};
	object->R_num = rnum;
	live_objects.push_back(object);
	return object;
}
void obj_to_room(P_obj object, int room)
{
	object->loc.room = room;
}
void extract_obj(P_obj object, int)
{
	live_objects.erase(std::find(live_objects.begin(), live_objects.end(), object));
	free(object->name);
	free(object->description);
	free(object->short_description);
	delete object;
}
P_char read_mobile(int rnum, int)
{
	assert(rnum >= 0);
	if (fail_mobile)
		return nullptr;
	auto mob = new char_data{};
	mob->specials.act = ACT_ISNPC;
	live_mobs.push_back(mob);
	return mob;
}
affected_type *affect_to_char(P_char mob, affected_type *value)
{
	mob->affected = new affected_type(*value);
	return mob->affected;
}
void equip_char(P_char, P_obj, int, int) {}
bool char_to_room(P_char mob, int room, int)
{
	mob->in_room = room;
	return true;
}

#ifndef __NO_MYSQL__
static MYSQL connection;
MYSQL *DB = &connection;
static MYSQL_RES result;
static size_t cursor;
bool qry_at(persistence_query_site, const char *, ...)
{
	cursor = 0;
	return !fail_query;
}
extern "C" MYSQL_RES *mysql_store_result(MYSQL *)
{
	return fail_result ? nullptr : &result;
}
extern "C" MYSQL_ROW mysql_fetch_row(MYSQL_RES *)
{
	static std::array<char *, 8> fields;
	if (cursor == rows.size())
		return nullptr;
	for (size_t i = 0; i < fields.size(); ++i)
		fields[i] = const_cast<char *>(rows[cursor][i]);
	++cursor;
	return fields.data();
}
extern "C" void mysql_free_result(MYSQL_RES *)
{
	++freed_results;
}
#else
const char *persistence_mode_flatfile_root()
{
	return "fixture";
}
flatfile_nexus_result flatfile_nexus_list(const std::string &,
					  std::vector<flatfile_nexus_record> *out,
					  std::string *error)
{
	if (fail_query)
	{
		*error = "fixture authority read failure";
		return flatfile_nexus_result::io_error;
	}
	out->clear();
	for (const auto &row : rows)
		out->push_back({ atoi(row[0]), row[1], atoi(row[2]), atoi(row[3]), atoi(row[4]),
				 atoi(row[5]), row[7] ? atoi(row[7]) : 0, atoi(row[6]) });
	return flatfile_nexus_result::ok;
}
flatfile_nexus_result flatfile_nexus_establish(const std::string &,
					       const std::vector<flatfile_nexus_record> &,
					       std::string *)
{
	return flatfile_nexus_result::unchanged;
}
flatfile_nexus_result flatfile_nexus_find(const std::string &root, int id,
					  flatfile_nexus_record *out, std::string *error)
{
	std::vector<flatfile_nexus_record> records;
	const auto result = flatfile_nexus_list(root, &records, error);
	if (result != flatfile_nexus_result::ok)
		return result;
	for (const auto &record : records)
		if (record.id == id)
		{
			*out = record;
			return result;
		}
	return flatfile_nexus_result::not_found;
}
#endif

static void reset()
{
	while (!live_objects.empty())
		extract_obj(live_objects.back(), false);
	for (auto mob : live_mobs)
	{
		delete mob->affected;
		delete mob;
	}
	live_mobs.clear();
	log_messages.clear();
	rows.clear();
	missing_mobile = missing_object = -1;
	fail_mobile = fail_object = fail_query = fail_result = false;
	freed_results = fatal_errors = 0;
	cyrics_revenge = reinterpret_cast<P_ship>(&ship_token);
	ship_room = 3003;
}
static void catalogue()
{
	rows = { { "1", "Marduk", "1001", "0", "0", "0", "1", nullptr },
		 { "3", "Enlil", "130399", "0", "0", "0", "3", nullptr } };
}
static size_t stone_count()
{
	return std::count_if(live_objects.begin(), live_objects.end(),
			     [](auto obj) { return obj->R_num == 394; });
}

int main()
{
	world[0].number = 1001;
	world[1].number = 3003;
	assert(load_nexus_stones(true));
	assert(logs_containing("catalogue is empty") == 1);
	assert(logs_containing("docs/ongoing-projects/plan-issue-109.md") == 1);
	assert(load_nexus_stones());
	assert(logs_containing("catalogue is empty") == 1);
	reset();
	init_nexus_stones();
	assert(fatal_errors == 0 && logs_containing("catalogue is empty") == 1);
	assert(mob_index[65].func.mob == nexus_stone_guardian);
	assert(mob_index[68].func.mob == nexus_sage);
	assert(mob_index[74].func.mob == nullptr);
	assert(obj_index[394].func.obj == nexus_stone);
	for (int missing : { 65, 66, 67, 68, 394, 395 })
	{
		reset();
		if (missing < 100)
			missing_mobile = missing;
		else
			missing_object = missing;
		init_nexus_stones();
		assert(fatal_errors == 0 && logs_containing("is missing") == 1);
	}
	reset();
	catalogue();
	assert(load_nexus_stones(true) && stone_count() == 2 && live_mobs.size() == 2);
	assert(logs_containing("Nexus Stone (3) loaded in [3003]") == 1);
	NexusStoneInfo info;
	assert(nexus_stone_info(3, &info) && info.room_vnum == 130399);
	reset();
	catalogue();
	cyrics_revenge = nullptr;
	assert(!load_nexus_stones(true) && stone_count() == 1);
	assert(logs_containing("ship is missing") == 1 &&
	       logs_containing("incomplete (1 loaded)") == 1);
	assert(!logs_containing("Nexus Stone (3) loaded"));
	reset();
	ship_room = -1;
	assert(!load_nexus_stone(3, "Enlil", 1001, 0) && stone_count() == 0);
	assert(logs_containing("room -1 does not exist") == 1);
	for (int failure = 0; failure < 5; ++failure)
	{
		reset();
		if (failure == 0)
			missing_object = 394;
		if (failure == 1)
			fail_object = true;
		if (failure == 2)
			missing_mobile = 74;
		if (failure == 3)
			fail_mobile = true;
		assert(!load_nexus_stone(1, "Marduk", failure == 4 ? -1 : 1001, 0));
		assert(stone_count() == 0 && live_mobs.empty());
		assert(logs_containing("not loadable") + logs_containing("does not exist") == 1);
		assert(!logs_containing("Nexus Stone (1) loaded") &&
		       !logs_containing("Nexus Guardian [1] loaded"));
	}
	for (int missing : { MOB_GOOD_GUARDIAN, MOB_EVIL_GUARDIAN })
	{
		for (int align = STONE_ALIGN_EVIL; align <= STONE_ALIGN_GOOD; ++align)
		{
			reset();
			missing_mobile = missing;
			assert(!load_nexus_stone(1, "Marduk", 1001, align));
			assert(stone_count() == 0 && live_mobs.empty());
			assert(!logs_containing("Nexus Stone (1) loaded"));
		}
		reset();
		catalogue();
		missing_mobile = missing;
		init_nexus_stones();
		assert(stone_count() == 0 && live_mobs.empty());
		assert(logs_containing("incomplete (0 loaded)") == 1);
#ifdef __NO_MYSQL__
		assert(fatal_errors == 1);
#else
		assert(fatal_errors == 0);
		assert(!nexus_stone_info(1, &info));
#endif
		// Reload cannot bypass the same activation prerequisite.
		assert(!load_nexus_stones());
		assert(stone_count() == 0 && live_mobs.empty());
	}
	reset();
	fail_query = true;
	assert(!load_nexus_stones(true) && !logs_containing("catalogue is empty"));
#ifndef __NO_MYSQL__
	assert(logs_containing("SQL query failed") == 1 && freed_results == 0);
	reset();
	fail_result = true;
	assert(!load_nexus_stones(true) && logs_containing("mysql_store_result failed") == 1);
	for (auto bad : std::array<std::pair<int, const char *>, 5>{
		     { { 0, "0" }, { 1, "" }, { 3, "4" }, { 6, "6" }, { 4, nullptr } } })
	{
		reset();
		catalogue();
		rows[1][bad.first] = bad.second;
		assert(!load_nexus_stones(true) && freed_results == 1 && stone_count() == 1);
		assert(logs_containing("incomplete (1 loaded)") == 1);
		assert(!nexus_stone_info(3, &info));
	}
#else
	assert(logs_containing("authority read failure") == 1);
	init_nexus_stones();
	assert(fatal_errors == 1);
#endif
	reset();
	std::cout
		<< "Nexus empty/init, placement, ship, partial catalogue and backend failures passed\n";
}
