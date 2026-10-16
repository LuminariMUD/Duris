#include "player/news.h"
#include "sql/sql.h"
#include "sql/sql_async.h"

#include <cassert>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <optional>

static int failures;
void logit(const char *, const char *, ...)
{
	++failures;
}
void send_to_char(const char *, P_char) {}

#ifndef __NO_MYSQL__
static std::function<void(bool, const sql_rows &)> refresh;
static std::function<void(P_char, const sql_rows &)> reload;
bool sql_read_at(persistence_query_site, std::string query,
		 std::function<void(bool, const sql_rows &)> done)
{
	assert(query == "SELECT name, content FROM mud_info");
	refresh = std::move(done);
	return true;
}
bool sql_read_for_at(persistence_query_site, P_char, std::string query,
		     std::function<void(P_char, const sql_rows &)> done)
{
	assert(query == "SELECT name, content FROM mud_info");
	reload = std::move(done);
	return true;
}
static sql_rows rows(const std::string &text)
{
	sql_row row;
	row.fields = { std::string("news"), text };
	return { row };
}
#endif

int main(int argc, char **argv)
{
	assert(argc == 2);
	assert(current_news().text.empty() && current_news().fingerprint.empty());
	assert(publish_news("abc"));
	const std::string hash = current_news().fingerprint;
	assert(hash == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
	assert(publish_news("abc") && current_news().fingerprint == hash);
	assert(!publish_news(std::string("abc\0bad", 7)));
	assert(current_news().text == "abc" && current_news().fingerprint == hash);
	assert(publish_news("&+Gabc\n") && current_news().fingerprint != hash);
	assert(publish_news("abc") && current_news().fingerprint == hash);
	assert(publish_news("") && current_news().fingerprint.empty());

	const std::filesystem::path root(argv[1]);
	std::filesystem::create_directories(root / "lib/information");
	const auto file = root / "lib/information/news";
	std::string error;
	std::ofstream(file) << "abc";
	assert(load_news_file(root.string(), &error));
	assert(current_news().fingerprint == hash);
	std::filesystem::remove(file);
	assert(!load_news_file(root.string(), &error) && !error.empty());
	assert(current_news().fingerprint == hash);
	std::ofstream(file, std::ios::binary).write("abc\0bad", 7);
	assert(!load_news_file(root.string(), &error));
	assert(current_news().fingerprint == hash);
	std::ofstream(file).close();
	assert(load_news_file(root.string(), &error) && current_news().text.empty());

#ifdef __NO_MYSQL__
	std::filesystem::current_path(root);
	std::ofstream(file) << "changed on disk";
	bool completed = false;
	sql_mud_info_reload(nullptr, [&](P_char) { completed = true; });
	assert(completed && current_news().text == "changed on disk");
	std::filesystem::remove(file);
	sql_mud_info_reload(nullptr, [](P_char) {});
	assert(failures == 1 && current_news().text == "changed on disk");
#else
	sql_mud_info_refresh();
	assert(refresh);
	refresh(true, rows("abc"));
	assert(get_mud_info("news") == "abc" && current_news().fingerprint == hash);
	refresh(false, rows("failed query"));
	assert(current_news().fingerprint == hash);
	refresh(true, rows("B"));
	assert(get_mud_info("news") == "B" && current_news().fingerprint != hash);
	const auto before = current_news();
	refresh(true, rows(std::string("B\0bad", 5)));
	assert(failures == 1 && current_news().text == before.text &&
	       current_news().fingerprint == before.fingerprint);
	bool completed = false;
	sql_mud_info_reload(nullptr, [&](P_char) { completed = true; });
	assert(reload);
	reload(nullptr, rows("abc"));
	assert(completed && current_news().fingerprint == hash);
	refresh(true, {});
	assert(current_news().text.empty() && current_news().fingerprint.empty());
	refresh(true, rows(""));
	assert(current_news().fingerprint.empty());
#endif
	std::cout << "news publication and reload passed\n";
}
