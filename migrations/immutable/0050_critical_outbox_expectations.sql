-- Record the writer's expected contiguous event indexes (0..count-1).
-- NULL preserves unknown historical expectations. Never infer from surviving events.
-- INSTANT refuses a table-copy fallback; apply before starting the new writer.
SET @critical_outbox_expectations_sql = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE critical_operation_inbox ADD COLUMN expected_outbox_events SMALLINT UNSIGNED NULL DEFAULT NULL, ALGORITHM=INSTANT',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'critical_operation_inbox'
      AND column_name = 'expected_outbox_events'
);
PREPARE critical_outbox_expectations_stmt FROM @critical_outbox_expectations_sql;
EXECUTE critical_outbox_expectations_stmt;
DEALLOCATE PREPARE critical_outbox_expectations_stmt;
