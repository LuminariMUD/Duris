#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT/tests/async/disposable_schema.sh"
mysql -h "$DB_HOST" -P "${DB_PORT:-3306}" -u "$DB_USER" "$DB_NAME" < "$ROOT/migrations/combat_outcome.sql"
mysql -h "$DB_HOST" -P "${DB_PORT:-3306}" -u "$DB_USER" "$DB_NAME" < "$ROOT/migrations/immutable/0040_combat_outcome_allies.sql"
"$ROOT/migrations/immutable/0040_combat_outcome_allies.sh"
"$ROOT/migrations/immutable/0041_pkill_log_capacity.sh"
"$ROOT/migrations/verify_combat_outcome_schema.sh"
# Upgrade historical rows without inventing consent, and replay without changing it.
PRIVACY_MYSQL=(mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -N -B "$DB_NAME")
"${PRIVACY_MYSQL[@]}" -e "ALTER TABLE pkill_info DROP COLUMN webinfo_at_capture;
INSERT INTO pkill_info(pid,pk_type,equip,log) VALUES(4294000201,'legacy','OLD_EQUIP','OLD_LOG');"
if "$ROOT/migrations/immutable/0045_pkill_webinfo_at_capture.sh"; then
    echo 'capture verifier accepted absent consent schema' >&2; exit 1
fi
for _ in 1 2; do
    "${PRIVACY_MYSQL[@]}" < "$ROOT/migrations/immutable/0045_pkill_webinfo_at_capture.sql"
    "$ROOT/migrations/immutable/0045_pkill_webinfo_at_capture.sh"
done
[[ "$("${PRIVACY_MYSQL[@]}" -e "SELECT CONCAT(webinfo_at_capture IS NULL,':',equip,':',log) FROM pkill_info WHERE pid=4294000201;")" == '1:OLD_EQUIP:OLD_LOG' ]]
# Old writers continue to create unknown rows. Noncanonical definitions fail closed.
"${PRIVACY_MYSQL[@]}" -e "INSERT INTO pkill_info(pid,pk_type,equip) VALUES(4294000202,'legacy','');"
[[ "$("${PRIVACY_MYSQL[@]}" -e 'SELECT webinfo_at_capture IS NULL FROM pkill_info WHERE pid=4294000202;')" == 1 ]]
for definition in 'SMALLINT NULL' 'TINYINT UNSIGNED NULL' 'TINYINT NULL DEFAULT 1' 'TINYINT NULL AFTER equip'; do
    "${PRIVACY_MYSQL[@]}" -e "ALTER TABLE pkill_info MODIFY webinfo_at_capture $definition;"
    "${PRIVACY_MYSQL[@]}" < "$ROOT/migrations/immutable/0045_pkill_webinfo_at_capture.sql"
    if "$ROOT/migrations/immutable/0045_pkill_webinfo_at_capture.sh"; then
        echo "capture verifier accepted $definition" >&2; exit 1
    fi
    "${PRIVACY_MYSQL[@]}" -e 'ALTER TABLE pkill_info MODIFY webinfo_at_capture TINYINT NULL DEFAULT NULL AFTER player_description;'
done
"${PRIVACY_MYSQL[@]}" -e 'DELETE FROM pkill_info WHERE pid IN (4294000201,4294000202);'
"${PRIVACY_MYSQL[@]}" -e 'ALTER TABLE pkill_info MODIFY webinfo_at_capture TINYINT NOT NULL DEFAULT 0;'
if "$ROOT/migrations/immutable/0045_pkill_webinfo_at_capture.sh"; then
    echo 'capture verifier accepted NOT NULL' >&2; exit 1
fi
"${PRIVACY_MYSQL[@]}" -e 'ALTER TABLE pkill_info MODIFY webinfo_at_capture TINYINT NULL DEFAULT NULL;'
"$ROOT/migrations/immutable/0045_pkill_webinfo_at_capture.sh"
mkdir -p "$ROOT/bin/tests"
read -r -a MYSQL_CFLAGS <<< "$(mysql_config --cflags)"
read -r -a MYSQL_LIBS <<< "$(mysql_config --libs)"
g++ -std=c++20 -ffunction-sections -fdata-sections -Wall -Wextra -Wpedantic -Werror -pthread -Isrc \
    "${MYSQL_CFLAGS[@]}" tests/async/combat_outcome_mysql_harness.cpp tests/async/harness_stubs.cpp \
    src/persistence/critical_command.c src/world/epic_command.c src/economy/currency_command.c \
    src/item/item_transfer_command.c src/item/item_transfer_repository.c src/item/item_claim_repository.c src/persistence/persistence_observability.c src/item/item_claim.c src/persistence/dupe_log.c src/economy/auction_command.c \
    src/sql/item_extra_descr_codec.c tests/async/item_extra_descr_codec_sql_escape_stub.cpp \
    src/economy/auction_repository.c src/combat/combat_outcome_command.c src/combat/combat_outcome_repository.c src/combat/combat_outcome_intent.c src/flatfile/flatfile_store.c src/persistence/critical_command_coordinator.c src/player/player_save_worker.c src/combat/frag_cap.c src/combat/frag_cap_repository.c src/combat/frag_cap_config.c \
    src/guild/artifact_guild_command.c src/guild/artifact_guild_repository.c \
    src/economy/boon_reward_command.c src/economy/boon_reward_repository.c \
    src/world/zone_touch_command.c src/world/zone_touch_repository.c \
    src/account/session_audit_command.c src/account/session_audit_repository.c \
    src/player/player_snapshot_codec.c src/player/player_snapshot_repository.c \
    src/economy/collector_command.c src/economy/collector_codec.c \
    src/economy/collector_policy.c src/economy/collector_repository.c \
    src/economy/divine_trade.c src/economy/divine_trade_command.c src/economy/divine_trade_repository.c \
    src/persistence/critical_command_repository.c "${MYSQL_LIBS[@]}" -lcrypto -lz -Wl,--gc-sections,--wrap=mysql_real_query,--wrap=mysql_errno \
    -o "$ROOT/bin/tests/combat_outcome_mysql_harness"
"$ROOT/bin/tests/combat_outcome_mysql_harness"

# Reproduce an upgraded legacy database whose log column is still TEXT. The
# bootstrap above already uses MEDIUMTEXT, so it cannot cover this failure alone.
MYSQL=(mysql -h "$DB_HOST" -P "${DB_PORT:-3306}" -u "$DB_USER" -N -B "$DB_NAME")
"${MYSQL[@]}" -e "ALTER TABLE pkill_info MODIFY COLUMN log TEXT NULL;
INSERT INTO pkill_info(pid,pk_type,equip,log) VALUES
    (4294000200,'legacy','',NULL),
    (4294000200,'legacy','',REPEAT('x',65535));"
if "$ROOT/migrations/immutable/0041_pkill_log_capacity.sh"; then
    echo 'log capacity verifier accepted the undersized legacy column' >&2
    exit 1
fi
if "${MYSQL[@]}" -e "SET SESSION sql_mode='STRICT_ALL_TABLES';
    INSERT INTO pkill_info(pid,pk_type,equip,log)
    VALUES(4294000200,'legacy','',REPEAT('x',65536));" \
    2> "$ROOT/bin/tests/combat_log_limit.err"; then
    echo 'strict SQL mode accepted an oversized log in the legacy TEXT column' >&2
    exit 1
fi
grep -q 'ERROR 1406' "$ROOT/bin/tests/combat_log_limit.err"

for _ in 1 2; do
    "${MYSQL[@]}" < "$ROOT/migrations/immutable/0041_pkill_log_capacity.sql"
    "$ROOT/migrations/immutable/0041_pkill_log_capacity.sh"
done
preserved=$("${MYSQL[@]}" -e "SELECT CONCAT(COUNT(*),':',SUM(log IS NULL),':',
    SUM(log=REPEAT('x',65535))) FROM pkill_info WHERE pid=4294000200;")
[[ "$preserved" == '2:1:1' ]]
"${MYSQL[@]}" -e "SET SESSION sql_mode='STRICT_ALL_TABLES';
INSERT INTO pkill_info(pid,pk_type,equip,log) VALUES
    (4294000200,'legacy','',REPEAT('x',65536)),
    (4294000200,'legacy','',CONCAT(REPEAT(CONVERT(0xF09F94A5 USING utf8mb4),24999),'xyz'));"
lengths=$("${MYSQL[@]}" -e "SELECT GROUP_CONCAT(OCTET_LENGTH(log) ORDER BY id)
    FROM pkill_info WHERE pid=4294000200;")
[[ "$lengths" == '65535,65536,99999' ]]
# Replay with oversized data already stored must preserve every byte.
"${MYSQL[@]}" < "$ROOT/migrations/immutable/0041_pkill_log_capacity.sql"
"$ROOT/bin/tests/combat_outcome_mysql_harness"
[[ "$("${MYSQL[@]}" -e "SELECT HEX(log)=CONCAT(REPEAT('F09F94A5',24999),'78797A')
    FROM pkill_info WHERE pid=4294000200 ORDER BY id DESC LIMIT 1;")" == 1 ]]

# A noncanonical wider column must not be narrowed or certified for runtime boot.
"${MYSQL[@]}" -e 'ALTER TABLE pkill_info MODIFY COLUMN log LONGTEXT NULL;'
"${MYSQL[@]}" < "$ROOT/migrations/immutable/0041_pkill_log_capacity.sql"
if "$ROOT/migrations/immutable/0041_pkill_log_capacity.sh"; then
    echo 'log verifier accepted LONGTEXT despite the canonical MEDIUMTEXT boot contract' >&2
    exit 1
fi
[[ "$("${MYSQL[@]}" -e "SELECT data_type FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='pkill_info' AND column_name='log';")" == longtext ]]
# MEDIUMTEXT alone is insufficient: the runtime metadata contract also fixes
# nullability, encoding, default and column position. Use empty probe rows here
# so a NOT NULL fixture does not itself fail while converting historical NULLs.
"${MYSQL[@]}" -e 'DELETE FROM pkill_info WHERE pid=4294000200;'
for definition in 'MEDIUMTEXT NOT NULL' \
    'MEDIUMTEXT CHARACTER SET latin1 COLLATE latin1_bin NULL' \
    "MEDIUMTEXT NULL DEFAULT ('fixture')" 'MEDIUMTEXT NULL AFTER leader'; do
    "${MYSQL[@]}" -e "ALTER TABLE pkill_info MODIFY COLUMN log $definition;"
    "${MYSQL[@]}" < "$ROOT/migrations/immutable/0041_pkill_log_capacity.sql"
    if "$ROOT/migrations/immutable/0041_pkill_log_capacity.sh"; then
        echo "log verifier accepted noncanonical metadata: $definition" >&2
        exit 1
    fi
    "${MYSQL[@]}" -e 'ALTER TABLE pkill_info MODIFY COLUMN log MEDIUMTEXT
        CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL AFTER equip;'
    "$ROOT/migrations/immutable/0041_pkill_log_capacity.sh"
done
echo 'legacy combat log capacity, data preservation, strict limits and replay: ok'

# Upgrade the exact prior inbox shape, preserve its results, and replay safely.
[[ "$("${MYSQL[@]}" -e 'SELECT COALESCE(MAX(OCTET_LENGTH(result_payload)),0) FROM critical_operation_inbox;')" -le 4096 ]]
"${MYSQL[@]}" -e 'ALTER TABLE critical_operation_inbox MODIFY COLUMN result_payload VARBINARY(4096) NOT NULL;'
if "$ROOT/migrations/immutable/0054_full_group_combat_results.sh"; then
    echo 'full-group verifier accepted the old 4096-byte inbox' >&2; exit 1
fi
before=$("${MYSQL[@]}" -e 'SELECT HEX(result_payload) FROM critical_operation_inbox ORDER BY operation_id LIMIT 1;')
for _ in 1 2; do
    "${MYSQL[@]}" < "$ROOT/migrations/immutable/0054_full_group_combat_results.sql"
    "$ROOT/migrations/immutable/0054_full_group_combat_results.sh"
done
[[ "$before" == "$("${MYSQL[@]}" -e 'SELECT HEX(result_payload) FROM critical_operation_inbox ORDER BY operation_id LIMIT 1;')" ]]
PVP_FULL_GROUP_ONLY=1 "$ROOT/bin/tests/combat_outcome_mysql_harness"
[[ "$("${MYSQL[@]}" -e 'SELECT MAX(OCTET_LENGTH(result_payload)) FROM critical_operation_inbox;')" == 8192 ]]
"${MYSQL[@]}" < "$ROOT/migrations/immutable/0054_full_group_combat_results.sql"
"$ROOT/migrations/immutable/0054_full_group_combat_results.sh"
"${MYSQL[@]}" -e 'ALTER TABLE critical_operation_inbox MODIFY COLUMN result_payload VARBINARY(16384) NOT NULL;'
"${MYSQL[@]}" < "$ROOT/migrations/immutable/0054_full_group_combat_results.sql"
if "$ROOT/migrations/immutable/0054_full_group_combat_results.sh"; then
    echo 'full-group verifier accepted an unexpected wider inbox' >&2; exit 1
fi
[[ "$("${MYSQL[@]}" -e "SELECT character_octet_length FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='critical_operation_inbox' AND column_name='result_payload';")" == 16384 ]]
echo 'full-group result migration, data preservation, rollback and replay: ok'
