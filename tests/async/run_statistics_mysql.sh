#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT/tests/async/disposable_schema.sh"
export STATISTICS_TEST_DB="$DB_NAME"
cd "$ROOT"
python3 tests/async/run_statistics_mysql.py
