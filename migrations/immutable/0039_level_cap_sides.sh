#!/usr/bin/env bash
set -euo pipefail
: "${DB_HOST:?}" "${DB_USER:?}" "${DB_PASSWD:?}" "${DB_NAME:?}"
export MYSQL_PWD="$DB_PASSWD"
if mysql --help 2>&1 | grep -- '--ssl-mode' >/dev/null; then MYSQL_SSL=(--ssl-mode=PREFERRED); else MYSQL_SSL=(--skip-ssl); fi
MYSQL=(mysql "${MYSQL_SSL[@]}" -h "$DB_HOST" -P "${DB_PORT:-3306}" -u "$DB_USER" -N -B "$DB_NAME")
scalar() { "${MYSQL[@]}" -e "$1"; }

columns=$(scalar "SELECT COUNT(*) FROM information_schema.columns
WHERE table_schema=DATABASE()
  AND table_name='level_cap'
  AND column_name IN ('level_good', 'level_evil')
  AND data_type='int'
  AND is_nullable='NO'
  AND column_default IN ('0', '''0''');")
[[ "$columns" == 2 ]] || {
    echo "FAILED: level_cap.level_good and level_evil must be INT NOT NULL DEFAULT 0" >&2
    exit 1
}
levels=$(scalar "SELECT COUNT(*) FROM level_cap
WHERE level_good BETWEEN 0 AND 56 AND level_evil BETWEEN 0 AND 56;")
rows=$(scalar "SELECT COUNT(*) FROM level_cap;")
[[ "$levels" == "$rows" ]] || {
    echo "FAILED: a level_cap side level is outside 0-56" >&2
    exit 1
}

printf 'level_cap holds a level for each side\n'
