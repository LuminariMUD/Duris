#!/usr/bin/env bash
set -euo pipefail
: "${DB_HOST:?}" "${DB_USER:?}" "${DB_PASSWD:?}" "${DB_NAME:?}"
export MYSQL_PWD="$DB_PASSWD"
if mysql --help 2>&1 | grep -- '--ssl-mode' >/dev/null; then MYSQL_SSL=(--ssl-mode=PREFERRED); else MYSQL_SSL=(--skip-ssl); fi
MYSQL=(mysql "${MYSQL_SSL[@]}" -h "$DB_HOST" -P "${DB_PORT:-3306}" -u "$DB_USER" -N -B "$DB_NAME")
scalar() { "${MYSQL[@]}" -e "$1"; }

left=$(scalar "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND (table_name LIKE 'player\_death\_%' OR table_name LIKE 'economic\_%');")
[[ "$left" == 0 ]] || { echo "FAILED: $left death custody or accounting tables remain" >&2; exit 1; }

index=$(scalar "SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema=DATABASE() AND table_name='item_ownership_ledger' AND index_name='uq_item_ledger_accounting_reference';")
[[ "$index" == 0 ]] || { echo "FAILED: the accounting reference index remains on item_ownership_ledger" >&2; exit 1; }

printf 'death custody and accounting tables retired\n'
