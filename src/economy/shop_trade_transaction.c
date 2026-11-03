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
#include "core/files.h"
#include "economy/shop_trade_runtime.h"
#include "player/player_save_pipeline.h"
#include "player/player_snapshot_codec.h"
#include "core/utils.h"

#include <algorithm>
#include <cerrno>
#include <chrono>
#include <openssl/sha.h>
#include <new>
#include <string>
#include <unordered_map>

extern P_room world;

namespace
{
struct pending_trade
{
	uint32_t player_pid = 0;
	shop_trade_payload payload = {};
	shop_trade_completion_fn completion = nullptr;
	bool completion_ready = false;
	critical_completion completed = {};
	// Reserved until the compound item/payment transaction commits.
	int64_t payment = 0;
	// A sale's item, taken out of the seller's inventory at submit.
	P_obj held = nullptr;
	shop_trade_prepare_fn prepare = nullptr;
	bool publication_failed = false;
	bool wallet_published = false;
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
	transfer.multi_root = payload.multi_root;
	transfer.selected_item_uid = payload.multi_root ? 0 : payload.selected_item_uid;
	transfer.target_root_item_uid = payload.target_root_item_uid ?
						payload.target_root_item_uid :
						payload.selected_item_uid;
	transfer.target_parent_item_uid = payload.target_parent_item_uid;
	transfer.expected_target_parent_revision = payload.expected_target_parent_revision;
	if (payload.multi_root && !payload.target_parent_item_uid)
		transfer.target_root_item_uid = 0;
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
	return item_ownership_runtime_apply(transfer, transfer_result,
					    result.item_revisions.data());
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
	if (committed && entry.payload.multi_root &&
	    (result.action != entry.payload.action ||
	     result.item_count != entry.payload.item_count ||
	     !std::equal(result.item_uids.begin(), result.item_uids.begin() + result.item_count,
			 entry.payload.items.begin(),
			 [](uint64_t uid, const auto &item) { return uid == item.item_uid; })))
		return false;
	if (committed && character && entry.prepare &&
	    !entry.prepare(character, entry.payload, result))
	{
		if (!entry.publication_failed)
		{
			entry.publication_failed = true;
			send_to_char("Your purchase committed and is awaiting safe delivery.\r\n",
				     character);
		}
		return false;
	}
	bool published =
		decoded &&
		(!committed || shop_trade_runtime_can_advance(entry.payload.shop_id,
							      entry.payload.expected_shop_revision,
							      result.shop_revision));
	if (!entry.wallet_published)
	{
		if (committed && entry.payment &&
		    !currency_transaction_publish_trade(character, entry.payment))
			return false;
		entry.wallet_published = true;
		if (entry.payment)
		{
			player_save_pipeline_release_trade(entry.player_pid);
			currency_transaction_release_trade(entry.player_pid);
		}
	}
	if (published && committed)
		published = publish_ownership(entry.payload, result);
	// Both publications run on the game thread without yielding. Once ownership
	// is applied, this already-validated shop revision advances in the same call.
	if (published && committed)
		published = shop_trade_runtime_advance(entry.payload.shop_id,
						       entry.payload.expected_shop_revision,
						       result.shop_revision);
	if (committed && character && entry.payload.multi_root && !published)
		return false;
	// A refused sale gives its item back; a committed one the completion hands to the
	// shopkeeper, and one that cannot be published is gone from the seller either way.
	// The item may have been extracted while it was held.
	P_obj held = find_live_object(entry.held, entry.payload.selected_item_uid);
	if (held && !committed)
	{
		if (character)
			obj_to_char(held, character);
		else
			extract_obj(held, FALSE); // the retained capture restores it on login
	}
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
				   shop_trade_completion_fn completion,
				   shop_trade_prepare_fn prepare)
{
	if (character && currency_transaction_wallet_busy(character))
		return false;
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
	command.accepted_at_usec = std::chrono::duration_cast<std::chrono::microseconds>(
					   std::chrono::system_clock::now().time_since_epoch())
					   .count();
	const int64_t payment = buying(payload.action)	? -payload.price :
				selling(payload.action) ? payload.price :
							  0;
	if (payment && character->only.pc->wallet_revision != payload.expected_wallet_revision)
		return false;
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
		pending.emplace(key, pending_trade{ payload.player_pid,
						    payload,
						    completion,
						    false,
						    {},
						    payment,
						    held,
						    prepare });
	}
	catch (const std::bad_alloc &)
	{
		return false;
	}
	if (payment)
	{
		player_pending_trade_snapshot tag;
		tag.operation = operation_id.bytes;
		tag.payment = payment;
		tag.wallet_revision = payload.expected_wallet_revision;
		std::vector<uint8_t> encoded;
		if (critical_command_encode(command, &encoded) != critical_command_codec_result::ok)
		{
			pending.erase(key);
			return false;
		}
		SHA256(encoded.data(), encoded.size(), tag.command_hash.data());
		if (!currency_transaction_reserve_trade(character, payment))
		{
			pending.erase(key);
			return false;
		}
		if (!player_save_pipeline_reserve_trade(payload.player_pid, tag))
		{
			currency_transaction_release_trade(payload.player_pid);
			pending.erase(key);
			return false;
		}
	}
	// Preserve the original purse and sale item until commit. A crash before the
	// command must leave both intact; later captures carry the payment receipt.
	if (payload.action != shop_trade_action::discard_invalid)
	{
		const int room = character->in_room == NOWHERE ? NOWHERE :
								 world[character->in_room].number;
		const auto saved = player_save_pipeline_request(
			character, PLAYER_CHECKPOINT_COMPONENT_ALL, RENT_CRASH, room);
		if (saved != player_save_pipeline_result::queued &&
		    saved != player_save_pipeline_result::coalesced)
		{
			if (payment)
			{
				player_save_pipeline_release_trade(payload.player_pid);
				currency_transaction_release_trade(payload.player_pid);
			}
			pending.erase(key);
			return false;
		}
	}
	if (held)
		obj_from_char(held);
	const auto submitted = critical_command_coordinator_submit(std::move(command));
	if (!critical_submit_result_keeps_operation(submitted))
	{
		pending.erase(key);
		if (payment)
		{
			player_save_pipeline_release_trade(payload.player_pid);
			currency_transaction_release_trade(payload.player_pid);
		}
		if (held)
			obj_to_char(held, character);
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
	// Safe delivery can fail while the buyer is online, then the buyer can
	// unload without another completion. Sweep retained replies on every pulse.
	for (auto next = pending.begin(); next != pending.end();)
	{
		auto found = next++;
		if (!found->second.completion_ready || find_player_by_pid(found->second.player_pid))
			continue;
		if (!found->second.wallet_published)
		{
			// Login reads the compound purse after queued captures settle. It
			// cannot wait for an absent actor to publish that same purse.
			auto &entry = found->second;
			shop_trade_result result;
			const bool decoded = shop_trade_command_decode_result(
				entry.completed.result_payload.data(), entry.completed.result_size,
				&result);
			const bool committed =
				entry.completed.outcome == critical_apply_outcome::applied ||
				entry.completed.outcome == critical_apply_outcome::already_applied;
			entry.wallet_published = decoded &&
						 ((committed && result.wallet_revision) ||
						  entry.completed.outcome ==
							  critical_apply_outcome::terminal_failure);
			if (entry.payment)
			{
				player_save_pipeline_release_trade(entry.player_pid);
				currency_transaction_release_trade(entry.player_pid);
			}
		}
		if (found->second.wallet_published || !found->second.payment)
			publish(found, nullptr);
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
		if (!publish(found, character))
			break;
	}
}

bool shop_trade_transaction_player_busy(P_char character)
{
	return character && !IS_NPC(character) && GET_PID(character) > 0 &&
	       player_pending(static_cast<uint32_t>(GET_PID(character)));
}

bool shop_trade_transaction_blocks_commands(P_char character)
{
	if (!character || IS_NPC(character) || GET_PID(character) <= 0)
		return false;
	return std::any_of(pending.begin(), pending.end(),
			   [&](const auto &entry)
			   {
				   return entry.second.player_pid ==
						  static_cast<uint32_t>(GET_PID(character)) &&
					  entry.second.payload.multi_root;
			   });
}

void shop_trade_transaction_reset_for_tests(void)
{
	for (const auto &[key, entry] : pending)
	{
		(void)key;
		if (entry.payment && !entry.wallet_published)
		{
			player_save_pipeline_release_trade(entry.player_pid);
			currency_transaction_release_trade(entry.player_pid);
		}
	}
	pending.clear();
}

bool shop_trade_transaction_capture_items(P_char character, player_snapshot *snapshot)
try
{
	if (!character || !snapshot)
		return false;
	if (!(snapshot->components & PLAYER_COMPONENT_INVENTORY))
		return true;
	for (const auto &[key, entry] : pending)
	{
		(void)key;
		if (entry.player_pid != static_cast<uint32_t>(GET_PID(character)) ||
		    !selling(entry.payload.action) || entry.wallet_published ||
		    !find_live_object(entry.held, entry.payload.selected_item_uid))
			continue;
		// The submit-time capture runs before detaching the item.
		if (std::any_of(snapshot->items.begin(), snapshot->items.end(),
				[&](const auto &item)
				{ return item.object_uid == entry.payload.selected_item_uid; }))
			return true;
		std::vector<player_item_snapshot> items;
		if (player_item_snapshot_list_decode(entry.payload.item_blob.data(),
						     entry.payload.item_blob_size,
						     &items) != player_snapshot_codec_result::ok)
			return false;
		const size_t bytes =
			entry.payload.item_blob_size + items.size() * sizeof(player_item_snapshot);
		if (bytes > PLAYER_SNAPSHOT_MAX_BYTES - snapshot->encoded_size_bound ||
		    items.size() > PLAYER_SNAPSHOT_MAX_OBJECTS - snapshot->items.size())
			return false;
		const size_t offset = snapshot->items.size();
		for (auto &item : items)
		{
			if (item.parent_index >= 0)
				item.parent_index += offset;
			snapshot->items.push_back(std::move(item));
		}
		snapshot->encoded_size_bound += bytes;
	}
	return true;
}
catch (const std::bad_alloc &)
{
	return false;
}
