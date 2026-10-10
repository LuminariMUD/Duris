#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
# Synthetic data only, in a disposable server. Never source the checkout's .env:
# it may point at the live game.
NAME="duris-save-claim-$$-$RANDOM"
PASSWORD="claim-$$-$RANDOM"
IMAGE="${PLAYER_SAVE_CLAIM_DB_IMAGE:-mariadb:10.11}"
WORK="$(mktemp -d)"
cleanup() { docker rm -fv "$NAME" >/dev/null 2>&1 || true; rm -rf "$WORK"; }
trap cleanup EXIT HUP INT TERM
if [[ "$IMAGE" == mariadb:* ]]; then PASSWORD_ENV=MARIADB_ROOT_PASSWORD; else PASSWORD_ENV=MYSQL_ROOT_PASSWORD; fi
docker run -d --name "$NAME" -p 127.0.0.1::3306 -e "$PASSWORD_ENV=$PASSWORD" "$IMAGE" >/dev/null
mapping="$(docker port "$NAME" 3306/tcp)"
export ENVIRONMENT=test DB_HOST=127.0.0.1 DB_PORT="${mapping##*:}"
export DB_USER=root DB_PASSWD="$PASSWORD" MYSQL_PWD="$PASSWORD"
export DB_NAME=player_save_claim_test
export DUPE_LOG_PATH_FOR_TEST="$WORK/logs/dupes"
if mysql --help 2>&1 | grep -- '--ssl-mode' >/dev/null; then MYSQL_SSL=(--ssl-mode=PREFERRED); else MYSQL_SSL=(--skip-ssl); fi
MYSQL=(mysql "${MYSQL_SSL[@]}" --protocol=tcp -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -N -B)
ready=0
for _ in $(seq 1 90); do
    if "${MYSQL[@]}" -e 'SELECT 1' >/dev/null 2>&1; then ready=1; break; fi
    sleep 1
done
[[ "$ready" == 1 ]]
"${MYSQL[@]}" -e "CREATE DATABASE $DB_NAME CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
"${MYSQL[@]}" "$DB_NAME" < "$ROOT/migrations/bootstrap_multithread_safe.sql"
for migration in "$ROOT"/migrations/immutable/*.sql; do
    "${MYSQL[@]}" "$DB_NAME" < "$migration"
done
# The audit migration is additive and rerunnable, and its verifier checks it.
"${MYSQL[@]}" "$DB_NAME" < "$ROOT/migrations/immutable/0033_item_owner_audit.sql"
"$ROOT/migrations/immutable/0033_item_owner_audit.sh"
"${MYSQL[@]}" "$DB_NAME" -e "INSERT INTO accounts(account_name) VALUES ('claim_probe');
INSERT INTO player_data(pid,name,account_name) VALUES (1,'Claimer','claim_probe'),(2,'Other','claim_probe');"

mkdir -p "$ROOT/bin/tests"
read -r -a MYSQL_CFLAGS <<< "$(mysql_config --cflags)"
read -r -a MYSQL_LIBS <<< "$(mysql_config --libs)"
g++ -std=c++20 -Wall -Wextra -Wpedantic -Werror -pthread -Isrc \
    "${MYSQL_CFLAGS[@]}" tests/async/player_save_claim_mysql_harness.cpp tests/async/harness_stubs.cpp \
    src/player/player_snapshot_repository.c src/player/player_snapshot_codec.c \
    src/item/item_claim_repository.c src/item/item_claim.c src/persistence/dupe_log.c \
    src/sql/item_extra_descr_codec.c src/persistence/persistence_observability.c \
    src/economy/collector_repository.c src/economy/collector_policy.c \
    src/economy/collector_codec.c src/economy/collector_command.c \
    src/economy/currency_command.c src/item/item_transfer_command.c \
    src/persistence/critical_command.c \
    "${MYSQL_LIBS[@]}" -lcrypto -o "$ROOT/bin/tests/player_save_claim_mysql_harness"
"$ROOT/bin/tests/player_save_claim_mysql_harness"

# Loads take only what the ownership table gives them: run the load filter leg on the
# same schema.
g++ -std=c++20 -Wall -Wextra -Wpedantic -Werror -pthread -ffunction-sections -fdata-sections \
    -Isrc "${MYSQL_CFLAGS[@]}" tests/async/player_load_filter_mysql_harness.cpp tests/async/harness_stubs.cpp \
    src/player/player_load_repository.c src/player/player_load_topology.c \
    src/player/player_snapshot_repository.c src/player/player_snapshot_codec.c \
    src/item/item_claim_repository.c src/item/item_claim.c src/persistence/dupe_log.c \
    src/sql/item_extra_descr_codec.c src/persistence/persistence_observability.c \
    -Wl,--gc-sections "${MYSQL_LIBS[@]}" -lcrypto \
    -o "$ROOT/bin/tests/player_load_filter_mysql_harness"
"$ROOT/bin/tests/player_load_filter_mysql_harness"

# The zone-story state is saved through sql_queue() on the writer: a state above 64 KiB
# is stored whole on the same schema.
g++ -std=c++20 -Wall -Wextra -Wpedantic -Werror -pthread -ffunction-sections -fdata-sections \
    -Isrc "${MYSQL_CFLAGS[@]}" tests/async/zone_story_state_mysql_harness.cpp tests/async/harness_stubs.cpp \
    src/sql/zone_story_quest_state_repository.c src/sql/sql_async.c \
    src/player/player_snapshot_repository.c src/player/player_snapshot_codec.c \
    src/item/item_claim_repository.c src/item/item_claim.c src/persistence/dupe_log.c \
    src/sql/item_extra_descr_codec.c src/persistence/persistence_observability.c \
    -Wl,--gc-sections "${MYSQL_LIBS[@]}" -lcrypto \
    -o "$ROOT/bin/tests/zone_story_state_mysql_harness"
"$ROOT/bin/tests/zone_story_state_mysql_harness"
