#!/usr/bin/env bash
# Run a command against its own disposable MariaDB: a new container on a random
# loopback port, removed on exit. Never sources the checkout's .env.
set -euo pipefail

NAME="duris-test-db-$$-$RANDOM"
PASSWORD="test-db-$$-$RANDOM"
cleanup() { docker rm -fv "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT HUP INT TERM
docker run -d --name "$NAME" -p 127.0.0.1::3306 -e "MARIADB_ROOT_PASSWORD=$PASSWORD" \
    mariadb:10.11 >/dev/null
mapping="$(docker port "$NAME" 3306/tcp)"
export TEST_DB_HOST=127.0.0.1 TEST_DB_PORT="${mapping##*:}" TEST_DB_USER=root
export TEST_DB_PASSWORD="$PASSWORD"
ready=0
for _ in $(seq 1 90); do
    if mysql --protocol=tcp -h 127.0.0.1 -P "$TEST_DB_PORT" -uroot -p"$PASSWORD" -e 'SELECT 1' \
        >/dev/null 2>&1; then ready=1; break; fi
    sleep 1
done
[[ "$ready" == 1 ]]
"$@"
