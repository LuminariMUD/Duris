/****************************************************************************
 *
 *  File: boon_reward_transaction.c                             Part of Duris
 *  Usage: pending boon rewards and their acknowledgement
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "economy/boon_reward_transaction.h"
#include "economy/divine_boon_runtime.h"

#include "economy/boon.h"
#include "flatfile/flatfile_boon_repository.h"
#include "persistence/persistence_mode.h"
#include "core/prototypes.h"
#include "magic/spells.h"
#include "core/utils.h"
#include "sql/sql_async.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <new>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace
{
struct pending_reward
{
	uint32_t pid;
	boon_reward_payload payload;
	uint64_t submitted_at_msec;
	bool published = false;
	boon_reward_result committed_result = {};
	uint64_t completion_order = 0;
};

std::unordered_map<std::string, pending_reward> pending;
// Flat legacy receipts have no saved player watermark. Retain only their
// process-local publication identities, bounded by the durable catalog's
// 32768-operation limit, without consuming an in-flight admission slot.
std::unordered_set<std::string> published_flat;
boon_reward_health health = {};
sql_rows definitions;
std::atomic<uint64_t> definition_generation{ 0 };
uint64_t definitions_generation = 0;
uint64_t definitions_read_at_msec = 0;
bool definitions_available = false;
bool definitions_loading = false;
constexpr uint64_t DEFINITION_FRESH_MSEC = 60000;
uint64_t completion_order = 0;

uint64_t monotonic_msec()
{
	return std::chrono::duration_cast<std::chrono::milliseconds>(
		       std::chrono::steady_clock::now().time_since_epoch())
		.count();
}

bool definition_may_match(const boon_reward_payload &payload)
{
	if (persistence_mode_get() != PERSISTENCE_MODE_MARIADB_PRIMARY)
		return true;
	const uint64_t now = monotonic_msec();
	if (!definitions_available || definitions_generation != definition_generation.load() ||
	    now - definitions_read_at_msec >= DEFINITION_FRESH_MSEC)
	{
		if (!definitions_loading)
		{
			definitions_loading = true;
			const uint64_t generation = definition_generation.load();
			if (!sql_read("SELECT opt,racewar,pid FROM boons WHERE active=1 LIMIT 100",
				      [generation, now](bool ok, const sql_rows &rows)
				      {
					      definitions_loading = false;
					      if (!ok || rows.size() > MAX_BOONS ||
						  std::any_of(rows.begin(), rows.end(),
							      [](const sql_row &row) {
								      return !row[0] || !row[1] ||
									     !row[2];
							      }))
					      {
						      ++health.definition_failures;
						      return;
					      }
					      if (generation != definition_generation.load())
						      return;
					      definitions = rows;
					      definitions_read_at_msec = now;
					      definitions_generation = generation;
					      definitions_available = true;
					      ++health.definition_refreshes;
				      }))
			{
				definitions_loading = false;
				++health.definition_failures;
			}
		}
		// Never delay or discard an event while its view is missing or stale.
		return true;
	}
	// Deliberately conservative: criteria and progress stay on the authoritative
	// writer. Check the current payload's side and target, never a cached player.
	return std::any_of(definitions.begin(), definitions.end(),
			   [&payload](const sql_row &row)
			   {
				   return atoi(row[0]) == payload.option &&
					  (!atoi(row[1]) || atoi(row[1]) == payload.racewar) &&
					  (!strtoul(row[2], nullptr, 10) ||
					   strtoul(row[2], nullptr, 10) == payload.pid);
			   }) ||
	       definitions_generation != definition_generation.load();
}

std::string operation_key(const critical_operation_id &operation_id)
{
	return std::string(reinterpret_cast<const char *>(operation_id.bytes.data()),
			   operation_id.bytes.size());
}

bool publish_reward(P_char character, const critical_operation_id &operation_id, double data,
		    const boon_reward_result &result)
{
	const std::string key = operation_key(operation_id);
	const bool retain = persistence_mode_get() == PERSISTENCE_MODE_FLATFILE_PRIMARY &&
			    boon_reward_requires_checkpoint(result);
	if (retain && published_flat.contains(key))
		return false;
	bool publish;
	try
	{
		auto [entry, inserted] = pending.try_emplace(
			key, pending_reward{ result.pid, {}, monotonic_msec() });
		entry->second.committed_result = result;
		publish = !entry->second.published;
		if (publish)
		{
			if (retain)
				published_flat.insert(key);
			// Publication may submit more boons and rehash pending. Consume the award
			// first and use its key, rather than this iterator, after calling out.
			entry->second.published = true;
			if (!inserted)
				++health.committed;
			health.max_results =
				std::max<uint64_t>(health.max_results, result.entry_count);
		}
	}
	catch (const std::bad_alloc &)
	{
		return false;
	}
	if (publish)
		boon_publish_transaction_result(character, data, result);
	// The old result has no saved recipient watermark. Keep its original flat
	// receipt and this process's publication marker; a reconnect must not replay it.
	if (persistence_mode_get() == PERSISTENCE_MODE_FLATFILE_PRIMARY)
	{
		if (retain)
		{
			pending.erase(key);
			return false;
		}
		const char *root = persistence_mode_flatfile_root();
		std::string error;
		if (!root || flatfile_boon_acknowledge_reward(root, operation_id, &error) !=
				     flatfile_boon_result::ok)
		{
			persistence_alert(AVATAR, "boon_reward", "player", "unknown", "publication",
					  "checkpoint_free_ack_retained", "pid=%u", result.pid);
			return false;
		}
	}
	pending.erase(key);
	return true;
}
} // namespace

void boon_reward_definition_view_invalidate(void)
{
	++definition_generation;
}

bool boon_reward_transaction_submit(P_char character, P_char victim, double data, int option)
{
	if (!divine_boon_legacy_admissions_allowed())
		return false;
	if (!character || IS_NPC(character) || GET_PID(character) <= 0 || option < 0 ||
	    option >= MAX_BOPT || pending.size() >= BOON_REWARD_PENDING_MAX)
		return false;
	boon_reward_payload payload = {
		.pid = static_cast<uint32_t>(GET_PID(character)),
		.racewar = static_cast<uint8_t>(GET_RACEWAR(character)),
		.level = static_cast<uint16_t>(std::max(0, GET_LEVEL(character))),
		.zone_number = character->in_room >= 0 ? ROOM_ZONE_NUMBER(character->in_room) : 0,
		.option = static_cast<uint8_t>(option),
		.data = data,
		.victim_vnum = victim && IS_NPC(victim) ? GET_VNUM(victim) : 0,
		.victim_race = static_cast<int16_t>(victim ? GET_RACE(victim) : 0),
		.victim_flags = 0
	};
	if (victim && IS_NPC(victim) && !IS_PC_PET(victim))
		payload.victim_flags |= 1;
	if (victim && ((IS_NPC(victim) && !get_linked_char(victim, LNK_PET) &&
			!affected_by_spell(victim, TAG_CONJURED_PET)) ||
		       (IS_PC(victim) && GET_RACEWAR(character) != GET_RACEWAR(victim))))
		payload.victim_flags |= 2;
	++health.checked;
	if (!definition_may_match(payload))
	{
		// This check has not generated or admitted an operation ID. All accepted
		// IDs, including ambiguous retries, still go through the canonical writer.
		++health.filtered;
		return true;
	}
	critical_operation_id operation_id = {};
	critical_command command = {};
	if (!critical_operation_id_generate(&operation_id) ||
	    !boon_reward_command_build(&command, operation_id, payload))
		return false;
	const std::string key = operation_key(operation_id);
	try
	{
		pending.emplace(key, pending_reward{ payload.pid, payload, monotonic_msec() });
	}
	catch (const std::bad_alloc &)
	{
		return false;
	}
	const critical_submit_result submitted =
		critical_command_coordinator_submit(std::move(command));
	if (!critical_submit_result_keeps_operation(submitted))
	{
		pending.erase(key);
		++health.submission_failures;
		return false;
	}
	++health.submitted;
	return true;
}

void boon_reward_transaction_handle_completions(const critical_completion *completions,
						size_t count)
{
	if (count && !completions)
		return;
	for (size_t index = 0; index < count; ++index)
	{
		auto found = pending.find(operation_key(completions[index].operation_id));
		if (found == pending.end())
			continue;
		boon_reward_result result = {};
		const bool decoded =
			boon_reward_command_decode_result(completions[index].result_payload.data(),
							  completions[index].result_size, &result);
		const bool committed =
			decoded &&
			(completions[index].outcome == critical_apply_outcome::applied ||
			 completions[index].outcome == critical_apply_outcome::already_applied);
		if (committed)
		{
			if (result.entry_count)
				boon_reward_definition_view_invalidate();
			found->second.committed_result = result;
			if (!found->second.completion_order)
				found->second.completion_order = ++completion_order;
			P_char character = find_player_by_pid(found->second.pid);
			if (character || found->second.published)
			{
				const double data = found->second.payload.data;
				publish_reward(character, completions[index].operation_id, data,
					       result);
			}
			else if (!boon_reward_requires_checkpoint(result))
			{
				// Progress and shop counters are already committed. No player
				// callback/checkpoint is needed to finish their admission.
				if (!found->second.published)
				{
					found->second.published = true;
					++health.committed;
				}

				if (persistence_mode_get() == PERSISTENCE_MODE_FLATFILE_PRIMARY)
				{
					const char *root = persistence_mode_flatfile_root();
					std::string error;
					if (!root || flatfile_boon_acknowledge_reward(
							     root, completions[index].operation_id,
							     &error) != flatfile_boon_result::ok)
					{
						persistence_alert(AVATAR, "boon_reward", "player",
								  "unknown", "completion",
								  "checkpoint_free_ack_retained",
								  "pid=%u", result.pid);
						continue; // Keep the ACK retry visible across mode transitions.
					}
				}
				health.max_results =
					std::max<uint64_t>(health.max_results, result.entry_count);
				pending.erase(found);
			}
			else
			{
				health.max_results =
					std::max<uint64_t>(health.max_results, result.entry_count);
				// Keep this known, not-yet-published completion for a same-process
				// reconnect. A process restart has no publication proof and
				// must retain the receipt rather than blindly grant it again.
			}
		}
		else
		{
			++health.rejected;
			pending.erase(found);
		}
	}
}

void boon_reward_transaction_player_ready(P_char character)
try
{
	if (!character || IS_NPC(character) || GET_PID(character) <= 0)
		return;
	// Scan known committed admissions independently of the durable receipt order.
	// Retaining the first receipt must not hide another safe same-process award.
	std::vector<std::string> known;
	for (const auto &[key, entry] : pending)
		if (entry.pid == static_cast<uint32_t>(GET_PID(character)) &&
		    entry.committed_result.pid &&
		    (!entry.published || !boon_reward_requires_checkpoint(entry.committed_result)))
			known.push_back(key);
	std::sort(
		known.begin(), known.end(), [](const auto &left, const auto &right)
		{ return pending.at(left).completion_order < pending.at(right).completion_order; });
	for (const auto &key : known)
	{
		auto found = pending.find(key);
		if (found == pending.end())
			continue;
		const auto result = found->second.committed_result;
		const auto data = found->second.payload.data;
		critical_operation_id operation;
		std::copy_n(key.begin(), operation.bytes.size(), operation.bytes.begin());
		publish_reward(character, operation, data, result);
	}
	if (persistence_mode_get() != PERSISTENCE_MODE_FLATFILE_PRIMARY)
		return;
	const char *root = persistence_mode_flatfile_root();
	if (!root)
		return;
	bool safe_only = false;
	for (size_t delivered = 0; delivered < 64; ++delivered)
	{
		flatfile_boon_pending_reward reward;
		std::string error;
		const auto found = flatfile_boon_find_pending_reward(
			root, static_cast<uint32_t>(GET_PID(character)), &reward, &error,
			safe_only);
		if (found == flatfile_boon_result::not_found)
			break;
		if (found != flatfile_boon_result::ok)
		{
			persistence_alert(AVATAR, "boon_reward", "player", "unknown",
					  "load_pending", "flat_read_failed", "error=%s",
					  error.c_str());
			break;
		}

		if (published_flat.contains(operation_key(reward.operation_id)))
		{
			safe_only = true;
			continue;
		}
		if (boon_reward_requires_checkpoint(reward.result) &&
		    pending.find(operation_key(reward.operation_id)) == pending.end())
		{
			// Old receipts cannot distinguish an unpaid reward from a reward
			// published just before a crash. Preserve it for reconciliation; no
			// earned callback with a known live admission is suppressed.
			send_to_char(
				"A legacy boon receipt is retained for staff reconciliation.\r\n",
				character);
			persistence_alert(AVATAR, "boon_reward", "player", "unknown",
					  "load_pending", "legacy_uncheckpointed", "pid=%u",
					  reward.result.pid);
			safe_only = true;
			continue;
		}
		if (!publish_reward(character, reward.operation_id, reward.event_data,
				    reward.result))
		{
			if (!boon_reward_requires_checkpoint(reward.result))
				break; // A checkpoint-free ACK failed; keep its retry visible.
			safe_only = true;
		}
	}
}

catch (const std::bad_alloc &)
{
	persistence_alert(AVATAR, "boon_reward", "player", "unknown", "load_pending",
			  "memory_unavailable", "retained receipt remains durable");
}

critical_outbox_delivery_result
boon_reward_transaction_outbox_delivery(const critical_outbox_record &record, void *)
{
	if (record.destination != 8 || record.event_type != 1 || record.payload_version != 1)
		return critical_outbox_delivery_result::terminal_failure;

	boon_reward_result result = {};
	if (!boon_reward_command_decode_result(record.payload.data(), record.payload.size(),
					       &result))
		return critical_outbox_delivery_result::terminal_failure;
	// This callback runs on the outbox worker. Health/status exposes retained
	// records; never call game-thread descriptor/wizlog notification here.
	return boon_reward_requires_checkpoint(result) ?
		       critical_outbox_delivery_result::terminal_failure :
		       critical_outbox_delivery_result::delivered;
}

boon_reward_health boon_reward_transaction_health_copy(void)
{
	health.pending = 0;
	health.oldest_age_msec = 0;
	const uint64_t now = monotonic_msec();
	for (const auto &[key, entry] : pending)
	{
		(void)key;
		// Published checkpoint-dependent IDs already left this map. A published
		// entry still here needs an acknowledgement retry and remains visible.
		++health.pending;
		health.oldest_age_msec =
			std::max(health.oldest_age_msec, now - entry.submitted_at_msec);
	}
	return health;
}

void boon_reward_transaction_reset_for_tests(void)
{
	pending.clear();
	published_flat.clear();
	health = {};
	boon_reward_definition_view_invalidate();
	definitions_available = false;
	definitions.clear();
	definitions_loading = false;
	completion_order = 0;
}
