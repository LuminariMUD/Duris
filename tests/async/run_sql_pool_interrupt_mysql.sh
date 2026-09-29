#!/usr/bin/env bash
# Shutdown cuts off a writer query blocked on the database (MR !2 review finding 5) and
# leaves a borrower stuck opening a connection (review round 2, finding 2):
# the real connection pool against a disposable MariaDB. Never sources the checkout's
# .env.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
NAME="duris-pool-interrupt-$$-$RANDOM"
PASSWORD="interrupt-$$-$RANDOM"
IMAGE="${SQL_POOL_INTERRUPT_DB_IMAGE:-mariadb:10.11}"
cleanup() { docker rm -fv "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT HUP INT TERM
docker run -d --name "$NAME" -p 127.0.0.1::3306 -e "MARIADB_ROOT_PASSWORD=$PASSWORD" \
    "$IMAGE" >/dev/null
mapping="$(docker port "$NAME" 3306/tcp)"
export DB_HOST=127.0.0.1 DB_PORT="${mapping##*:}" DB_USER=root DB_PASSWD="$PASSWORD"
export DB_NAME=sql_pool_interrupt_test MYSQL_PWD="$PASSWORD"
MYSQL=(mysql --protocol=tcp -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -N -B)
ready=0
for _ in $(seq 1 90); do
    if "${MYSQL[@]}" -e 'SELECT 1' >/dev/null 2>&1; then ready=1; break; fi
    sleep 1
done
[[ "$ready" == 1 ]]
"${MYSQL[@]}" -e "CREATE DATABASE $DB_NAME"

mkdir -p "$ROOT/bin/tests"
read -r -a MYSQL_CFLAGS <<< "$(mysql_config --cflags)"
read -r -a MYSQL_LIBS <<< "$(mysql_config --libs)"
g++ -std=c++20 -Wall -Wextra -Wpedantic -Werror -pthread -ffunction-sections -fdata-sections \
    -Isrc "${MYSQL_CFLAGS[@]}" tests/async/sql_pool_interrupt_mysql_harness.cpp \
    src/sql/sql_pool.c -Wl,--gc-sections "${MYSQL_LIBS[@]}" \
    -o "$ROOT/bin/tests/sql_pool_interrupt_mysql_harness"
"$ROOT/bin/tests/sql_pool_interrupt_mysql_harness"
