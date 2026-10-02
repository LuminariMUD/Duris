-- Since bank changes became deltas (persistence reset Phase 2), the delta that creates an
-- account_banks row wrote no currency_bank_baseline, and boot refuses a bank without one.
-- The server now writes it with the bank; this gives every older bank its baseline from
-- the row as it stands. INSERT IGNORE leaves an existing baseline alone, so it re-runs.
INSERT IGNORE INTO currency_bank_baseline(bank_id,opening_copper,opening_silver,opening_gold,
    opening_platinum,opening_revision)
SELECT id,bank_copper,bank_silver,bank_gold,bank_platinum,bank_revision FROM account_banks;
