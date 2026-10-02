#!/usr/bin/env python3
"""Source contracts for the live corpse save and restore routing."""

from _paths import SRC


FILES = (SRC / "files.c").read_text()


def body(source: str, signature: str, next_signature: str) -> str:
    start = source.index(signature)
    end = source.index(next_signature, start)
    return source[start:end]


write_corpse = body(FILES, "void writeCorpse(P_obj corpse)",
                    "void persistence_refresh_restored_corpse")
purge_corpse = body(FILES, "void PurgeCorpseFile(P_obj corpse)", "ush_int getShort")
restore_corpses = body(FILES, "void restoreCorpses(void)", "/** Pet only functions")

# Corpses live in memory: the corpse save is a writer job on both backends, and a job
# the writer refuses is reported, not run on the loop.
assert "queue_corpse_save(corpse, !present)" in write_corpse
assert "sql_" not in write_corpse and '"queue_failed"' in write_corpse
assert "sql_delete_corpse" not in purge_corpse
assert "PERSISTENCE_MODE_FLATFILE_PRIMARY" in purge_corpse
assert "skip_corpse_save" in purge_corpse
assert "queue_corpse_save(corpse, true)" in purge_corpse
assert "flatfile_corpse_restore_catalog" in restore_corpses
assert "fatal_boot_error" in restore_corpses
print("[PASS] corpse saves, removals and the boot restore route through the writer and catalog")
