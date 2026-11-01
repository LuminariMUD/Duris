#!/usr/bin/env bash
set -euo pipefail
: "${DB_HOST:?}" "${DB_USER:?}" "${DB_PASSWD:?}" "${DB_NAME:?}"
export MYSQL_PWD="$DB_PASSWD"
# Keep verification on the same trust boundary as migration_runner.MysqlExecutor.
# Production target confirmation/backup authorization belongs to the runner.
fail_connection() { echo "FAILED: bartender reward count verifier $1" >&2; exit 1; }
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
columns=$("${MYSQL[@]}" -e "SELECT COUNT(*) FROM information_schema.columns
WHERE table_schema=DATABASE() AND table_name='player_data'
  AND column_name='quest_reward_item_count'
  AND data_type='int' AND column_type NOT LIKE '%unsigned%'
  AND is_nullable='NO' AND column_default='0' AND extra='';")
[[ "$columns" == 1 ]] || { echo 'FAILED: bartender reward count column differs' >&2; exit 1; }
echo 'Bartender reward count column verified'
