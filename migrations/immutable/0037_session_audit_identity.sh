#!/usr/bin/env bash
set -euo pipefail
: "${DB_HOST:?}" "${DB_USER:?}" "${DB_PASSWD:?}" "${DB_NAME:?}"
export MYSQL_PWD="$DB_PASSWD"
MYSQL=(mysql -h "$DB_HOST" -P "${DB_PORT:-3306}" -u "$DB_USER" -N -B "$DB_NAME")
columns=$("${MYSQL[@]}" -e "SELECT COUNT(*) FROM information_schema.columns
WHERE table_schema=DATABASE() AND table_name='session_audit_outcome' AND is_nullable='YES'
AND (column_default IS NULL OR column_default='NULL') AND (
  (column_name='account_name' AND data_type='varchar' AND character_maximum_length=50
    AND collation_name='utf8mb4_unicode_ci') OR
  (column_name='is_staff' AND data_type='tinyint' AND column_type LIKE '%unsigned%'));")
[[ "$columns" == 2 ]] || { echo 'FAILED: session audit identity snapshot columns' >&2; exit 1; }
printf 'Session audit identity snapshot columns verified\n'
