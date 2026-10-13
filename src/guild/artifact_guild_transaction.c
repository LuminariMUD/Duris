/****************************************************************************
 *
 *  File: artifact_guild_transaction.c                          Part of Duris
 *  Usage: pending artifact guild operations and their messages
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "guild/artifact_guild_transaction.h"

#include "guild/assocs.h"
#include "net/comm.h"
#include "core/prototypes.h"
#include "redis/redis_report_cache.h"
#include "core/utils.h"

#include <algorithm>
#include <chrono>
#include <mutex>
#include <new>
#include <string>
#include <unordered_map>
#include <map>
#include <thread>
#include <cerrno>
#include "sql/sql_async.h"

namespace
{
constexpr uint32_t ARTIFACT_GUILD_DERIVATION_DOMAIN = 0x41475431;

struct pending_outcome
{
	critical_command command;
	uint64_t submitted_at_msec;
	int epics;
	int epic_type;
	bool queued = false;
};

std::map<std::array<uint8_t, CRITICAL_COMMAND_ID_BYTES>, pending_outcome> pending;
uint64_t next_retry_msec = 0;
artifact_guild_health health = {};
std::mutex outbox_mutex;
std::unordered_map<uint64_t, bool> outbox_publications;

uint64_t monotonic_msec()
{
	return std::chrono::duration_cast<std::chrono::milliseconds>(
		       std::chrono::steady_clock::now().time_since_epoch())
		.count();
}

void diagnostic(const critical_operation_id &operation, const critical_operation_id &parent,
		const char *stage, const char *reason, unsigned int error, uint64_t age = 0)
{
	// The reporter permits numeric substitutions only. Categories carry the
	// controlled stage/reason; two big-endian words retain each full opaque ID.
	uint64_t operation_words[2] = {}, parent_words[2] = {};
	for (size_t i = 0; i < operation.bytes.size(); ++i)
	{
		operation_words[i / 8] = (operation_words[i / 8] << 8) | operation.bytes[i];
		parent_words[i / 8] = (parent_words[i / 8] << 8) | parent.bytes[i];
	}
	char domain[64];
	snprintf(domain, sizeof(domain), "artifact_guild/%s", stage);
	persistence_alert(AVATAR, domain, "redacted", "none", "none", reason,
			  "operation=%016llx%016llx parent=%016llx%016llx error=%u elapsed_ms=%llu",
			  static_cast<unsigned long long>(operation_words[0]),
			  static_cast<unsigned long long>(operation_words[1]),
			  static_cast<unsigned long long>(parent_words[0]),
			  static_cast<unsigned long long>(parent_words[1]), error,
			  static_cast<unsigned long long>(age));
}

bool queue_history(pending_outcome &entry)
{
	critical_submit_result submitted;
	try
	{
		errno = 0;
		submitted = critical_command_coordinator_submit(entry.command);
	}
	catch (const std::bad_alloc &)
	{
		errno = ENOMEM;
		submitted = critical_submit_result::overloaded;
	}
	if (critical_submit_result_keeps_operation(submitted))
	{
		entry.queued = true;
		++health.submitted;
		return true;
	}
	critical_operation_id parent = {};
	std::copy_n(entry.command.payload.begin(), parent.bytes.size(), parent.bytes.begin());
	const unsigned int error = errno;
	diagnostic(entry.command.operation_id, parent, "history_admission",
		   submitted == critical_submit_result::identity_conflict ? "identity_conflict" :
		   submitted == critical_submit_result::invalid		  ? "malformed_payload" :
		   error == ENOMEM					  ? "allocation_failure" :
		   submitted == critical_submit_result::overloaded	  ? "queue_capacity" :
									    "unavailable_or_quiesced",
		   error, monotonic_msec() - entry.submitted_at_msec);
	++health.submission_failures;
	return submitted != critical_submit_result::invalid &&
	       submitted != critical_submit_result::identity_conflict;
}

void publish_messages(P_char character, const artifact_guild_payload &payload)
{
	if (!character)
		return;
	if (payload.guild_id && payload.prestige_delta > 0)
		send_to_char("&+bYour guild gained prestige!\n", character);
	if (payload.construction_delta > 0)
	{
		Guild *guild = GET_ASSOC(character);
		if (guild)
		{
			statuslog(GREATER_G, "Association %s &ngained %lld construction points.",
				  guild->get_name().c_str(),
				  static_cast<long long>(payload.construction_delta));
			logit(LOG_STATUS, "Association %s &ngained %lld construction points.",
			      guild->get_name().c_str(),
			      static_cast<long long>(payload.construction_delta));
		}
	}
	if (payload.artifact_count)
		send_to_char("&+RYou feel a sense of satisfaction from your artifact(s).&n\r\n",
			     character);
}
} // namespace

// New source publication only. The boon/combat/stone producers own live once-only
// publication; a prepared command is retried below without recapturing or granting.
bool artifact_guild_transaction_submit(P_char character,
				       const critical_operation_id &parent_operation_id, int epics,
				       int epic_type)
{
	if (!character || IS_NPC(character) || GET_PID(character) <= 0)
		return false;
	critical_operation_id operation_id = {};
	if (!critical_operation_id_derive(parent_operation_id, ARTIFACT_GUILD_DERIVATION_DOMAIN,
					  static_cast<uint64_t>(GET_PID(character)), &operation_id))
		return false;
	auto existing = pending.find(operation_id.bytes);
	if (existing != pending.end())
	{
		if (existing->second.epics == epics && existing->second.epic_type == epic_type)
			return true;
		diagnostic(operation_id, parent_operation_id, "capture", "identity_conflict",
			   EEXIST);
		return false;
	}
	artifact_guild_payload payload = {};
	const auto captured = artifact_guild_state_capture(character, epics, epic_type,
							   parent_operation_id, &payload);
	if (captured == artifact_guild_capture_status::no_effect)
		return true;
	if (captured != artifact_guild_capture_status::ready)
	{
		++health.unavailable;
		diagnostic(operation_id, parent_operation_id, "capture",
			   captured == artifact_guild_capture_status::invalid ?
				   "invalid_bounds" :
				   "unsupported_or_unavailable",
			   EINVAL);
		return false;
	}
	artifact_guild_state_apply(character, payload);
	publish_messages(character, payload);
	++health.live_applied;
	health.max_artifacts = std::max<uint64_t>(health.max_artifacts, payload.artifact_count);
	if (pending.size() >= ARTIFACT_GUILD_PENDING_MAX)
	{
		++health.history_lost;
		diagnostic(operation_id, parent_operation_id, "history_retention", "queue_capacity",
			   ENOSPC);
		return true;
	}
	try
	{
		critical_command command = {};
		if (!artifact_guild_command_build(&command, operation_id, payload))
		{
			++health.history_lost;
			diagnostic(operation_id, parent_operation_id, "history_retention",
				   "malformed_payload", EINVAL);
			return true;
		}
		command.accepted_at_usec =
			std::chrono::duration_cast<std::chrono::microseconds>(
				std::chrono::system_clock::now().time_since_epoch())
				.count();
		auto [entry, inserted] = pending.emplace(
			operation_id.bytes, pending_outcome{ std::move(command), monotonic_msec(),
							     epics, epic_type, false });
		(void)inserted;
		if (!queue_history(entry->second))
		{
			pending.erase(entry);
			++health.history_lost;
		}
	}
	catch (const std::bad_alloc &)
	{
		++health.history_lost;
		diagnostic(operation_id, parent_operation_id, "history_retention",
			   "allocation_failure", ENOMEM);
	}
	health.pending = pending.size();
	return true;
}

void artifact_guild_transaction_handle_completions(const critical_completion *completions,
						   size_t count)
{
	if (count && !completions)
		return;
	for (size_t index = 0; index < count; ++index)
	{
		auto found = pending.find(completions[index].operation_id.bytes);
		if (found == pending.end())
			continue;
		artifact_guild_result result = {};
		const bool decoded = artifact_guild_command_decode_result(
			completions[index].result_payload.data(), completions[index].result_size,
			&result);
		if (decoded &&
		    (completions[index].outcome == critical_apply_outcome::applied ||
		     completions[index].outcome == critical_apply_outcome::already_applied))
			++health.committed;
		else
		{
			++health.rejected;
			const bool expected_result =
				completions[index].outcome == critical_apply_outcome::applied ||
				completions[index].outcome ==
					critical_apply_outcome::already_applied;
			if (!decoded && expected_result)
				++health.malformed_completions;
			critical_operation_id parent = {};
			std::copy_n(found->second.command.payload.begin(), parent.bytes.size(),
				    parent.bytes.begin());
			diagnostic(completions[index].operation_id, parent, "history_completion",
				   expected_result ? "malformed_completion" :
				   completions[index].error_code == ENOENT ? "missing_parent" :
				   completions[index].error_code == EEXIST ? "identity_conflict" :
				   completions[index].error_code == EPROTONOSUPPORT ?
									     "legacy_uncommitted" :
									     "storage_failure",
				   completions[index].error_code,
				   monotonic_msec() - found->second.submitted_at_msec);
		}
		// Receipts never change memory, enqueue an old snapshot, or repeat feedback.
		pending.erase(found);
	}
	health.pending = pending.size();
}

void artifact_guild_transaction_pulse()
{
	const uint64_t now = monotonic_msec();
	const bool retry = now >= next_retry_msec;
	health.dirty_artifacts = artifact_save_pulse(retry);
	health.dirty_guilds = guild_save_pulse(retry);
	if (!retry)
		return;
	next_retry_msec = now + 1000;
	size_t attempts = 0;
	for (auto entry = pending.begin(); entry != pending.end() && attempts < 8;)
	{
		if (!entry->second.queued)
		{
			++attempts;
			if (!queue_history(entry->second))
			{
				entry = pending.erase(entry);
				++health.history_lost;
				continue;
			}
		}
		++entry;
	}
	health.pending = pending.size();
}

// Run before coordinator quiescence, so parent completions can still publish
// their derived histories. Failure keeps copyover live; shutdown reports it.
bool artifact_guild_transaction_drain(uint64_t timeout_msec)
{
	const auto deadline =
		std::chrono::steady_clock::now() + std::chrono::milliseconds(timeout_msec);
	do
	{
		critical_command_coordinator_drain(1);
		// A committed character deletion must release its guild member before
		// a fresh guild snapshot can retry without that deleted player's FK.
		sql_async_pulse();
		artifact_guild_transaction_pulse();
		if (pending.empty() && !health.dirty_artifacts && !health.dirty_guilds &&
		    !critical_command_coordinator_health_copy().inflight)
			return true;
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	} while (std::chrono::steady_clock::now() < deadline);
	return false;
}

void artifact_guild_transaction_report_unsaved()
{
	artifact_report_unsaved();
	guild_report_unsaved();
	for (const auto &[id, entry] : pending)
	{
		critical_operation_id parent = {};
		std::copy_n(entry.command.payload.begin(), parent.bytes.size(),
			    parent.bytes.begin());
		diagnostic(entry.command.operation_id, parent, "shutdown", "history_unresolved",
			   EIO, monotonic_msec() - entry.submitted_at_msec);
	}
}

critical_outbox_delivery_result
artifact_guild_transaction_outbox_delivery(const critical_outbox_record &record, void *)
{
	if (record.destination != 7 || record.event_type != 1 || record.payload_version != 1)
		return critical_outbox_delivery_result::terminal_failure;
	artifact_guild_result result = {};
	if (!artifact_guild_command_decode_result(record.payload.data(), record.payload.size(),
						  &result))
		return critical_outbox_delivery_result::terminal_failure;
	std::lock_guard<std::mutex> lock(outbox_mutex);
	auto found = outbox_publications.find(record.outbox_id);
	if (found != outbox_publications.end())
	{
		if (found->second)
		{
			outbox_publications.erase(found);
			return critical_outbox_delivery_result::delivered;
		}
		return critical_outbox_delivery_result::retryable_failure;
	}
	if (outbox_publications.size() >= 1024)
		return critical_outbox_delivery_result::retryable_failure;
	outbox_publications.emplace(record.outbox_id, false);
	return critical_outbox_delivery_result::retryable_failure;
}

void artifact_guild_transaction_publish_outbox(void)
{
	bool publish = false;
	{
		std::lock_guard<std::mutex> lock(outbox_mutex);
		for (auto &[outbox_id, published] : outbox_publications)
		{
			(void)outbox_id;
			if (!published)
			{
				published = true;
				publish = true;
			}
		}
	}
	if (publish)
	{
		redis_invalidate_artifact_cache();
		critical_outbox_resume();
	}
}

artifact_guild_health artifact_guild_transaction_health_copy(void)
{
	health.pending = pending.size();
	health.oldest_age_msec = 0;
	const uint64_t now = monotonic_msec();
	for (const auto &[key, entry] : pending)
	{
		(void)key;
		health.oldest_age_msec =
			std::max(health.oldest_age_msec, now - entry.submitted_at_msec);
	}
	return health;
}

void artifact_guild_transaction_reset_for_tests(void)
{
	pending.clear();
	health = {};
	next_retry_msec = 0;
	std::lock_guard<std::mutex> lock(outbox_mutex);
	outbox_publications.clear();
}
