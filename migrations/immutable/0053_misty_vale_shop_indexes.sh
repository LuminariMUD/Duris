#!/usr/bin/env bash
set -euo pipefail
: "${DB_HOST:?}" "${DB_USER:?}" "${DB_PASSWD:?}" "${DB_NAME:?}"
export MYSQL_PWD="$DB_PASSWD"
# Keep verification on the same trust boundary as migration_runner.MysqlExecutor.
# Production target confirmation/backup authorization belongs to the runner.
fail_connection() { echo "FAILED: Misty Vale shop verifier $1" >&2; exit 1; }
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

# Read-only: absent shops are valid; every saved affected identity must use its new index.
conflicts=$("${MYSQL[@]}" -e "SELECT COUNT(*) FROM shopkeepers s
LEFT JOIN (SELECT 534 AS new_id,300036 AS mob_vnum,300056 AS room_vnum
    UNION ALL SELECT 535,400004,400000
    UNION ALL SELECT 536,402027,0
    UNION ALL SELECT 537,402028,0
    UNION ALL SELECT 538,402039,402113
    UNION ALL SELECT 539,402047,402136
    UNION ALL SELECT 540,402048,402137
    UNION ALL SELECT 541,101,36329
    UNION ALL SELECT 542,101,37718
    UNION ALL SELECT 543,101,97685
    UNION ALL SELECT 544,101,132767
    UNION ALL SELECT 545,91401,91401
    UNION ALL SELECT 546,91406,91469
    UNION ALL SELECT 547,91414,91476
    UNION ALL SELECT 548,91415,91460
    UNION ALL SELECT 549,91419,91471
    UNION ALL SELECT 550,91426,91457
    UNION ALL SELECT 551,91456,91468
    UNION ALL SELECT 552,91483,91505) m
  ON s.mob_vnum=m.mob_vnum AND (m.room_vnum=0 OR s.room_vnum=m.room_vnum)
WHERE (m.new_id IS NOT NULL AND
       (s.shop_id<>m.new_id OR COALESCE(s.room_vnum,0)<=0))
   OR (m.new_id IS NULL AND s.shop_id BETWEEN 534 AND 552);")
[[ "$conflicts" == 0 ]] || { echo 'FAILED: Misty Vale shop indexes conflict with the new catalogue' >&2; exit 1; }
echo 'Misty Vale shop indexes verified'
