-- Acknowledgement belongs to the character's normal status checkpoint.
-- Leave an existing column untouched; the verifier refuses an incompatible shape.
SET @news_ack_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='player_data'
      AND column_name='last_read_news_hash'),
    'SELECT 1',
    'ALTER TABLE player_data ADD COLUMN last_read_news_hash VARBINARY(64) NOT NULL DEFAULT ''''');
PREPARE news_ack_stmt FROM @news_ack_sql;
EXECUTE news_ack_stmt;
DEALLOCATE PREPARE news_ack_stmt;
