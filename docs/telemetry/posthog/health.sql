-- Counters are cumulative per producer: select its latest snapshot, never sum heartbeats.
WITH deduplicated AS (
    SELECT
        properties.duris_event_id AS event_id,
        any(timestamp) AS captured_at,
        any(properties.producer_boot_id) AS producer_boot_id,
        any(properties.producer_process_id) AS producer_process_id,
        any(accurateCastOrNull(properties.sampled_monotonic_usec, 'Decimal(38, 0)')) AS sampled_at,
        any(properties.native_transport) AS native,
        any(properties.reducer) AS reducer,
        any(properties.http_delivery) AS delivery,
        any(properties.active_reason_mask) AS active_reason_mask
    FROM events
    WHERE timestamp >= now() - INTERVAL 31 DAY AND timestamp < now()
      AND event = 'duris_telemetry_health'
      AND properties.duris_schema_version = 1
      AND properties.duris_environment_id = '1'
      AND properties.duris_season_id = '1'
      AND coalesce(properties.duris_test_run, '') = ''
    GROUP BY event_id
), latest AS (
    SELECT
        producer_boot_id, producer_process_id,
        max(captured_at) AS as_of_utc,
        argMax(toString(native), sampled_at) AS native,
        argMax(toString(reducer), sampled_at) AS reducer,
        argMax(toString(delivery), sampled_at) AS delivery,
        argMax(active_reason_mask, sampled_at) AS active_reason_mask
    FROM deduplicated
    GROUP BY producer_boot_id, producer_process_id
)
SELECT
    producer_boot_id, producer_process_id, as_of_utc,
    dateDiff('second', as_of_utc, now()) AS snapshot_age_seconds,
    JSONExtractString(native, 'state') AS native_state,
    JSONExtractString(native, 'storage_check') AS native_storage_check,
    JSONExtractString(native, 'queue_depth') AS native_queue_depth,
    JSONExtractString(native, 'dropped_detail') AS dropped_detail,
    JSONExtractString(native, 'dropped_control') AS dropped_control,
    JSONExtractString(native, 'consumed_records') AS native_consumed,
    JSONExtractString(native, 'sequence_gap_count') AS sequence_gaps,
    JSONExtractString(native, 'unclosed_tail_count') AS unclosed_tails,
    active_reason_mask,
    JSONExtractString(reducer, 'reduction_refusals') AS reduction_refusals,
    JSONExtractString(reducer, 'output_suppressed') AS output_suppressed,
    JSONExtractString(reducer, 'output_expired') AS output_expired,
    JSONExtractString(reducer, 'ambiguous_events') AS ambiguous_events,
    toInt(JSONExtractRaw(reducer, 'output_events')) AS output_events,
    toInt(JSONExtractRaw(reducer, 'output_bytes')) AS output_bytes,
    toInt(JSONExtractRaw(delivery, 'state')) AS sender_state,
    toInt(JSONExtractRaw(delivery, 'http_status')) AS http_status,
    toInt(JSONExtractRaw(delivery, 'quota_error')) AS quota_error,
    JSONExtractString(delivery, 'reserved_events') AS producer_reserved_events,
    JSONExtractString(delivery, 'submitted_events') AS producer_submitted_events,
    JSONExtractString(delivery, 'storage_failures') AS journal_failures,
    JSONExtractString(delivery, 'clock_failures') AS clock_failures,
    JSONExtractString(delivery, 'cancellations') AS cancellations
FROM latest
ORDER BY as_of_utc DESC
LIMIT 500
