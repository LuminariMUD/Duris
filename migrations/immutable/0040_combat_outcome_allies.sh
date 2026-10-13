#!/usr/bin/env bash
set -euo pipefail
: "${DB_HOST:?}" "${DB_USER:?}" "${DB_PASSWD:?}" "${DB_NAME:?}"
export MYSQL_PWD="$DB_PASSWD"
if mysql --help 2>&1 | grep -- '--ssl-mode' >/dev/null; then MYSQL_SSL=(--ssl-mode=PREFERRED); else MYSQL_SSL=(--skip-ssl); fi
MYSQL=(mysql "${MYSQL_SSL[@]}" -h "$DB_HOST" -P "${DB_PORT:-3306}" -u "$DB_USER" -N -B "$DB_NAME")
columns=$("${MYSQL[@]}" -e "SELECT COUNT(*) FROM information_schema.columns
WHERE table_schema=DATABASE() AND table_name='combat_outcome'
  AND column_name='killer_allies' AND data_type='int'
  AND column_type LIKE '%unsigned' AND is_nullable='NO'
  AND column_default IN ('0', '''0''');")
[[ "$columns" == 1 ]] || {
    echo "FAILED: combat_outcome.killer_allies must be INT UNSIGNED NOT NULL DEFAULT 0" >&2
    exit 1
}
printf 'combat outcomes retain the killer-side ally count\n'
