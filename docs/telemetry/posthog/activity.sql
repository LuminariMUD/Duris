-- Rolling character returns, not account/player retention. Reconnects are not entries.
WITH deduplicated AS (
    SELECT
        properties.duris_event_id AS event_id,
        any(properties.duris_character_id) AS character_id,
        any(properties.duris_session_id) AS session_id,
        any(properties.transition) AS transition,
        any(properties.timestamp_basis) AS timestamp_basis
    FROM events
    WHERE timestamp >= now() - INTERVAL 31 DAY AND timestamp < now()
      AND event = 'duris_session'
      AND properties.duris_schema_version = 1
      AND properties.duris_environment_id = '1'
      AND properties.duris_season_id = '1'
      AND coalesce(properties.duris_test_run, '') = ''
    GROUP BY event_id
), characters AS (
    SELECT
        character_id,
        uniqExactIf(session_id, transition = 'logical_entry' AND timestamp_basis = 'occurrence') AS entries,
        uniqExactIf(session_id, transition = 'logical_exit' AND timestamp_basis = 'occurrence') AS exits,
        countIf(transition = 'connection_attached' AND timestamp_basis = 'occurrence') AS attachments,
        countIf(transition = 'logical_entry' AND timestamp_basis != 'occurrence') AS unallocated_entries
    FROM deduplicated
    GROUP BY character_id
)
SELECT
    countIf(entries > 0) AS characters_with_entries,
    sum(entries) AS logical_entries,
    countIf(entries > 1) AS returning_characters,
    sum(exits) AS logical_exits,
    sum(attachments) AS connection_attachments,
    sum(unallocated_entries) AS entries_without_occurrence_time
FROM characters
