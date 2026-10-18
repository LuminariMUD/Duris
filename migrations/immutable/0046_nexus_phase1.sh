#!/usr/bin/env bash
set -euo pipefail
: "${DB_HOST:?}" "${DB_USER:?}" "${DB_PASSWD:?}" "${DB_NAME:?}"
export MYSQL_PWD="$DB_PASSWD"
# Keep verification on the same trust boundary as migration_runner.MysqlExecutor.
# Production target confirmation/backup authorization belongs to the runner.
fail_connection() { echo "FAILED: Nexus catalogue verifier $1" >&2; exit 1; }
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

matching=$("${MYSQL[@]}" -e "SELECT COUNT(*) FROM nexus_stones
WHERE ((id=1 AND BINARY name=BINARY 'Marduk' AND room_vnum=130199 AND bonus=1)
    OR (id=3 AND BINARY name=BINARY 'Enlil' AND room_vnum=130399 AND bonus=3))
  AND stat_affect=0 AND affect_amount=0 AND align BETWEEN -3 AND 3;")
[[ "$matching" == 2 ]] || { echo 'FAILED: Nexus IDs 1/3 must match the Phase 1 catalogue and valid alignment' >&2; exit 1; }
conflicts=$("${MYSQL[@]}" -e "SELECT COUNT(*) FROM nexus_stones
WHERE (name='Marduk' AND id<>1) OR (name='Enlil' AND id<>3);")
[[ "$conflicts" == 0 ]] || { echo 'FAILED: Nexus names Marduk/Enlil have conflicting IDs' >&2; exit 1; }
echo 'Marduk and Enlil catalogue verified; existing ownership/timestamps preserved'
