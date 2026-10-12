#!/usr/bin/env bash
set -euo pipefail
: "${DB_HOST:?}" "${DB_USER:?}" "${DB_PASSWD:?}" "${DB_NAME:?}"
export MYSQL_PWD="$DB_PASSWD"
MYSQL=(mysql -h "$DB_HOST" -P "${DB_PORT:-3306}" -u "$DB_USER" -N -B "$DB_NAME")
columns=$("${MYSQL[@]}" -e "SELECT COUNT(*) FROM information_schema.columns
WHERE table_schema=DATABASE() AND table_name='player_data'
  AND column_name='learned_flight_stops' AND data_type='bigint'
  AND column_type LIKE '%unsigned%' AND is_nullable='NO' AND column_default='0';")
[[ "$columns" == 1 ]] || { echo 'FAILED: learned flight stops status column' >&2; exit 1; }
printf 'Learned flight stops status column verified\n'
