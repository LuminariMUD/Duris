#include "player/player_load_offline.h"

#include "core/prototypes.h"
#include "core/structs.h"
#include "core/mm.h"
#include "persistence/persistence_observability.h"
#include "player/player_load_materialize.h"
#include "player/player_load_pipeline.h"

#include <unordered_map>

extern struct mm_ds *dead_mob_pool;
extern struct mm_ds *dead_pconly_pool;

namespace
{
// Game thread only.
std::unordered_map<uint64_t, std::function<void(P_char)>> offline_loads;

P_char materialize(const player_load_result &result)
{
	if (result.outcome != player_load_outcome::applied)
		return nullptr;
	P_char character = (P_char)mm_get(dead_mob_pool);
	if (!character)
		return nullptr;
	clear_char(character);
	ensure_pconly_pool();
	character->only.pc = (struct pc_only_data *)mm_get(dead_pconly_pool);
	if (!character->only.pc)
	{
		mm_release(dead_mob_pool, character);
		return nullptr;
	}
	if (!player_load_materialize(character, result))
	{
		free_char(character);
		return nullptr;
	}
	return character;
}
} // namespace

bool player_load_offline(const char *name, bool include_items, std::function<void(P_char)> done)
{
	if (!name || !*name || !done)
		return false;
	player_load_request request = {};
	request.request_id = player_load_pipeline_next_request_id();
	request.player_name = name;
	request.include_items = include_items;
	request.include_pets = false;
	request.deadline_usec = persistence_observability_now_usec() + PLAYER_LOAD_TIMEOUT_USEC;
	if (player_load_pipeline_submit(request) != player_load_submit_outcome::accepted)
		return false;
	offline_loads.emplace(request.request_id, std::move(done));
	return true;
}

bool player_load_offline_for(P_char ch, const char *name, bool include_items,
			     std::function<void(P_char ch, P_char loaded)> done)
{
	const uint64_t runtime_id = ch->runtime_id;
	if (player_load_offline(name, include_items,
				[runtime_id, done = std::move(done)](P_char loaded)
				{
					P_char live = find_character_by_runtime_id(runtime_id);
					if (live)
						done(live, loaded);
					else if (loaded)
						free_char(loaded);
				}))
		return true;
	send_to_char("That is not available right now.\r\n", ch);
	return false;
}

bool player_load_offline_complete(const player_load_result &result)
{
	auto found = offline_loads.find(result.request_id);
	if (found == offline_loads.end())
		return false;
	std::function<void(P_char)> done = std::move(found->second);
	offline_loads.erase(found);
	done(materialize(result));
	return true;
}
