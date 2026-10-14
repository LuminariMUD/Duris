#!/usr/bin/env bash
# Read-only persisted-state/history audit. Supply credentials explicitly; never
# source a checkout's .env. This does not observe the game thread or prove drain.
set -euo pipefail
: "${DB_HOST:?DB_HOST is required}" "${DB_USER:?DB_USER is required}"
: "${DB_PASSWD?DB_PASSWD must be set}" "${DB_NAME:?DB_NAME is required}"
export MYSQL_PWD="$DB_PASSWD"
if mysql --help 2>&1 | grep -- '--ssl-mode' >/dev/null; then MYSQL_SSL=(--ssl-mode=PREFERRED); else MYSQL_SSL=(--skip-ssl); fi
MYSQL=(mysql "${MYSQL_SSL[@]}" -h "$DB_HOST" -P "${DB_PORT:-3306}" -u "$DB_USER" -N -B "$DB_NAME")
results=$("${MYSQL[@]}" <<'SQL'
SET time_zone='+00:00';
SET SESSION TRANSACTION READ ONLY;
START TRANSACTION WITH CONSISTENT SNAPSHOT;
SELECT 'artifact_mirror_mismatches', COUNT(*)
FROM artifacts a LEFT JOIN artifact_domain_state s ON s.vnum=a.vnum
LEFT JOIN artifact_bind b ON b.vnum=a.vnum
WHERE s.vnum IS NULL OR NOT (s.owned <=> (a.owned='Y'))
 OR NOT (s.loc_type <=> a.locType) OR s.location<>COALESCE(a.location,0)
 OR s.timer_epoch<>COALESCE(UNIX_TIMESTAMP(a.timer),0)
 OR s.artifact_type<>COALESCE(a.type,0)
 OR s.bind_owner_pid<>COALESCE(b.owner_pid,0) OR s.bind_timer_epoch<>COALESCE(b.timer,0);
SELECT 'artifact_missing_legacy_rows', COUNT(*)
FROM artifact_domain_state s LEFT JOIN artifacts a ON a.vnum=s.vnum WHERE a.vnum IS NULL;
SELECT 'artifact_missing_item_owners', COUNT(*)
FROM artifact_domain_state s LEFT JOIN item_current_owner i ON i.item_uid=s.item_uid
WHERE s.item_uid IS NOT NULL AND i.item_uid IS NULL;
SELECT 'outcome_count_mismatches', COUNT(*)
FROM artifact_guild_outcome o LEFT JOIN
 (SELECT operation_id,COUNT(*) n FROM artifact_guild_outcome_delta GROUP BY operation_id) d
 ON d.operation_id=o.operation_id WHERE o.artifact_count<>COALESCE(d.n,0);
SELECT 'artifact_ledger_mismatches', COUNT(*)
FROM artifact_guild_outcome_delta d LEFT JOIN artifact_delta_ledger l
 ON l.operation_id=d.operation_id AND l.artifact_index=d.artifact_index
WHERE l.operation_id IS NULL OR l.vnum<>d.vnum OR l.timer_delta<>d.timer_after-d.timer_before
 OR l.bind_owner_pid<>d.bind_owner_after OR l.bind_timer_epoch<>d.bind_timer_after OR l.revision<>d.revision;
SELECT 'artifact_ledger_orphans', COUNT(*)
FROM artifact_delta_ledger l LEFT JOIN artifact_guild_outcome_delta d
 ON l.operation_id=d.operation_id AND l.artifact_index=d.artifact_index WHERE d.operation_id IS NULL;
SELECT 'artifact_delta_orphans', COUNT(*)
FROM artifact_guild_outcome_delta d LEFT JOIN artifact_guild_outcome o
 ON o.operation_id=d.operation_id WHERE o.operation_id IS NULL;
SELECT 'guild_ledger_mismatches', COUNT(*)
FROM artifact_guild_outcome o LEFT JOIN guild_outcome_ledger l ON l.operation_id=o.operation_id
WHERE (o.guild_id<>0 AND (l.operation_id IS NULL OR l.guild_id<>o.guild_id
 OR l.prestige_delta<>o.prestige_delta OR l.construction_delta<>o.construction_delta
 OR l.prestige_after<>o.guild_prestige_after OR l.construction_after<>o.guild_construction_after
 OR l.guild_revision<>o.guild_revision))
 OR (o.guild_id=0 AND (o.prestige_delta<>0 OR o.construction_delta<>0 OR l.operation_id IS NOT NULL));
SELECT 'guild_ledger_orphans', COUNT(*)
FROM guild_outcome_ledger l LEFT JOIN artifact_guild_outcome o
 ON o.operation_id=l.operation_id WHERE o.operation_id IS NULL;
SELECT 'outcome_receipt_mismatches', COUNT(*)
FROM artifact_guild_outcome o LEFT JOIN critical_operation_inbox c ON c.operation_id=o.operation_id
LEFT JOIN critical_operation_inbox p ON p.operation_id=o.parent_operation_id
WHERE c.operation_id IS NULL OR c.command_type<>9 OR c.status<>1 OR p.operation_id IS NULL OR p.status<>1;
SELECT 'duplicate_parent_actors', COUNT(*) FROM
 (SELECT parent_operation_id,actor_pid FROM artifact_guild_outcome GROUP BY parent_operation_id,actor_pid HAVING COUNT(*)>1) duplicates;
COMMIT;
SQL
)
status=0
while IFS=$'\t' read -r name count; do
    printf '%s=%s\n' "$name" "$count"
    [[ "$count" == 0 ]] || status=1
done <<< "$results"
printf '%s\n' 'scope=persisted_history_and_mirror live_unsaved_state=not_observed'
exit "$status"
