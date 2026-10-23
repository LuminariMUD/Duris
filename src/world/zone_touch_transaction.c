/****************************************************************************
 *
 *  File: zone_touch_transaction.c                              Part of Duris
 *  Usage: pending zone touch awards and their completion handling
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "world/zone_touch_transaction.h"

#include "core/structs.h"
#include "core/utils.h"
#include "core/prototypes.h"
#include "world/epic.h"
#include "persistence/persistence_checkpoint.h"
#include "guild/artifact_guild_transaction.h"
#include "persistence/persistence_mode.h"
#include "redis/redis_report_cache.h"
#include "economy/divine_boon_delivery.h"
#include "guild/artifact_guild_state.h"
#include "guild/artifact_guild_delivery.h"

#include <algorithm>
#include <new>
#include <string>
#include <unordered_map>

namespace
{
struct pending_touch
{
	critical_command command;
	zone_touch_payload payload;
	zone_touch_result result;
	std::array<bool, ZONE_TOUCH_MAX_PARTICIPANTS> published = {};
	bool committed = false;
};
std::unordered_map<std::string, pending_touch> pending;

std::string operation_key(const critical_operation_id &operation_id)
{
	return std::string(reinterpret_cast<const char *>(operation_id.bytes.data()),
			   operation_id.bytes.size());
}

void notify(const zone_touch_payload &payload, const char *message)
{
	for (size_t i = 0; i < payload.group_size; ++i)
		if (P_char ch = find_player_by_pid(payload.participant_pids[i]))
			send_to_char(message, ch);
}

bool publish(pending_touch &entry)
{
	for (size_t i = 0; i < entry.result.group_size; ++i)
	{
		if (entry.published[i])
			continue;
		P_char ch = find_player_by_pid(entry.result.participant_pids[i]);
		if ((!ch || IS_NPC(ch)) && !entry.result.prepared_delivery)
			continue;
		if (entry.result.prepared_delivery)
		{
			divine_epic_delivery delivery;
			if (!divine_epic_delivery_from_zone(entry.result.parent_operation,
							    entry.result, i, &delivery))
				return false;
			divine_boon_delivery_completed(delivery);
			entry.published[i] = true;
			continue;
		}
		// Dispatch for each recipient when ready, retaining the child ledger as proof.
		critical_command award = {};
		if (zone_touch_award_command(entry.command, i, &award) &&
		    !artifact_guild_transaction_submit(ch, award.operation_id,
						       entry.result.awards[i].amount, EPIC_ZONE))
			logit(LOG_FILE,
			      "epic_stone: component=artifact_effect outcome=unavailable actor=redacted");
		entry.published[i] = true;
		// Epic points live in memory: the committed award is added now, once, and the
		// player's save writes it. The repository only recorded it in the ledger.
		ch->only.pc->epics += entry.result.awards[i].amount;
		++ch->only.pc->epic_revision;
		mark_player_dirty_components(GET_PID(ch), PLAYER_COMPONENT_STATUS);
		epic_publish_stone_award(ch, entry.result, i);
	}
	return std::all_of(entry.published.begin(),
			   entry.published.begin() + entry.result.group_size,
			   [](bool value) { return value; });
}
} // namespace

bool zone_touch_transaction_busy(uint64_t stone_uid, uint32_t zone_number)
{
	for (const auto &[key, entry] : pending)
	{
		(void)key;
		if (!entry.committed &&
		    (entry.payload.stone_uid == stone_uid ||
		     (entry.payload.record_zone && entry.payload.zone_number == zone_number)))
			return true;
	}
	return false;
}

bool zone_touch_transaction_submit(const zone_touch_payload &payload)
{
	// Flatfile has no atomic world/zone repository; never queue partial rewards there.
	// Completed receipts await reconnect; they no longer occupy transaction slots.
	const auto in_flight = std::count_if(pending.begin(), pending.end(), [](const auto &item)
					     { return !item.second.committed; });
	if (payload.group_size > ZONE_TOUCH_MAX_PARTICIPANTS ||
	    (!persistence_mode_requires_mysql() && !payload.prepared_delivery) ||
	    static_cast<size_t>(in_flight) >= ZONE_TOUCH_PENDING_MAX ||
	    (payload.stone_uid &&
	     zone_touch_transaction_busy(payload.stone_uid, payload.zone_number)))
		return false;
	critical_operation_id operation_id = {};
	if (!critical_operation_id_generate(&operation_id))
		return false;
	zone_touch_payload prepared;
	std::string key;
	bool reserved = false;
	try
	{
		prepared = payload;
		prepared.artifact_deliveries.clear();
		prepared.artifact_intents = prepared.prepared_delivery;
		if (prepared.artifact_intents)
			for (size_t i = 0; i < prepared.group_size; ++i)
			{
				critical_command child;
				const auto captured = artifact_guild_state_prepare_delivery(
					find_player_by_pid(prepared.participant_pids[i]),
					prepared.awards[i].amount, EPIC_ZONE, operation_id, &child);
				if (captured == artifact_guild_capture_status::ready)
					prepared.artifact_deliveries.push_back(std::move(child));
				else if (captured != artifact_guild_capture_status::no_effect)
					return false;
			}
		critical_command command = {};
		if (!zone_touch_command_build(&command, operation_id, prepared) ||
		    !artifact_guild_delivery_reserve(prepared.artifact_deliveries))
			return false;
		reserved = true;
		key = operation_key(operation_id);
		pending.emplace(key, pending_touch{ command, prepared, {}, {}, false });
		const auto submitted = critical_command_coordinator_submit(std::move(command));
		if (!critical_submit_result_keeps_operation(submitted))
		{
			artifact_guild_delivery_complete(prepared.artifact_deliveries, false);
			pending.erase(key);
			return false;
		}
	}
	catch (const std::bad_alloc &)
	{
		if (reserved)
			artifact_guild_delivery_complete(prepared.artifact_deliveries, false);
		pending.erase(key);
		return false;
	}
	return true;
}

void zone_touch_transaction_handle_completions(const critical_completion *completions, size_t count)
{
	if (count && !completions)
		return;
	for (size_t index = 0; index < count; ++index)
	{
		auto found = pending.find(operation_key(completions[index].operation_id));
		if (found == pending.end() || found->second.committed)
			continue;
		auto &entry = found->second;
		const auto &completion = completions[index];
		// The writer retries a lost connection or an ambiguous commit itself, so a
		// completion is final.
		const bool committed = completion.outcome == critical_apply_outcome::applied ||
				       completion.outcome ==
					       critical_apply_outcome::already_applied;
		if (!committed)
		{
			artifact_guild_delivery_complete(entry.payload.artifact_deliveries, false);
			notify(entry.payload,
			       "The stone reward failed. The stone remains available; please try again.\r\n");
			pending.erase(found);
			continue;
		}
		if (!zone_touch_command_decode_result(completion.result_payload.data(),
						      completion.result_size, &entry.result) ||
		    entry.result.stone_uid != entry.payload.stone_uid ||
		    (!entry.result.recovered_claim &&
		     entry.result.artifact_intents != entry.payload.artifact_intents))
		{
			// The parent committed its immutable children even when its result is unreadable.
			artifact_guild_delivery_complete(entry.payload.artifact_deliveries, true);
			notify(entry.payload,
			       "The stone reward receipt is unavailable. Please contact staff.\r\n");
			continue; // Unknown committed result must not become a new award attempt.
		}
		artifact_guild_delivery_complete(entry.payload.artifact_deliveries,
						 !entry.result.recovered_claim);
		entry.committed = true;
		if (!entry.payload.stone_uid)
		{
			epic_publish_zone_touch(
				entry.result); // historical v1 metadata-only completion
			pending.erase(found);
			continue;
		}
		epic_finish_stone_touch(entry.result);
		// Recovered claims consume the surviving stone but never repeat player side effects.
		if (entry.result.recovered_claim || publish(entry))
			pending.erase(found);
	}
}

void zone_touch_transaction_player_ready(P_char character)
{
	if (!character || IS_NPC(character))
		return;
	for (auto found = pending.begin(); found != pending.end();)
	{
		if (found->second.committed && publish(found->second))
			found = pending.erase(found);
		else
			++found;
	}
}

critical_outbox_delivery_result
zone_touch_transaction_outbox_delivery(const critical_outbox_record &record, void *)
{
	if (record.destination != 9 || record.event_type != 1 || record.payload_version != 1)
		return critical_outbox_delivery_result::terminal_failure;
	zone_touch_result result = {};
	if (!zone_touch_command_decode_result(record.payload.data(), record.payload.size(),
					      &result))
		return critical_outbox_delivery_result::terminal_failure;
	redis_invalidate_epic_zones();
	return critical_outbox_delivery_result::delivered;
}

void zone_touch_transaction_reset_for_tests(void)
{
	pending.clear();
}
