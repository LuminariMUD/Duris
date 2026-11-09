/****************************************************************************
 *
 *  File: auction_transaction.c                                 Part of Duris
 *  Usage: pending auction operations and their completion handling
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "economy/auction_transaction.h"

#include "economy/auction_houses.h"
#include "economy/currency_transaction.h"
#include "net/gmcp.h"
#include "item/item_ownership_runtime.h"
#include "core/prototypes.h"
#include "sql/sql_player.h"
#include "core/utils.h"
#include "player/player_save_pipeline.h"

#include <algorithm>
#include <cerrno>
#include <climits>
#include <chrono>
#include <openssl/sha.h>
#include <new>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

extern P_char character_list;

namespace
{
struct pending_auction
{
	uint32_t actor_pid;
	auction_command_payload payload;
	auction_completion_fn completion;
	bool completion_ready;
	critical_completion completed;
	// What the submit took from the wallet: a listing's fee or a bid.
	int64_t escrow;
	// A listing's items, taken out of the seller's inventory at submit.
	std::vector<P_obj> held;
};

std::unordered_map<std::string, pending_auction> pending;

enum class outbox_publication_state : uint8_t
{
	queued,
	publishing,
	published,
	failed,
};

struct pending_outbox_publication
{
	auction_command_result result;
	outbox_publication_state state;
};

std::mutex outbox_mutex;
std::unordered_map<uint64_t, pending_outbox_publication> outbox_publications;
constexpr size_t AUCTION_OUTBOX_PENDING_MAX = 1024;

std::string operation_key(const critical_operation_id &operation_id)
{
	return std::string(reinterpret_cast<const char *>(operation_id.bytes.data()),
			   operation_id.bytes.size());
}

bool publish(std::unordered_map<std::string, pending_auction>::iterator found, P_char character)
{
	pending_auction &entry = found->second;
	const bool money_claim = entry.payload.action == auction_action::claim_money &&
				 entry.payload.value > 0;
	if (money_claim && !character)
		for (P_char current = character_list; current; current = current->next)
			if (IS_PC(current) &&
			    static_cast<uint32_t>(GET_PID(current)) == entry.actor_pid)
			{
				character = current;
				break;
			}
	auction_command_result result = {};
	const bool decoded = auction_command_decode_result(entry.completed.result_payload.data(),
							   entry.completed.result_size, &result);
	const bool durable_commit = entry.completed.outcome == critical_apply_outcome::applied ||
				    entry.completed.outcome ==
					    critical_apply_outcome::already_applied;
	const bool committed = decoded && durable_commit;
	// The auction keeps what it charged of the fee or bid the submit took and gives the
	// rest back, all of it when refused; a money claim brings its money.
	const int64_t credit = entry.escrow + (committed ? result.wallet_value_delta : 0);
	if (money_claim)
	{
		if (durable_commit &&
		    (!decoded || result.action != auction_action::claim_money ||
		     result.wallet_value_delta != entry.payload.value ||
		     result.wallet_revision != entry.payload.expected_wallet_revision + 1))
			return false;
		if (committed && character &&
		    !currency_transaction_publish_trade(character, entry.payload.value))
			return false;
		player_save_pipeline_release_trade(entry.actor_pid);
		currency_transaction_release_trade(entry.actor_pid);
	}
	else if (character && credit > 0)
	{
		const uint64_t revision = character->only.pc->wallet_revision;
		if (!currency_transaction_submit_wallet_value(
			    character, credit,
			    committed && result.action == auction_action::claim_money ?
				    currency_reason_type::auction_pickup :
				    currency_reason_type::refund,
			    entry.payload.auction_id, critical_source_site::command,
			    critical_deadline_class::interactive, nullptr, nullptr, 0) ||
		    character->only.pc->wallet_revision == revision)
			return false; // Retain the receipt and held items until its credit applies.
	}
	// A held item may have been extracted while the listing was in flight.
	for (size_t index = 0; index < entry.held.size(); ++index)
		if (P_obj object = find_live_object(entry.held[index],
						    entry.payload.items[index].item_uid))
		{
			if (committed)
				extract_obj(object);
			else if (character)
				obj_to_char(object, character);
		}
	if (committed && result.item_count)
	{
		// Settlement advances both owners. Updating only the destination leaves
		// the seller's next inventory or coin transfer fenced by a stale revision.
		const item_owner_identity source_owner = {
			result.action == auction_action::list ? item_owner_type::player :
								item_owner_type::auction,
			result.action == auction_action::list ? entry.actor_pid : result.auction_id,
			0
		};
		const uint64_t source_revision = result.action == auction_action::list ?
							 result.player_owner_revision :
							 result.auction_owner_revision;
		uint64_t current_source_revision = 0;
		if (!item_ownership_runtime_owner_revision(source_owner,
							   &current_source_revision) ||
		    !item_ownership_runtime_hydrate_owner(
			    source_owner, std::max(current_source_revision, source_revision)))
		{
			if (entry.completion)
				entry.completion(character, false, {}, ESTALE, entry.payload);
			pending.erase(found);
			return false;
		}
		const item_owner_identity owner = {
			result.action == auction_action::list ? item_owner_type::auction :
								item_owner_type::player,
			result.action == auction_action::list ? result.auction_id : entry.actor_pid,
			0
		};
		const uint64_t owner_revision = result.action == auction_action::list ?
							result.auction_owner_revision :
							result.player_owner_revision;
		for (size_t index = 0; index < result.item_count; ++index)
			if (!item_ownership_runtime_hydrate(
				    { result.item_uids[index], result.item_uids[index], 0, owner,
				      result.item_revisions[index], owner_revision,
				      entry.payload.items[index].vnum,
				      item_custody_state::active }))
			{
				if (entry.completion)
					entry.completion(character, false, {}, ESTALE,
							 entry.payload);
				pending.erase(found);
				return false;
			}
	}
	if (entry.completion)
		entry.completion(character, committed, decoded ? result : auction_command_result{},
				 entry.completed.error_code, entry.payload);
	pending.erase(found);
	return committed;
}

P_obj carried_item(P_char character, uint64_t item_uid)
{
	for (P_obj object = character->carrying; object; object = object->next_content)
		if (object->obj_uid == item_uid)
			return object;
	return nullptr;
}

bool submit(P_char character, const auction_command_payload &payload,
	    auction_completion_fn completion, critical_source_site source,
	    critical_deadline_class deadline)
{
	if (character && currency_transaction_wallet_busy(character))
		return false;
	if (pending.size() >= AUCTION_PENDING_MAX ||
	    (payload.actor_pid && (!character || IS_NPC(character) ||
				   static_cast<uint32_t>(GET_PID(character)) != payload.actor_pid)))
		return false;
	critical_operation_id operation_id = {};
	critical_command command = {};
	if (!critical_operation_id_generate(&operation_id) ||
	    !auction_command_build(&command, operation_id, payload, source, deadline))
		return false;
	const bool money_claim = payload.action == auction_action::claim_money && payload.value > 0;
	player_pending_trade_snapshot claim = {};
	if (money_claim)
	{
		if (payload.expected_wallet_revision != character->only.pc->wallet_revision)
			return false;
		command.accepted_at_usec =
			std::chrono::duration_cast<std::chrono::microseconds>(
				std::chrono::system_clock::now().time_since_epoch())
				.count();
		std::vector<uint8_t> encoded;
		if (critical_command_encode(command, &encoded) != critical_command_codec_result::ok)
			return false;
		claim.operation = operation_id.bytes;
		SHA256(encoded.data(), encoded.size(), claim.command_hash.data());
		claim.payment = payload.value;
		claim.wallet_revision = payload.expected_wallet_revision;
	}
	// A listing's fee and a bid leave the wallet now, and the player's save is queued
	// before the command, so a crash between them loses the money instead of paying it
	// twice. The completion gives back what the auction did not keep.
	const int64_t escrow = !payload.actor_pid		      ? 0 :
			       payload.action == auction_action::list ? payload.listing_fee :
			       payload.action == auction_action::bid  ? payload.value :
									0;
	// A listing's items leave the seller's inventory now too, so no save captured before
	// the listing commits can claim them back from the auction. The completion extracts
	// them, or gives them back when the listing is refused.
	std::vector<P_obj> held;
	if (payload.actor_pid && payload.action == auction_action::list)
		for (size_t index = 0; index < payload.item_count; ++index)
		{
			P_obj object = carried_item(character, payload.items[index].item_uid);
			if (!object)
				return false;
			held.push_back(object);
		}
	pending_auction entry = { .actor_pid = payload.actor_pid,
				  .payload = payload,
				  .completion = completion,
				  .completion_ready = false,
				  .completed = {},
				  .escrow = std::max<int64_t>(escrow, 0),
				  .held = held };
	const std::string key = operation_key(operation_id);
	try
	{
		pending.emplace(key, std::move(entry));
	}
	catch (const std::bad_alloc &)
	{
		return false;
	}
	if (money_claim)
	{
		if (!currency_transaction_reserve_trade(character, payload.value))
		{
			pending.erase(key);
			return false;
		}
		if (!player_save_pipeline_reserve_trade(payload.actor_pid, claim))
		{
			currency_transaction_release_trade(payload.actor_pid);
			pending.erase(key);
			return false;
		}
	}
	if (escrow > 0)
	{
		const uint64_t revision = character->only.pc->wallet_revision;
		if (!currency_transaction_submit_wallet_value(
			    character, -escrow,
			    payload.action == auction_action::list ?
				    currency_reason_type::auction_listing :
				    currency_reason_type::auction_bid,
			    payload.auction_id, source, deadline, nullptr, nullptr, 0) ||
		    character->only.pc->wallet_revision == revision)
		{
			pending.erase(key);
			return false;
		}
	}
	for (P_obj object : held)
		obj_from_char(object);
	if (escrow > 0 || !held.empty() || money_claim)
		currency_transaction_save_first(character);
	const critical_submit_result submitted =
		critical_command_coordinator_submit(std::move(command));
	if (!critical_submit_result_keeps_operation(submitted))
	{
		auto found = pending.find(key);
		found->second.completion = nullptr; // Refused admission has no business completion.
		found->second.completed.outcome = critical_apply_outcome::terminal_failure;
		found->second.completion_ready = true;
		// Keep the refund and item if the purse cannot take them yet.
		publish(found, character);
		return false;
	}
	return true;
}
} // namespace

bool auction_transaction_submit(P_char character, const auction_command_payload &payload,
				auction_completion_fn completion, critical_deadline_class deadline)
{
	return submit(character, payload, completion, critical_source_site::command, deadline);
}

bool auction_transaction_submit_background(const auction_command_payload &payload,
					   auction_completion_fn completion)
{
	return !payload.actor_pid &&
	       submit(nullptr, payload, completion, critical_source_site::zone_event,
		      critical_deadline_class::background);
}

void auction_transaction_handle_completions(const critical_completion *completions, size_t count)
{
	if (count && !completions)
		return;
	for (size_t index = 0; index < count; ++index)
	{
		auto found = pending.find(operation_key(completions[index].operation_id));
		if (found == pending.end())
			continue;
		found->second.completed = completions[index];
		found->second.completion_ready = true;
		P_char character = found->second.actor_pid ?
					   find_player_by_pid(found->second.actor_pid) :
					   nullptr;
		if (!found->second.actor_pid || character ||
		    (found->second.payload.action == auction_action::claim_money &&
		     found->second.payload.value > 0))
			publish(found, character);
	}
}

void auction_transaction_player_ready(P_char character)
{
	if (!character || IS_NPC(character))
		return;
	for (auto found = pending.begin(); found != pending.end();)
	{
		auto current = found++;
		if (current->second.actor_pid == static_cast<uint32_t>(GET_PID(character)) &&
		    current->second.completion_ready)
			publish(current, character);
	}
}

bool auction_transaction_player_busy(P_char character)
{
	if (!character || IS_NPC(character))
		return false;
	return std::any_of(
		pending.begin(), pending.end(), [&](const auto &entry)
		{ return entry.second.actor_pid == static_cast<uint32_t>(GET_PID(character)); });
}

critical_outbox_delivery_result
auction_transaction_outbox_delivery(const critical_outbox_record &record, void *context)
{
	if (record.destination != 5)
		return critical_outbox_test_destination(record, context);
	auction_command_result result = {};
	if (record.event_type != 1 || record.payload_version != 1 ||
	    !auction_command_decode_result(record.payload.data(), record.payload.size(), &result))
		return critical_outbox_delivery_result::terminal_failure;
	std::lock_guard<std::mutex> lock(outbox_mutex);
	auto found = outbox_publications.find(record.outbox_id);
	if (found != outbox_publications.end())
	{
		if (found->second.state == outbox_publication_state::published)
		{
			outbox_publications.erase(found);
			return critical_outbox_delivery_result::delivered;
		}
		if (found->second.state == outbox_publication_state::failed)
		{
			outbox_publications.erase(found);
			return critical_outbox_delivery_result::retryable_failure;
		}
		return critical_outbox_delivery_result::publication_pending;
	}
	try
	{
		if (outbox_publications.size() >= AUCTION_OUTBOX_PENDING_MAX)
			return critical_outbox_delivery_result::retryable_failure;
		outbox_publications.emplace(
			record.outbox_id,
			pending_outbox_publication{ result, outbox_publication_state::queued });
	}
	catch (const std::bad_alloc &)
	{
		return critical_outbox_delivery_result::retryable_failure;
	}
	return critical_outbox_delivery_result::publication_pending;
}

void auction_transaction_outbox_published(unsigned long long outbox_id, bool succeeded)
{
	std::lock_guard<std::mutex> lock(outbox_mutex);
	auto found = outbox_publications.find(outbox_id);
	if (found == outbox_publications.end())
		return;
	found->second.state = succeeded ? outbox_publication_state::published :
					  outbox_publication_state::failed;
	if (succeeded)
		critical_outbox_resume();
}

void auction_transaction_publish_outbox(void)
{
	for (auto found = pending.begin(); found != pending.end();)
	{
		auto current = found++;
		if (current->second.completion_ready)
		{
			P_char character = find_player_by_pid(current->second.actor_pid);
			if (character ||
			    (current->second.payload.action == auction_action::claim_money &&
			     current->second.payload.value > 0))
				publish(current, character);
		}
	}
	std::vector<std::pair<uint64_t, auction_command_result>> work;
	{
		std::lock_guard<std::mutex> lock(outbox_mutex);
		for (auto &[outbox_id, publication] : outbox_publications)
		{
			if (work.size() >= 64)
				break;
			if (publication.state == outbox_publication_state::queued)
			{
				publication.state = outbox_publication_state::publishing;
				work.emplace_back(outbox_id, publication.result);
			}
		}
	}
	for (const auto &[outbox_id, result] : work)
	{
		if (!auction_publish_committed_event(result, outbox_id))
			auction_transaction_outbox_published(outbox_id, false);
	}
}

void auction_transaction_reset_for_tests(void)
{
	for (const auto &[operation, entry] : pending)
	{
		static_cast<void>(operation);
		if (entry.payload.action == auction_action::claim_money && entry.payload.value > 0)
		{
			player_save_pipeline_release_trade(entry.actor_pid);
			currency_transaction_release_trade(entry.actor_pid);
		}
	}
	pending.clear();
	std::lock_guard<std::mutex> lock(outbox_mutex);
	outbox_publications.clear();
}
