#include "sql/sql.h"

#include <cstdlib>
#include <iostream>
#include <string>
#include <unistd.h>

namespace
{
void require(bool condition, const std::string &message)
{
	if (!condition)
	{
		std::cerr << message << '\n';
		exit(1);
	}
}
} // namespace

int logged = 0;
void logit(const char *, const char *, ...)
{
	logged++;
}

int main(int argc, char **argv)
{
	require(argc == 2, "broken root argument required");
	const std::string news = get_mud_info("NeWs");
	require(news.find("Added 'taunt'") != std::string::npos,
		"get_mud_info did not return tracked news");
	require(!get_mud_info("motd").empty(), "get_mud_info did not return tracked motd");
	require(get_mud_info("../unsafe").empty(), "get_mud_info accepted an unsafe name");
	// "lock" is an optional page that has no source here: absent is its normal state.
	require(get_mud_info("lock").empty() && logged == 0, "an absent page was logged");
	// In the broken root there is no news file, and the motd is a directory.
	require(chdir(argv[1]) == 0, "broken root unavailable");
	require(get_mud_info("news").empty() && logged == 0, "a missing page was logged");
	require(get_mud_info("motd").empty() && logged == 1, "a read error was not logged");
	std::cout << "flat-file mud_info runtime passed\n";
	return 0;
}
