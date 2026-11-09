-- Remember why a character last left the game, so the next login can act on it.
-- Zero means unknown and preserves today's ordinary login for existing characters.
SET @player_save_intent_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='player_data'
      AND column_name='save_intent'),
    'SELECT 1',
    'ALTER TABLE player_data ADD COLUMN save_intent TINYINT UNSIGNED NOT NULL DEFAULT 0');
PREPARE player_save_intent_stmt FROM @player_save_intent_sql;
EXECUTE player_save_intent_stmt;
DEALLOCATE PREPARE player_save_intent_stmt;
