-- log_entries.ip_address was VARCHAR(15), so sql_log() cut every IPv6 address (and the
-- 16-character UNTRACEABLE placeholder) to fit. 45 characters hold any IPv6 address, as
-- account_ips already does. The guard issues no ALTER once the column holds 45, so the
-- step re-runs.
SET @log_entries_ipv6_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE()
      AND table_name='log_entries'
      AND column_name='ip_address'
      AND character_maximum_length>=45),
    'SELECT 1',
    'ALTER TABLE log_entries MODIFY COLUMN ip_address VARCHAR(45) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT ''''');
PREPARE log_entries_ipv6_stmt FROM @log_entries_ipv6_sql;
EXECUTE log_entries_ipv6_stmt;
DEALLOCATE PREPARE log_entries_ipv6_stmt;
