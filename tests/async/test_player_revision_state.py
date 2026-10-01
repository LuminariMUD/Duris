#!/usr/bin/env python3
"""Runtime and source contracts for player revision/component state."""

from _paths import SRC, rel
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HEADER = (SRC / "player_revision_state.h").read_text()
SOURCE = (SRC / "player_revision_state.c").read_text()
SQL_PLAYER = (SRC / "sql_player.c").read_text()


HARNESS = r'''
#include "player/player_revision_state.h"

#include <cassert>
#include <cstdint>
#include <limits>

int main()
{
    player_revision_reset_for_tests();
    assert(!player_revision_hydrate(0, 0));
    assert(player_revision_hydrate(7, 5));
    assert(player_revision_state_count() == 1);

    player_revision_snapshot snapshot = {};
    assert(player_revision_snapshot_copy(7, &snapshot));
    assert(snapshot.current_revision == 5);
    assert(snapshot.acknowledged_revision == 5);

    player_revision_t revision = 0;
    assert(player_revision_mark(7, PLAYER_COMPONENT_STATUS, &revision));
    assert(revision == 6);
    player_component_mask_t components = 0;
    assert(player_revision_queue(7, &revision, &components));
    assert(revision == 6);
    assert(components == PLAYER_COMPONENT_STATUS);

    assert(player_revision_mark(7, PLAYER_COMPONENT_INVENTORY, &revision));
    assert(revision == 7);
    assert(player_revision_queue(7, &revision, &components));
    assert(revision == 7);
    assert(components == (PLAYER_COMPONENT_STATUS | PLAYER_COMPONENT_INVENTORY));

    // Revision 6 lands: only the components marked by then are clean.
    assert(!player_revision_acknowledge_durable(7, 4, PLAYER_COMPONENT_STATUS));
    assert(!player_revision_acknowledge_durable(7, 8, PLAYER_COMPONENT_STATUS));
    assert(player_revision_acknowledge_durable(
        7, 6, PLAYER_COMPONENT_STATUS | PLAYER_COMPONENT_INVENTORY));
    assert(player_revision_snapshot_copy(7, &snapshot));
    assert(snapshot.acknowledged_revision == 6);
    assert(snapshot.unacknowledged_components == PLAYER_COMPONENT_INVENTORY);
    assert(player_revision_dirty_count() == 1);

    // While a save is outstanding, only the acknowledged revision hydrates again.
    assert(player_revision_hydrate(7, 6));
    assert(!player_revision_hydrate(7, 7));

    assert(player_revision_acknowledge_durable(7, 7, PLAYER_COMPONENT_INVENTORY));
    assert(player_revision_snapshot_copy(7, &snapshot));
    assert(snapshot.unacknowledged_components == 0);
    assert(player_revision_dirty_count() == 0);
    assert(!player_revision_queue(7, &revision, &components));
    assert(player_revision_record_written(7, 7));
    assert(player_revision_snapshot_copy(7, &snapshot));
    assert(snapshot.written_revision == 7);

    assert(!player_revision_hydrate(7, 6));
    assert(player_revision_hydrate(7, 9));
    assert(player_revision_snapshot_copy(7, &snapshot));
    assert(snapshot.current_revision == 9 && snapshot.acknowledged_revision == 9);
    assert(!player_revision_mark(7, UINT64_C(1) << 62, nullptr));

    assert(player_revision_hydrate(8, std::numeric_limits<player_revision_t>::max()));
    assert(!player_revision_mark(8, PLAYER_COMPONENT_STATUS, nullptr));
    assert(player_revision_snapshot_copy(8, &snapshot));
    assert(snapshot.current_revision == std::numeric_limits<player_revision_t>::max());
    assert(snapshot.overflowed);

    player_revision_forget(7);
    assert(!player_revision_snapshot_copy(7, &snapshot));
    assert(player_revision_state_count() == 1);
    return 0;
}
'''


with tempfile.TemporaryDirectory(prefix="duris-player-revision-") as temp_dir:
    source = Path(temp_dir) / "revision_test.cpp"
    binary = Path(temp_dir) / "revision_test"
    source.write_text(HARNESS)
    subprocess.run(
        [
            "g++",
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-Isrc",
            str(source),
            rel("player_revision_state.c"),
            "-o",
            str(binary),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run([str(binary)], check=True)

assert "std::unordered_map<int, player_revision_entry>" in SOURCE
assert "MAX_PLAYER_REVISION_STATES" in SOURCE
assert "component_revisions" in SOURCE
assert "numeric_limits<player_revision_t>::max()" in SOURCE
print("[PASS] PID-keyed runtime state is monotonic, cumulative, exact, and overflow-safe")

schemas = (
    ROOT / "migrations/run_migration.sh",
    ROOT / "migrations/pfile_to_db_combined_migration.sql",
    ROOT / "migrations/bootstrap_multithread_safe.sql",
)
for schema in schemas:
    text = schema.read_text()
    if schema.name == "run_migration.sh":
        assert "player_save_revision.sql" in text
    else:
        assert "save_revision" in text
        assert "BIGINT UNSIGNED NOT NULL DEFAULT" in text.upper()

migration = (ROOT / "migrations/player_save_revision.sql").read_text()
assert "information_schema.columns" in migration
assert "column_name = 'save_revision'" in migration
assert "BIGINT UNSIGNED NOT NULL DEFAULT 0" in migration
assert "ALTER TABLE player_data ADD COLUMN" in migration
print("[PASS] additive guarded schema initializes legacy and new rows at revision zero")

# A deleted character's revision state is forgotten once its deletion commits.
FILES = (SRC / "files.c").read_text()
forget = FILES[FILES.index("character_delete_result forget_deleted_character("):]
assert "player_revision_forget(deleted.pid);" in forget[:forget.index("\n}\n")]
delete = FILES[FILES.index("void delete_character(P_char ch, bool delete_locker,"):]
assert delete.index("sql_read_work(") < delete.index("done(forget_deleted_character(deleted));", delete.index("sql_read_work("))
assert "player_revision_forget" not in SQL_PLAYER

# A rename keeps the pid, so it leaves the revision state alone.
rename_start = SQL_PLAYER.rindex("std::vector<std::string> sql_rename_character_statements(")
rename_body = SQL_PLAYER[rename_start:SQL_PLAYER.index("\n}\n", rename_start)]
assert "player_revision_forget" not in rename_body
assert "player_revision_hydrate" not in rename_body
print("[PASS] required load/new/delete lifecycle is PID-stable and fail-closed")

production_sources = [
    path
    for path in SRC.glob("*.c")
    if path.name != "player_revision_state.c"
]
mark_callers = [path.name for path in production_sources if "player_revision_mark(" in path.read_text()]
assert mark_callers == ["player_save_pipeline.c"], (
    f"uncontrolled production marks: {mark_callers}"
)
assert "writeCharacter" not in SOURCE
assert "sql_save_player" not in SOURCE
assert "player_save_pipeline_mark" in (SRC / "persistence_checkpoint.c").read_text()
print("[PASS] production marks are limited to the pipeline")

print("player revision and component state contracts passed")
