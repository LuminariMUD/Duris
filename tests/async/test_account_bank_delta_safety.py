#!/usr/bin/env python3
"""Account-bank delta and committed-publication source contracts."""

from _paths import SRC
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sql = (SRC / "sql_player.c").read_text()
header = (SRC / "sql_player.h").read_text()
utility = (SRC / "utility.c").read_text()
actoth = (SRC / "actoth.c").read_text()
boon = (SRC / "boon.c").read_text()
ships = (SRC / "ships/ship_base.c").read_text()


def section(text: str, start_marker: str, end_marker: str) -> str:
    start = text.rfind(start_marker)
    assert start >= 0, start_marker
    end = text.find(end_marker, start)
    assert end >= 0, end_marker
    return text[start:end]


all_sources = "\n".join(
    path.read_text(errors="replace") for path in SRC.rglob("*.[ch]")
)
assert "sql_save_account_bank" not in all_sources
assert "set bank_copper=%d" not in sql
print("[PASS] cached absolute account-bank save API and write are gone")

assert "struct AccountBankBalances" in header
publish = section(
    utility,
    "void publish_account_bank_balances_revision(const char *account_name, int racewar,",
    "static void currency_adjustment_committed(",
)
assert "descriptor_list" in publish
assert "desc->connected != CON_PLAYING" in publish
assert "strcasecmp(desc->account->acct_name, account_name)" in publish
assert "GET_RACEWAR(target) != racewar" in publish
assert "gmcp_char_vitals(target);" in publish
assert all(
    field in publish
    for field in (
        "GET_BALANCE_COPPER(target) = balances->copper;",
        "GET_BALANCE_SILVER(target) = balances->silver;",
        "GET_BALANCE_GOLD(target) = balances->gold;",
        "GET_BALANCE_PLATINUM(target) = balances->platinum;",
    )
)
print("[PASS] committed results reach every playing same-account/same-side character")

do_deposit = section(actoth, "void do_deposit(", "void do_withdraw(")
assert "sql_account_bank_deposit" not in do_deposit
assert "currency_reason_type::atm_deposit" in do_deposit
deposit_all = section(do_deposit, 'if (strstr("all", argument))', "half_chop")
assert deposit_all.count("currency_transaction_submit(") == 1
assert "wallet_delta.amount[coin_type] = -money" in deposit_all
assert "bank_delta.amount[coin_type] = money" in deposit_all
do_withdraw = section(actoth, "void do_withdraw(", "void do_sneak(")
assert "sql_account_bank_withdraw" not in do_withdraw
assert "currency_reason_type::atm_withdraw" in do_withdraw
assert "wallet_delta.amount[ctype] = money" in do_withdraw
assert "bank_delta.amount[ctype] = -money" in do_withdraw
assert "The bank could not complete that withdrawal" in actoth
assert "atm_transaction_complete" in actoth
print("[PASS] ATM callers submit atomic vectors and publish only completion results")

sub_balance = section(utility, "int SUB_BALANCE(", "int SUB_MONEY(")
assert "GET_BALANCE(ch)" not in sub_balance
assert "sql_account_bank_withdraw_value" not in sub_balance
assert "currency_transaction_submit_bank_payment" in sub_balance
assert "sql_save_account_bank" not in sub_balance
print("[PASS] aggregate payments use the typed transaction boundary")

cash_boon = section(boon, "case BTYPE_CASH:", "case BTYPE_LEVEL:")
assert "sql_account_bank_deposit_balances" not in cash_boon
assert "currency_transaction_submit_bank_reward" in cash_boon
assert "currency_reason_type::boon_reward" in cash_boon
assert "GET_BALANCE_" not in cash_boon
insurance = section(ships, "int insurance = 0;", "int old_class = ship->m_class;")
assert "sql_account_bank_deposit" not in insurance
assert "currency_transaction_submit_bank_reward" in insurance
assert "currency_reason_type::ship_insurance" in insurance
assert "GET_BALANCE_PLATINUM(owner) +=" not in insurance
assert "insert_money_pickup" in insurance
print("[PASS] boon and ship rewards use transactional credits with staged fallbacks")

print("account-bank delta safety source contracts passed")
