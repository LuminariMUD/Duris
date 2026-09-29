#!/usr/bin/env bash
# Phase 1 of the persistence reset on a real server and a disposable MariaDB: quit
# does not wait for a stalled writer, and shutdown with the database down exits
# within its bound. Never sources the checkout's .env.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
NAME="duris-stalled-writer-$$-$RANDOM"
PASSWORD="stalled-$$-$RANDOM"
cleanup() { docker rm -fv "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT HUP INT TERM
docker run -d --name "$NAME" -p 127.0.0.1::3306 -e "MARIADB_ROOT_PASSWORD=$PASSWORD" \
    "${STALLED_WRITER_DB_IMAGE:-mariadb:10.11}" >/dev/null
mapping="$(docker port "$NAME" 3306/tcp)"
export TEST_DB_HOST=127.0.0.1 TEST_DB_PORT="${mapping##*:}" TEST_DB_USER=root
export TEST_DB_PASSWORD="$PASSWORD" TEST_DB_CONTAINER="$NAME"
ready=0
for _ in $(seq 1 90); do
    if mysql --protocol=tcp -h 127.0.0.1 -P "$TEST_DB_PORT" -uroot -p"$PASSWORD" -e 'SELECT 1' \
        >/dev/null 2>&1; then ready=1; break; fi
    sleep 1
done
[[ "$ready" == 1 ]]
python3 tests/async/test_mysql_stalled_writer_journey.py "$@"
