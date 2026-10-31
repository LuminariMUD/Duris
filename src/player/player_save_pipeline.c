/****************************************************************************
 *
 *  File: player_save_pipeline.c                                Part of Duris
 *  Usage: player save pipeline: snapshots, completions, and shutdown
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "player/player_save_pipeline.h"
#include "persistence/persistence_observability.h"
#include <cstdlib>
#include <cstring>
#include <cstdio>

#include "core/prototypes.h"
#include "core/files.h"
#include "item/storage_lockers.h"
#include "economy/collector_death_enrollment.h"
#include "economy/currency_value.h"
#include "economy/divine_boon_runtime.h"
#include "flatfile/flatfile_player_repository.h"
#include "player/player_save_worker.h"
#include "player/player_snapshot_capture.h"
#include "player/player_snapshot_repository.h"
#include "core/structs.h"
#include "core/utils.h"
#include "persistence/critical_command_coordinator.h"

#include <array>
#include <cerrno>
#include <chrono>
#include <mutex>
#include <thread>
#include <unordered_map>
#include <unordered_set>
#include <utility>

extern P_char character_list;
extern P_room world;

namespace
{
uint32_t trade_player_pid = 0;
player_pending_trade_snapshot trade_capture;
struct pending_world_quest_save
{
	player_pending_world_quest quest;
	std::function<bool(P_char, const player_pending_world_quest &)> committed;
	player_revision_t first_revision = 0;
	std::shared_ptr<player_snapshot> latest;
	std::chrono::steady_clock::time_point retry{};
	bool durable = false;
};
std::unordered_map<int, std::shared_ptr<pending_world_quest_save>> pending_world_quests;

/** Cache the explicit diagnostic switch for player-save capture and durability tracing. */
bool trace_player_saves()
{
	static const bool enabled = []
	{
		const char *value = std::getenv("DURIS_NEVENT_TRACE_PLAYER");
		return value && std::strcmp(value, "1") == 0;
	}();
	return enabled;
}

std::mutex pipeline_mutex;
player_save_pipeline_health health = {};
bool accepting = false;

player_save_apply_fn selected_snapshot_apply()
{
#ifdef __NO_MYSQL__
	return flatfile_player_snapshot_apply_selected;
#else
	return player_snapshot_repository_apply_from_pool;
#endif
}

P_char live_player(int pid)
{
	for (P_char ch = character_list; ch; ch = ch->next)
		if (IS_PC(ch) && GET_PID(ch) == pid)
			return ch;
	return nullptr;
}

void retire_ended_player(int pid)
{
	player_revision_snapshot revision = {};
	if (player_revision_snapshot_copy(pid, &revision) && revision.session_ended &&
	    !live_player(pid) && !player_save_pipeline_world_quest_pending(pid) &&
	    !player_save_worker_pid_pending(pid))
		player_revision_forget(pid);
}

bool completion_succeeded(const player_save_completion &completion)
{
	return completion.outcome == player_save_apply_outcome::applied ||
	       completion.outcome == player_save_apply_outcome::already_applied ||
	       completion.outcome == player_save_apply_outcome::stale_revision;
}

/** Account for one writer completion on the game thread. */
void finish_completion(const player_save_completion &completion)
{
	if (trace_player_saves())
		logit(LOG_STATUS,
		      "PLAYER SAVE TRACE: stage=completion mono_us=%llu kind=%s owner=%llu revision=%llu components=%llu outcome=%u error=%u retries=%u queued_us=%llu started_us=%llu completed_us=%llu",
		      (unsigned long long)persistence_observability_now_usec(),
		      persistence_job_kind_name(completion.kind),
		      (unsigned long long)completion.owner, (unsigned long long)completion.revision,
		      (unsigned long long)completion.components, (unsigned)completion.outcome,
		      completion.error_code, completion.retry_count,
		      (unsigned long long)completion.queued_at_usec,
		      (unsigned long long)completion.started_at_usec,
		      (unsigned long long)completion.completed_at_usec);
	const bool succeeded = completion_succeeded(completion);
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		++health.completions;
		if (!succeeded)
			++health.write_failures;
	}
	if (succeeded)
	{
		if (completion.kind == persistence_job_kind::player)
		{
			player_revision_record_written(completion.pid, completion.revision);
			std::lock_guard<std::mutex> lock(pipeline_mutex);
			auto pending = pending_world_quests.find(completion.pid);
			if (pending != pending_world_quests.end() &&
			    pending->second->first_revision &&
			    completion.revision >= pending->second->first_revision &&
			    completion.outcome != player_save_apply_outcome::stale_revision)
			{
				pending->second->durable = true;
				pending->second->retry = {};
			}
		}
		if (completion.kind == persistence_job_kind::corpse)
			collector_death_enrollment_saved(completion.owner, completion.error_code);
		return;
	}
	if (completion.kind != persistence_job_kind::player)
	{
		char domain[64];
		snprintf(domain, sizeof(domain), "persistence_writer/%s",
			 persistence_job_kind_name(completion.kind));
		persistence_alert(AVATAR, domain, "redacted", "none", "none", "write_failed",
				  "owner=%llu error=%u", (unsigned long long)completion.owner,
				  completion.error_code);
		return;
	}
	// The job is gone. Mark the owner dirty so its next save carries the state again.
	P_char ch = live_player(completion.pid);
#ifdef __NO_MYSQL__
	// The player's records are missing: the next save establishes them synchronously.
	// (MariaDB has no such save; its writer inserts a missing row from the status.)
	if (ch && completion.error_code == ENOENT)
		SET_BIT(ch->runtime_flags, CHAR_RFLAG_NO_DB_BASELINE);
#endif
	const bool remarked = ch &&
			      player_save_pipeline_mark(completion.pid, completion.components);
	player_revision_snapshot revision = {};
	player_revision_snapshot_copy(completion.pid, &revision);
	// Persistence alerts accept numeric substitutions only. Keep the bounded field
	// identifier in a separate diagnostic, correlated by PID and failed revision.
	if (completion.failed_field[0])
		logit(LOG_FILE, "PLAYER SAVE FIELD: pid=%d revision=%llu field=%.63s",
		      completion.pid, (unsigned long long)completion.revision,
		      completion.failed_field.data());
	persistence_alert(
		AVATAR, "player_save", "redacted", "none", "none", "write_failed",
		"pid=%d revision=%llu error=%u remarked=%d ended=%d queued_revision=%llu written_revision=%llu rollback_confirmed=%d",
		completion.pid, (unsigned long long)completion.revision, completion.error_code,
		remarked ? 1 : 0, revision.session_ended ? 1 : 0,
		(unsigned long long)revision.acknowledged_revision,
		(unsigned long long)revision.written_revision, completion.rolled_back ? 1 : 0);
}

/** Hand a sealed capture to the writer. The owner is clean once it is queued. */
player_save_pipeline_result submit_snapshot(player_snapshot snapshot)
{
	const int pid = snapshot.pid;
	const player_revision_t revision = snapshot.revision;
	const player_component_mask_t components = snapshot.components;
	const player_save_submit_result submitted = player_save_worker_submit(std::move(snapshot));
	if (trace_player_saves())
		logit(LOG_STATUS,
		      "PLAYER SAVE TRACE: stage=submit mono_us=%llu pid=%d revision=%llu outcome=%u",
		      (unsigned long long)persistence_observability_now_usec(), pid,
		      (unsigned long long)revision, (unsigned)submitted);
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	if (submitted != player_save_submit_result::accepted &&
	    submitted != player_save_submit_result::replaced)
	{
		++health.submit_failures;
		return player_save_pipeline_result::unavailable;
	}
	player_revision_acknowledge_durable(pid, revision, components);
	if (submitted == player_save_submit_result::replaced)
	{
		++health.coalesced;
		return player_save_pipeline_result::coalesced;
	}
	++health.captured;
	return player_save_pipeline_result::queued;
}
} // namespace

bool player_save_pipeline_init(void)
{
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		if (health.initialized)
			return false;
		health = {};
	}
	if (!player_save_worker_init(selected_snapshot_apply(), nullptr))
		return false;
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	health.initialized = true;
	accepting = true;
	health.accepting = true;
	return true;
}

/** Stop the writer and release pipeline state. */
void player_save_pipeline_shutdown(void)
{
	player_save_worker_shutdown();
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	accepting = false;
	health.accepting = false;
	health.initialized = false;
}

/** Mark player components dirty. */
bool player_save_pipeline_mark(int pid, player_component_mask_t components)
{
	/* Equipment and inventory are one item graph: a save writes both halves. */
	if (components & (PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY))
		components |= PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY;
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	if (!accepting)
		return false;
	player_revision_t revision = 0;
	if (!player_revision_mark(pid, components, &revision))
		return false;
	++health.marked;
	return true;
}

/** Capture and queue pending player components with the supplied save intent and room. */
player_save_pipeline_result player_save_pipeline_checkpoint_dirty(P_char ch, int save_intent,
								  int room_vnum)
{
	if (!ch || IS_NPC(ch) || GET_PID(ch) <= 0)
		return player_save_pipeline_result::invalid;
	if (ch->only.pc->divine_boon_delivery_applying)
		return player_save_pipeline_result::coalesced;
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		if (!health.initialized)
			return player_save_pipeline_result::unavailable;
	}
	player_revision_snapshot revision = {};
	if (!player_revision_snapshot_copy(GET_PID(ch), &revision))
		return player_save_pipeline_result::unavailable;
	if (!revision.unacknowledged_components)
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		++health.unchanged;
		return player_save_pipeline_result::unchanged;
	}
	// The player snapshot removes absent inventory rows. Commit a private chest's
	// destination first, so a failed chest write cannot erase the last saved copy.
	if ((revision.unacknowledged_components &
	     (PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY)) &&
	    !locker_private_contents_durable(ch))
		return player_save_pipeline_result::capture_failed;
	player_revision_t queued_revision = 0;
	player_component_mask_t components = 0;
	if (!player_revision_queue(GET_PID(ch), &queued_revision, &components))
		return player_save_pipeline_result::capture_failed;
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		auto pending = pending_world_quests.find(GET_PID(ch));
		if (pending != pending_world_quests.end())
		{
			components |= PLAYER_COMPONENT_STATUS;
			if (!pending->second->quest.reward_items.empty())
				components |= PLAYER_COMPONENT_EQUIPMENT |
					      PLAYER_COMPONENT_INVENTORY;
		}
	}
	player_snapshot snapshot;
	if (player_snapshot_capture(ch, queued_revision, components, save_intent, room_vnum,
				    &snapshot) != player_snapshot_capture_result::ok)
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		++health.capture_failures;
		return player_save_pipeline_result::capture_failed;
	}
	try
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		if (trade_player_pid == static_cast<uint32_t>(GET_PID(ch)))
		{
			snapshot.pending_trade = trade_capture;
			const auto extra =
				trade_capture.has_cargo_effect ?
					trade_capture.cargo_effect.wear_off_character.size() +
						trade_capture.cargo_effect.wear_off_room.size() :
					0;
			if (extra > PLAYER_SNAPSHOT_MAX_BYTES - snapshot.encoded_size_bound)
				return player_save_pipeline_result::capture_failed;
			snapshot.encoded_size_bound += extra;
		}
		auto pending = pending_world_quests.find(GET_PID(ch));
		if (pending != pending_world_quests.end())
		{
			auto quest = pending->second->quest;
			quest.before_quest = snapshot.quest_values;
			for (const auto &row : snapshot.status_integers)
			{
				if (row.field == player_status_field::quest_origin_room)
					quest.before_origin =
						static_cast<int32_t>(row.signed_value);
				else if (row.field == player_status_field::quest_replacement_due)
					quest.before_replacement_due =
						static_cast<int32_t>(row.signed_value);
			}
			const size_t extra = sizeof(quest) + quest.player_name.size() +
					     quest.reward_description.size();
			if (snapshot.encoded_size_bound > PLAYER_SNAPSHOT_MAX_BYTES ||
			    extra > PLAYER_SNAPSHOT_MAX_BYTES - snapshot.encoded_size_bound)
				return player_save_pipeline_result::capture_failed;
			snapshot.encoded_size_bound += extra;
			if (snapshot.items.size() > PLAYER_SNAPSHOT_MAX_OBJECTS ||
			    snapshot.retained_items.rows.size() >
				    PLAYER_SNAPSHOT_MAX_OBJECTS - snapshot.items.size() ||
			    quest.reward_encoded_size >
				    (PLAYER_SNAPSHOT_MAX_BYTES - snapshot.encoded_size_bound) / 2 ||
			    quest.reward_items.size() > PLAYER_SNAPSHOT_MAX_OBJECTS -
								snapshot.items.size() -
								snapshot.retained_items.rows.size())
				return player_save_pipeline_result::capture_failed;
			snapshot.encoded_size_bound += 2 * quest.reward_encoded_size;
			if (!quest.reward_items.empty())
			{
				std::unordered_set<uint64_t> ids;
				for (const auto &item : snapshot.items)
					if (item.object_uid)
						ids.insert(item.object_uid);
				const size_t offset = snapshot.items.size();
				for (size_t index = 0; index < quest.reward_items.size(); ++index)
				{
					auto item = quest.reward_items[index];
					if (!item.object_uid ||
					    !ids.insert(item.object_uid).second ||
					    item.parent_index < PLAYER_SNAPSHOT_NO_PARENT ||
					    item.parent_index >= static_cast<int32_t>(index) ||
					    (index &&
					     item.parent_index == PLAYER_SNAPSHOT_NO_PARENT))
						return player_save_pipeline_result::capture_failed;
					if (item.parent_index != PLAYER_SNAPSHOT_NO_PARENT)
						item.parent_index += static_cast<int32_t>(offset);
					snapshot.items.push_back(std::move(item));
				}
			}
			snapshot.pending_world_quest = quest;
			if (quest.escrow_fee)
			{
				currency_vector before{}, after{};
				std::array<player_snapshot_integer *, 4> wallet{};
				for (auto &row : snapshot.status_integers)
					if (row.field >= player_status_field::copper &&
					    row.field <= player_status_field::platinum)
					{
						const auto index =
							static_cast<size_t>(row.field) -
							static_cast<size_t>(
								player_status_field::copper);
						wallet[index] = &row;
						before.amount[index] = row.signed_value;
					}
				if (std::any_of(wallet.begin(), wallet.end(),
						[](const auto *row) { return !row; }) ||
				    snapshot.wallet_revision == UINT64_MAX ||
				    !currency_wallet_after_value(
					    before, -static_cast<int64_t>(quest.escrow_fee),
					    &after))
					return player_save_pipeline_result::capture_failed;
				snapshot.pending_world_quest.before_wallet = before.amount;
				snapshot.pending_world_quest.before_wallet_revision =
					snapshot.wallet_revision;
				for (size_t index = 0; index < wallet.size(); ++index)
					wallet[index]->signed_value = after.amount[index];
				++snapshot.wallet_revision;
			}
			if (quest.awaiting_reward)
			{
				snapshot.quest_values[3] =
					quest.final_kill_reward ?
						PLAYER_WORLD_QUEST_KILL_REWARD_PENDING :
						PLAYER_WORLD_QUEST_REWARD_PENDING;
				// Once completed, receiver/share/kill counters are no longer used.
				// The marker makes these fields a durable reward receipt until reset.
				snapshot.quest_values[8] = quest.reward.experience;
				snapshot.quest_values[9] = quest.reward.epic;
				snapshot.quest_values[10] = quest.reward.money;
			}
			else
			{
				snapshot.quest_values.fill(0);
				snapshot.quest_values[5] = -1;
				for (auto &row : snapshot.status_integers)
					if (row.field == player_status_field::quest_origin_room ||
					    row.field == player_status_field::quest_replacement_due)
					{
						row.signed_value = 0;
						row.unsigned_value = 0;
					}
			}
			pending->second->latest = std::make_shared<player_snapshot>(snapshot);
			if (!pending->second->first_revision)
				pending->second->first_revision = queued_revision;
		}
	}
	catch (const std::bad_alloc &)
	{
		return player_save_pipeline_result::capture_failed;
	}
	if (trace_player_saves())
		logit(LOG_STATUS,
		      "PLAYER SAVE TRACE: stage=capture mono_us=%llu pid=%d revision=%llu components=%llu intent=%d room=%d",
		      (unsigned long long)persistence_observability_now_usec(), GET_PID(ch),
		      (unsigned long long)queued_revision, (unsigned long long)components,
		      save_intent, room_vnum);
	return submit_snapshot(std::move(snapshot));
}

/** Mark requested components and capture a checkpoint with the supplied intent and room. */
player_save_pipeline_result player_save_pipeline_request(P_char ch,
							 player_component_mask_t components,
							 int save_intent, int room_vnum)
{
	// A character saves only the components its load read (player_load_materialize()).
	if (!ch || IS_NPC(ch) ||
	    !player_save_pipeline_mark(GET_PID(ch), components & ~ch->only.pc->unloaded_components))
		return player_save_pipeline_result::invalid;
	return player_save_pipeline_checkpoint_dirty(ch, save_intent, room_vnum);
}

/** Capture fresh terminal intent and wait for it to be written within the caller timeout. */
player_save_terminal_result player_save_pipeline_terminal(P_char ch, int save_intent, int room_vnum,
							  uint64_t timeout_msec)
{
	if (!ch || IS_NPC(ch) || GET_PID(ch) <= 0 || !timeout_msec)
		return player_save_terminal_result::invalid;
	const int pid = GET_PID(ch);
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		if (!health.initialized)
			return player_save_terminal_result::unavailable;
		++health.terminal_saves;
	}
	// Every terminal call captures the caller's current intent and room.
	player_revision_t revision = 0;
	if (!player_revision_mark(pid, PLAYER_CHECKPOINT_COMPONENT_ALL, &revision))
		return player_save_terminal_result::unavailable;
	const auto checkpoint = player_save_pipeline_checkpoint_dirty(ch, save_intent, room_vnum);
	if (trace_player_saves())
		logit(LOG_STATUS,
		      "PLAYER SAVE TRACE: stage=terminal_begin mono_us=%llu pid=%d revision=%llu checkpoint=%u intent=%d timeout_ms=%llu",
		      (unsigned long long)persistence_observability_now_usec(), pid,
		      (unsigned long long)revision, (unsigned)checkpoint, save_intent,
		      (unsigned long long)timeout_msec);
	const auto deadline =
		std::chrono::steady_clock::now() + std::chrono::milliseconds(timeout_msec);
	while (std::chrono::steady_clock::now() < deadline)
	{
		player_save_pipeline_pulse();
		player_revision_snapshot written = {};
		if (player_revision_snapshot_copy(pid, &written) &&
		    written.written_revision >= revision)
		{
			std::lock_guard<std::mutex> lock(pipeline_mutex);
			++health.terminal_database_acks;
			return player_save_terminal_result::database_acknowledged;
		}
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	}
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	if (trace_player_saves())
		logit(LOG_STATUS,
		      "PLAYER SAVE TRACE: stage=terminal_timeout mono_us=%llu pid=%d target=%llu",
		      (unsigned long long)persistence_observability_now_usec(), pid,
		      (unsigned long long)revision);
	++health.terminal_timeouts;
	return player_save_terminal_result::timed_out;
}

/** Account for every writer completion on the game thread. */
void player_save_pipeline_pulse(void)
{
	player_save_completion completions[PLAYER_SAVE_PIPELINE_PULSE_BUDGET] = {};
	for (;;)
	{
		const size_t completed =
			player_save_worker_pulse(completions, PLAYER_SAVE_PIPELINE_PULSE_BUDGET);
		for (size_t index = 0; index < completed; ++index)
			finish_completion(completions[index]);
		// Finish the entire batch before retiring any previous session's revision.
		for (size_t index = 0; index < completed; ++index)
			if (completions[index].kind == persistence_job_kind::player)
				retire_ended_player(completions[index].pid);
		if (completed < PLAYER_SAVE_PIPELINE_PULSE_BUDGET)
			break;
	}
	// A failed terminal save can outlive its actor. Retain the last immutable
	// capture and retry it rather than dropping the pending history on logout.
	std::vector<std::pair<int, std::shared_ptr<player_snapshot>>> retry;
	std::vector<std::pair<int, std::shared_ptr<pending_world_quest_save>>> publish;
	try
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		for (auto &[pid, pending] : pending_world_quests)
			if (std::chrono::steady_clock::now() >= pending->retry)
			{
				if (pending->durable)
					publish.emplace_back(pid, pending);
				else if (accepting && health.initialized && pending->latest)
					retry.emplace_back(pid, pending->latest);
				pending->retry =
					std::chrono::steady_clock::now() + std::chrono::seconds(1);
			}
	}
	catch (const std::bad_alloc &)
	{
		return;
	}
	for (const auto &[pid, pending] : publish)
	{
		bool published = false;
		try
		{
			published = pending->committed(live_player(pid), pending->quest);
		}
		catch (const std::bad_alloc &)
		{
			// Keep the committed after-image until publication can be retried.
			std::lock_guard<std::mutex> lock(pipeline_mutex);
			++health.capture_failures;
		}
		if (published)
		{
			{
				std::lock_guard<std::mutex> lock(pipeline_mutex);
				auto found = pending_world_quests.find(pid);
				if (found != pending_world_quests.end() && found->second == pending)
					pending_world_quests.erase(found);
			}
			retire_ended_player(pid);
		}
	}
	for (const auto &[pid, snapshot] : retry)
	{
		if (player_save_worker_pid_pending(pid))
			continue;
		if (P_char actor = live_player(pid))
		{
			const int room = actor->in_room == NOWHERE ? NOWHERE :
								     world[actor->in_room].number;
			player_save_pipeline_request(actor, PLAYER_COMPONENT_STATUS, RENT_CRASH,
						     room);
		}
		else
		{
			try
			{
				submit_snapshot(*snapshot);
			}
			catch (const std::bad_alloc &)
			{
				// Keep the immutable capture for the next retry.
				std::lock_guard<std::mutex> lock(pipeline_mutex);
				++health.submit_failures;
			}
		}
	}
}

void player_save_pipeline_quiesce(void)
{
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	accepting = false;
	health.accepting = false;
}

void player_save_pipeline_resume(void)
{
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	if (health.initialized)
		accepting = true;
	health.accepting = accepting;
}

bool player_save_pipeline_drain(uint64_t timeout_msec)
{
	if (!timeout_msec)
		return false;
	player_save_pipeline_quiesce();
	const bool drained = persistence_writer_wait_idle(timeout_msec);
	player_save_pipeline_pulse();
	divine_boon_runtime_pulse();
	bool quest_pending;
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		quest_pending = !pending_world_quests.empty();
	}
	const bool complete = drained && !divine_boon_runtime_pending() && !quest_pending;
	if (!complete)
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		++health.drain_failures;
	}
	return complete;
}

std::vector<persistence_job_owner> player_save_pipeline_finish(uint64_t deadline_usec,
							       void (*interrupt)(void))
{
	player_save_pipeline_quiesce();
	const uint64_t now = persistence_observability_now_usec();
	const bool drained = persistence_writer_wait_idle(
		deadline_usec > now ? (deadline_usec - now) / 1000 : 0);
	player_save_pipeline_pulse();
	player_save_worker_shutdown(drained ? nullptr : interrupt);
	// The job the writer was on when it stopped may have failed since the pulse.
	player_save_pipeline_pulse();
	std::vector<persistence_job_owner> left = persistence_writer_pending_owners();
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		for (const auto &[pid, pending] : pending_world_quests)
		{
			(void)pending;
			const persistence_job_owner owner(persistence_job_kind::player, pid);
			if (std::find(left.begin(), left.end(), owner) == left.end())
				left.push_back(owner);
		}
	}
	divine_boon_runtime_pulse();
	if (divine_boon_runtime_pending())
		left.emplace_back(persistence_job_kind::divine_boon, 1);
	player_save_pipeline_shutdown();
	return left;
}

player_save_pipeline_health player_save_pipeline_health_copy(void)
{
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	return health;
}

size_t player_save_pipeline_dirty_count(void)
{
	return player_revision_dirty_count();
}

/** Classify save intents that do not require a terminal durability fence. */
bool player_save_pipeline_is_nonterminal_type(int save_intent)
{
	return save_intent != RENT_INN && save_intent != RENT_LINKDEAD &&
	       save_intent != RENT_CAMPED && save_intent != RENT_DEATH &&
	       save_intent != RENT_POOFARTI && save_intent != RENT_SWAPARTI &&
	       save_intent != RENT_FIGHTARTI;
}

bool player_save_pipeline_load_held(int pid)
{
	if (pid <= 0)
		return false;
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		if (trade_player_pid == static_cast<uint32_t>(pid) ||
		    pending_world_quests.count(pid))
			return true;
	}
	return player_save_worker_pid_pending(pid) ||
	       critical_command_coordinator_is_fenced(
		       { critical_entity_type::player, static_cast<uint64_t>(pid) }, nullptr);
}

void player_save_pipeline_end_session(int pid)
{
	if (pid <= 0 || live_player(pid))
		return;
	player_revision_end_session(pid);
	retire_ended_player(pid);
}

/** Stop the pipeline and clear writer, revision, and health state for an isolated test. */
void player_save_pipeline_reset_for_tests(void)
{
	player_save_pipeline_shutdown();
	player_save_worker_reset_for_tests();
	player_revision_reset_for_tests();
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	health = {};
	accepting = false;
	trade_player_pid = 0;
	trade_capture = {};
	pending_world_quests.clear();
}

bool player_save_pipeline_world_quest_pending(int pid)
{
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	return pending_world_quests.count(pid) != 0;
}

bool player_save_pipeline_submit_world_quest(
	P_char ch, const player_pending_world_quest &quest,
	std::function<bool(P_char, const player_pending_world_quest &)> committed)
{
	const auto required = PLAYER_COMPONENT_STATUS |
			      (quest.reward_items.empty() ?
				       0 :
				       PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY);
	if (!ch || IS_NPC(ch) || !ch->only.pc || GET_PID(ch) <= 0 || !quest.present || !committed ||
	    (ch->only.pc->unloaded_components & required) || quest.escrow_fee < 0 ||
	    quest.fallback_only || (quest.awaiting_reward && quest.escrow_fee) ||
	    (quest.final_kill_reward && !quest.awaiting_reward) ||
	    (!quest.awaiting_reward && !quest.reward_items.empty()) ||
	    (quest.reward_items.empty() != (quest.reward_encoded_size == 0)))
		return false;
	const int pid = GET_PID(ch);
	try
	{
		{
			std::lock_guard<std::mutex> lock(pipeline_mutex);
			if (!accepting || !health.initialized || pending_world_quests.count(pid) ||
			    pending_world_quests.size() >= PLAYER_SAVE_PIPELINE_MAX_SNAPSHOTS)
				return false;
			pending_world_quests.emplace(
				pid, std::make_shared<pending_world_quest_save>(
					     quest, std::move(committed), 0, nullptr,
					     std::chrono::steady_clock::time_point{}, false));
		}
		const int room = ch->in_room == NOWHERE ? NOWHERE : world[ch->in_room].number;
		const auto result =
			player_save_pipeline_request(ch, PLAYER_COMPONENT_STATUS, RENT_CRASH, room);
		if (result == player_save_pipeline_result::queued ||
		    result == player_save_pipeline_result::coalesced)
			return true;
	}
	catch (const std::bad_alloc &)
	{
		std::lock_guard<std::mutex> lock(pipeline_mutex);
		++health.capture_failures;
	}
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	pending_world_quests.erase(pid);
	return false;
}

bool player_save_pipeline_reserve_trade(uint32_t pid, const player_pending_trade_snapshot &trade)
try
{
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	if (!pid || trade_player_pid || !accepting || !health.initialized ||
	    !std::any_of(trade.operation.begin(), trade.operation.end(),
			 [](uint8_t b) { return b; }) ||
	    !std::any_of(trade.command_hash.begin(), trade.command_hash.end(),
			 [](uint8_t b) { return b; }) ||
	    trade.payment < -static_cast<int64_t>(INT32_MAX) || trade.payment > INT32_MAX ||
	    trade.wallet_revision == UINT64_MAX)
		return false;
	trade_capture = trade;
	trade_player_pid = pid;
	return true;
}
catch (const std::bad_alloc &)
{
	return false;
}
void player_save_pipeline_release_trade(uint32_t pid)
{
	std::lock_guard<std::mutex> lock(pipeline_mutex);
	if (trade_player_pid == pid)
	{
		trade_player_pid = 0;
		trade_capture = {};
	}
}
