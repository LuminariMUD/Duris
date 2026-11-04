-- NULL identifies legacy compact rows. Their original slot positions are unknown.
-- Apply before starting the slot-aware binary. An older writer can discard slot data.

SET @item_slot_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='player_item_affects' AND column_name='affect_slot'),
    'SELECT 1',
    'ALTER TABLE player_item_affects ADD COLUMN affect_slot TINYINT UNSIGNED NULL,
        ADD UNIQUE KEY uk_item_affect_slot (item_id, affect_slot), DROP INDEX uk_item_affect');
PREPARE item_slot_stmt FROM @item_slot_sql;
EXECUTE item_slot_stmt;
DEALLOCATE PREPARE item_slot_stmt;

SET @item_slot_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='player_pet_item_affects' AND column_name='affect_slot'),
    'SELECT 1',
    'ALTER TABLE player_pet_item_affects ADD COLUMN affect_slot TINYINT UNSIGNED NULL,
        ADD UNIQUE KEY uk_item_affect_slot (item_id, affect_slot), DROP INDEX uk_pet_item_affect');
PREPARE item_slot_stmt FROM @item_slot_sql;
EXECUTE item_slot_stmt;
DEALLOCATE PREPARE item_slot_stmt;

SET @item_slot_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='locker_item_affects' AND column_name='affect_slot'),
    'SELECT 1',
    'ALTER TABLE locker_item_affects ADD COLUMN affect_slot TINYINT UNSIGNED NULL,
        ADD UNIQUE KEY uk_item_affect_slot (item_id, affect_slot)');
PREPARE item_slot_stmt FROM @item_slot_sql;
EXECUTE item_slot_stmt;
DEALLOCATE PREPARE item_slot_stmt;

SET @item_slot_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='corpse_item_affects' AND column_name='affect_slot'),
    'SELECT 1',
    'ALTER TABLE corpse_item_affects ADD COLUMN affect_slot TINYINT UNSIGNED NULL,
        ADD UNIQUE KEY uk_item_affect_slot (item_id, affect_slot)');
PREPARE item_slot_stmt FROM @item_slot_sql;
EXECUTE item_slot_stmt;
DEALLOCATE PREPARE item_slot_stmt;

SET @item_slot_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='shopkeeper_item_affects' AND column_name='affect_slot'),
    'SELECT 1',
    'ALTER TABLE shopkeeper_item_affects ADD COLUMN affect_slot TINYINT UNSIGNED NULL,
        ADD UNIQUE KEY uk_item_affect_slot (item_id, affect_slot)');
PREPARE item_slot_stmt FROM @item_slot_sql;
EXECUTE item_slot_stmt;
DEALLOCATE PREPARE item_slot_stmt;

SET @item_slot_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='saved_item_affects' AND column_name='affect_slot'),
    'SELECT 1',
    'ALTER TABLE saved_item_affects ADD COLUMN affect_slot TINYINT UNSIGNED NULL,
        ADD UNIQUE KEY uk_item_affect_slot (item_id, affect_slot)');
PREPARE item_slot_stmt FROM @item_slot_sql;
EXECUTE item_slot_stmt;
DEALLOCATE PREPARE item_slot_stmt;
