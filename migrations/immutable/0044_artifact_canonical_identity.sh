#!/usr/bin/env bash
set -euo pipefail
: "${DB_HOST:?}" "${DB_USER:?}" "${DB_PASSWD:?}" "${DB_NAME:?}"
export MYSQL_PWD="$DB_PASSWD"
# Keep verification on the same trust boundary as migration_runner.MysqlExecutor.
# Production target confirmation/backup authorization belongs to the runner.
fail_connection() { echo "FAILED: artifact identity verifier $1" >&2; exit 1; }
environment="${ENVIRONMENT:-}"
environment="${environment,,}"
local_host=0
case "$DB_HOST" in 127.0.0.1|localhost|::1) local_host=1 ;; esac
if [[ "$environment" != production ]]; then
    case "$environment" in local|development|dev|test) ;; *) fail_connection "requires an explicit migration environment" ;; esac
    [[ "$local_host" == 1 ]] || fail_connection "non-production target must be loopback"
    [[ ! "${DB_NAME,,}" =~ (^|[_-])prod(uction)?($|[_-]) ]] || fail_connection "non-production target cannot name a production database"
fi
if [[ -n "${DB_SOCKET:-}" ]]; then
    [[ "$environment" != production && "$local_host" == 1 ]] || fail_connection "socket requires a local non-production target"
    [[ "$DB_SOCKET" == /* ]] || fail_connection "DB_SOCKET must be an absolute path"
    MYSQL_CONNECTION=(--protocol=socket "--socket=$DB_SOCKET")
else
    MYSQL_CONNECTION=(--protocol=tcp -h "$DB_HOST" -P "${DB_PORT:-3306}")
    if [[ "$local_host" != 1 ]]; then
        [[ "${DB_TLS:-}" == TRUE && -f "${DB_SSL_CA:-}" ]] || fail_connection "remote target requires TLS and a regular CA file"
        mysql_help=$(mysql --help) || fail_connection "cannot inspect database client TLS capabilities"
        [[ "$mysql_help" == *--ssl-ca* ]] || fail_connection "database client cannot configure a remote CA file"
        if [[ "$mysql_help" == *--ssl-mode* ]]; then
            MYSQL_CONNECTION+=(--ssl-mode=VERIFY_IDENTITY "--ssl-ca=$DB_SSL_CA")
        elif [[ "$mysql_help" == *--ssl-verify-server-cert* ]]; then
            MYSQL_CONNECTION+=("--ssl-ca=$DB_SSL_CA" --ssl-verify-server-cert)
        else
            fail_connection "database client cannot verify remote server identity"
        fi
    fi
fi
MYSQL=(mysql "${MYSQL_CONNECTION[@]}" -u "$DB_USER" -N -B "$DB_NAME")
uid_shape=$("${MYSQL[@]}" -e "SELECT COUNT(*) FROM information_schema.columns c
WHERE c.table_schema=DATABASE() AND c.table_name='artifact_domain_state'
  AND c.column_name='canonical_item_uid' AND c.data_type='bigint'
  AND c.column_type LIKE '%unsigned%' AND c.is_nullable='YES'
  AND (c.column_default IS NULL OR UPPER(c.column_default)='NULL') AND c.extra=''
  AND c.ordinal_position=(SELECT p.ordinal_position+1 FROM information_schema.columns p
    WHERE p.table_schema=DATABASE() AND p.table_name='artifact_domain_state' AND p.column_name='updated_at');")
state_shape=$("${MYSQL[@]}" -e "SELECT COUNT(*) FROM information_schema.columns c
WHERE c.table_schema=DATABASE() AND c.table_name='artifact_domain_state'
  AND c.column_name='identity_state' AND c.data_type='tinyint'
  AND c.column_type LIKE '%unsigned%' AND c.is_nullable='NO'
  AND TRIM(BOTH '\'' FROM c.column_default)='0' AND c.extra=''
  AND c.ordinal_position=(SELECT p.ordinal_position+1 FROM information_schema.columns p
    WHERE p.table_schema=DATABASE() AND p.table_name='artifact_domain_state' AND p.column_name='canonical_item_uid');")
index_shape=$("${MYSQL[@]}" -e "SELECT COUNT(*) FROM information_schema.statistics
WHERE table_schema=DATABASE() AND table_name='artifact_domain_state'
  AND index_name='uq_artifact_canonical_uid' AND non_unique=0 AND seq_in_index=1
  AND column_name='canonical_item_uid' AND sub_part IS NULL;")
index_width=$("${MYSQL[@]}" -e "SELECT COUNT(*) FROM information_schema.statistics
WHERE table_schema=DATABASE() AND table_name='artifact_domain_state'
  AND index_name='uq_artifact_canonical_uid';")
custody_fk=$("${MYSQL[@]}" -e "SELECT COUNT(*) FROM information_schema.key_column_usage k
JOIN information_schema.referential_constraints r ON r.constraint_schema=k.constraint_schema AND r.constraint_name=k.constraint_name
WHERE k.constraint_schema=DATABASE() AND k.table_name='artifact_domain_state'
  AND k.constraint_name='artifact_domain_item_fk' AND k.column_name='item_uid'
  AND k.referenced_table_name='item_current_owner' AND k.referenced_column_name='item_uid'
  AND r.update_rule='RESTRICT' AND r.delete_rule='RESTRICT';")
canonical_fk=$("${MYSQL[@]}" -e "SELECT COUNT(*) FROM information_schema.key_column_usage
WHERE constraint_schema=DATABASE() AND table_name='artifact_domain_state'
  AND column_name='canonical_item_uid' AND referenced_table_name IS NOT NULL;")
[[ "$uid_shape" == 1 && "$state_shape" == 1 && "$index_shape" == 1 && "$index_width" == 1 && "$custody_fk" == 1 && "$canonical_fk" == 0 ]] ||
  { echo 'FAILED: artifact canonical identity schema differs' >&2; exit 1; }
invalid=$("${MYSQL[@]}" -e "SELECT COUNT(*) FROM artifact_domain_state
WHERE NOT ((identity_state IN (0,3) AND canonical_item_uid IS NULL)
        OR (identity_state IN (1,2) AND canonical_item_uid IS NOT NULL AND canonical_item_uid>0));")
[[ "$invalid" == 0 ]] || { echo 'FAILED: inconsistent artifact identity evidence' >&2; exit 1; }
echo 'artifact canonical identity storage verified'
