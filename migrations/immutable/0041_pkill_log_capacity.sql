-- Legacy upgrades can retain TEXT, which cannot hold a 99,999-byte PvP log.
-- Preserve existing rows and leave MEDIUMTEXT/LONGTEXT columns unchanged on replay.
SET @pkill_log_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='pkill_info'
      AND column_name='log' AND data_type IN ('mediumtext', 'longtext')),
    'SELECT 1',
    'ALTER TABLE pkill_info MODIFY COLUMN log MEDIUMTEXT NULL');
PREPARE pkill_log_stmt FROM @pkill_log_sql;
EXECUTE pkill_log_stmt;
DEALLOCATE PREPARE pkill_log_stmt;
