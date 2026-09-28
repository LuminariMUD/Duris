#!/usr/bin/env bash
set -euo pipefail
: "${DB_HOST:?}" "${DB_USER:?}" "${DB_PASSWD:?}" "${DB_NAME:?}"
export MYSQL_PWD="$DB_PASSWD"
if mysql --help 2>&1 | grep -- '--ssl-mode' >/dev/null; then MYSQL_SSL=(--ssl-mode=PREFERRED); else MYSQL_SSL=(--skip-ssl); fi
MYSQL=(mysql "${MYSQL_SSL[@]}" -h "$DB_HOST" -P "${DB_PORT:-3306}" -u "$DB_USER" -N -B "$DB_NAME")
scalar() { "${MYSQL[@]}" -e "$1"; }

shape=$(scalar "SELECT CONCAT(engine,':',table_collation) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='item_owner_audit' AND table_type='BASE TABLE';")
[[ "$shape" == "InnoDB:utf8mb4_unicode_ci" ]] || {
    echo "FAILED: item_owner_audit engine/collation differs: $shape" >&2
    exit 1
}

columns=$(scalar "SELECT GROUP_CONCAT(CONCAT(column_name,' ',column_type,' ',is_nullable) ORDER BY ordinal_position SEPARATOR ',') FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='item_owner_audit';")
expected="audit_id bigint(20) unsigned NO,item_uid bigint(20) unsigned NO,vnum int(11) NO,old_owner_type tinyint(3) unsigned NO,old_owner_id bigint(20) unsigned NO,old_owner_context_id bigint(20) unsigned NO,new_owner_type tinyint(3) unsigned NO,new_owner_id bigint(20) unsigned NO,new_owner_context_id bigint(20) unsigned NO,claimed_at timestamp(6) NO"
# MySQL 8 omits integer display widths.
normalized=$(sed -E 's/(int|bigint|tinyint)\([0-9]+\)/\1/g' <<<"$columns")
[[ "$normalized" == "$(sed -E 's/(int|bigint|tinyint)\([0-9]+\)/\1/g' <<<"$expected")" ]] || {
    echo "FAILED: item_owner_audit columns differ: $columns" >&2
    exit 1
}

increment=$(scalar "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='item_owner_audit' AND column_name='audit_id' AND LOWER(extra) LIKE '%auto_increment%';")
[[ "$increment" == 1 ]] || { echo "FAILED: item_owner_audit.audit_id is not AUTO_INCREMENT" >&2; exit 1; }

indexes=$(scalar "SELECT GROUP_CONCAT(CONCAT(index_name,':',non_unique,':',column_name) ORDER BY index_name,seq_in_index SEPARATOR ',') FROM information_schema.statistics WHERE table_schema=DATABASE() AND table_name='item_owner_audit';")
[[ "$indexes" == "idx_item_owner_audit_claimed:1:claimed_at,idx_item_owner_audit_item:1:item_uid,idx_item_owner_audit_item:1:audit_id,PRIMARY:0:audit_id" ]] || {
    echo "FAILED: item_owner_audit indexes differ: $indexes" >&2
    exit 1
}

foreign=$(scalar "SELECT COUNT(*) FROM information_schema.key_column_usage WHERE table_schema=DATABASE() AND table_name='item_owner_audit' AND referenced_table_name IS NOT NULL;")
[[ "$foreign" == 0 ]] || { echo "FAILED: item_owner_audit must not have foreign keys" >&2; exit 1; }

printf 'item owner audit migration verified: columns, indexes and the absence of foreign keys are exact\n'
