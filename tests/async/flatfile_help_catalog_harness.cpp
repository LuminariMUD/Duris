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
	flatfile_help_catalog catalog;
	std::string error;
	require(flatfile_help_catalog_load(argv[1], &catalog, &error),
		"catalog load failed: " + error);
	require(catalog.entries.size() > 1500, "catalog did not load the complete help sources");

	const flatfile_help_entry *charisma = flatfile_help_catalog_find(catalog, "cHaRiSmA");
	require(charisma && charisma->text.find("major attributes") != std::string::npos,
		"case-insensitive exact lookup failed");
	const flatfile_help_entry *help = flatfile_help_catalog_find(catalog, "help advanced");
	require(help && help->text.find("SOCIETY EXAMPLES") != std::string::npos,
		"individual help source was not loaded");
	const flatfile_help_entry *hardcore = flatfile_help_catalog_find(catalog, "HARDCORE");
	require(hardcore && hardcore->text.find("three lives") != std::string::npos &&
			hardcore->text.find(
				"third counted death permanently deletes the character") !=
				std::string::npos &&
			hardcore->text.find("Arena deaths do not consume a life") !=
				std::string::npos,
		"Hardcore help did not publish the three-life policy");
	const flatfile_help_entry *monk = flatfile_help_catalog_find(catalog, "Monk");
	require(monk && monk->text.find("Loose inventory does not count") != std::string::npos &&
			monk->text.find("free attack allowance is STR / 2") != std::string::npos,
		"Monk help did not publish equipment-only attack encumbrance");
	const flatfile_help_entry *martial = flatfile_help_catalog_find(catalog, "Martial Arts");
	require(martial &&
			martial->text.find("Attacks: add half of each equipped item's weight") !=
				std::string::npos &&
			martial->text.find("rounding each item down") != std::string::npos &&
			martial->text.find("Weight cannot add attacks") != std::string::npos,
		"Martial Arts help did not publish weight rounding and attack limits");

	const auto matches = flatfile_help_catalog_search(catalog, "celest", 101);
	require(matches.size() > 1, "substring search did not find multiple topics");
	for (size_t index = 1; index < matches.size(); ++index)
		require(matches[index - 1]->title <= matches[index]->title,
			"search results were not title sorted");
	require(flatfile_help_catalog_search(catalog, "", 7).size() == 7,
		"search limit was not enforced");
	require(!flatfile_help_catalog_find(catalog, "definitely missing topic"),
		"missing exact lookup returned an entry");

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

	std::cout << "flat-file help catalog passed\n";
	return 0;
}
