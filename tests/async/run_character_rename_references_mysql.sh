#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT/tests/async/disposable_schema.sh"

python3 "$ROOT/tests/async/character_rename_references_mysql_harness.py"
