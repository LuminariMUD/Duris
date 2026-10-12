-- Capture identity at the event, never infer historical ownership from player_data.
-- NULL marks pre-upgrade journal entries and rows whose identity was unavailable.
SET @session_identity_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='session_audit_outcome'
      AND column_name='account_name'),
    'SELECT 1',
    'ALTER TABLE session_audit_outcome ADD COLUMN account_name VARCHAR(50) COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL');
PREPARE session_identity_stmt FROM @session_identity_sql;
EXECUTE session_identity_stmt;
DEALLOCATE PREPARE session_identity_stmt;

SET @session_identity_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='session_audit_outcome'
      AND column_name='is_staff'),
    'SELECT 1',
    'ALTER TABLE session_audit_outcome ADD COLUMN is_staff TINYINT UNSIGNED NULL DEFAULT NULL');
PREPARE session_identity_stmt FROM @session_identity_sql;
EXECUTE session_identity_stmt;
DEALLOCATE PREPARE session_identity_stmt;
