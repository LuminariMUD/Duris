-- stat_data stores signed shorts. Widen only TINYINT columns, never narrow data.
-- Build one ALTER and retain each column's existing nullability and numeric default.
SET @base_stats_columns = (
    SELECT GROUP_CONCAT(CONCAT('MODIFY COLUMN `', column_name, '` SMALLINT ',
        IF(is_nullable='YES', 'NULL', 'NOT NULL'),
        IF(column_default IS NULL, IF(is_nullable='YES', ' DEFAULT NULL', ''),
           CONCAT(' DEFAULT ', column_default))) ORDER BY ordinal_position SEPARATOR ', ')
    FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='player_data'
      AND column_name IN ('base_str','base_dex','base_agi','base_con','base_pow',
                          'base_int','base_wis','base_cha','base_kar','base_luk')
      AND data_type='tinyint');
SET @base_stats_sql = IF(@base_stats_columns IS NULL, 'SELECT 1',
                        CONCAT('ALTER TABLE player_data ', @base_stats_columns));
PREPARE base_stats_stmt FROM @base_stats_sql;
EXECUTE base_stats_stmt;
DEALLOCATE PREPARE base_stats_stmt;
