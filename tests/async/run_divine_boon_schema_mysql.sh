#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
source "$ROOT/tests/async/disposable_schema.sh"
"${disposable_mysql[@]}" "$DB_NAME" < migrations/immutable/0048_divine_boon_state.sql
bash migrations/immutable/0048_divine_boon_state.sh
mkdir -p bin/tests
read -r -a MYSQL_CFLAGS <<< "$(mysql_config --cflags)"
read -r -a MYSQL_LIBS <<< "$(mysql_config --libs)"
g++ -std=c++20 -g -Og -Wall -Wextra -Wpedantic -Werror -Isrc "${MYSQL_CFLAGS[@]}" \
    tests/async/divine_boon_repository_harness.cpp \
    src/economy/divine_boon.c src/economy/divine_boon_repository.c \
    src/flatfile/flatfile_authority_transaction.c src/flatfile/flatfile_store.c \
    "${MYSQL_LIBS[@]}" -lcrypto -pthread -o bin/tests/divine_boon_mysql
bin/tests/divine_boon_mysql
"${disposable_mysql[@]}" "$DB_NAME" < migrations/immutable/0048_divine_boon_state.sql
bash migrations/immutable/0048_divine_boon_state.sh
preserved=$("${disposable_mysql[@]}" -N -B "$DB_NAME" -e "SELECT COUNT(*) FROM divine_boon_state WHERE state_id=1 AND snapshot=UNHEX('00')")
[[ "$preserved" == 1 ]]
