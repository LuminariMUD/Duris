#include "cmd/information_cache.h"
#include "sql/sql_pool.h"
#include <array>
#include <cassert>
#include <cstring>
#include <iostream>
#include <map>
#include <optional>
#include <string>
#include <vector>

// A fake mud_info table behind the client calls load_information() makes.
namespace
{
std::map<std::string, std::string> mud_info;
std::vector<std::pair<std::string, std::optional<std::string>>> rows;
size_t next_row;
std::array<char *, 2> row_values;
std::array<unsigned long, 2> row_lengths;
MYSQL_RES *const fake_result = reinterpret_cast<MYSQL_RES *>(&next_row);
}

extern "C"
{
	MYSQL *sql_pool_acquire(void)
	{
		return reinterpret_cast<MYSQL *>(&mud_info);
	}
	void sql_pool_release(MYSQL *) {}
	int STDCALL mysql_real_query(MYSQL *, const char *, unsigned long)
	{
		rows.clear();
		next_row = 0;
		for (const auto &[name, content] : mud_info)
			if (content.size() <= 131072)
				rows.emplace_back(name, content);
			else
				rows.emplace_back(name, std::nullopt);
		return 0;
	}
	MYSQL_RES *STDCALL mysql_use_result(MYSQL *)
	{
		return fake_result;
	}
	MYSQL_ROW STDCALL mysql_fetch_row(MYSQL_RES *)
	{
		if (next_row == rows.size())
			return nullptr;
		auto &[name, content] = rows[next_row++];
		row_values = { name.data(), content ? content->data() : nullptr };
		row_lengths = { name.size(), content ? content->size() : 0 };
		return row_values.data();
	}
	unsigned long *STDCALL mysql_fetch_lengths(MYSQL_RES *)
	{
		return row_lengths.data();
	}
	unsigned int STDCALL mysql_errno(MYSQL *)
	{
		return 0;
	}
	void STDCALL mysql_free_result(MYSQL_RES *) {}
}

int main()
{
	assert(!information_cache_get("credits"));
	assert(information_cache_refresh());
	information_cache_shutdown();
	assert(!information_cache_get("credits"));
	for (const char *name : { "credits", "faq", "wizlist" })
		mud_info[name] = name;
	assert(information_cache_refresh());
	assert(information_cache_refresh());
	information_cache_shutdown();
	for (const char *name : { "credits", "faq", "wizlist" })
		assert(*information_cache_get(name) == name);
	assert(!information_cache_get("lock"));
	// A pager's owned text outlives a replaced snapshot.
	std::string pager = *information_cache_get("credits");
	mud_info["credits"] = "new credits";
	mud_info["faq"] = "";
	assert(information_cache_refresh());
	assert(*information_cache_get("credits") == "credits");
	information_cache_shutdown();
	assert(pager == "credits");
	assert(*information_cache_get("credits") == "new credits");
	assert(information_cache_get("faq")->empty());
	// A missing page keeps the previous snapshot.
	mud_info.erase("wizlist");
	assert(information_cache_refresh());
	information_cache_shutdown();
	assert(*information_cache_get("wizlist") == "wizlist");
	// The query returns NULL for an oversized page, which also keeps the snapshot.
	mud_info["wizlist"] = std::string(131073, 'x');
	assert(information_cache_refresh());
	information_cache_shutdown();
	assert(*information_cache_get("wizlist") == "wizlist");
	mud_info["wizlist"] = std::string(128 * 1024, 'x');
	assert(information_cache_refresh());
	information_cache_shutdown();
	assert(information_cache_get("wizlist")->size() == 128 * 1024);
	for (int i = 0; i < 10000; ++i)
		assert(*information_cache_get("credits") == "new credits");
	std::cout
		<< "information cache initial failure, refresh, empty/missing/oversized content and owned text passed\n";
}
