-- Checkpoint the applied prepared-award sequence with the player's epic balance.
-- Existing characters start at zero; additive and re-runnable.
SET @divine_delivery_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='player_data'
      AND column_name='divine_boon_delivery_seq'),
    'SELECT 1',
    'ALTER TABLE player_data ADD COLUMN divine_boon_delivery_seq BIGINT UNSIGNED NOT NULL DEFAULT 0');
PREPARE divine_delivery_stmt FROM @divine_delivery_sql;
EXECUTE divine_delivery_stmt;
DEALLOCATE PREPARE divine_delivery_stmt;
