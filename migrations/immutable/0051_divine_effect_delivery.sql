-- Store delivery proof atomically with the ordinary entity snapshot.
-- NULL denotes the pre-delivery empty set or a legacy guild incarnation.
SET @divine_effect_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='artifact_domain_state'
      AND column_name='delivery_ids'),
    'SELECT 1',
    'ALTER TABLE artifact_domain_state ADD COLUMN delivery_ids VARBINARY(4096) NULL');
PREPARE divine_effect_stmt FROM @divine_effect_sql;
EXECUTE divine_effect_stmt;
DEALLOCATE PREPARE divine_effect_stmt;
SET @divine_effect_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='guilds'
      AND column_name='delivery_ids'),
    'SELECT 1',
    'ALTER TABLE guilds ADD COLUMN delivery_ids VARBINARY(4096) NULL');
PREPARE divine_effect_stmt FROM @divine_effect_sql;
EXECUTE divine_effect_stmt;
DEALLOCATE PREPARE divine_effect_stmt;
SET @divine_effect_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='guilds'
      AND column_name='delivery_identity'),
    'SELECT 1',
    'ALTER TABLE guilds ADD COLUMN delivery_identity BINARY(16) NULL');
PREPARE divine_effect_stmt FROM @divine_effect_sql;
EXECUTE divine_effect_stmt;
DEALLOCATE PREPARE divine_effect_stmt;
