-- NULL leaves the corresponding prototype value on legacy item rows.

SET @item_instance_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='player_items' AND column_name='extra2_flags'),
    'SELECT 1',
    'ALTER TABLE player_items ADD COLUMN extra2_flags INT UNSIGNED NULL,
        ADD COLUMN anti_flags INT UNSIGNED NULL, ADD COLUMN anti2_flags INT UNSIGNED NULL,
        ADD COLUMN craftsmanship SMALLINT NULL');
PREPARE item_instance_stmt FROM @item_instance_sql;
EXECUTE item_instance_stmt;
DEALLOCATE PREPARE item_instance_stmt;

SET @item_instance_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='player_pet_items' AND column_name='extra2_flags'),
    'SELECT 1',
    'ALTER TABLE player_pet_items ADD COLUMN extra2_flags INT UNSIGNED NULL,
        ADD COLUMN anti_flags INT UNSIGNED NULL, ADD COLUMN anti2_flags INT UNSIGNED NULL,
        ADD COLUMN craftsmanship SMALLINT NULL');
PREPARE item_instance_stmt FROM @item_instance_sql;
EXECUTE item_instance_stmt;
DEALLOCATE PREPARE item_instance_stmt;

SET @item_instance_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='locker_items' AND column_name='extra2_flags'),
    'SELECT 1',
    'ALTER TABLE locker_items ADD COLUMN extra2_flags INT UNSIGNED NULL,
        ADD COLUMN anti_flags INT UNSIGNED NULL, ADD COLUMN anti2_flags INT UNSIGNED NULL,
        ADD COLUMN craftsmanship SMALLINT NULL');
PREPARE item_instance_stmt FROM @item_instance_sql;
EXECUTE item_instance_stmt;
DEALLOCATE PREPARE item_instance_stmt;

SET @item_instance_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='corpse_items' AND column_name='extra2_flags'),
    'SELECT 1',
    'ALTER TABLE corpse_items ADD COLUMN extra2_flags INT UNSIGNED NULL,
        ADD COLUMN anti_flags INT UNSIGNED NULL, ADD COLUMN anti2_flags INT UNSIGNED NULL,
        ADD COLUMN craftsmanship SMALLINT NULL');
PREPARE item_instance_stmt FROM @item_instance_sql;
EXECUTE item_instance_stmt;
DEALLOCATE PREPARE item_instance_stmt;

SET @item_instance_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='shopkeeper_items' AND column_name='extra2_flags'),
    'SELECT 1',
    'ALTER TABLE shopkeeper_items ADD COLUMN extra2_flags INT UNSIGNED NULL,
        ADD COLUMN anti_flags INT UNSIGNED NULL, ADD COLUMN anti2_flags INT UNSIGNED NULL,
        ADD COLUMN craftsmanship SMALLINT NULL');
PREPARE item_instance_stmt FROM @item_instance_sql;
EXECUTE item_instance_stmt;
DEALLOCATE PREPARE item_instance_stmt;

SET @item_instance_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='saved_items' AND column_name='extra2_flags'),
    'SELECT 1',
    'ALTER TABLE saved_items ADD COLUMN extra2_flags INT UNSIGNED NULL,
        ADD COLUMN anti_flags INT UNSIGNED NULL, ADD COLUMN anti2_flags INT UNSIGNED NULL,
        ADD COLUMN craftsmanship SMALLINT NULL');
PREPARE item_instance_stmt FROM @item_instance_sql;
EXECUTE item_instance_stmt;
DEALLOCATE PREPARE item_instance_stmt;
