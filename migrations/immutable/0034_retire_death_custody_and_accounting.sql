-- Every server is treated as new (persistence reset Phase 3): nothing reads the
-- death custody and restitution records or the economy accounting evidence any
-- more, so their tables go. DROP TABLE IF EXISTS is rerunnable, and each table
-- goes before the tables its foreign keys reference.
DROP TABLE IF EXISTS player_death_restitution_runtime;
DROP TABLE IF EXISTS player_death_restitution_delivery;
DROP TABLE IF EXISTS player_death_restitution_item;
DROP TABLE IF EXISTS player_death_restitution_receipt;
DROP TABLE IF EXISTS player_death_custody;
DROP TABLE IF EXISTS player_death_disposition;
DROP TABLE IF EXISTS economic_baseline_reservation;
DROP TABLE IF EXISTS economic_baseline_witness;
DROP TABLE IF EXISTS economic_baseline_control;
DROP TABLE IF EXISTS economic_accounting_source_claim;
DROP TABLE IF EXISTS economic_accounting_item_reference;
DROP TABLE IF EXISTS economic_accounting_child;
DROP TABLE IF EXISTS economic_accounting_coin_posting;
DROP TABLE IF EXISTS economic_accounting_account_effect;
DROP TABLE IF EXISTS economic_account_mapping;
DROP TABLE IF EXISTS economic_accounting_operation;
DROP TABLE IF EXISTS economic_lineage_state;
DROP TABLE IF EXISTS economic_epoch;

-- 0031 added this ledger index for the accounting item references.
SET @accounting_reference_index = (SELECT COUNT(*) FROM information_schema.statistics
    WHERE table_schema=DATABASE() AND table_name='item_ownership_ledger'
      AND index_name='uq_item_ledger_accounting_reference');
SET @accounting_reference_sql = IF(@accounting_reference_index>0,
    'DROP INDEX uq_item_ledger_accounting_reference ON item_ownership_ledger',
    'SELECT 1');
PREPARE accounting_reference_stmt FROM @accounting_reference_sql;
EXECUTE accounting_reference_stmt;
DEALLOCATE PREPARE accounting_reference_stmt;
