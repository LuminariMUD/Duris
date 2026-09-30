#!/usr/bin/env python3
"""Money moves in memory: at once, completed before the submit returns, saved in order.

Links the production currency transaction with the live world, the save pipeline and the
writer stubbed out, and records what is queued, in order.
"""

from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, rel


HARNESS = r'''
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
// Everything queued, in order: "save:<pid>" and "bank:<copper delta>", plus
// "completion" when a completion runs.
static std::vector<std::string> order;
static int dirty = 0;

[[noreturn]] int panic_corruption_int(const char *, const char *, ...) { abort(); }
void logit(const char *, const char *, ...) {}
void persistence_alert(int, const char *, const char *, const char *, const char *,
                       const char *, const char *, ...) {}
void gmcp_char_vitals(P_char) {}
void mark_player_dirty_components(int, player_component_mask_t) { ++dirty; }
const char *get_account_name_safe(P_char ch)
{
    return ch && GET_PID(ch) == 45 ? "other_account" : "money_account";
}
persistence_mode persistence_mode_get(void) { return PERSISTENCE_MODE_MARIADB_PRIMARY; }
const char *persistence_mode_flatfile_root(void) { return nullptr; }
player_save_apply_result flatfile_bank_delta_apply(const std::string &, const std::string &,
                                                   int8_t, const std::array<int64_t, 4> &,
                                                   flatfile_authority_operation *, std::string *)
{
    return {player_save_apply_outcome::applied, 0, 0};
}
player_save_apply_result bank_delta_repository_apply_from_pool(const bank_delta_snapshot &)
{
    return {player_save_apply_outcome::applied, 0, 0};
}
player_save_submit_result persistence_writer_submit(persistence_job_kind kind, uint64_t, size_t,
                                                    persistence_job_write_fn)
{
    assert(kind == persistence_job_kind::bank);
    order.push_back("bank");
    return player_save_submit_result::accepted;
}
player_save_pipeline_result player_save_pipeline_request(P_char ch, player_component_mask_t,
                                                         int, int)
{
    order.push_back("save:" + std::to_string(GET_PID(ch)));
    return player_save_pipeline_result::queued;
}

// The online characters of one account and side share the bank.
static P_char online[2] = {};
void publish_account_bank_balances_revision(const char *account, int racewar,
                                            const AccountBankBalances *balances,
                                            uint64_t revision)
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
    return {GET_COPPER(ch), GET_SILVER(ch), GET_GOLD(ch), GET_PLATINUM(ch)};
}

int main()
{
    player alice(44), twin(46), stranger(45);
    online[0] = &alice.ch;
    online[1] = &twin.ch;

    // A reward lands in the wallet before the submit returns; nothing is queued.
    assert(currency_transaction_submit_wallet_value(
        &alice.ch, 1234, currency_reason_type::wallet_reward, 0, critical_source_site::command,
        critical_deadline_class::interactive, completion, nullptr, 0));
    assert(last_committed && (wallet(&alice.ch) == std::array<int64_t, 4>{4, 3, 2, 1}));
    assert((order == std::vector<std::string>{"completion"}) && dirty == 1);
    order.clear();

    // A spend the wallet cannot cover is refused and changes nothing.
    currency_vector overdraft = {};
    overdraft.amount[3] = -2;
    assert(currency_transaction_submit(&alice.ch, overdraft, {},
                                       currency_reason_type::wallet_spend, 0,
                                       critical_source_site::command,
                                       critical_deadline_class::interactive, completion,
                                       nullptr, 0));
    assert(!last_committed && last_error == ENOSPC);
    assert((wallet(&alice.ch) == std::array<int64_t, 4>{4, 3, 2, 1}));
    order.clear();

    // A credit a denomination cannot hold is refused too, and leaves the wallet's
    // revision where it was: a coin pickup reads that to leave the pile alone.
    const uint64_t revision = alice.pc.wallet_revision;
    GET_PLATINUM(&alice.ch) = INT_MAX - 1;
    assert(currency_transaction_submit_wallet_value(
        &alice.ch, 2000, currency_reason_type::wallet_reward, 0, critical_source_site::command,
        critical_deadline_class::interactive, completion, nullptr, 0));
    assert(!last_committed && last_error == ENOSPC && alice.pc.wallet_revision == revision);
    GET_PLATINUM(&alice.ch) = 1;
    order.clear();

    // A deposit: the wallet shrinks and the bank of every online character of the
    // account and side grows. The player's save is queued before the bank credit, and
    // after the completion.
    currency_vector out = {}, in = {};
    out.amount[0] = -3;
    in.amount[0] = 3;
    assert(currency_transaction_submit(&alice.ch, out, in, currency_reason_type::atm_deposit, 0,
                                       critical_source_site::command,
                                       critical_deadline_class::interactive, completion,
                                       nullptr, 0));
    assert(last_committed && GET_COPPER(&alice.ch) == 1);
    assert(GET_BALANCE_COPPER(&alice.ch) == 3 && GET_BALANCE_COPPER(&twin.ch) == 3);
    assert((order == std::vector<std::string>{"completion", "save:44", "bank"}));
    order.clear();

    // A withdrawal: the bank debit is queued before the player's save.
    currency_vector back = {}, taken = {};
    back.amount[0] = 2;
    taken.amount[0] = -2;
    assert(currency_transaction_submit(&twin.ch, back, taken, currency_reason_type::atm_withdraw,
                                       0, critical_source_site::command,
                                       critical_deadline_class::interactive, completion,
                                       nullptr, 0));
    assert(last_committed && GET_COPPER(&twin.ch) == 2);
    assert(GET_BALANCE_COPPER(&alice.ch) == 1 && GET_BALANCE_COPPER(&twin.ch) == 1);
    assert((order == std::vector<std::string>{"bank", "completion", "save:46"}));
    order.clear();

    // More than the bank holds is refused, and nothing is queued.
    currency_vector too_much = {};
    too_much.amount[0] = -5;
    assert(currency_transaction_submit(&alice.ch, {}, too_much,
                                       currency_reason_type::bank_payment, 0,
                                       critical_source_site::command,
                                       critical_deadline_class::interactive, completion,
                                       nullptr, 0));
    assert(!last_committed && last_error == ENOSPC);
    assert((order == std::vector<std::string>{"completion"}));
    order.clear();

    // Another account's bank is not touched.
    stranger.ch.player.racewar = 1;
    assert(currency_transaction_submit_bank_reward(
        &stranger.ch, 7, currency_reason_type::bank_reward, 0, critical_source_site::command,
        critical_deadline_class::interactive, completion, nullptr, 0));
    assert(GET_BALANCE_COPPER(&stranger.ch) == 0 && GET_BALANCE_COPPER(&alice.ch) == 1);
    order.clear();

    // A prepared locker payment applies the same way.
    critical_command prepared = {};
    assert(currency_transaction_prepare_identify(&alice.ch, 1000, &prepared));
    assert(currency_transaction_submit_prepared(&alice.ch, prepared, completion, nullptr, 0));
    assert(last_committed && GET_PLATINUM(&alice.ch) == 0);
    const currency_transaction_health health = currency_transaction_health_copy();
    assert(health.committed == 5 && health.rejected == 3 && health.bank_deltas == 3);
    return 0;
}
'''


with tempfile.TemporaryDirectory(prefix="duris-currency-in-memory-") as temporary:
    source = Path(temporary) / "harness.cpp"
    binary = Path(temporary) / "harness"
    source.write_text(HARNESS)
    subprocess.run(
        [
            "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
            "-Wno-missing-field-initializers", "-g", "-O1", "-fsanitize=address,undefined",
            "-ffunction-sections", "-fdata-sections", "-Isrc", "-I/usr/include/mysql",
            str(source), rel("currency_transaction.c"), rel("currency_command.c"),
            rel("critical_command.c"), "-Wl,--gc-sections", "-lcrypto", "-o", str(binary),
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run([str(binary)], check=True, timeout=60)
print("[PASS] a reward and a spend change the wallet before the submit returns")
print("[PASS] a spend or debit the balance cannot cover, or a credit it cannot hold, is refused")
print("[PASS] a deposit saves the player before the bank credit; a withdrawal debits first")
print("[PASS] the bank of every online character of the account and side changes together")
