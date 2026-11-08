#include "flatfile/flatfile_zone_story_quest_state.h"
#include "world/zone_story_quest_feature.h"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>

namespace
{
void require(bool condition, const char *message)
{
	if (!condition)
	{
		std::cerr << message << '\n';
		std::exit(1);
	}
}
} // namespace

int main()
{
	const std::filesystem::path root =
		std::filesystem::temp_directory_path() / "duris-zone-story-flatfile-state-test";
	std::filesystem::remove_all(root);
	std::filesystem::create_directories(root / "domains");
	std::filesystem::permissions(root, std::filesystem::perms::owner_all,
				     std::filesystem::perm_options::replace);
	std::filesystem::permissions(root / "domains", std::filesystem::perms::owner_all,
				     std::filesystem::perm_options::replace);
	std::string error;
	// A restart through this backend recovers the tracker a completion saved.
	zone_story_quest_tracking::quest_definition definition{};
	definition.definition_id = "zone-story:900:001";
	definition.source_system = "zone_story";
	definition.zone_number = 900;
	definition.source_area = "production-qst";
	definition.giver_vnum = 90001;
	definition.completion_key = "zone-story:900:001";
	definition.active = true;
	definition.eligible_for_zone_completion = true;
	definition.repeatable = true;
	definition.content_revision = 7;
	definition.display_name = definition.giver_name = definition.zone_name = "x";
	definition.objective = "x";
	const zone_story_quest_catalog::catalog catalog = { .content_revision = 7,
							    .definitions = { definition } };
	zone_story_quest_feature::service before_restart(catalog);
	zone_story_quest_feature::completion_event event;
	event.transaction.schema_version =
		zone_story_quest_tracking::ZONE_STORY_QUEST_TRACKING_SCHEMA_VERSION;
	event.transaction.transaction_id = "flatfile-restart";
	event.transaction.quest_definition_id = definition.definition_id;
	event.transaction.zone_number = 900;
	event.transaction.direct_completer_pid = 42;
	event.transaction.credited_pids = { 42 };
	event.transaction.room_vnum = 90010;
	event.transaction.completed_at = 172800100;
	event.transaction.season_id = 7;
	event.transaction.content_revision = 7;
	event.character_name = "Alice";
	event.level = 10;
	event.racewar = 1;
	require(before_restart.record_completion(event, &error) ==
			zone_story_quest_feature::result::applied,
		"completion was not applied");
	require(flatfile_zone_story_quest_state_save(root.string().c_str(), 7,
						     before_restart.serialize_state(), &error) ==
			flatfile_zone_story_quest_result::ok,
		"tracker state did not save");
	std::string saved;
	zone_story_quest_feature::service after_restart(catalog);
	require(flatfile_zone_story_quest_state_load(root.string().c_str(), 7, &saved, &error) ==
				flatfile_zone_story_quest_result::ok &&
			after_restart.deserialize_state(saved, &error) &&
			after_restart.summary_for(7, 42).completed == 1 &&
			after_restart.record_completion(event, &error) ==
				zone_story_quest_feature::result::already_applied,
		"tracker state did not recover through a flat-file restart");

	const std::string state = "ZSQF|1\nT|74657374|76616c7565\n";
	require(flatfile_zone_story_quest_state_save(root.string().c_str(), 7, state, &error) ==
			flatfile_zone_story_quest_result::ok,
		"flat-file state did not save");
	std::string recovered;
	require(flatfile_zone_story_quest_state_load(root.string().c_str(), 7, &recovered,
						     &error) ==
				flatfile_zone_story_quest_result::ok &&
			recovered == state,
		"flat-file state did not round-trip");
	require(flatfile_zone_story_quest_state_load(root.string().c_str(), 8, &recovered,
						     &error) ==
			flatfile_zone_story_quest_result::corrupt,
		"flat-file state accepted a stale catalog revision");

	const auto state_path = root / "domains" / "zone-story-quests.state";
	std::fstream file(state_path, std::ios::in | std::ios::out | std::ios::binary);
	file.seekp(-1, std::ios::end);
	char value = 0;
	file.read(&value, 1);
	file.seekp(-1, std::ios::end);
	value ^= 1;
	file.write(&value, 1);
	file.close();
	require(flatfile_zone_story_quest_state_load(root.string().c_str(), 7, &recovered,
						     &error) ==
			flatfile_zone_story_quest_result::corrupt,
		"flat-file checksum corruption was not detected");
	std::filesystem::remove_all(root);
	std::cout << "zone-story flat-file state regression passed\n";
	return 0;
}
