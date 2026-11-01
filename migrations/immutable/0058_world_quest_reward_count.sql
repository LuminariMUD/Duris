-- Freeze the bartender completion quantity across failed reward preparation.
-- Zero preserves the legacy one-item entitlement of already completed quests.
SET @quest_reward_count_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='player_data'
      AND column_name='quest_reward_item_count'),
    'SELECT 1',
    'ALTER TABLE player_data ADD COLUMN quest_reward_item_count INT NOT NULL DEFAULT 0');
PREPARE quest_reward_count_stmt FROM @quest_reward_count_sql;
EXECUTE quest_reward_count_stmt;
DEALLOCATE PREPARE quest_reward_count_stmt;
