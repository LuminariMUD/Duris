-- Full 20/20 outcomes need an 8192-byte result instead of the legacy 4096-byte inbox.
-- Widen only the known prior shape. Unexpected definitions are left for the
-- verifier to reject, preserving their data. INPLACE/LOCK=NONE forbid a table-copy fallback.
SET @full_group_combat_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='critical_operation_inbox'
      AND column_name='result_payload' AND column_type='varbinary(4096)'
      AND is_nullable='NO'),
    'ALTER TABLE critical_operation_inbox MODIFY COLUMN result_payload VARBINARY(8192) NOT NULL, ALGORITHM=INPLACE, LOCK=NONE',
    'SELECT 1');
PREPARE full_group_combat_stmt FROM @full_group_combat_sql;
EXECUTE full_group_combat_stmt;
DEALLOCATE PREPARE full_group_combat_stmt;
