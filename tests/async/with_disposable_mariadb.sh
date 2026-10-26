#!/usr/bin/env bash
# Run a command against disposable SQL (MariaDB by default): a new container on a random
# loopback port, removed on exit. Never sources the checkout's .env.
set -euo pipefail

IMAGE="${TEST_DB_IMAGE:-mariadb:10.11}"
case "$IMAGE" in
    mariadb:10.11) PASSWORD_VARIABLE=MARIADB_ROOT_PASSWORD ;;
    mysql:8.0) PASSWORD_VARIABLE=MYSQL_ROOT_PASSWORD ;;
    *) echo "Unsupported disposable SQL image" >&2; exit 2 ;;
esac

NAME="duris-test-db-$$-$RANDOM"
PASSWORD="test-db-$$-$RANDOM"
cleanup() { docker rm -fv "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT HUP INT TERM
docker run -d --name "$NAME" -p 127.0.0.1::3306 -e "$PASSWORD_VARIABLE=$PASSWORD" \
    "$IMAGE" >/dev/null
mapping="$(docker port "$NAME" 3306/tcp)"
export TEST_DB_HOST=127.0.0.1 TEST_DB_PORT="${mapping##*:}" TEST_DB_USER=root
export TEST_DB_PASSWORD="$PASSWORD"
if mysql --help 2>&1 | grep -- '--ssl-mode' >/dev/null; then
    MYSQL_SSL=(--ssl-mode=DISABLED)
else
    MYSQL_SSL=(--skip-ssl)
fi
ready=0
for _ in $(seq 1 90); do
    if mysql "${MYSQL_SSL[@]}" --protocol=tcp -h 127.0.0.1 -P "$TEST_DB_PORT" -uroot -p"$PASSWORD" -e 'SELECT 1' \
        >/dev/null 2>&1; then ready=1; break; fi
    sleep 1
done
[[ "$ready" == 1 ]]
"$@"
