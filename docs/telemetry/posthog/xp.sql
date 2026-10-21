-- Expand XP independently of time. Observed XP is not a committed-save ledger.
WITH deduplicated AS (
    SELECT
        properties.duris_event_id AS event_id,
        any(event) AS family,
        any(timestamp) AS captured_at,
        any(properties.timestamp_basis) AS timestamp_basis,
        any(properties.duris_character_id) AS character_id,
        any(toInt(properties.xp_observed_level)) AS observed_level,
        any(properties.xp_allocations) AS allocations,
        any(properties.unattributed_xp) AS unattributed,
        any(toInt(properties.class_id)) AS class_id,
        any(toInt(properties.race_id)) AS race_id,
        any(toInt(properties.faction_id)) AS faction_id,
        any(toInt(properties.level_band)) AS level_band,
        any(toInt(properties.before_level)) AS before_level,
        any(toInt(properties.after_level)) AS after_level,
        any(properties.threshold_xp) AS threshold_xp,
        any(toInt(properties.source)) AS source,
        any(toInt(properties.reason)) AS reason
    FROM events
    WHERE timestamp >= now() - INTERVAL 31 DAY AND timestamp < now()
      AND event IN ('duris_character_summary', 'duris_level_change')
      AND properties.duris_schema_version = 1
      AND properties.duris_environment_id = '1'
      AND properties.duris_season_id = '1'
      AND coalesce(properties.duris_test_run, '') = ''
    GROUP BY event_id
), buckets AS (
    SELECT
        if(timestamp_basis = 'occurrence', toDate(captured_at), NULL) AS utc_day,
        observed_level,
        arrayJoin(arrayConcat(JSONExtractArrayRaw(coalesce(toString(allocations), '[]')), [coalesce(toString(unattributed), '{}')])) AS bucket
    FROM deduplicated
    WHERE family = 'duris_character_summary'
), deltas AS (
    SELECT
        'observed_xp' AS row_plane, utc_day,
        if(JSONHas(bucket, 'class_id'), 'captured_bucket', 'unattributed') AS allocation,
        toInt(JSONExtractRaw(bucket, 'class_id')) AS class_id,
        toInt(JSONExtractRaw(bucket, 'race_id')) AS race_id,
        toInt(JSONExtractRaw(bucket, 'faction_id')) AS faction_id,
        toInt(JSONExtractRaw(bucket, 'level_band')) AS level_band,
        observed_level,
        toInt(JSONExtractRaw(bucket, 'source')) AS source,
        toInt(JSONExtractRaw(bucket, 'reason')) AS reason,
        toInt(JSONExtractRaw(bucket, 'modifier_flags')) AS modifier_flags,
        NULL AS character_id, NULL AS before_level, NULL AS after_level, NULL AS threshold_xp,
        toString(sumOrNull(accurateCastOrNull(JSONExtractString(bucket, 'requested_xp'), 'Decimal(38, 0)'))) AS requested_xp,
        toString(sumOrNull(accurateCastOrNull(JSONExtractString(bucket, 'computed_xp'), 'Decimal(38, 0)'))) AS computed_xp,
        toString(sumOrNull(accurateCastOrNull(JSONExtractString(bucket, 'applied_xp'), 'Decimal(38, 0)'))) AS applied_xp,
        toString(sumOrNull(accurateCastOrNull(JSONExtractString(bucket, 'attempts'), 'Decimal(38, 0)'))) AS attempts,
        toString(sumOrNull(accurateCastOrNull(JSONExtractString(bucket, 'zero_applied'), 'Decimal(38, 0)'))) AS zero_applied,
        countIf(JSONExtractRaw(bucket, 'requested_xp') = 'null' OR JSONExtractRaw(bucket, 'computed_xp') = 'null'
                OR JSONExtractRaw(bucket, 'applied_xp') = 'null' OR JSONExtractRaw(bucket, 'attempts') = 'null'
                OR JSONExtractRaw(bucket, 'zero_applied') = 'null') AS unavailable_inputs
    FROM buckets
    WHERE JSONExtractString(bucket, 'attempts') != '0'
    GROUP BY utc_day, allocation, class_id, race_id, faction_id, level_band, observed_level, source, reason, modifier_flags
), planes AS (
    SELECT * FROM deltas
    UNION ALL
    SELECT
        'level_change', if(timestamp_basis = 'occurrence', toDate(captured_at), NULL), 'captured_transition',
        class_id, race_id, faction_id, level_band, NULL, source, reason, NULL,
        character_id, before_level, after_level, threshold_xp,
        NULL, NULL, NULL, NULL, NULL, 0
    FROM deduplicated
    WHERE family = 'duris_level_change'
)
SELECT *, count() OVER () AS total_rows_before_limit
FROM planes
ORDER BY row_plane, utc_day DESC, class_id, race_id, faction_id, level_band, observed_level, source, reason, modifier_flags, character_id, before_level
LIMIT 500
