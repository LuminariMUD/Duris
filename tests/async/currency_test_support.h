// World and persistence stubs shared by native currency tests.
#pragma once
#include "core/utils.h"
#include "economy/currency_transaction.h"
#include "persistence/persistence_mode.h"
#include "player/player_save_pipeline.h"
#include "player/player_snapshot_repository.h"
#include "flatfile/flatfile_player_repository.h"
#include "sql/sql_player.h"

#include <cassert>
#include <cerrno>
#include <cstdlib>
#include <string>
#include <vector>

P_room world = nullptr;
// Everything queued, in order: "save:<pid>" and "bank", plus
// "completion" when a completion runs.
static std::vector<std::string> order;
static int dirty = 0;
static int alerts = 0;
static P_char invalid_account = nullptr;

[[noreturn]] int panic_corruption_int(const char *, const char *, ...)
{
	abort();
}
void logit(const char *, const char *, ...) {}
void persistence_alert(int, const char *, const char *, const char *, const char *, const char *,
		       const char *, ...)
{
	++alerts;
}
void gmcp_char_vitals(P_char) {}
void mark_player_dirty_components(int, player_component_mask_t)
{
	++dirty;
}
const char *get_account_name_safe(P_char ch)
{
	if (ch == invalid_account)
		return "Unknown";
	return ch && GET_PID(ch) == 45 ? "other_account" : "money_account";
}
persistence_mode persistence_mode_get(void)
{
	return PERSISTENCE_MODE_MARIADB_PRIMARY;
}
const char *persistence_mode_flatfile_root(void)
{
	return nullptr;
}
player_save_apply_result flatfile_bank_delta_apply(const std::string &, const std::string &, int8_t,
						   const std::array<int64_t, 4> &,
						   flatfile_authority_operation *, std::string *)
{
	return { player_save_apply_outcome::applied, 0, 0 };
}
player_save_apply_result bank_delta_repository_apply_from_pool(const bank_delta_snapshot &)
{
	return { player_save_apply_outcome::applied, 0, 0 };
}
player_save_submit_result persistence_writer_submit(persistence_job_kind kind, uint64_t, size_t,
						    persistence_job_write_fn)
{
	assert(kind == persistence_job_kind::bank);
	order.push_back("bank");
	return player_save_submit_result::accepted;
}
player_save_pipeline_result player_save_pipeline_request(P_char ch, player_component_mask_t, int,
							 int)
{
	order.push_back("save:" + std::to_string(GET_PID(ch)));
	return player_save_pipeline_result::queued;
}

// The online characters of one account and side share the bank.
static P_char online[2] = {};
void publish_account_bank_balances_revision(const char *account, int racewar,
					    const AccountBankBalances *balances, uint64_t revision)
{
	for (P_char ch : online)
		if (ch && std::string(get_account_name_safe(ch)) == account &&
		    GET_RACEWAR(ch) == racewar)
		{
			GET_BALANCE_COPPER(ch) = balances->copper;
			GET_BALANCE_SILVER(ch) = balances->silver;
			GET_BALANCE_GOLD(ch) = balances->gold;
			GET_BALANCE_PLATINUM(ch) = balances->platinum;
			ch->only.pc->bank_revision = revision;
		}
}

struct player
{
	char_data ch = {};
	pc_only_data pc = {};
	explicit player(int pid)
	{
		ch.only.pc = &pc;
		pc.pid = pid;
		ch.player.racewar = 1;
		ch.in_room = NOWHERE;
	}
};

static bool last_committed = false;
static unsigned int last_error = 0;
static void completion(P_char, bool committed, const currency_command_result &,
		       unsigned int error_code, const uint8_t *, size_t)
{
	last_committed = committed;
	last_error = error_code;
	order.push_back("completion");
}

static std::array<int64_t, 4> wallet(P_char ch)
{
	return { GET_COPPER(ch), GET_SILVER(ch), GET_GOLD(ch), GET_PLATINUM(ch) };
}
