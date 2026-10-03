#!/usr/bin/env bash
set -euo pipefail
: "${DB_HOST:?}" "${DB_USER:?}" "${DB_PASSWD:?}" "${DB_NAME:?}"
export MYSQL_PWD="$DB_PASSWD"
if mysql --help 2>&1 | grep -- '--ssl-mode' >/dev/null; then MYSQL_SSL=(--ssl-mode=PREFERRED); else MYSQL_SSL=(--skip-ssl); fi
MYSQL=(mysql "${MYSQL_SSL[@]}" -h "$DB_HOST" -P "${DB_PORT:-3306}" -u "$DB_USER" -N -B "$DB_NAME")
scalar() { "${MYSQL[@]}" -e "$1"; }

column=$(scalar "SELECT COUNT(*) FROM information_schema.columns
WHERE table_schema=DATABASE()
  AND table_name='log_entries'
  AND column_name='ip_address'
  AND data_type='varchar'
  AND character_maximum_length=45
  AND is_nullable='NO'
  AND column_default IN ('', '''''');")
[[ "$column" == 1 ]] || {
    echo "FAILED: log_entries.ip_address must be VARCHAR(45) NOT NULL DEFAULT ''" >&2
    exit 1
}

printf 'log_entries.ip_address holds an IPv6 address\n'
