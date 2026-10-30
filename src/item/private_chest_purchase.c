#include "item/private_chest_purchase.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "economy/currency_transaction.h"
#include "sql/sql_async.h"
#include "sql/sql.h"
#include <climits>
#include <array>
#include <chrono>
#include <memory>

namespace
{
struct purchase
{
	uint32_t pid;
	int locker_id, racewar;
	std::string account, name, hash, operation;
	std::array<int64_t, 4> wallet, bank;
	uint64_t wallet_revision, bank_revision;
	bool bank_changes = false;
	bool inflight = false;
	std::chrono::steady_clock::time_point retry{};
	private_chest_purchase_completion done;
};
// Like the cargo market, one purchase at a time reserves the affected balances.
std::shared_ptr<purchase> pending;

#ifndef __NO_MYSQL__
unsigned int apply_purchase(MYSQL *connection, const purchase &p, sql_rows *rows)
{
	auto outcome = [&](const char *result, int id = 0)
	{
		sql_row row;
		row.fields = { std::string(result), std::to_string(id) };
		rows->push_back(std::move(row));
		return 0U;
	};
	// Escape on this worker's connection, never the game thread's DB handle.
	auto escape = [connection](const std::string &text)
	{
		std::string escaped(text.size() * 2 + 1, '\0');
		escaped.resize(mysql_real_escape_string(connection, escaped.data(), text.c_str(),
							text.size()));
		return escaped;
	};
	sql_rows receipt;
	if (const auto error =
		    sql_select(connection,
			       "SELECT id FROM private_chests WHERE purchase_operation=UNHEX('" +
				       p.operation + "')",
			       &receipt))
		return error;
	if (!receipt.empty())
		return outcome("created", atoi(receipt[0][0]));
	// Serialize count/name decisions with every purchase of this locker.
	sql_rows lockers;
	if (const auto error = sql_select(
		    connection,
		    sql_format("SELECT id FROM lockers WHERE id=%d FOR UPDATE", p.locker_id),
		    &lockers))
		return error;
	if (lockers.empty())
		return outcome("unavailable");
	sql_rows chests;
	if (const auto error = sql_select(
		    connection,
		    sql_format(
			    "SELECT chest_name FROM private_chests WHERE locker_id=%d AND is_public=0",
			    p.locker_id),
		    &chests))
		return error;
	for (const auto &row : chests)
		if (row[0] && !strcasecmp(row[0], p.name.c_str()))
			return outcome("taken");
	if (chests.size() >= 5)
		return outcome("full");
	sql_rows player;
	if (const auto error = sql_select(
		    connection,
		    sql_format("SELECT wallet_revision FROM player_data WHERE pid=%u FOR UPDATE",
			       p.pid),
		    &player))
		return error;
	if (player.empty() || strtoull(player[0][0], NULL, 10) > p.wallet_revision)
		return outcome("conflict");
	const std::string account = escape(p.account);
	if (p.bank_changes)
	{
		sql_rows bank;
		if (const auto error = sql_select(
			    connection,
			    sql_format(
				    "SELECT bank_revision FROM account_banks WHERE account_name='%s' AND racewar=%d FOR UPDATE",
				    account.c_str(), p.racewar),
			    &bank))
			return error;
		if (bank.empty() || strtoull(bank[0][0], NULL, 10) != p.bank_revision)
			return outcome("conflict");
	}
	// These statements and the receipt commit together. A lost COMMIT response is
	// reconciled by the same operation ID, never by charging a second time.
	if (const auto error = sql_execute(
		    connection,
		    sql_format(
			    "INSERT INTO private_chests (locker_id, chest_name, password_hash, is_public, purchase_operation) VALUES (%d, '%s', %s, 0, UNHEX('%s'))",
			    p.locker_id, escape(p.name).c_str(),
			    p.hash.empty() ? "NULL" : ("'" + escape(p.hash) + "'").c_str(),
			    p.operation.c_str())))
		return error;
	const int chest_id = static_cast<int>(mysql_insert_id(connection));
	if (const auto error = sql_execute(
		    connection,
		    sql_format(
			    "UPDATE player_data SET copper=%lld,silver=%lld,gold=%lld,platinum=%lld,wallet_revision=%llu WHERE pid=%u",
			    static_cast<long long>(p.wallet[0]),
			    static_cast<long long>(p.wallet[1]),
			    static_cast<long long>(p.wallet[2]),
			    static_cast<long long>(p.wallet[3]),
			    static_cast<unsigned long long>(p.wallet_revision) + 1ULL, p.pid)))
		return error;
	if (p.bank_changes)
		if (const auto error = sql_execute(
			    connection,
			    sql_format(
				    "UPDATE account_banks SET bank_copper=%lld,bank_silver=%lld,bank_gold=%lld,bank_platinum=%lld,bank_revision=%llu WHERE account_name='%s' AND racewar=%d",
				    static_cast<long long>(p.bank[0]),
				    static_cast<long long>(p.bank[1]),
				    static_cast<long long>(p.bank[2]),
				    static_cast<long long>(p.bank[3]),
				    static_cast<unsigned long long>(p.bank_revision) + 1ULL,
				    account.c_str(), p.racewar)))
			return error;
	return outcome("created", chest_id);
}
#endif
}

bool private_chest_purchase_locker_busy(int locker_id)
{
	return pending && pending->locker_id == locker_id;
}

bool private_chest_purchase_start(P_char actor, int locker_id, const std::string &name,
				  const std::string &hash, private_chest_purchase_completion done)
{
	if (!DB || pending || !actor || !actor->only.pc || locker_id <= 0 || !done ||
	    actor->only.pc->wallet_revision == UINT64_MAX ||
	    actor->only.pc->bank_revision == UINT64_MAX)
		return false;
	critical_command command;
	currency_command_payload payment;
	if (!currency_transaction_prepare_identify(actor, 500000, &command) ||
	    !currency_command_decode_payload(command, &payment))
		return false;
	auto p = std::make_shared<purchase>();
	p->pid = payment.pid;
	p->locker_id = locker_id;
	p->racewar = payment.racewar;
	p->account = payment.account_name.data();
	p->name = name;
	p->hash = hash;
	char operation[33];
	if (!critical_operation_id_to_hex(command.operation_id, operation, sizeof(operation)))
		return false;
	p->operation = operation;
	p->wallet = { GET_COPPER(actor), GET_SILVER(actor), GET_GOLD(actor), GET_PLATINUM(actor) };
	p->bank = { GET_BALANCE_COPPER(actor), GET_BALANCE_SILVER(actor), GET_BALANCE_GOLD(actor),
		    GET_BALANCE_PLATINUM(actor) };
	for (size_t i = 0; i < 4; ++i)
	{
		p->wallet[i] += payment.wallet_delta.amount[i];
		p->bank[i] += payment.bank_delta.amount[i];
		p->bank_changes = p->bank_changes || payment.bank_delta.amount[i];
		if (p->wallet[i] < 0 || p->wallet[i] > INT_MAX || p->bank[i] < 0 ||
		    p->bank[i] > INT_MAX)
			return false;
	}
	p->wallet_revision = actor->only.pc->wallet_revision;
	p->bank_revision = actor->only.pc->bank_revision;
	p->done = std::move(done);
	if (!currency_transaction_reserve_chest(actor))
		return false;
	pending = std::move(p);
	private_chest_purchase_pulse();
	return true;
}

void private_chest_purchase_pulse(void)
{
#ifndef __NO_MYSQL__
	if (!pending || pending->inflight || std::chrono::steady_clock::now() < pending->retry)
		return;
	auto p = pending;
	p->inflight = true;
	if (!sql_read_work(
		    [p](MYSQL *connection, sql_rows *rows)
		    { return apply_purchase(connection, *p, rows); },
		    [p](bool ok, const sql_rows &rows)
		    {
			    p->inflight = false;
			    if (!ok || rows.empty() || !rows[0][0])
			    {
				    // This includes an unknown COMMIT outcome. Keep the reservation
				    // and reconcile the durable operation even if the actor is gone.
				    p->retry = std::chrono::steady_clock::now() +
					       std::chrono::seconds(1);
				    return;
			    }
			    const std::string outcome = rows[0][0];
			    const bool committed = outcome == "created";
			    P_char actor = find_player_by_pid(p->pid);
			    if (actor &&
				(GET_RACEWAR(actor) != p->racewar ||
				 strcasecmp(get_account_name_safe(actor), p->account.c_str())))
				    actor = NULL;
			    if (committed)
			    {
				    currency_command_result result{};
				    result.wallet.amount = p->wallet;
				    result.bank.amount = p->bank;
				    result.wallet_revision = p->wallet_revision + 1;
				    result.bank_revision = p->bank_revision + 1;
				    currency_transaction_publish_chest(actor, result,
								       p->bank_changes);
			    }
			    currency_transaction_release_chest(p->pid);
			    pending.reset();
			    p->done(actor, committed && rows[0][1] ? atoi(rows[0][1]) : 0, outcome);
		    }))
	{
		p->inflight = false;
		p->retry = std::chrono::steady_clock::now() + std::chrono::seconds(1);
	}
#endif
}
