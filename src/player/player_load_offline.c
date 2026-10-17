/****************************************************************************
 *
 *  File: player_load_offline.c                                 Part of Duris
 *  Usage: loads an offline character for a command and completes it
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "player/player_load_offline.h"

#include "core/prototypes.h"
#include "core/structs.h"
#include "core/mm.h"
#include "persistence/persistence_observability.h"
#include "player/player_load_items.h"
#include "player/player_load_materialize.h"
#include "player/player_load_pipeline.h"
#include "sql/sql_player.h"

#include <unordered_map>

extern struct mm_ds *dead_mob_pool;
extern struct mm_ds *dead_pconly_pool;

namespace
{
// Game thread only.
std::unordered_map<uint64_t, std::function<void(const player_load_result &)>> offline_loads;

// Full item loads are for an offline owner; status-only temporary reads and raw
// inspections do not construct a second gameplay item graph.
bool can_materialize_items(const player_load_result &result)
{
	return result.outcome != player_load_outcome::applied ||
	       (!player_load_pid_busy(result.pid, nullptr) &&
		!player_load_pipeline_pid_pending(result.pid));
}

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
bool submit_offline(const char *name, bool include_items,
		    std::function<void(const player_load_result &)> done)
{
	if (!name || !*name || !done)
		return false;
	player_load_request request = {};
	request.request_id = player_load_pipeline_next_request_id();
	// By pid when the character exists: the load then waits for its queued saves, as a
	// login does, so a copy that is saved back is never older than them.
	const int pid = sql_get_player_pid(name);
	if (pid > 0)
		request.pid = pid;
	else
		request.player_name = name;
	request.include_items = include_items;
	request.include_pets = false;
	request.deadline_usec = persistence_observability_now_usec() + PLAYER_LOAD_TIMEOUT_USEC;
	if (player_load_pipeline_submit(request) != player_load_submit_outcome::accepted)
		return false;
	offline_loads.emplace(request.request_id, std::move(done));
	return true;
}

bool submit_offline_for(P_char ch, const char *name, bool include_items,
			std::function<void(P_char, const player_load_result &)> done)
{
	if (!ch || !done)
		return false;
	const uint64_t runtime_id = ch->runtime_id;
	if (submit_offline(name, include_items,
			   [runtime_id, done = std::move(done)](const player_load_result &result)
			   {
				   if (P_char live = find_character_by_runtime_id(runtime_id))
					   done(live, result);
			   }))
		return true;
	send_to_char("That is not available right now.\r\n", ch);
	return false;
}
} // namespace

bool player_load_offline(const char *name, bool include_items, std::function<void(P_char)> done)
{
	if (!done)
		return false;
	return submit_offline(
		name, include_items,
		[include_items, done = std::move(done)](const player_load_result &result) {
			done(include_items && !can_materialize_items(result) ? nullptr :
									       materialize(result));
		});
}

bool player_load_offline_for(P_char ch, const char *name, bool include_items,
			     std::function<void(P_char, P_char)> done)
{
	if (!done)
		return false;
	return submit_offline_for(
		ch, name, include_items,
		[include_items, done = std::move(done)](P_char live,
							const player_load_result &result)
		{
			if (include_items && !can_materialize_items(result))
			{
				send_to_char_f(
					live,
					"Character pid %d is already active or loading; item load refused.\r\n",
					result.pid);
				return;
			}
			done(live, materialize(result));
		});
}

bool player_load_offline_inspect_for(P_char ch, const char *name,
				     std::function<void(P_char, const player_load_result &)> done)
{
	return submit_offline_for(ch, name, true, std::move(done));
}

bool player_load_offline_complete(const player_load_result &result)
{
	auto found = offline_loads.find(result.request_id);
	if (found == offline_loads.end())
		return false;
	auto done = std::move(found->second);
	offline_loads.erase(found);
	done(result);
	return true;
}
