-- A checkpoint belongs to the current season-reset singleton/epoch.
-- NULL preserves legacy/unknown provenance; only a new begin arms it as 0.
SET @pwipe_roster_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='season_reset_state'
      AND column_name='roster_recreated'),
    'SELECT 1',
    'ALTER TABLE season_reset_state ADD COLUMN roster_recreated TINYINT UNSIGNED NULL DEFAULT NULL');
PREPARE pwipe_roster_stmt FROM @pwipe_roster_sql;
EXECUTE pwipe_roster_stmt;
DEALLOCATE PREPARE pwipe_roster_stmt;
