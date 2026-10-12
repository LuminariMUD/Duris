-- Discoveries are part of character status, checkpointed with the discovery EXP.
SET @flight_stops_sql = IF(EXISTS(
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='player_data'
      AND column_name='learned_flight_stops'),
    'SELECT 1',
    'ALTER TABLE player_data ADD COLUMN learned_flight_stops BIGINT UNSIGNED NOT NULL DEFAULT 0');
PREPARE flight_stops_stmt FROM @flight_stops_sql;
EXECUTE flight_stops_stmt;
DEALLOCATE PREPARE flight_stops_stmt;
