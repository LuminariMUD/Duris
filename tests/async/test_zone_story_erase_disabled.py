#!/usr/bin/env python3
"""Deleting a character works when the zone-story catalog is disabled and nothing is stored.

erase_character() failed whenever the catalog had not booted, so every character deletion
in a world without zone-story content (the minimal journey worlds, or a boot whose catalog
failed) ended in "Deletion could not be confirmed". With the catalog disabled nothing is
tracked; the erase now succeeds when no zone-story state has ever been stored, and still
fails closed when an earlier boot stored some, which only the catalog can rewrite. The
boot looks once (nothing stores state while the catalog is off), so the erase never
queries on the game loop.
run_mysql_deletion_journey.py deletes a character this way.
"""
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
runtime = (SRC / "world/zone_story_quest_runtime.c").read_text()


def body(text, signature):
    start = text.index(signature)
    return text[start:text.index("\n}\n", start) + 3]


erase = body(runtime, "bool erase_character(uint32_t pid, std::string *error)")
assert erase.index("if (!pid)") < erase.index("if (!ready())")
disabled = erase[erase.index("if (!ready())"):erase.index("const std::string before")]
assert "state_absent_at_boot ||" in disabled and "fail(error," in disabled
note = body(runtime, "void note_stored_state()")
assert "state_absent_at_boot = persisted_state_absent(" in note
# Every boot looks, with or without spec procedures (the journeys boot with -s).
boot_db = body((SRC / "world/db.c").read_text(), "void boot_db(int mini_mode)")
specials = boot_db[boot_db.index("if (!no_specials)"):]
specials = specials[:specials.index("\n\t}\n") + 4]
assert "zone_story_quest_runtime::note_stored_state();" in boot_db.replace(specials, "")
absent = body(runtime, "bool persisted_state_absent(std::string *error)")
assert "flatfile_zone_story_quest_result::not_found" in absent
assert "sql_zone_story_quest_state_result::not_found" in absent
print("[PASS] a disabled zone-story catalog erases nothing it never stored, and fails closed otherwise")
