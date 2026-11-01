#include "flatfile/flatfile_world_quest_history.h"
#include "sql/sql.h"
#include "player/player_snapshot_capture.h"
#include "player/player_load_items.h"
#include "flatfile/flatfile_item_repository.h"
#include "player/player_save_pipeline.h"
#include "player/player_snapshot.h"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>

namespace fs = std::filesystem;

namespace
{
std::string state_root;

void require(bool condition, const std::string &message)
{
	if (!condition)
	{
		std::cerr << message << '\n';
		exit(1);
	}
}
} // namespace

const char *persistence_mode_flatfile_root()
{
	return state_root.c_str();
}

// The difficulty module is not linked; a neutral world quest dial leaves the allowance alone.
int difficulty_scale_world_quest_allowance(int allowance)
{
	return allowance;
}
float get_property(const char *, double)
{
	return 2.0F;
}

void persistence_alert(int, const char *, const char *, const char *, const char *, const char *,
		       const char *, ...)
{
}

P_obj object_list = nullptr;
P_index obj_index = nullptr;
bool item_ownership_runtime_hydrate_many_atomic(const item_ownership_runtime_entry *, size_t)
{
	std::abort();
}
void obj_to_char(P_obj, P_char)
{
	std::abort();
}
void extract_obj(P_obj, int)
{
	std::abort();
}
player_snapshot_capture_result
player_item_snapshot_tree_capture(P_obj, std::vector<player_item_snapshot> *, size_t *)
{
	std::abort();
}
bool player_load_item_graph_materialize_detached(const std::vector<player_item_snapshot> &,
						 const std::vector<player_load_item_identity> &,
						 const item_owner_identity &, uint64_t, bool, bool,
						 std::vector<P_obj> *,
						 player_load_item_materialize_metrics *)
{
	std::abort();
}
flatfile_item_repository_result
flatfile_item_repository_load_owner(const std::string &, const item_owner_identity &, uint64_t *,
				    std::vector<flatfile_item_ownership_record> *, std::string *)
{
	std::abort();
}

bool player_save_pipeline_submit_world_quest(
	P_char ch, const player_pending_world_quest &quest,
	std::function<bool(P_char, const player_pending_world_quest &)> committed)
{
	std::string error;
	if (flatfile_world_quest_record(persistence_mode_flatfile_root(), ch->only.pc->pid,
					quest.target, quest.level, quest.occurred_at,
					&error) != flatfile_world_quest_result::ok)
		return false;
	return committed(ch, quest);
}
int main(int argc, char **argv)
{
	require(argc == 2, "state root argument required");
	state_root = argv[1];
	const fs::path players = fs::path(state_root) / "players";
	fs::create_directories(players);
	fs::permissions(state_root, fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(players, fs::perms::owner_all, fs::perm_options::replace);

	constexpr int64_t day = 100 * 60 * 60 * 24;
	std::string error;
	int count = -1;
	require(flatfile_world_quest_count_day(state_root.c_str(), 7, 30, day + 10, &count,
					       &error) == flatfile_world_quest_result::ok &&
			count == 0,
		"missing world-quest history was not an empty history");
	require(flatfile_world_quest_record(state_root.c_str(), 7, 1001, 30, day + 20, &error) ==
			flatfile_world_quest_result::ok,
		"deterministic world-quest completion failed");
	bool completed = false;
	require(flatfile_world_quest_completed(state_root.c_str(), 7, 1001, &completed, &error) ==
				flatfile_world_quest_result::ok &&
			completed,
		"completed target was not retained");
	require(flatfile_world_quest_count_day(state_root.c_str(), 7, 30, day + 30, &count,
					       &error) == flatfile_world_quest_result::ok &&
			count == 1,
		"same-level daily completion was not counted");
	require(flatfile_world_quest_count_day(state_root.c_str(), 7, 31, day + 30, &count,
					       &error) == flatfile_world_quest_result::ok &&
			count == 0,
		"sub-level-50 daily count included another level");
	require(flatfile_world_quest_count_day(state_root.c_str(), 7, 50, day + 30, &count,
					       &error) == flatfile_world_quest_result::ok &&
			count == 1,
		"level-50 daily count did not include all completion levels");
	require(flatfile_world_quest_record(state_root.c_str(), 7, 1002, 30, day - 60 * 60 * 24,
					    &error) == flatfile_world_quest_result::ok &&
			flatfile_world_quest_count_day(state_root.c_str(), 7, 30, day + 30, &count,
						       &error) == flatfile_world_quest_result::ok &&
			count == 1,
		"prior-day completion affected the current daily allowance");

	pc_only_data pc = {};
	pc.pid = 42;
	char_data player = {};
	player.only.pc = &pc;
	player.player.name = const_cast<char *>("Tester");
	player.player.level = 30;
	require(sql_world_quest_can_do_another(&player) == 2,
		"missing SQL-compatible history did not return the configured allowance");
	pc.quest_mob_vnum = 2001;
	require(sql_world_quest_finish_async(&player, {}, false, false, {}, 0,
					     [](P_char) { return true; }),
		"first completion was refused");
	require(sql_world_quest_done_already(&player, 2001) == 1 &&
			sql_world_quest_can_do_another(&player) == 1,
		"first SQL-compatible completion was not retained or counted");
	pc.quest_mob_vnum = 2002;
	require(sql_world_quest_finish_async(&player, {}, false, false, {}, 0,
					     [](P_char) { return true; }),
		"second completion was refused");
	require(sql_world_quest_can_do_another(&player) == 0,
		"daily world-quest allowance was not exhausted");
	player.player.level = 31;
	require(sql_world_quest_can_do_another(&player) == 2,
		"sub-level-50 allowance did not follow current-level database semantics");
	player.player.level = 50;
	require(sql_world_quest_can_do_another(&player) == 0,
		"level-50 allowance did not count all today's completions");

	const fs::path authority = players / "42.world-quests";
	require(fs::is_regular_file(authority), "world-quest history file was not created");
	require((fs::status(authority).permissions() & fs::perms::group_all) == fs::perms::none &&
			(fs::status(authority).permissions() & fs::perms::others_all) ==
				fs::perms::none,
		"world-quest history permissions were not private");
	std::fstream corrupt(authority, std::ios::in | std::ios::out | std::ios::binary);
	require(corrupt.good(), "could not open world-quest history for corruption test");
	corrupt.seekg(-1, std::ios::end);
	char byte = 0;
	corrupt.read(&byte, 1);
	byte ^= 0x5a;
	corrupt.seekp(-1, std::ios::end);
	corrupt.write(&byte, 1);
	corrupt.close();
	require(sql_world_quest_done_already(&player, 2001) < 0 &&
			sql_world_quest_can_do_another(&player) < 0,
		"corrupt world-quest history did not fail closed");
	require(flatfile_world_quest_record(state_root.c_str(), 42, 2003, 50, day + 40, &error) ==
			flatfile_world_quest_result::corrupt,
		"completion overwrote corrupt world-quest history");

	std::cout << "flat-file world-quest history regression passed\n";
	return 0;
}
