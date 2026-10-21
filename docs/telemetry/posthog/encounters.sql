-- Run and actor rows stay separate. Window counts expose missing cloud actor rows.
WITH deduplicated AS (
    SELECT
        properties.duris_event_id AS event_id,
        any(timestamp) AS captured_at,
        any(properties.duris_run_id) AS run_id,
        any(properties.row_type) AS row_type,
        any(properties.actor_kind) AS actor_kind,
        any(properties.duris_actor_id) AS actor_id,
        any(properties.duris_owner_character_id) AS owner_character_id,
        any(toInt(properties.mode)) AS mode,
        any(toInt(properties.outcome)) AS outcome,
        any(properties.native_terminal_complete = true) AS native_complete,
        any(properties.timestamp_basis) AS timestamp_basis,
        any(toInt(properties.participant_rows_expected)) AS expected_participants,
        any(properties.run_elapsed_usec) AS run_usec,
        any(properties.participant_usec) AS participant_usec,
        any(properties.participant_time_basis) AS participant_time_basis,
        any(properties.unattributed_player_rows) AS unattributed_player_rows,
        any(properties.unattributed_pet_rows) AS unattributed_pet_rows,
        any(properties.unattributed_roster_usec) AS unattributed_roster_usec,
        any(properties.unattributed_player_combat) AS unattributed_player_combat,
        any(properties.unattributed_pet_combat) AS unattributed_pet_combat,
        any(properties.combat.damage_dealt) AS damage_dealt,
        any(properties.combat.damage_taken) AS damage_taken,
        any(properties.combat.effective_healing) AS effective_healing,
        any(properties.combat.casting_attempts) AS casting_attempts,
        any(properties.combat.casting_completions) AS casting_completions,
        any(properties.combat.casting_aborts) AS casting_aborts,
        any(properties.combat.tanking_usec) AS tanking_usec,
        any(properties.duris_coverage) AS coverage
    FROM events
    WHERE timestamp >= now() - INTERVAL 31 DAY AND timestamp < now()
      AND event = 'duris_encounter_summary'
      AND properties.duris_schema_version = 1
      AND properties.duris_environment_id = '1'
      AND properties.duris_season_id = '1'
      AND coalesce(properties.duris_test_run, '') = ''
    GROUP BY event_id
), observed AS (
    SELECT *,
        countIf(row_type = 'run') OVER (PARTITION BY run_id) AS run_rows,
        countIf(row_type = 'participant') OVER (PARTITION BY run_id) AS observed_actor_rows,
        max(if(row_type = 'run', toInt(expected_participants), NULL)) OVER (PARTITION BY run_id) AS expected_actor_rows
    FROM deduplicated
)
SELECT
    run_id, row_type, actor_kind, actor_id, owner_character_id,
    if(timestamp_basis = 'occurrence', toDate(captured_at), NULL) AS utc_day,
    multiIf(mode = 1, 'pve', mode = 2, 'pvp', mode = 3, 'mixed', 'unknown') AS encounter_mode,
    multiIf(outcome = 1, 'success', outcome = 2, 'failure', outcome = 3, 'death',
            outcome = 4, 'flee', outcome = 5, 'withdrawal', outcome = 6, 'abandonment',
            outcome = 7, 'timeout', outcome = 8, 'copyover', outcome = 9, 'shutdown', 'unknown') AS encounter_outcome,
    native_complete, run_rows, expected_actor_rows, observed_actor_rows,
    if(run_rows = 1 AND isNotNull(expected_actor_rows), observed_actor_rows = expected_actor_rows, NULL) AS cloud_actor_rows_complete,
    run_usec, participant_usec, participant_time_basis,
    unattributed_player_rows, unattributed_pet_rows, unattributed_roster_usec,
    toString(unattributed_player_combat) AS unattributed_player_combat,
    toString(unattributed_pet_combat) AS unattributed_pet_combat,
    damage_dealt, damage_taken, effective_healing,
    casting_attempts, casting_completions, casting_aborts, tanking_usec,
    toString(coverage) AS coverage,
    count() OVER () AS total_rows_before_limit
FROM observed
ORDER BY captured_at DESC, run_id, row_type, actor_kind, actor_id
LIMIT 500
