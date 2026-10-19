#!/usr/bin/env bash
set -euo pipefail
: "${DB_HOST:?}" "${DB_USER:?}" "${DB_PASSWD:?}" "${DB_NAME:?}"
export MYSQL_PWD="$DB_PASSWD"
if mysql --help 2>&1 | grep -- '--ssl-mode' >/dev/null; then MYSQL_SSL=(--ssl-mode=PREFERRED); else MYSQL_SSL=(--skip-ssl); fi
MYSQL=(mysql "${MYSQL_SSL[@]}" -h "$DB_HOST" -P "${DB_PORT:-3306}" -u "$DB_USER" -N -B "$DB_NAME")
shape=$("${MYSQL[@]}" -e "SELECT COUNT(*) FROM information_schema.columns AS c
WHERE c.table_schema=DATABASE() AND c.table_name='player_data'
  AND c.column_name='last_read_news_hash' AND c.column_type='varbinary(64)'
  AND c.character_maximum_length=64 AND c.character_octet_length=64
  AND c.is_nullable='NO' AND TRIM(BOTH '\'' FROM c.column_default)=''
  AND c.character_set_name IS NULL AND c.collation_name IS NULL AND c.extra=''
  AND c.ordinal_position=(SELECT p.ordinal_position+1 FROM information_schema.columns AS p
      WHERE p.table_schema=DATABASE() AND p.table_name='player_data'
        AND p.column_name='learned_flight_stops');")
[[ "$shape" == 1 ]] || { echo 'FAILED: player news acknowledgement column differs' >&2; exit 1; }
echo 'player news acknowledgement schema verified'
