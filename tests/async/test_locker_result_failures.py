#!/usr/bin/env python3
"""Regression checks for fail-closed locker result handling."""
from _paths import SRC
from pathlib import Path

source = (SRC / "storage_lockers.c").read_text()

assert "int name_len = snprintf(name, sizeof(name), \"%s\", esc_locker_name);" in source
assert "(size_t)name_len >= sizeof(name)" in source
assert "locker_require_owner" in source
assert "locker_require_active_user" not in source
assert "Only the locker owner can manage access." in source
assert "bool is_owner = locker_char && esc_locker_name_matches_player" in source
# Non-owner opens must pass the async verification and credential recheck.
opening = source[source.index("static int locker_opencmd(P_char ch, char *arg)\n{"):source.index("static int locker_closecmd(P_char ch, char * /*arg*/)\n{")]
assert "sql_verify_chest_password" not in opening
assert "if (is_owner)" in opening
# The chest's password is held in memory while the locker is open.
assert "PrivateChest *chest = pLocker->FindPrivateChest(arg1);" in opening
assert "finish(ch->desc, hash.empty() && !arg2[0], nullptr);" in opening
assert "password_async_start(" in opening
assert "password_work_submit(arg2, hash.c_str(), nullptr, 1, 1)" in opening
# A racing password change fails closed, and a rehash only replaces what it checked.
assert "current->GetPasswordHash() == hash" in opening
assert "finish(completed_desc, valid && same, nullptr);" in opening
assert "locker_chest_id(locker, name.c_str()) != chest_id" in opening
assert opening.index("if (!valid)") < opening.index("locker->SetCurrentChestId(chest_id)")
failed = opening[opening.index("if (!valid)"):opening.index("locker->SetCurrentChestId(chest_id)")]
assert "CHEST_ACTION_FAIL" in failed and "return;" in failed
assert "if (!submitted)" in opening
assert "Password service is busy; try again later." in opening
assert "strcpy(name, esc_locker_name);" not in source
# Personal-locker ownership is a stable PID/racewar decision, read on the writer with
# the entry and checked before visitor grants; the verdict decides for both idle and
# actively occupied lockers.
entry = source[source.index("static unsigned int locker_entry_read("):source.index("static const sql_row *locker_row(")]
assert "JOIN account_characters ac ON ac.pid=l.owner_pid" in entry
assert "l.owner_pid=%d" in entry
assert "l.owner_assoc_id IS NULL" in entry
assert "ac.racewar=l.racewar" in entry
assert "ac.blocked=0" in entry
assert "ac.deleted_at IS NULL" in entry
assert entry.index("l.owner_pid=%d") < entry.index("locker_granted(")
assert source.count("&& !has_access)") == 2
# grants are added and removed on the writer, and a failure is reported
assert "static void locker_access_add(P_char ch, P_char locker, const char *name)" in source
assert "static void locker_access_remove(P_char ch, P_char locker, const char *name)" in source
assert "Failed to add access (database error)." in source
assert "Failed to remove access (database error)." in source
# guild locker authorization
assert "locker_is_guild_member" in source
assert "bool is_guild_member = locker_is_guild_member(pLocker, ch);" in source
# PFileToLocker puts items on room floor, not invisible locker char
assert "obj_to_room(tmp_object, m_realRoom);" in source
# UnsortedChest rejects containers (in header)
header = (SRC / "storage_lockers.h").read_text()
assert "obj->type == ITEM_CONTAINER" in header
# Deferred terminal save
assert "event_deferredTerminalSave" in source
# CanAddAccount checks racewar
assert "AND racewar = %d" in source

print("locker result failure checks passed")
