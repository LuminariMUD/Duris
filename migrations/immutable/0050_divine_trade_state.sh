#!/usr/bin/env bash
set -euo pipefail
: "${DB_HOST:?}" "${DB_USER:?}" "${DB_PASSWD:?}" "${DB_NAME:?}"
export MYSQL_PWD="$DB_PASSWD"
# Keep verification on the same trust boundary as migration_runner.MysqlExecutor.
# Production target confirmation/backup authorization belongs to the runner.
fail_connection() { echo "FAILED: Divine trade verifier $1" >&2; exit 1; }
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
shape=$("${MYSQL[@]}" -e "SELECT COUNT(*) FROM information_schema.tables
WHERE table_schema=DATABASE() AND table_name='divine_trade_state'
AND engine='InnoDB' AND table_collation='utf8mb4_unicode_ci';")
[[ "$shape" == 1 ]] || { echo 'FAILED: Divine trade table engine/collation differs' >&2; exit 1; }
columns=$("${MYSQL[@]}" -e "SELECT GROUP_CONCAT(CONCAT(column_name,':',data_type,':',is_nullable,':',IF(column_type LIKE '%unsigned',1,0)) ORDER BY ordinal_position SEPARATOR ',') FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='divine_trade_state';")
[[ "$columns" == 'account_key:bigint:NO:1,boon_id:bigint:NO:1,revision:bigint:NO:1,snapshot:mediumblob:NO:0' ]] || { echo 'FAILED: Divine trade columns differ' >&2; exit 1; }
primary=$("${MYSQL[@]}" -e "SELECT GROUP_CONCAT(column_name ORDER BY seq_in_index) FROM information_schema.statistics WHERE table_schema=DATABASE() AND table_name='divine_trade_state' AND index_name='PRIMARY';")
[[ "$primary" == account_key,boon_id ]] || { echo 'FAILED: Divine trade primary key differs' >&2; exit 1; }
global=$("${MYSQL[@]}" -e "SELECT COUNT(*) FROM divine_trade_state WHERE account_key=0 AND boon_id=0 AND OCTET_LENGTH(snapshot)=0;")
[[ "$global" == 1 ]] || { echo 'FAILED: Divine trade market generation is missing or malformed' >&2; exit 1; }
echo 'Divine trade state schema verified'
