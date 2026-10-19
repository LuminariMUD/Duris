-- The existing item_uid FK is a custody projection. Unclaimed NPC/ground items
-- need a canonical physical identity before they have a durable custody row.
-- Preserve that FK and all legacy evidence. NULL/0 means unresolved, not absent.
SET @artifact_identity_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='artifact_domain_state'
      AND column_name='canonical_item_uid'),
    'SELECT 1',
    'ALTER TABLE artifact_domain_state ADD COLUMN canonical_item_uid BIGINT UNSIGNED NULL AFTER updated_at');
PREPARE artifact_identity_stmt FROM @artifact_identity_sql;
EXECUTE artifact_identity_stmt;
DEALLOCATE PREPARE artifact_identity_stmt;

-- 0 unresolved, 1 present, 2 retired, 3 proven absent. The UID remains on a
-- retired record so an old saved/recovered payload cannot resurrect that copy.
SET @artifact_identity_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='artifact_domain_state'
      AND column_name='identity_state'),
    'SELECT 1',
    'ALTER TABLE artifact_domain_state ADD COLUMN identity_state TINYINT UNSIGNED NOT NULL DEFAULT 0 AFTER canonical_item_uid');
PREPARE artifact_identity_stmt FROM @artifact_identity_sql;
EXECUTE artifact_identity_stmt;
DEALLOCATE PREPARE artifact_identity_stmt;

SET @artifact_identity_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.statistics
    WHERE table_schema=DATABASE() AND table_name='artifact_domain_state'
      AND index_name='uq_artifact_canonical_uid'),
    'SELECT 1',
    'ALTER TABLE artifact_domain_state ADD UNIQUE KEY uq_artifact_canonical_uid (canonical_item_uid)');
PREPARE artifact_identity_stmt FROM @artifact_identity_sql;
EXECUTE artifact_identity_stmt;
DEALLOCATE PREPARE artifact_identity_stmt;
