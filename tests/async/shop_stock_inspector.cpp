#include "flatfile/flatfile_shopkeeper_repository.h"
#include "flatfile/flatfile_shopkeeper_ownership.h"
#include <iostream>
#include <string>

int main(int argc, char **argv)
{
	if (argc != 4)
		return 2;
	std::vector<flatfile_shopkeeper_record> records;
	std::string error;
	if (flatfile_shopkeeper_list(argv[1], &records, &error) != flatfile_shopkeeper_result::ok)
	{
		std::cerr << error << '\n';
		return 1;
	}
	const int room = std::stoi(argv[2]);
	const int keeper = std::stoi(argv[3]);
	for (const auto &record : records)
		if (record.room_vnum == room && record.mob_vnum == keeper)
		{
			uint64_t revision = 0;
			std::vector<player_load_item_identity> identities;
			if (flatfile_shopkeeper_load_item_ownership(argv[1], record, &revision,
								    &identities, &error) !=
			    flatfile_shopkeeper_ownership_result::ok)
				return 1;
			for (size_t index = 0; index < record.items.size(); ++index)
			{
				const auto &item = record.items[index];
				std::cout << item.object_uid << '\t' << item.vnum << '\t'
					  << identities[index].parent_item_uid << '\t'
					  << item.equipment_slot << '\t' << item.cost << '\n';
			}
			return 0;
		}
	return 1;
}
