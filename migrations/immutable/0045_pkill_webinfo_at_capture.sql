-- Historical consent is unknown. Never infer it from a mutable player flag.
-- Append the column so existing ordinal metadata (including log) stays stable.
SET @pkill_webinfo_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='pkill_info'
      AND column_name='webinfo_at_capture'),
    'SELECT 1',
    'ALTER TABLE pkill_info ADD COLUMN webinfo_at_capture TINYINT NULL DEFAULT NULL');
PREPARE pkill_webinfo_stmt FROM @pkill_webinfo_sql;
EXECUTE pkill_webinfo_stmt;
DEALLOCATE PREPARE pkill_webinfo_stmt;
