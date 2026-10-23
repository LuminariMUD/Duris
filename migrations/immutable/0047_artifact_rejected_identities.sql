-- Keep rejected physical UIDs with the canonical decision across generations.
-- NULL is the legacy empty set. Runtime writes sorted, unique decimal UIDs.
SET @artifact_rejected_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='artifact_domain_state'
      AND column_name='rejected_item_uids'),
    'SELECT 1',
    'ALTER TABLE artifact_domain_state ADD COLUMN rejected_item_uids LONGTEXT NULL AFTER identity_state');
PREPARE artifact_rejected_stmt FROM @artifact_rejected_sql;
EXECUTE artifact_rejected_stmt;
DEALLOCATE PREPARE artifact_rejected_stmt;
