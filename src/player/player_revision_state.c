/****************************************************************************
 *
 *  File: player_revision_state.c                               Part of Duris
 *  Usage: tracks written and acknowledged player save revisions
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "player/player_revision_state.h"

#include <array>
#include <limits>
#include <new>
#include <unordered_map>

namespace
{
constexpr size_t MAX_PLAYER_REVISION_STATES = 8192;
constexpr size_t CHECKPOINT_COMPONENT_COUNT = 14;

struct player_revision_entry
{
	player_revision_t current_revision = 0;
	player_revision_t acknowledged_revision = 0;
	player_revision_t written_revision = 0;
	player_component_mask_t unacknowledged_components = 0;
	std::array<player_revision_t, CHECKPOINT_COMPONENT_COUNT> component_revisions = {};
	bool overflowed = false;
};

std::unordered_map<int, player_revision_entry> revision_states;

bool valid_components(player_component_mask_t components)
{
	return components && !(components & ~PLAYER_CHECKPOINT_COMPONENT_ALL);
}

player_revision_entry *find_state(int pid)
{
	auto found = revision_states.find(pid);
	return found == revision_states.end() ? nullptr : &found->second;
}

void clear_acknowledged_components(player_revision_entry &state, player_revision_t revision,
				   player_component_mask_t components)
{
	for (size_t index = 0; index < CHECKPOINT_COMPONENT_COUNT; ++index)
	{
		const player_component_mask_t component = UINT64_C(1) << index;
		if ((components & component) && state.component_revisions[index] <= revision)
			state.unacknowledged_components &= ~component;
	}
}
} // namespace

bool player_revision_hydrate(int pid, player_revision_t durable_revision)
{
	if (pid <= 0)
		return false;

	player_revision_entry *state = find_state(pid);
	if (state)
	{
		if (state->unacknowledged_components)
			return durable_revision == state->acknowledged_revision;
		if (durable_revision < state->acknowledged_revision)
			return false;
		state->current_revision = durable_revision;
		state->acknowledged_revision = durable_revision;
		state->written_revision = durable_revision;
		state->component_revisions.fill(durable_revision);
		return true;
	}

	if (revision_states.size() >= MAX_PLAYER_REVISION_STATES)
		return false;

	try
	{
		player_revision_entry entry;
		entry.current_revision = durable_revision;
		entry.acknowledged_revision = durable_revision;
		entry.written_revision = durable_revision;
		entry.component_revisions.fill(durable_revision);
		revision_states.emplace(pid, entry);
	}
	catch (const std::bad_alloc &)
	{
		return false;
	}
	return true;
}

bool player_revision_mark(int pid, player_component_mask_t components,
			  player_revision_t *revision_out)
{
	player_revision_entry *state = find_state(pid);
	if (!state || !valid_components(components) || state->overflowed)
		return false;
	if (state->current_revision == std::numeric_limits<player_revision_t>::max())
	{
		state->overflowed = true;
		return false;
	}

	++state->current_revision;
	state->unacknowledged_components |= components;
	for (size_t index = 0; index < CHECKPOINT_COMPONENT_COUNT; ++index)
	{
		if (components & (UINT64_C(1) << index))
			state->component_revisions[index] = state->current_revision;
	}
	if (revision_out)
		*revision_out = state->current_revision;
	return true;
}

bool player_revision_queue(int pid, player_revision_t *revision_out,
			   player_component_mask_t *components_out)
{
	player_revision_entry *state = find_state(pid);
	if (!state || !state->unacknowledged_components)
		return false;

	if (revision_out)
		*revision_out = state->current_revision;
	if (components_out)
		*components_out = state->unacknowledged_components;
	return true;
}

bool player_revision_acknowledge_durable(int pid, player_revision_t revision,
					 player_component_mask_t components)
{
	player_revision_entry *state = find_state(pid);
	if (!state || !valid_components(components) || revision < state->acknowledged_revision ||
	    revision > state->current_revision)
		return false;

	clear_acknowledged_components(*state, revision, components);
	if (revision > state->acknowledged_revision)
		state->acknowledged_revision = revision;
	return true;
}

bool player_revision_record_written(int pid, player_revision_t revision)
{
	player_revision_entry *state = find_state(pid);
	if (!state)
		return false;
	if (revision > state->written_revision)
		state->written_revision = revision;
	return true;
}

bool player_revision_snapshot_copy(int pid, struct player_revision_snapshot *snapshot_out)
{
	const player_revision_entry *state = find_state(pid);
	if (!state || !snapshot_out)
		return false;

	*snapshot_out = {
		.pid = pid,
		.current_revision = state->current_revision,
		.acknowledged_revision = state->acknowledged_revision,
		.written_revision = state->written_revision,
		.unacknowledged_components = state->unacknowledged_components,
		.overflowed = state->overflowed,
	};
	return true;
}

void player_revision_forget(int pid)
{
	if (pid > 0)
		revision_states.erase(pid);
}

void player_revision_reset_for_tests(void)
{
	revision_states.clear();
}

size_t player_revision_state_count(void)
{
	return revision_states.size();
}

size_t player_revision_dirty_count(void)
{
	size_t count = 0;
	for (const auto &[pid, state] : revision_states)
	{
		(void)pid;
		if (state.unacknowledged_components)
			++count;
	}
	return count;
}
