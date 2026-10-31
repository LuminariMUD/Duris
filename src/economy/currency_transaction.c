/****************************************************************************
 *
 *  File: currency_transaction.c                                Part of Duris
 *  Usage: wallet and bank changes queued to the persistence writer
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "economy/currency_transaction.h"
#include "economy/currency_value.h"
#include "economy/auction_transaction.h"
#include "economy/collector_transaction.h"
#include "economy/shop_trade_transaction.h"

#include "core/files.h"
#include "flatfile/flatfile_player_repository.h"
#include "net/gmcp.h"
#include "persistence/persistence_checkpoint.h"
#include "persistence/persistence_mode.h"
#include "player/player_save_pipeline.h"
#include "player/player_snapshot_repository.h"
#include "sql/sql_player.h"
#include "core/prototypes.h"
#include "core/utils.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <climits>
#include <cerrno>
#include <cstring>
#include <string>

extern P_room world;

namespace
{
currency_transaction_health health = {};

uint32_t reserved_trade_pid;
int64_t reserved_trade_payment;
uint32_t reserved_chest_pid = 0;
std::string reserved_chest_account;
int reserved_chest_racewar = 0;

bool wallet_value_delta(P_char character, int64_t value, currency_vector *delta)
{
	if (!character || IS_NPC(character))
		return false;
	const currency_vector before{ { GET_COPPER(character), GET_SILVER(character),
					GET_GOLD(character), GET_PLATINUM(character) } };
	return currency_wallet_value_delta(before, value, delta);
}

bool bank_payment_deltas(P_char character, int64_t value, currency_vector *wallet,
			 currency_vector *bank)
{
	if (!character || IS_NPC(character) || value <= 0)
		return false;
	const std::array<int64_t, CURRENCY_DENOMINATION_COUNT> current = {
		GET_BALANCE_COPPER(character), GET_BALANCE_SILVER(character),
		GET_BALANCE_GOLD(character), GET_BALANCE_PLATINUM(character)
	};
	static constexpr std::array<int64_t, CURRENCY_DENOMINATION_COUNT> values = { 1, 10, 100,
										     1000 };
	int64_t total = 0;
	for (size_t index = 0; index < current.size(); ++index)
	{
		if (current[index] > (INT64_MAX - total) / values[index])
			return false;
		total += current[index] * values[index];
	}
	if (total < value)
		return false;
	currency_vector bank_delta = {};
	int64_t remaining = value;
	for (size_t index = 0; index < current.size() && remaining > 0; ++index)
	{
		const int64_t needed = (remaining + values[index] - 1) / values[index];
		const int64_t used = std::min(current[index], needed);
		bank_delta.amount[index] = -used;
		remaining -= used * values[index];
	}
	currency_vector wallet_delta = {};
	if (remaining < 0)
		wallet_delta = currency_canonical_value(-remaining);
	*wallet = wallet_delta;
	*bank = bank_delta;
	return true;
}

bool player_account(P_char character, std::string *account)
{
	if (!character || IS_NPC(character) || !character->only.pc || GET_PID(character) <= 0)
		return false;
	const char *name = get_account_name_safe(character);
	if (!name || !strcmp(name, "Unknown") || strlen(name) > CURRENCY_ACCOUNT_NAME_MAX_BYTES)
		return false;
	*account = name;
	return true;
}

// Each bank change is its own owner on the writer, so none replaces another.
void queue_bank_delta(const std::string &account, int racewar, const currency_vector &delta)
{
	static uint64_t sequence = 0;
	persistence_job_write_fn write;
	if (persistence_mode_get() == PERSISTENCE_MODE_FLATFILE_PRIMARY)
	{
		const char *root = persistence_mode_flatfile_root();
		if (root)
			write = [path = std::string(root), account, racewar, amounts = delta.amount,
				 prepared = flatfile_authority_operation{}]() mutable
			{
				std::string error;
				return flatfile_bank_delta_apply(path, account,
								 static_cast<int8_t>(racewar),
								 amounts, &prepared, &error);
			};
	}
	else
	{
		bank_delta_snapshot bank;
		bank.account_name = account;
		bank.racewar = racewar;
		bank.delta = delta.amount;
		write = [bank]() { return bank_delta_repository_apply_from_pool(bank); };
	}
	if (write && persistence_writer_submit(persistence_job_kind::bank, ++sequence,
					       sizeof(delta) + account.size(), std::move(write)) ==
			     player_save_submit_result::accepted)
	{
		++health.bank_deltas;
		return;
	}
	persistence_alert(AVATAR, "currency", "bank", "none", "none", "queue_failed",
			  "racewar=%d copper=%lld silver=%lld gold=%lld platinum=%lld", racewar,
			  static_cast<long long>(delta.amount[0]),
			  static_cast<long long>(delta.amount[1]),
			  static_cast<long long>(delta.amount[2]),
			  static_cast<long long>(delta.amount[3]));
}

bool apply(P_char character, const currency_command_payload &payload,
	   currency_completion_fn completion, const void *context, size_t context_size)
{
	// Other characters share the bank, not the purchaser's wallet. Their
	// already-committed wallet credits must still publish while the bank is held.
	if (currency_transaction_chest_busy(character) &&
	    (payload.pid == reserved_chest_pid ||
	     std::any_of(payload.bank_delta.amount.begin(), payload.bank_delta.amount.end(),
			 [](int64_t delta) { return delta != 0; })))
		return false;
	std::string account;
	if (!player_account(character, &account) ||
	    payload.pid != static_cast<uint32_t>(GET_PID(character)) ||
	    payload.racewar != static_cast<uint8_t>(GET_RACEWAR(character)) ||
	    strcasecmp(account.c_str(), payload.account_name.data()) ||
	    context_size > CURRENCY_PENDING_CONTEXT_MAX_BYTES || (context_size && !context))
		return false;
	++health.submitted;
	const auto *bytes = static_cast<const uint8_t *>(context);
	currency_command_result result = {};
	result.wallet.amount = { GET_COPPER(character), GET_SILVER(character), GET_GOLD(character),
				 GET_PLATINUM(character) };
	result.bank.amount = { GET_BALANCE_COPPER(character), GET_BALANCE_SILVER(character),
			       GET_BALANCE_GOLD(character), GET_BALANCE_PLATINUM(character) };
	bool bank_changes = false, bank_loses = false;
	for (size_t index = 0; index < CURRENCY_DENOMINATION_COUNT; ++index)
	{
		result.wallet.amount[index] += payload.wallet_delta.amount[index];
		result.bank.amount[index] += payload.bank_delta.amount[index];
		bank_changes = bank_changes || payload.bank_delta.amount[index];
		bank_loses = bank_loses || payload.bank_delta.amount[index] < 0;
		if (result.wallet.amount[index] < 0 || result.wallet.amount[index] > INT_MAX ||
		    result.bank.amount[index] < 0 || result.bank.amount[index] > INT_MAX)
		{
			++health.rejected;
			if (completion)
				completion(character, false, {}, ENOSPC, bytes, context_size);
			return true;
		}
	}
	if (reserved_trade_pid == payload.pid)
	{
		currency_vector eventual;
		if (!currency_wallet_after_value(result.wallet, reserved_trade_payment, &eventual))
		{
			++health.rejected;
			if (completion)
				completion(character, false, {}, ENOSPC, bytes, context_size);
			return true;
		}
	}
	GET_COPPER(character) = static_cast<int>(result.wallet.amount[0]);
	GET_SILVER(character) = static_cast<int>(result.wallet.amount[1]);
	GET_GOLD(character) = static_cast<int>(result.wallet.amount[2]);
	GET_PLATINUM(character) = static_cast<int>(result.wallet.amount[3]);
	result.wallet_revision = ++character->only.pc->wallet_revision;
	result.bank_revision = character->only.pc->bank_revision;
	if (bank_changes)
	{
		const AccountBankBalances balances = { static_cast<int>(result.bank.amount[0]),
						       static_cast<int>(result.bank.amount[1]),
						       static_cast<int>(result.bank.amount[2]),
						       static_cast<int>(result.bank.amount[3]) };
		result.bank_revision = character->only.pc->bank_revision + 1;
		publish_account_bank_balances_revision(account.c_str(), GET_RACEWAR(character),
						       &balances, result.bank_revision);
	}
	mark_player_dirty_components(GET_PID(character), PLAYER_COMPONENT_STATUS);
	gmcp_char_vitals(character);
	if (bank_loses)
		queue_bank_delta(account, GET_RACEWAR(character), payload.bank_delta);
	++health.committed;
	if (completion)
		completion(character, true, result, 0, bytes, context_size);
	if (bank_changes)
	{
		// The player's save (which also records what the completion marked done)
		// is queued after a bank debit and before a bank credit.
		currency_transaction_save_first(character);
		if (!bank_loses)
			queue_bank_delta(account, GET_RACEWAR(character), payload.bank_delta);
	}
	return true;
}
} // namespace

bool currency_transaction_submit(P_char character, const currency_vector &wallet_delta,
				 const currency_vector &bank_delta, currency_reason_type reason,
				 int64_t reason_id, critical_source_site source_site,
				 critical_deadline_class deadline_class,
				 currency_completion_fn completion, const void *context,
				 size_t context_size)
{
	return currency_transaction_submit_identified(character, {}, wallet_delta, bank_delta,
						      reason, reason_id, source_site,
						      deadline_class, completion, context,
						      context_size);
}

// The operation id and the source and deadline no longer matter: the change is applied
// once, now, and the save carries it.
bool currency_transaction_submit_identified(
	P_char character, const critical_operation_id & /*operation_id*/,
	const currency_vector &wallet_delta, const currency_vector &bank_delta,
	currency_reason_type reason, int64_t reason_id, critical_source_site /*source_site*/,
	critical_deadline_class /*deadline_class*/, currency_completion_fn completion,
	const void *context, size_t context_size)
{
	std::string account;
	if (!player_account(character, &account))
		return false;
	currency_command_payload payload = { .pid = static_cast<uint32_t>(GET_PID(character)),
					     .racewar =
						     static_cast<uint8_t>(GET_RACEWAR(character)),
					     .reason = reason,
					     .reason_id = reason_id,
					     .account_name = {},
					     .wallet_delta = wallet_delta,
					     .bank_delta = bank_delta };
	memcpy(payload.account_name.data(), account.data(), account.size());
	return apply(character, payload, completion, context, context_size);
}

bool currency_transaction_prepare_identify(P_char character, int64_t cost,
					   critical_command *command)
{
	std::string account;
	if (!command || cost <= 0 || currency_transaction_chest_busy(character) ||
	    reserved_trade_pid || !player_account(character, &account))
		return false;
	currency_vector wallet_delta = {}, bank_delta = {};
	const bool use_bank = GET_MONEY(character) < cost;
	if (use_bank ? !bank_payment_deltas(character, cost, &wallet_delta, &bank_delta) :
		       !wallet_value_delta(character, -cost, &wallet_delta))
		return false;
	currency_command_payload payload = {};
	payload.pid = static_cast<uint32_t>(GET_PID(character));
	payload.racewar = static_cast<uint8_t>(GET_RACEWAR(character));
	payload.reason = use_bank ? currency_reason_type::bank_payment :
				    currency_reason_type::wallet_spend;
	memcpy(payload.account_name.data(), account.data(), account.size());
	payload.wallet_delta = wallet_delta;
	payload.bank_delta = bank_delta;
	critical_operation_id id = {};
	if (!critical_operation_id_generate(&id) ||
	    !currency_command_build(command, id, payload, character->only.pc->wallet_revision,
				    character->only.pc->bank_revision,
				    critical_source_site::command,
				    critical_deadline_class::interactive))
		return false;
	command->accepted_at_usec = std::chrono::duration_cast<std::chrono::microseconds>(
					    std::chrono::system_clock::now().time_since_epoch())
					    .count();
	return critical_command_normalize(command);
}

bool currency_transaction_submit_prepared(P_char character, const critical_command &command,
					  currency_completion_fn completion, const void *context,
					  size_t context_size)
{
	currency_command_payload payload = {};
	return character && currency_command_decode_payload(command, &payload) &&
	       apply(character, payload, completion, context, context_size);
}

bool currency_transaction_submit_wallet_value(P_char character, int64_t value_delta,
					      currency_reason_type reason, int64_t reason_id,
					      critical_source_site source_site,
					      critical_deadline_class deadline_class,
					      currency_completion_fn completion,
					      const void *context, size_t context_size)
{
	currency_vector wallet_delta;
	if (!wallet_value_delta(character, value_delta, &wallet_delta))
		return false;
	return currency_transaction_submit(character, wallet_delta, {}, reason, reason_id,
					   source_site, deadline_class, completion, context,
					   context_size);
}

bool currency_transaction_submit_bank_reward(P_char character, int64_t value,
					     currency_reason_type reason, int64_t reason_id,
					     critical_source_site source_site,
					     critical_deadline_class deadline_class,
					     currency_completion_fn completion, const void *context,
					     size_t context_size)
{
	if (value <= 0)
		return false;
	return currency_transaction_submit(character, {}, currency_canonical_value(value), reason,
					   reason_id, source_site, deadline_class, completion,
					   context, context_size);
}

bool currency_transaction_submit_bank_payment(P_char character, int64_t value,
					      currency_reason_type reason, int64_t reason_id,
					      critical_source_site source_site,
					      critical_deadline_class deadline_class,
					      currency_completion_fn completion,
					      const void *context, size_t context_size)
{
	currency_vector wallet_delta = {}, bank_delta = {};
	if (!bank_payment_deltas(character, value, &wallet_delta, &bank_delta))
		return false;
	return currency_transaction_submit(character, wallet_delta, bank_delta, reason, reason_id,
					   source_site, deadline_class, completion, context,
					   context_size);
}

void currency_transaction_save_first(P_char character)
{
	if (!character || IS_NPC(character) || GET_PID(character) <= 0)
		return;
	const int room = character->in_room == NOWHERE ? NOWHERE : world[character->in_room].number;
	player_save_pipeline_request(character, PLAYER_CHECKPOINT_COMPONENT_ALL, RENT_CRASH, room);
}

currency_transaction_health currency_transaction_health_copy(void)
{
	return health;
}

void currency_transaction_reset_for_tests(void)
{
	reserved_trade_pid = 0;
	reserved_trade_payment = 0;
	reserved_chest_pid = 0;
	reserved_chest_account.clear();
	health = {};
}

bool currency_transaction_reserve_trade(P_char character, int64_t payment)
{
	if (!character || IS_NPC(character) || GET_PID(character) <= 0 || reserved_trade_pid ||
	    currency_transaction_chest_busy(character))
		return false;
	const currency_vector before{ { GET_COPPER(character), GET_SILVER(character),
					GET_GOLD(character), GET_PLATINUM(character) } };
	currency_vector after;
	if (!currency_wallet_after_value(before, payment, &after))
		return false;
	reserved_trade_pid = static_cast<uint32_t>(GET_PID(character));
	reserved_trade_payment = payment;
	return true;
}

void currency_transaction_release_trade(uint32_t pid)
{
	if (reserved_trade_pid == pid)
	{
		reserved_trade_pid = 0;
		reserved_trade_payment = 0;
	}
}

bool currency_transaction_publish_trade(P_char character, int64_t payment)
{
	if (!character || IS_NPC(character) || !character->only.pc ||
	    currency_transaction_chest_busy(character) ||
	    character->only.pc->wallet_revision == UINT64_MAX)
		return false;
	currency_vector before, after;
	before.amount = { GET_COPPER(character), GET_SILVER(character), GET_GOLD(character),
			  GET_PLATINUM(character) };
	if (!currency_wallet_after_value(before, payment, &after))
		return false;
	GET_COPPER(character) = static_cast<int>(after.amount[0]);
	GET_SILVER(character) = static_cast<int>(after.amount[1]);
	GET_GOLD(character) = static_cast<int>(after.amount[2]);
	GET_PLATINUM(character) = static_cast<int>(after.amount[3]);
	++character->only.pc->wallet_revision;
	mark_player_dirty_components(GET_PID(character), PLAYER_COMPONENT_STATUS);
	gmcp_char_vitals(character);
	return true;
}

bool currency_transaction_chest_account_busy(const char *account_name)
{
	return reserved_chest_pid && account_name &&
	       !strcasecmp(account_name, reserved_chest_account.c_str());
}

bool currency_transaction_chest_busy(P_char character)
{
	return reserved_chest_pid && character && !IS_NPC(character) &&
	       (static_cast<uint32_t>(GET_PID(character)) == reserved_chest_pid ||
		(GET_RACEWAR(character) == reserved_chest_racewar &&
		 currency_transaction_chest_account_busy(get_account_name_safe(character))));
}

bool currency_transaction_reserve_chest(P_char character)
{
	std::string account;
	if (reserved_chest_pid || reserved_trade_pid || !player_account(character, &account) ||
	    auction_transaction_player_busy(character) ||
	    collector_transaction_player_busy(character) ||
	    shop_trade_transaction_player_busy(character))
		return false;
	reserved_chest_pid = static_cast<uint32_t>(GET_PID(character));
	reserved_chest_account = std::move(account);
	reserved_chest_racewar = GET_RACEWAR(character);
	return true;
}

void currency_transaction_release_chest(uint32_t pid)
{
	if (pid == reserved_chest_pid)
	{
		reserved_chest_pid = 0;
		reserved_chest_account.clear();
	}
}

void currency_transaction_publish_chest(P_char character, const currency_command_result &result,
					bool bank_changes)
{
	if (!reserved_chest_pid)
		return;
	if (character && static_cast<uint32_t>(GET_PID(character)) == reserved_chest_pid)
	{
		GET_COPPER(character) = static_cast<int>(result.wallet.amount[0]);
		GET_SILVER(character) = static_cast<int>(result.wallet.amount[1]);
		GET_GOLD(character) = static_cast<int>(result.wallet.amount[2]);
		GET_PLATINUM(character) = static_cast<int>(result.wallet.amount[3]);
		character->only.pc->wallet_revision = result.wallet_revision;
		// A disconnected purchaser has no descriptor for shared-bank publication.
		if (bank_changes && result.bank_revision >= character->only.pc->bank_revision)
		{
			GET_BALANCE_COPPER(character) = static_cast<int>(result.bank.amount[0]);
			GET_BALANCE_SILVER(character) = static_cast<int>(result.bank.amount[1]);
			GET_BALANCE_GOLD(character) = static_cast<int>(result.bank.amount[2]);
			GET_BALANCE_PLATINUM(character) = static_cast<int>(result.bank.amount[3]);
			character->only.pc->bank_revision = result.bank_revision;
		}
		mark_player_dirty_components(reserved_chest_pid, PLAYER_COMPONENT_STATUS);
		gmcp_char_vitals(character);
	}
	if (bank_changes)
	{
		const AccountBankBalances bank{ static_cast<int>(result.bank.amount[0]),
						static_cast<int>(result.bank.amount[1]),
						static_cast<int>(result.bank.amount[2]),
						static_cast<int>(result.bank.amount[3]) };
		publish_account_bank_balances_revision(reserved_chest_account.c_str(),
						       reserved_chest_racewar, &bank,
						       result.bank_revision);
	}
}
