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
#include "currency_test_support.h"

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
    // A trade reserves its future debit without moving money. Ordinary
    // callers still complete synchronously, but cannot spend the reserved value.
    GET_COPPER(&alice.ch)=100;GET_SILVER(&alice.ch)=0;
    GET_GOLD(&alice.ch)=0;GET_PLATINUM(&alice.ch)=0;
    const auto reserved_revision=alice.pc.wallet_revision;
    assert(currency_transaction_reserve_trade(&alice.ch,-80));
    assert(wallet(&alice.ch)[0]==100 && alice.pc.wallet_revision==reserved_revision);
    assert(!currency_transaction_reserve_trade(&twin.ch,1));
    assert(currency_transaction_submit_wallet_value(&alice.ch,-30,
      currency_reason_type::wallet_spend,0,critical_source_site::command,
      critical_deadline_class::interactive,completion,nullptr,0));
    assert(!last_committed && last_error==ENOSPC && wallet(&alice.ch)[0]==100);
    assert(currency_transaction_submit_wallet_value(&alice.ch,-20,
      currency_reason_type::wallet_spend,0,critical_source_site::command,
      critical_deadline_class::interactive,completion,nullptr,0));
    assert(last_committed && wallet(&alice.ch)==(std::array<int64_t,4>{0,8,0,0}));
    currency_transaction_release_trade(999); // another player cannot release it
    assert(!currency_transaction_reserve_trade(&twin.ch,1));
    currency_transaction_release_trade(44);
    assert(currency_transaction_submit_wallet_value(&alice.ch,-80,
      currency_reason_type::wallet_spend,0,critical_source_site::command,
      critical_deadline_class::interactive,completion,nullptr,0));
    assert(last_committed && wallet(&alice.ch)==(std::array<int64_t,4>{0,0,0,0}));
    // A pending credit also reserves denomination space.
    GET_PLATINUM(&alice.ch)=INT_MAX-1;
    assert(currency_transaction_reserve_trade(&alice.ch,1000));
    assert(currency_transaction_submit_wallet_value(&alice.ch,1000,
      currency_reason_type::wallet_reward,0,critical_source_site::command,
      critical_deadline_class::interactive,completion,nullptr,0));
    assert(!last_committed && last_error==ENOSPC && GET_PLATINUM(&alice.ch)==INT_MAX-1);
    currency_transaction_reset_for_tests();
    assert(currency_transaction_reserve_trade(&twin.ch,0));
    currency_transaction_release_trade(46);
    return 0;
}
'''


(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="currency-in-memory-", dir=ROOT / "bin/tests") as temporary:
    source = Path(temporary) / "harness.cpp"
    binary = Path(temporary) / "harness"
    source.write_text(HARNESS)
    subprocess.run(
        [
            "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
            "-Wno-missing-field-initializers", "-g", "-O1", "-fsanitize=address,undefined",
            "-ffunction-sections", "-fdata-sections", "-Isrc", "-Itests/async", "-I/usr/include/mysql",
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

print("[PASS] pending trades reserve spending and coin capacity without delaying ordinary completions")
