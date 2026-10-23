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
shape=$("${MYSQL[@]}" -e "SELECT COUNT(*) FROM information_schema.tables
WHERE table_schema=DATABASE() AND table_name='divine_boon_state'
AND engine='InnoDB' AND table_collation='utf8mb4_unicode_ci';")
[[ "$shape" == 1 ]] || { echo 'FAILED: Divine Boon table engine/collation differs' >&2; exit 1; }
columns=$("${MYSQL[@]}" -e "SELECT GROUP_CONCAT(CONCAT(column_name,':',data_type,':',is_nullable,':',COALESCE(character_maximum_length,0),':',IF(column_type LIKE '%unsigned',1,0)) ORDER BY ordinal_position SEPARATOR ',') FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='divine_boon_state';")
[[ "$columns" == 'state_id:tinyint:NO:0:1,revision:bigint:NO:0:1,snapshot:varbinary:NO:4096:0' ]] || { echo 'FAILED: Divine Boon columns differ' >&2; exit 1; }
primary=$("${MYSQL[@]}" -e "SELECT GROUP_CONCAT(column_name ORDER BY seq_in_index) FROM information_schema.statistics WHERE table_schema=DATABASE() AND table_name='divine_boon_state' AND index_name='PRIMARY';")
[[ "$primary" == state_id ]] || { echo 'FAILED: Divine Boon primary key differs' >&2; exit 1; }
checks=$("${MYSQL[@]}" -e "SELECT COUNT(*) FROM information_schema.check_constraints WHERE constraint_schema=DATABASE() AND ((constraint_name='divine_boon_singleton' AND REPLACE(REPLACE(REPLACE(REPLACE(LOWER(check_clause),CHAR(96),''),'(',''),')',''),' ','')='state_id=1') OR (constraint_name='divine_boon_revision' AND REPLACE(REPLACE(REPLACE(REPLACE(LOWER(check_clause),CHAR(96),''),'(',''),')',''),' ','')='revision>0'));")
[[ "$checks" == 2 ]] || { echo 'FAILED: Divine Boon CHECK expressions differ' >&2; exit 1; }
version=$("${MYSQL[@]}" -e 'SELECT VERSION();')
if [[ "$version" != *MariaDB* ]]; then
    enforced=$("${MYSQL[@]}" -e "SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema=DATABASE() AND table_name='divine_boon_state' AND constraint_type='CHECK' AND enforced='YES';")
    [[ "$enforced" == 2 ]] || { echo 'FAILED: Divine Boon CHECK enforcement differs' >&2; exit 1; }
fi
echo 'Divine Boon state schema verified'
