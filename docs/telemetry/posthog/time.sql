-- Interval deltas and latest checkpoint gaps are different planes; never add them.
WITH fragments AS (
    SELECT
        properties.duris_event_id AS event_id,
        any(timestamp) AS captured_at,
        any(properties.timestamp_basis) AS timestamp_basis,
        any(properties.duris_character_id) AS character_id,
        any(properties.duris_session_id) AS session_id,
        any(properties.time_allocations) AS allocations,
        any(properties.unattributed_time) AS unattributed,
        any(properties.reconciliation) AS reconciliation
    FROM events
    WHERE timestamp >= now() - INTERVAL 31 DAY AND timestamp < now()
      AND event = 'duris_character_summary'
      AND properties.duris_schema_version = 1
      AND properties.duris_environment_id = '1'
      AND properties.duris_season_id = '1'
      AND coalesce(properties.duris_test_run, '') = ''
    GROUP BY event_id
), buckets AS (
    SELECT
        if(timestamp_basis = 'occurrence', toDate(captured_at), NULL) AS utc_day,
        arrayJoin(arrayConcat(JSONExtractArrayRaw(coalesce(toString(allocations), '[]')), [coalesce(toString(unattributed), '{}')])) AS bucket
    FROM fragments
), deltas AS (
    SELECT
        'interval_delta' AS row_plane, utc_day,
        if(JSONHas(bucket, 'class_id'), 'captured_bucket', 'unattributed') AS allocation,
        toInt(JSONExtractRaw(bucket, 'class_id')) AS class_id,
        toInt(JSONExtractRaw(bucket, 'race_id')) AS race_id,
        toInt(JSONExtractRaw(bucket, 'faction_id')) AS faction_id,
        toInt(JSONExtractRaw(bucket, 'level_band')) AS level_band,
        toInt(JSONExtractRaw(bucket, 'zone')) AS zone,
        toInt(JSONExtractRaw(bucket, 'group_size')) AS group_size,
        toInt(JSONExtractRaw(bucket, 'context')) AS context,
        toInt(JSONExtractRaw(bucket, 'context_quality')) AS context_quality,
        NULL AS character_id, NULL AS session_id,
        toString(sumOrNull(accurateCastOrNull(JSONExtractString(bucket, 'connected_usec'), 'Decimal(38, 0)'))) AS connected_usec,
        toString(sumOrNull(accurateCastOrNull(JSONExtractString(bucket, 'active_usec'), 'Decimal(38, 0)'))) AS active_usec,
        toString(sumOrNull(accurateCastOrNull(JSONExtractString(bucket, 'idle_usec'), 'Decimal(38, 0)'))) AS idle_usec,
        toString(sumOrNull(accurateCastOrNull(JSONExtractString(bucket, 'unknown_usec'), 'Decimal(38, 0)'))) AS unknown_usec,
        toString(sumOrNull(accurateCastOrNull(JSONExtractString(bucket, 'resident_usec'), 'Decimal(38, 0)'))) AS resident_usec,
        toString(sumOrNull(accurateCastOrNull(JSONExtractString(bucket, 'linkdead_usec'), 'Decimal(38, 0)'))) AS linkdead_usec,
        countIf(JSONExtractRaw(bucket, 'connected_usec') = 'null' OR JSONExtractRaw(bucket, 'active_usec') = 'null'
                OR JSONExtractRaw(bucket, 'idle_usec') = 'null' OR JSONExtractRaw(bucket, 'unknown_usec') = 'null'
                OR JSONExtractRaw(bucket, 'resident_usec') = 'null' OR JSONExtractRaw(bucket, 'linkdead_usec') = 'null') AS unavailable_inputs
    FROM buckets
    WHERE JSONExtractString(bucket, 'resident_usec') != '0'
    GROUP BY utc_day, allocation, class_id, race_id, faction_id, level_band, zone, group_size, context, context_quality
), latest_reconciliation AS (
    -- Within one revision, cumulative observed duration grows. An unavailable
    -- comparison must not be replaced by an earlier apparently complete gap.
    SELECT
        character_id, session_id,
        argMax(toString(reconciliation), tuple(
            accurateCastOrNull(JSONExtractString(toString(reconciliation), 'revision'), 'Decimal(38, 0)'),
            NOT JSONExtractBool(toString(reconciliation), 'comparison_available'),
            coalesce(accurateCastOrNull(JSONExtractString(
                JSONExtractRaw(toString(reconciliation), 'observed_at_checkpoint'), 'resident_usec'), 'Decimal(38, 0)'), 0),
            event_id)) AS evidence
    FROM fragments
    WHERE JSONExtractBool(toString(reconciliation), 'checkpoint_available')
    GROUP BY character_id, session_id
), planes AS (
    SELECT * FROM deltas
    UNION ALL
    SELECT
        'checkpoint_gap_do_not_add', NULL, 'reconciliation_only',
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, character_id, session_id,
        nullIf(JSONExtractString(JSONExtractRaw(evidence, 'missing_detail'), 'connected_usec'), ''),
        nullIf(JSONExtractString(JSONExtractRaw(evidence, 'missing_detail'), 'active_usec'), ''),
        nullIf(JSONExtractString(JSONExtractRaw(evidence, 'missing_detail'), 'idle_usec'), ''),
        nullIf(JSONExtractString(JSONExtractRaw(evidence, 'missing_detail'), 'unknown_usec'), ''),
        nullIf(JSONExtractString(JSONExtractRaw(evidence, 'missing_detail'), 'resident_usec'), ''),
        nullIf(JSONExtractString(JSONExtractRaw(evidence, 'missing_detail'), 'linkdead_usec'), ''),
        if(JSONExtractBool(evidence, 'comparison_available'), 0, 1)
    FROM latest_reconciliation
)
SELECT *, count() OVER () AS total_rows_before_limit
FROM planes
ORDER BY row_plane, utc_day DESC, allocation, class_id, race_id, faction_id, level_band, zone, group_size, context, context_quality, session_id
LIMIT 500
