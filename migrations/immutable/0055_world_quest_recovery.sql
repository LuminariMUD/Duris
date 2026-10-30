-- Retain accepted bartender origin and free replacement entitlement.
-- Zero means unknown legacy origin / no replacement due.
SET @quest_origin_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='player_data'
      AND column_name='quest_origin_room'),
    'SELECT 1',
    'ALTER TABLE player_data ADD COLUMN quest_origin_room INT NOT NULL DEFAULT 0');
PREPARE quest_origin_stmt FROM @quest_origin_sql;
EXECUTE quest_origin_stmt;
DEALLOCATE PREPARE quest_origin_stmt;

SET @quest_replacement_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='player_data'
      AND column_name='quest_replacement_due'),
    'SELECT 1',
    'ALTER TABLE player_data ADD COLUMN quest_replacement_due INT NOT NULL DEFAULT 0');
PREPARE quest_replacement_stmt FROM @quest_replacement_sql;
EXECUTE quest_replacement_stmt;
DEALLOCATE PREPARE quest_replacement_stmt;
