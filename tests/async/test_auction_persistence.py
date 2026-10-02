#!/usr/bin/env python3
from _paths import source
from pathlib import Path
import sys

src = source("auction_houses.c")
text = src.read_text()

epic = source("epic.c")
epic_text = epic.read_text()

ship = source("ships") / 'ship_base.c'
ship_text = ship.read_text()

ok = True

# insert_money_pickup should be atomic upsert
helper_start = text.find('bool insert_money_pickup(int pid, int money)')
if helper_start == -1:
    print('[FAIL] insert_money_pickup not found')
    ok = False
else:
    helper_end = text.find('\nbool ', helper_start + 1)
    helper_section = text[helper_start:helper_end if helper_end != -1 else len(text)]
    upsert = helper_section.find('ON DUPLICATE KEY UPDATE money = money + VALUES(money)')
    legacy_select = helper_section.find('SELECT pid FROM auction_money_pickups')
    legacy_update = helper_section.find('UPDATE auction_money_pickups SET money = money + %d')
    if upsert == -1:
        print('[FAIL] insert_money_pickup is not using an atomic upsert')
        ok = False
    else:
        print('[PASS] insert_money_pickup uses a single atomic upsert')
    if legacy_select != -1 or legacy_update != -1:
        print('[FAIL] legacy select/update refund helper logic still present')
        ok = False

# other insert_money_pickup callers should also check failures and use safe fallbacks
if 'currency_transaction_submit_wallet_value(' in epic_text and 'currency_reason_type::refund' in epic_text:
    print('[PASS] epic.c falls back to a transactional wallet credit when pickup staging fails')
else:
    print('[FAIL] epic.c does not use a transactional refund fallback')
    ok = False

if 'ship->money += insurance;' in ship_text and 'fell back to ship coffers' in ship_text:
    print('[PASS] ship_base.c falls back to ship coffers when pickup staging fails')
else:
    print('[FAIL] ship_base.c does not route insurance failures to ship coffers')
    ok = False

sys.exit(0 if ok else 1)
