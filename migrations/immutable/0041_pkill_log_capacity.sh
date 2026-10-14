#!/usr/bin/env bash
set -euo pipefail
: "${DB_HOST:?}" "${DB_USER:?}" "${DB_PASSWD:?}" "${DB_NAME:?}"
export MYSQL_PWD="$DB_PASSWD"
if mysql --help 2>&1 | grep -- '--ssl-mode' >/dev/null; then MYSQL_SSL=(--ssl-mode=PREFERRED); else MYSQL_SSL=(--skip-ssl); fi
MYSQL=(mysql "${MYSQL_SSL[@]}" -h "$DB_HOST" -P "${DB_PORT:-3306}" -u "$DB_USER" -N -B "$DB_NAME")
columns=$("${MYSQL[@]}" -e "SELECT COUNT(*) FROM information_schema.columns
WHERE table_schema=DATABASE() AND table_name='pkill_info'
  AND column_name='log' AND data_type IN ('mediumtext', 'longtext')
  AND character_octet_length>=99999;")
[[ "$columns" == 1 ]] || {
    echo "FAILED: pkill_info.log must hold 99,999-byte public combat logs" >&2
    exit 1
}
printf 'pkill_info.log holds the maximum public combat snapshot\n'
