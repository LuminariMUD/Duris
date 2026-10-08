/****************************************************************************
 *
 *  File: shop_trade_transaction.c                              Part of Duris
 *  Usage: pending shop trades and their completion handling
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "economy/shop_trade_transaction.h"

#include "economy/currency_transaction.h"
#include "item/item_ownership_runtime.h"
#include "core/prototypes.h"
#include "economy/shop_trade_runtime.h"
#include "core/utils.h"

#include <algorithm>
#include <cerrno>
#include <new>
#include <string>
#include <unordered_map>

namespace
{
struct pending_trade
{
	uint32_t player_pid = 0;
	shop_trade_payload payload = {};
	shop_trade_completion_fn completion = nullptr;
	bool completion_ready = false;
	critical_completion completed = {};
	// A purchase's price, taken from the wallet at submit.
	int64_t escrow = 0;
	// A sale's item, taken out of the seller's inventory at submit.
	P_obj held = nullptr;
};

std::unordered_map<std::string, pending_trade> pending;

std::string operation_key(const critical_operation_id &operation_id)
{
	return std::string(reinterpret_cast<const char *>(operation_id.bytes.data()),
			   operation_id.bytes.size());
}

bool buying(shop_trade_action action)
{
	return action == shop_trade_action::buy_existing ||
	       action == shop_trade_action::buy_produced;
}

bool selling(shop_trade_action action)
{
	return action == shop_trade_action::sell_store || action == shop_trade_action::sell_destroy;
}

bool player_pending(uint32_t pid)
{
	return std::any_of(pending.begin(), pending.end(),
			   [pid](const auto &entry) { return entry.second.player_pid == pid; });
}

bool publish_ownership(const shop_trade_payload &payload, const shop_trade_result &result)
{
	const item_owner_identity player = { item_owner_type::player, payload.player_pid, 0 };
	const item_owner_identity shop = { item_owner_type::shopkeeper,
					   item_shopkeeper_owner_id(payload.shop_id), 0 };
	const item_owner_identity system = { item_owner_type::system, 0, 0 };
	const item_owner_identity destruction = { item_owner_type::destruction, 0, 0 };
	item_transfer_payload transfer = {};
	if (payload.action == shop_trade_action::buy_existing)
	{
		transfer.from_owner = shop;
		transfer.to_owner = player;
		transfer.reason = item_transfer_reason::shop_buy;
	}
	else if (payload.action == shop_trade_action::buy_produced)
	{
		transfer.from_owner = system;
		transfer.to_owner = player;
		transfer.reason = item_transfer_reason::creation;
	}
	else if (payload.action == shop_trade_action::sell_store)
	{
		transfer.from_owner = player;
		transfer.to_owner = shop;
		transfer.reason = item_transfer_reason::shop_sell;
	}
	else if (payload.action == shop_trade_action::sell_destroy)
	{
		transfer.from_owner = player;
		transfer.to_owner = destruction;
		transfer.reason = item_transfer_reason::destruction;
	}
	else if (payload.action == shop_trade_action::discard_invalid)
	{
		transfer.from_owner = shop;
		transfer.to_owner = destruction;
		transfer.reason = item_transfer_reason::destruction;
	}
	else
		return false;
	transfer.reason_id = payload.shop_id;
	transfer.selected_item_uid = payload.selected_item_uid;
	transfer.target_root_item_uid = payload.target_root_item_uid ?
						payload.target_root_item_uid :
						payload.selected_item_uid;
	transfer.target_parent_item_uid = payload.target_parent_item_uid;
	transfer.expected_target_parent_revision = payload.expected_target_parent_revision;
	transfer.item_count = payload.item_count;
	for (size_t index = 0; index < payload.item_count; ++index)
		transfer.items[index] = { payload.items[index].item_uid,
					  payload.items[index].root_item_uid,
					  payload.items[index].parent_item_uid,
					  payload.items[index].expected_item_revision,
					  payload.items[index].vnum,
					  payload.items[index].expected_state };
	const bool buy = buying(payload.action);
	const bool cleanup = payload.action == shop_trade_action::discard_invalid;
	item_transfer_result transfer_result = {
		.root_item_uid = payload.selected_item_uid,
		.item_count = result.item_count,
		.from_owner_revision = cleanup ? result.player_owner_revision :
				       buy     ? result.counterparty_owner_revision :
						 result.player_owner_revision,
		.to_owner_revision = cleanup ? result.counterparty_owner_revision :
				     buy     ? result.player_owner_revision :
					       result.counterparty_owner_revision,
		.max_item_revision = 0,
		.corpse_revision = 0,
	};
	for (size_t index = 0; index < result.item_count; ++index)
		transfer_result.max_item_revision =
			std::max(transfer_result.max_item_revision, result.item_revisions[index]);
	return item_ownership_runtime_apply(transfer, transfer_result);
}

bool publish(std::unordered_map<std::string, pending_trade>::iterator found, P_char character)
{
	pending_trade &entry = found->second;
	shop_trade_result result = {};
	const bool decoded = shop_trade_command_decode_result(entry.completed.result_payload.data(),
							      entry.completed.result_size, &result);
	const bool committed = decoded &&
			       (entry.completed.outcome == critical_apply_outcome::applied ||
				entry.completed.outcome == critical_apply_outcome::already_applied);
	bool published =
		decoded &&
		(!committed || shop_trade_runtime_can_advance(entry.payload.shop_id,
							      entry.payload.expected_shop_revision,
							      result.shop_revision));
	// The wallet is memory's: a purchase paid at submit and gets its price back when
	// refused; a sale is paid now.
	const bool sold = !buying(entry.payload.action) &&
			  entry.payload.action != shop_trade_action::discard_invalid;
	const int64_t credit = !committed ? entry.escrow : sold ? entry.payload.price : 0;
	if (credit > 0)
		currency_transaction_submit_wallet_value(
			character, credit,
			committed ? currency_reason_type::wallet_reward :
				    currency_reason_type::refund,
			entry.payload.shop_id, critical_source_site::command,
			critical_deadline_class::interactive, nullptr, nullptr, 0);
	if (published && committed)
		published = publish_ownership(entry.payload, result);
	if (published && committed)
		published = shop_trade_runtime_advance(entry.payload.shop_id,
						       entry.payload.expected_shop_revision,
						       result.shop_revision);
	// A refused sale gives its item back; a committed one the completion hands to the
	// shopkeeper, and one that cannot be published is gone from the seller either way.
	// The item may have been extracted while it was held.
	P_obj held = find_live_object(entry.held, entry.payload.selected_item_uid);
	if (held && !committed)
		obj_to_char(held, character);
	else if (held && !published)
		extract_obj(held, TRUE);
	const auto completion = entry.completion;
	const shop_trade_payload payload = entry.payload;
	const unsigned int error_code = decoded ? entry.completed.error_code : EBADMSG;
	pending.erase(found);
	if (completion)
		completion(character, committed && published,
			   decoded ? result : shop_trade_result{}, published ? error_code : ESTALE,
			   payload);
	return committed && published;
}
} // namespace

bool shop_trade_transaction_submit(P_char character, const shop_trade_payload &payload,
				   shop_trade_completion_fn completion)
{
	if (!character || IS_NPC(character) || GET_PID(character) <= 0 ||
	    static_cast<uint32_t>(GET_PID(character)) != payload.player_pid ||
	    pending.size() >= SHOP_TRADE_PENDING_MAX || player_pending(payload.player_pid))
		return false;
	critical_operation_id operation_id = {};
	critical_command command = {};
	if (!critical_operation_id_generate(&operation_id) ||
	    !shop_trade_command_build(&command, operation_id, payload,
				      critical_source_site::command,
				      critical_deadline_class::interactive))
		return false;
	// A purchase's price leaves the wallet now, and the buyer's save is queued before the
	// command, so a crash between them loses the money instead of paying it twice.
	const int64_t escrow = buying(payload.action) && payload.price > 0 ? payload.price : 0;
	// A sale's item leaves the seller's inventory now too, so no save captured before the
	// sale commits can claim it back from the shopkeeper.
	P_obj held = nullptr;
	if (selling(payload.action))
	{
		for (held = character->carrying; held && held->obj_uid != payload.selected_item_uid;
		     held = held->next_content)
			;
		if (!held)
			return false;
	}
	const std::string key = operation_key(operation_id);
	try
	{
		pending.emplace(
			key,
			pending_trade{
				payload.player_pid, payload, completion, false, {}, escrow, held });
	}
	catch (const std::bad_alloc &)
	{
		return false;
	}
	if (held)
	{
		obj_from_char(held);
		currency_transaction_save_first(character);
	}
	if (escrow)
	{
		if (!currency_transaction_submit_wallet_value(
			    character, -escrow, currency_reason_type::wallet_spend, payload.shop_id,
			    critical_source_site::command, critical_deadline_class::interactive,
			    nullptr, nullptr, 0))
		{
			pending.erase(key);
			return false;
		}
		currency_transaction_save_first(character);
	}
	const auto submitted = critical_command_coordinator_submit(std::move(command));
	if (!critical_submit_result_keeps_operation(submitted))
	{
		pending.erase(key);
		if (held)
			obj_to_char(held, character);
		if (escrow)
			currency_transaction_submit_wallet_value(
				character, escrow, currency_reason_type::refund, payload.shop_id,
				critical_source_site::command, critical_deadline_class::interactive,
				nullptr, nullptr, 0);
		return false;
	}
	return true;
}

void shop_trade_transaction_handle_completions(const critical_completion *completions, size_t count)
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
		if (P_char character = find_player_by_pid(found->second.player_pid))
			publish(found, character);
	}
}

void shop_trade_transaction_player_ready(P_char character)
{
	if (!character || IS_NPC(character) || GET_PID(character) <= 0)
		return;
	for (;;)
	{
		auto found = std::find_if(pending.begin(), pending.end(),
					  [&](const auto &entry)
					  {
						  return entry.second.player_pid ==
								 static_cast<uint32_t>(
									 GET_PID(character)) &&
							 entry.second.completion_ready;
					  });
		if (found == pending.end())
			break;
		publish(found, character);
	}
}

bool shop_trade_transaction_player_busy(P_char character)
{
	return character && !IS_NPC(character) && GET_PID(character) > 0 &&
	       player_pending(static_cast<uint32_t>(GET_PID(character)));
}

void shop_trade_transaction_reset_for_tests(void)
{
	pending.clear();
}
