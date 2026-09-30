#!/usr/bin/env python3

from _paths import SRC
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SQL_PLAYER = (SRC / "sql_player.c").read_text()
CRAFTING = (SRC / "crafting.c").read_text()
MAKEFILE = (SRC / "Makefile").read_text()

flat_start = SQL_PLAYER.index("#ifdef __NO_MYSQL__")
flat_end = SQL_PLAYER.index("#else", flat_start)
flat = SQL_PLAYER[flat_start:flat_end]

for function, repository_call in (
    ("bool sql_add_player_recipe", "flatfile_recipe_add"),
    ("bool sql_delete_player_recipes", "flatfile_recipe_clear"),
    ("bool sql_has_player_recipe", "flatfile_recipe_contains"),
    ("int *sql_get_player_recipes", "flatfile_recipe_list"),
):
    start = flat.index(function)
    end = flat.index("\n}", start)
    body = flat[start:end]
    if repository_call not in body:
        raise SystemExit(f"{function} does not route to {repository_call}")
    if "persistence_alert" not in body:
        raise SystemExit(f"{function} does not alert on flat authority failure")

legacy_guard = CRAFTING.index("persistence_mode_get() == PERSISTENCE_MODE_FLATFILE_PRIMARY")
legacy_open = CRAFTING.index('fopen(path, "r")')
if legacy_guard > legacy_open:
    raise SystemExit("flat recipe authority can fall through to legacy crafting files")

normal = SQL_PLAYER[flat_end:]
for token in (
    "INSERT IGNORE INTO player_recipes",
    "DELETE FROM player_recipes",
    "SELECT pid, recipe_vnum FROM player_recipes ORDER BY id",
):
    if token not in normal:
        raise SystemExit(f"MariaDB recipe behavior lost: {token}")

# Step 8: MariaDB reads every character's recipes at boot and answers from memory; learning
# or forgetting changes memory at once and is queued on the writer.
recipes = normal[normal.index("bool sql_add_player_recipe"):normal.index("// player load functions")]
for forbidden in ("db_query", "sql_run_query", "qry(", "mysql_store_result"):
    if forbidden in recipes:
        raise SystemExit(f"MariaDB recipes still query the game loop: {forbidden}")
if recipes.count("sql_queue(") != 2 or "recipes_by_pid" not in recipes:
    raise SystemExit("MariaDB recipes must answer from memory and queue their writes")
if "sql_player_recipes_load()" not in (SRC / "sql.c").read_text():
    raise SystemExit("MariaDB recipes are not read at boot")

if "flatfile_recipe_repository.o" not in MAKEFILE:
    raise SystemExit("flat recipe repository is missing from server build")

print("flat-file recipe runtime contract passed")
