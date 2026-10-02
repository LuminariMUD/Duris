#!/usr/bin/env bash
set -euo pipefail
: "${DB_HOST:?}" "${DB_USER:?}" "${DB_PASSWD:?}" "${DB_NAME:?}"
export MYSQL_PWD="$DB_PASSWD"
if mysql --help 2>&1 | grep -- '--ssl-mode' >/dev/null; then MYSQL_SSL=(--ssl-mode=PREFERRED); else MYSQL_SSL=(--skip-ssl); fi
MYSQL=(mysql "${MYSQL_SSL[@]}" -h "$DB_HOST" -P "${DB_PORT:-3306}" -u "$DB_USER" -N -B "$DB_NAME")
scalar() { "${MYSQL[@]}" -e "$1"; }

missing=$(scalar "SELECT COUNT(*) FROM account_banks bank LEFT JOIN currency_bank_baseline baseline ON baseline.bank_id=bank.id WHERE baseline.bank_id IS NULL;")
[[ "$missing" == 0 ]] || { echo "FAILED: $missing account banks have no opening baseline" >&2; exit 1; }

printf 'every account bank has an opening baseline\n'
