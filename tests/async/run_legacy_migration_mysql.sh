#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NAME="duris-legacy-migration-$RANDOM-$$"
PASSWORD="duris-legacy-test-$RANDOM-$$"
DB_IMAGE="${LEGACY_DB_IMAGE:-mysql:8.0}"
MIGRATED_DB="duris_legacy_migration_test"
BOOTSTRAP_DB="duris_fresh_bootstrap_test"
CONFIG=$(mktemp)

cleanup() {
    docker rm -fv "$NAME" >/dev/null 2>&1 || true
    rm -f "$CONFIG"
}
trap cleanup EXIT HUP INT TERM

chmod 600 "$CONFIG"
if mysql --help 2>&1 | grep -q -- '--ssl-mode'; then
    MYSQL_SSL=(--ssl-mode=PREFERRED)
else
    MYSQL_SSL=(--skip-ssl)
fi
docker run -d --name "$NAME" -p 127.0.0.1::3306 \
    -e MYSQL_ROOT_PASSWORD="$PASSWORD" "$DB_IMAGE" >/dev/null
mapping=$(docker port "$NAME" 3306/tcp)
DB_PORT=${mapping##*:}

ready=0
for _ in $(seq 1 90); do
    if MYSQL_PWD="$PASSWORD" mysql "${MYSQL_SSL[@]}" -h127.0.0.1 -P"$DB_PORT" \
        -uroot -N -B -e 'SELECT 1' >/dev/null 2>&1; then
        ready=1
        break
    fi
    sleep 1
done
if [[ "$ready" != 1 ]]; then
    echo "isolated legacy-migration database did not become reachable" >&2
    docker logs "$NAME" >&2 || true
    exit 1
fi

MYSQL=(mysql "${MYSQL_SSL[@]}" -h127.0.0.1 -P"$DB_PORT" -uroot)
MYSQL_PWD="$PASSWORD" "${MYSQL[@]}" -e "
CREATE DATABASE $MIGRATED_DB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE $BOOTSTRAP_DB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
MYSQL_PWD="$PASSWORD" "${MYSQL[@]}" "$MIGRATED_DB" \
    < "$ROOT/migrations/bootstrap_legacy_baseline.sql"
# A legacy table already on utf8mb4 retains TEXT during charset convergence.
# Keep historical rows to prove the immutable widening preserves their contents.
MYSQL_PWD="$PASSWORD" "${MYSQL[@]}" "$MIGRATED_DB" -e "
ALTER TABLE pkill_info CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE pkill_info MODIFY COLUMN log TEXT NULL;
INSERT INTO pkill_info(pid,pk_type,equip,log) VALUES
    (4294000200,'legacy','',NULL),
    (4294000200,'legacy','',REPEAT('x',65535));"
MYSQL_PWD="$PASSWORD" "${MYSQL[@]}" "$MIGRATED_DB" -e "
CREATE TABLE imported_extension_probe (
    id INT NOT NULL PRIMARY KEY,
    note VARCHAR(32) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT INTO imported_extension_probe VALUES (1, 'preserved');
CREATE TABLE server_reboots (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    boot_time INT NOT NULL,
    shutdown_time INT DEFAULT NULL,
    uptime_seconds INT DEFAULT NULL,
    shutdown_type VARCHAR(50) NOT NULL DEFAULT 'unknown',
    initiated_by VARCHAR(255) DEFAULT NULL,
    reason TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_boot_time (boot_time),
    KEY idx_shutdown_time (shutdown_time),
    KEY idx_shutdown_type (shutdown_type),
    KEY idx_uptime (uptime_seconds)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT INTO server_reboots
    (id,boot_time,shutdown_time,uptime_seconds,shutdown_type,initiated_by,reason)
VALUES
    (41,100,175,75,'reboot','operator','legacy row'),
    (42,200,NULL,NULL,'web_stop','operator','unfinished legacy row');"
MYSQL_PWD="$PASSWORD" "${MYSQL[@]}" "$BOOTSTRAP_DB" \
    < "$ROOT/migrations/bootstrap_multithread_safe.sql"
MYSQL_PWD="$PASSWORD" "${MYSQL[@]}" "$BOOTSTRAP_DB" -e "
SET FOREIGN_KEY_CHECKS=0;
INSERT INTO player_item_extra_descr (id,item_id,keyword,description) VALUES
    (9001,9001,'legacy-keyword','duplicate legacy metadata'),
    (9002,9001,'legacy-keyword','duplicate legacy metadata');
SET FOREIGN_KEY_CHECKS=1;"
MYSQL_PWD="$PASSWORD" "${MYSQL[@]}" "$BOOTSTRAP_DB" \
    < "$ROOT/migrations/legacy_schema_convergence.sql"

printf '%s\n' \
    'ENVIRONMENT=test' \
    'DB_HOST=127.0.0.1' \
    "DB_PORT=$DB_PORT" \
    'DB_USER=root' \
    "DB_PASSWD=$PASSWORD" \
    "DB_NAME=$MIGRATED_DB" \
    "DB_ALLOWED_TARGETS=127.0.0.1/$MIGRATED_DB" \
    'REDIS=FALSE' > "$CONFIG"

MIGRATION_ENV_FILE="$CONFIG" "$ROOT/migrations/run_migration.sh"
legacy_log_type=$(MYSQL_PWD="$PASSWORD" "${MYSQL[@]}" -N -B "$MIGRATED_DB" -e \
    "SELECT data_type FROM information_schema.columns WHERE table_schema=DATABASE()
     AND table_name='pkill_info' AND column_name='log';")
[[ "$legacy_log_type" == text ]]
# An unexpected wider type is preserved but cannot publish a successful head
# that the canonical runtime fingerprint would subsequently reject.
MYSQL_PWD="$PASSWORD" "${MYSQL[@]}" "$MIGRATED_DB" -e \
    'ALTER TABLE pkill_info MODIFY COLUMN log LONGTEXT NULL;'
if ENVIRONMENT=test DB_HOST=127.0.0.1 DB_PORT="$DB_PORT" DB_USER=root \
    DB_PASSWD="$PASSWORD" DB_NAME="$MIGRATED_DB" \
    python3 "$ROOT/scripts/migration_runner.py" run; then
    echo 'migration runner certified noncanonical LONGTEXT' >&2
    exit 1
fi
refused_head=$(MYSQL_PWD="$PASSWORD" "${MYSQL[@]}" -N -B "$MIGRATED_DB" -e \
    "SELECT CONCAT((SELECT applied_count FROM mud_schema_migration_state WHERE state_id=1),':',
     (SELECT COUNT(*) FROM mud_schema_history WHERE sequence_number=41),':',
     (SELECT data_type FROM information_schema.columns WHERE table_schema=DATABASE()
      AND table_name='pkill_info' AND column_name='log'));")
[[ "$refused_head" == '40:0:longtext' ]]
# Restore the supported legacy fixture and retry the still-pending migration.
MYSQL_PWD="$PASSWORD" "${MYSQL[@]}" "$MIGRATED_DB" -e \
    'ALTER TABLE pkill_info MODIFY COLUMN log TEXT NULL;'
ENVIRONMENT=test DB_HOST=127.0.0.1 DB_PORT="$DB_PORT" DB_USER=root \
    DB_PASSWD="$PASSWORD" DB_NAME="$MIGRATED_DB" \
    python3 "$ROOT/scripts/migration_runner.py" run

log_state=$(MYSQL_PWD="$PASSWORD" "${MYSQL[@]}" -N -B "$MIGRATED_DB" -e \
    "SELECT CONCAT(COUNT(*),':',SUM(log IS NULL),':',SUM(log=REPEAT('x',65535)))
     FROM pkill_info WHERE pid=4294000200;")
[[ "$log_state" == '2:1:1' ]]
MYSQL_PWD="$PASSWORD" "${MYSQL[@]}" "$MIGRATED_DB" -e "
SET SESSION sql_mode='STRICT_ALL_TABLES';
INSERT INTO pkill_info(pid,pk_type,equip,log) VALUES
    (4294000200,'legacy','',REPEAT('x',65536)),
    (4294000200,'legacy','',REPEAT('x',99999));"
# Exercise history replay as well as the SQL-level reruns in the combat harness.
ENVIRONMENT=test DB_HOST=127.0.0.1 DB_PORT="$DB_PORT" DB_USER=root \
    DB_PASSWD="$PASSWORD" DB_NAME="$MIGRATED_DB" \
    python3 "$ROOT/scripts/migration_runner.py" run
log_lengths=$(MYSQL_PWD="$PASSWORD" "${MYSQL[@]}" -N -B "$MIGRATED_DB" -e \
    "SELECT GROUP_CONCAT(OCTET_LENGTH(log) ORDER BY id) FROM pkill_info WHERE pid=4294000200;")
[[ "$log_lengths" == '65535,65536,99999' ]]

extension_state=$(MYSQL_PWD="$PASSWORD" "${MYSQL[@]}" -N -B "$MIGRATED_DB" -e \
    "SELECT CONCAT(COUNT(*), ':', MIN(note)) FROM imported_extension_probe;")
[[ "$extension_state" == "1:preserved" ]]
reboot_state=$(MYSQL_PWD="$PASSWORD" "${MYSQL[@]}" -N -B "$MIGRATED_DB" -e \
    "SELECT CONCAT(COUNT(*), ':', MIN(record_id), ':', MIN(boot_time), ':', SUM(record_id=42 AND shutdown_time=200 AND uptime_seconds=0 AND shutdown_type='unknown')) FROM server_reboots;")
[[ "$reboot_state" == "2:41:100:1" ]]
archive_state=$(MYSQL_PWD="$PASSWORD" "${MYSQL[@]}" -N -B "$MIGRATED_DB" -e \
    "SELECT CONCAT(COUNT(*), ':', MIN(source_id), ':', SUM(source_id=42 AND shutdown_time IS NULL AND uptime_seconds IS NULL AND shutdown_type='web_stop')) FROM legacy_import_server_reboots;")
[[ "$archive_state" == "2:41:1" ]]

ENVIRONMENT=test DB_HOST=127.0.0.1 DB_PORT="$DB_PORT" DB_USER=root \
    DB_PASSWD="$PASSWORD" DB_NAME="$BOOTSTRAP_DB" \
    python3 "$ROOT/scripts/migration_runner.py" adopt --kind fresh_bootstrap
ENVIRONMENT=test DB_HOST=127.0.0.1 DB_PORT="$DB_PORT" DB_USER=root \
    DB_PASSWD="$PASSWORD" DB_NAME="$BOOTSTRAP_DB" \
    python3 "$ROOT/scripts/migration_runner.py" run
metadata_state=$(MYSQL_PWD="$PASSWORD" "${MYSQL[@]}" -N -B "$BOOTSTRAP_DB" -e \
    "SELECT CONCAT((SELECT COUNT(*) FROM player_item_extra_descr WHERE item_id=9001), ':', (SELECT COUNT(*) FROM legacy_import_player_item_extra_descr WHERE item_id=9001));")
[[ "$metadata_state" == "1:2" ]]
MYSQL_PWD="$PASSWORD" "${MYSQL[@]}" "$BOOTSTRAP_DB" -e \
    "DROP TABLE legacy_import_player_item_extra_descr;"

MYSQL_PWD="$PASSWORD" MYSQL_HOST=127.0.0.1 MYSQL_PORT="$DB_PORT" MYSQL_USER=root \
    MIGRATION_TEST_DB="$MIGRATED_DB" MIGRATION_SCRIPT="$ROOT/migrations/run_migration.sh" \
    MIGRATION_ENV_FILE="$CONFIG" sh "$ROOT/tests/test_migration_replay_safety.sh"
MYSQL_PWD="$PASSWORD" MYSQL_HOST=127.0.0.1 MYSQL_PORT="$DB_PORT" MYSQL_USER=root \
    MIGRATION_TEST_DB="$MIGRATED_DB" sh "$ROOT/tests/test_run_migration_persistence_schema.sh"
MYSQL_PWD="$PASSWORD" MYSQL_HOST=127.0.0.1 MYSQL_PORT="$DB_PORT" MYSQL_USER=root \
    MIGRATED_DB="$MIGRATED_DB" BOOTSTRAP_DB="$BOOTSTRAP_DB" \
    sh "$ROOT/tests/compare_bootstrap_mud_schema.sh"
ENVIRONMENT=test DB_HOST=127.0.0.1 DB_PORT="$DB_PORT" DB_USER=root \
    DB_PASSWD="$PASSWORD" DB_NAME="$MIGRATED_DB" \
    "$ROOT/migrations/verify_runtime_compatibility.sh"

echo 'legacy migration, replay, bootstrap equivalence, and runtime compatibility: ok'
