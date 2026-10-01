#include "economy/currency_transaction.h"

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

currency_vector canonical_value(int64_t value)
{
	currency_vector result = {};
	static constexpr std::array<int64_t, CURRENCY_DENOMINATION_COUNT> values = { 1, 10, 100,
										     1000 };
	for (size_t index = values.size(); index-- > 0;)
	{
		result.amount[index] = value / values[index];
		value %= values[index];
	}
	return result;
}

bool wallet_value_delta(P_char character, int64_t value_delta, currency_vector *delta)
{
	if (!value_delta || value_delta == INT64_MIN)
		return false;
	currency_vector wallet_delta = {};
	if (value_delta > 0)
		wallet_delta = canonical_value(value_delta);
	else
	{
		if (!character || IS_NPC(character))
			return false;
		const std::array<int64_t, CURRENCY_DENOMINATION_COUNT> current = {
			GET_COPPER(character), GET_SILVER(character), GET_GOLD(character),
			GET_PLATINUM(character)
		};
		static constexpr std::array<int64_t, CURRENCY_DENOMINATION_COUNT> values = { 1, 10,
											     100,
											     1000 };
		int64_t total = 0;
		for (size_t index = 0; index < current.size(); ++index)
		{
			if (current[index] > (INT64_MAX - total) / values[index])
				return false;
			total += current[index] * values[index];
		}
		const int64_t spend = -value_delta;
		if (total < spend)
			return false;
		const currency_vector after = canonical_value(total - spend);
		for (size_t index = 0; index < current.size(); ++index)
			wallet_delta.amount[index] = after.amount[index] - current[index];
	}
	*delta = wallet_delta;
	return true;
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
		wallet_delta = canonical_value(-remaining);
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
	if (!command || cost <= 0 || !player_account(character, &account))
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
	return currency_transaction_submit(character, {}, canonical_value(value), reason, reason_id,
					   source_site, deadline_class, completion, context,
					   context_size);
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
	health = {};
}
