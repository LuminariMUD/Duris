#!/usr/bin/env python3
"""Artifact owners who are not in the game load through the player load pipeline.

The expiry event, artifact poof, swap, hunt and files loaded an offline owner on the game
loop with restoreCharOnly() (load_dummy_char()), and the artifact list loaded every owner
only to read its side. They now load through player_load_offline() and continue in its
callback, and the list reads the side with its rows.
"""
from _paths import SRC

artifact = (SRC / "artifact.c").read_text()


def body(signature: str) -> str:
    start = artifact.index(signature)
    brace = artifact.index("{", start)
    depth = 0
    for index in range(brace, len(artifact)):
        depth += (artifact[index] == "{") - (artifact[index] == "}")
        if depth == 0:
            return artifact[start : index + 1]
    raise AssertionError(signature)


assert "restoreCharOnly" not in artifact and "load_dummy_char" not in artifact
for signature, loader in (
    ("static bool poof_offline_artifact(", "player_load_offline("),
    ("void arti_poof_sql(P_char ch, char *arg)\n{", "player_load_offline_for("),
    ("void arti_swap_sql(P_char ch, char *arg)\n{", "player_load_offline_for("),
    ("void arti_hunt_sql(P_char ch, const char *arg)\n{", "player_load_offline_for("),
    ("void arti_files_to_sql(P_char ch, char *arg)\n{", "player_load_offline_for("),
):
    assert loader in body(signature), signature

# Each callback leaves an owner who entered the game meanwhile alone, and lets the loaded copy
# go with its items, whose artifact rows stay as its save holds them.
for callback in ("static void poof_loaded_owner(", "static void arti_poof_loaded(",
                 "static void arti_swap_loaded(", "static void arti_files_give("):
    loaded = body(callback)
    assert "is_pid_online(" in loaded and "release_offline_owner(" in loaded, callback
    # Another copy of the owner that is loading would save over this one.
    assert "player_load_pipeline_pid_pending(" in loaded, callback
    assert "extract_char(" not in loaded, callback
assert "player_load_items_discard(owner);" in body("static void release_offline_owner(")
# The expiry event loads an owner once at a time, even for two of its artifacts: two
# copies would each save back the artifact the other poofed. The callback clears the row.
assert "!player_load_pipeline_pid_pending(location) &&" in body("void event_artifact_check_poof_sql(")
assert "offline_poofs" not in artifact
# An owner that could not be loaded keeps the row for the next pass: clearing it would leave
# the artifact on a character whose row says it is gone. Only a missing character clears it.
poof = body("static void poof_loaded_owner(")
not_loaded = poof[poof.index("if (!owner)") : poof.index("return;", poof.index("if (!owner)"))]
assert "artifact_expire" not in not_loaded and "release_offline_owner" not in not_loaded
missing = body("static bool poof_offline_artifact(")
assert missing.index("if (!name)") < missing.index("artifact_expire(vnum);") < missing.index(
    "player_load_offline(")
assert "artifact_expire(vnum);" in body("static void poof_loaded_owner(")

# The lists read each owner's side with the rows (MariaDB) or from its identity (flat-file).
assert "LEFT JOIN player_data p ON p.pid = a.location" in artifact
assert "flatfile_identity_lookup_pid(" in body(
    "void list_artifacts_sql(P_char ch, int type, bool Godlist, bool allArtis)\n{")

print("artifact offline owner load contracts passed")
