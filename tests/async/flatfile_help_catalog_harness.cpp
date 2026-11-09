#include "flatfile/flatfile_help_catalog.h"

#include <cstdlib>
#include <iostream>
#include <string>

static void require(bool condition, const std::string &message)
{
	if (!condition)
	{
		std::cerr << message << '\n';
		exit(1);
	}
}

int main(int argc, char **argv)
{
	require(argc == 2, "project root argument required");
	std::string error;
	std::string information;
	require(flatfile_information_read(argv[1], "NeWs", &information, &error) &&
			information.find("Added 'taunt'") != std::string::npos,
		"tracked news was not available through mud_info");
	require(flatfile_information_read(argv[1], "motd", &information, &error) &&
			!information.empty(),
		"tracked motd was not available through mud_info");
	require(flatfile_information_read(argv[1], "credits", &information, &error) &&
			!information.empty(),
		"tracked credits were not available through mud_info");
	require(!flatfile_information_read(argv[1], "../unsafe", &information, &error),
		"unknown mud_info name escaped the source allow-list");

	std::cout << "flat-file information read passed\n";
	return 0;
}
