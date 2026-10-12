-- The level cap opens each spell circle level (31, 36, ... 56) to every side and the
-- levels between them to one side at a time. level stays the level open to all;
-- level_good and level_evil hold the level a side has opened beyond it, 0 when it has
-- opened none. Each column is guarded separately, so the step re-runs.
SET @level_cap_sides_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='level_cap'
      AND column_name='level_good'),
    'SELECT 1',
    'ALTER TABLE level_cap ADD COLUMN level_good INT NOT NULL DEFAULT 0 AFTER level');
PREPARE level_cap_sides_stmt FROM @level_cap_sides_sql;
EXECUTE level_cap_sides_stmt;
DEALLOCATE PREPARE level_cap_sides_stmt;

SET @level_cap_sides_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='level_cap'
      AND column_name='level_evil'),
    'SELECT 1',
    'ALTER TABLE level_cap ADD COLUMN level_evil INT NOT NULL DEFAULT 0 AFTER level_good');
PREPARE level_cap_sides_stmt FROM @level_cap_sides_sql;
EXECUTE level_cap_sides_stmt;
DEALLOCATE PREPARE level_cap_sides_stmt;
