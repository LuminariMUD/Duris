-- Keep the kill's unmodified ally count so level-cap maintenance can apply the
-- current base-share threshold. Existing outcomes have an unknown count (0)
-- and cannot unlock a level. No reward or history data is rewritten.
SET @combat_allies_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='combat_outcome'
      AND column_name='killer_allies'),
    'SELECT 1',
    'ALTER TABLE combat_outcome ADD COLUMN killer_allies INT UNSIGNED NOT NULL DEFAULT 0');
PREPARE combat_allies_stmt FROM @combat_allies_sql;
EXECUTE combat_allies_stmt;
DEALLOCATE PREPARE combat_allies_stmt;
