#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
# The transfer matrix uses only synthetic data in its own disposable server.
# Never source the checkout's .env: it may point at the live game.
NAME="duris-item-transfer-$$-$RANDOM"
PASSWORD="transfer-$$-$RANDOM"
IMAGE="${ITEM_TRANSFER_DB_IMAGE:-mariadb:10.11}"
cleanup() { docker rm -fv "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT HUP INT TERM
if [[ "$IMAGE" == mariadb:* ]]; then PASSWORD_ENV=MARIADB_ROOT_PASSWORD; else PASSWORD_ENV=MYSQL_ROOT_PASSWORD; fi
docker run -d --name "$NAME" -p 127.0.0.1::3306 -e "$PASSWORD_ENV=$PASSWORD" "$IMAGE" >/dev/null
mapping="$(docker port "$NAME" 3306/tcp)"
container_host="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$NAME")"
export ENVIRONMENT=test
export DB_USER=root DB_PASSWD="$PASSWORD" MYSQL_PWD="$PASSWORD"
export DB_NAME=item_transfer_test ITEM_TRANSFER_TEST_DB_NAME=item_transfer_test
if mysql --help 2>&1 | grep -- '--ssl-mode' >/dev/null; then MYSQL_SSL=(--ssl-mode=PREFERRED); else MYSQL_SSL=(--skip-ssl); fi
ready=0
for candidate in "127.0.0.1:${mapping##*:}" "host.docker.internal:${mapping##*:}" "$container_host:3306"; do
    [[ "$candidate" == :3306 ]] && continue
    export DB_HOST="${candidate%:*}" DB_PORT="${candidate##*:}"
    MYSQL=(mysql "${MYSQL_SSL[@]}" --protocol=tcp --connect-timeout=3 -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -N -B)
    for _ in $(seq 1 10); do
        if "${MYSQL[@]}" -e 'SELECT 1' >/dev/null 2>&1; then ready=1; break 2; fi
        sleep 1
    done
done
if [[ "$ready" != 1 ]]; then
    printf 'Disposable item transfer SQL readiness failed on the bounded local endpoints.\n' >&2
    exit 1
fi
"${MYSQL[@]}" -e "CREATE DATABASE $DB_NAME CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
"${MYSQL[@]}" "$DB_NAME" < "$ROOT/migrations/bootstrap_multithread_safe.sql"
"${MYSQL[@]}" "$DB_NAME" < "$ROOT/migrations/critical_command_inbox_outbox.sql"
for migration in "$ROOT"/migrations/immutable/*.sql; do
    "${MYSQL[@]}" "$DB_NAME" < "$migration"
done
DB_NAME="$DB_NAME" "$ROOT/migrations/verify_item_ownership_schema.sh"
mkdir -p "$ROOT/bin/tests"
read -r -a MYSQL_CFLAGS <<< "$(mysql_config --cflags)"
read -r -a MYSQL_LIBS <<< "$(mysql_config --libs)"
g++ -std=c++20 -Wall -Wextra -Wpedantic -Werror -pthread -Isrc \
    "${MYSQL_CFLAGS[@]}" tests/async/item_transfer_mysql_harness.cpp \
    tests/async/item_extra_descr_codec_sql_escape_stub.cpp \
    src/persistence/critical_command.c src/world/epic_command.c src/economy/currency_command.c \
    src/item/item_transfer_command.c src/item/item_transfer_repository.c \
    src/sql/item_extra_descr_codec.c \
	 src/economy/auction_command.c src/economy/auction_repository.c \
    src/combat/combat_outcome_command.c src/combat/combat_outcome_repository.c \
	 src/guild/artifact_guild_command.c src/guild/artifact_guild_repository.c \
    src/economy/boon_reward_command.c src/economy/boon_reward_repository.c \
    src/world/zone_touch_command.c src/world/zone_touch_repository.c \
    src/account/session_audit_command.c src/account/session_audit_repository.c \
    src/item/item_uid_allocator.c src/flatfile/flatfile_item_uid_allocator.c src/flatfile/flatfile_store.c \
    src/persistence/persistence_mode.c \
    src/economy/coin_transfer_command.c src/player/player_snapshot_codec.c \
    src/economy/collector_command.c src/economy/collector_codec.c \
    src/economy/collector_policy.c src/economy/collector_repository.c \
    src/persistence/corpse_lifecycle_command.c src/persistence/corpse_lifecycle_repository.c \
    src/persistence/player_death_restitution_command.c \
    src/persistence/player_death_restitution_repository.c \
    src/persistence/economic_accounting_repository.c \
    src/persistence/economic_sql_bank_transaction.c \
    src/economy/economic_currency_adapter.c \
    src/economy/economic_accounting_types.c \
    src/economy/economic_accounting_plan.c \
    src/economy/economic_accounting_intent.c \
    src/persistence/critical_command_repository.c "${MYSQL_LIBS[@]}" -lcrypto \
    -o "$ROOT/bin/tests/item_transfer_mysql_harness"
"$ROOT/bin/tests/item_transfer_mysql_harness"
printf 'item creation, subtree, stale, incomplete, replay, transfer, destruction, ledger, and outbox checks passed\n'
