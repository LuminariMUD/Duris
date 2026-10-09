#!/usr/bin/env bash
# Sourced by a database leg that tests/run_db_tests.sh runs under
# tests/async/with_disposable_mariadb.sh: creates duris_test on that disposable server with
# the full schema (the bootstrap and every immutable migration) and exports the DB_*
# settings the leg reads. A leg never reads the checkout's .env.
: "${TEST_DB_HOST:?run this leg under tests/async/with_disposable_mariadb.sh}"
export ENVIRONMENT=test DB_HOST="$TEST_DB_HOST" DB_PORT="$TEST_DB_PORT" DB_USER="$TEST_DB_USER" \
	DB_PASSWD="$TEST_DB_PASSWORD" DB_NAME=duris_test MYSQL_PWD="$TEST_DB_PASSWORD"
export DB_ALLOWED_TARGETS="$DB_HOST/$DB_NAME"
disposable_mysql=(mysql --protocol=tcp -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER")
"${disposable_mysql[@]}" -e "CREATE DATABASE $DB_NAME CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
"${disposable_mysql[@]}" "$DB_NAME" < "$ROOT/migrations/bootstrap_multithread_safe.sql"
for migration in "$ROOT"/migrations/immutable/*.sql; do
	"${disposable_mysql[@]}" "$DB_NAME" < "$migration"
done
