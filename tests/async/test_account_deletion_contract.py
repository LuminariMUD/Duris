#!/usr/bin/env python3
"""Safety and backend contracts for player-initiated account deletion."""

from _paths import SRC
from contract_text import contains, count as source_count, index


ACCOUNT = (SRC / "account.c").read_text(encoding="utf-8", errors="replace")
SQL_PLAYER = (SRC / "sql_player.c").read_text(encoding="utf-8", errors="replace")
ITEM_REPOSITORY = (SRC / "item_transfer_repository.c").read_text(
    encoding="utf-8", errors="replace"
)
FLAT_DELETE = (SRC / "flatfile_account_delete.c").read_text(
    encoding="utf-8", errors="replace"
)
GUILD = (SRC / "assocs.c").read_text(encoding="utf-8", errors="replace")
SHIP = (SRC / "ship_base.c").read_text(encoding="utf-8", errors="replace")


def function_body(source: str, signature: str, *, last: bool = False) -> str:
    start = source.rindex(signature) if last else source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for position in range(brace, len(source)):
        if source[position] == "{":
            depth += 1
        elif source[position] == "}":
            depth -= 1
            if depth == 0:
                return source[start : position + 1]
    raise AssertionError(f"unterminated function: {signature}")


password = function_body(ACCOUNT, "void get_account_password(")
password_completion = function_body(ACCOUNT, "static void finish_account_password(")
begin_delete = function_body(ACCOUNT, "void delete_account(")
confirm_delete = function_body(ACCOUNT, "void verify_delete_account(")
drain_guard = ACCOUNT[
    ACCOUNT.index("class account_deletion_drain_guard") : ACCOUNT.index(
        "void remove_deleted_account_runtime"
    )
]
sql_delete = function_body(SQL_PLAYER, "bool sql_delete_account(const char *name", last=True)
finish_delete = function_body(ACCOUNT, "static void finish_account_deletion(")
flat_delete = function_body(FLAT_DELETE, "flatfile_account_delete_result flatfile_account_delete(")
guild_forget = function_body(GUILD, "void forget_deleted_guild_member(")
ship_runtime_remove = function_body(SHIP, "void delete_ship_runtime(")
destroy_item_owners = function_body(
    ITEM_REPOSITORY, "bool item_transfer_repository_destroy_owners("
)
format_account_lockers = function_body(
    SQL_PLAYER, "static bool sql_format_account_locker_name_list("
)

# Login defers bcrypt/legacy verification; deletion still verifies before its confirmation.
assert "password_login_submit(" in password
assert "password_login_submit(arg, d->account->acct_password, 0)" in begin_delete
assert begin_delete.index("echo_off(d)") < begin_delete.index("password_login_submit")

# A matching password alone is insufficient: the account name must match byte-for-byte.
assert "strcmp(arg, d->account->acct_name)" in confirm_delete
assert "strcasecmp(arg, d->account->acct_name)" not in confirm_delete

# The durable, non-cancellable fence precedes disconnection, drains, and backend mutation.
fence = confirm_delete.index("d->account->acct_blocked = ACCOUNT_BLOCK_DELETION")
fence_write = confirm_delete.index("write_account(d->account)", fence)
disconnect = confirm_delete.index("close_other_account_sessions(d)")
backend = confirm_delete.index("sql_delete_account(")
assert fence < fence_write < disconnect < backend
assert "if (fenced)" in confirm_delete and "cannot be cancelled" in confirm_delete
assert "acct_blocked == ACCOUNT_BLOCK_DELETION" in password_completion
assert "display_account_deletion_confirmation(d, true)" in password_completion
assert password_completion.index("if (!password_valid)") < password_completion.index(
    "display_account_deletion_confirmation(d, true)"
)
assert "account_deletion_locker_runtime_active(account_name, identities)" in confirm_delete

# Every asynchronous writer that can republish live account/character state is drained.
for call in (
    "maintenance_scheduler_quiesce()",
    "critical_command_coordinator_quiesce()",
    "critical_outbox_quiesce()",
    "persistence_flush_all_character_saves()",
    "player_save_pipeline_quiesce()",
    "player_save_pipeline_drain(3000)",
    "locker_async_drain(3000)",
):
    assert call in drain_guard
assert "drain_pending_ship_saves()" in confirm_delete
assert confirm_delete.index("account_deletion_drain_guard drain_guard") > confirm_delete.index("#else")
runtime_remove = function_body(ACCOUNT, "void remove_deleted_account_runtime(")
detach_character = runtime_remove.index("character->desc = NULL")
detach_descriptor = runtime_remove.index("character_desc->character = NULL")
close_descriptor = runtime_remove.index("close_socket(character_desc)")
extract_character = runtime_remove.index("extract_char_after_terminal_save(character)")
assert detach_character < detach_descriptor < close_descriptor < extract_character
assert contains(runtime_remove, "player_revision_forget(identity.pid)")
assert contains(
    runtime_remove, "item_ownership_runtime_forget_player_domain(identity.pid)"
)
assert contains(runtime_remove, "redis_invalidate_ship_snapshot(identity.name.c_str())")
assert contains(runtime_remove, "forget_deleted_guild_member(identity.name.c_str())")
assert contains(runtime_remove, "delete_ship_runtime(identity.name.c_str())")
assert "delete_ship_by_owner(owner_name, false)" in ship_runtime_remove
assert "P_member *link = &guild->members" in guild_forget
assert "flatfile_association_list(root, &records, &error)" in guild_forget
assert "guild->frags.frags = durable->frags" in guild_forget
assert "guild->save()" not in guild_forget
# On MariaDB the member leaves its guild as the deletion's statements did, and the guild is
# saved again: a save queued while the deletion ran still held the member.
mariadb_forget = guild_forget[guild_forget.index("#ifndef __NO_MYSQL__") : guild_forget.index("#else")]
assert "guild->forget_deleted_member(character_name, 0);" in mariadb_forget
member_forget = function_body(GUILD, "void Guild::forget_deleted_member(")
saved = member_forget[member_forget.index("#ifndef __NO_MYSQL__") :]
assert "\tsave();\n#endif" in saved

# Compile-time backend selection prevents an accidental dual-authority delete.
assert "#ifndef __NO_MYSQL__" in confirm_delete
assert "#else" in confirm_delete
assert "flatfile_account_delete(" in confirm_delete

# MariaDB deletes on the persistence writer, one job and so one transaction, behind the
# account's queued saves: it locks the fence, removes the credential last, reconciles
# it absent, and the session learns the outcome in the job's reply.
assert "sql_read_work(" in sql_delete and "DB, " not in sql_delete
assert "qry(" not in sql_delete and "sql_begin_transaction()" not in sql_delete
fence_lock = index(sql_delete, '"LOWER(account_name)=LOWER(\'%s\') FOR UPDATE"')
missing_account = index(sql_delete, "if (rows.empty())", fence_lock)
fence_check = index(sql_delete, "atoi(rows[0][0]) != ACCOUNT_BLOCK_DELETION", missing_account)
already_deleted = sql_delete[missing_account:fence_check]
assert contains(already_deleted, "strtoull(left[0][0], NULL, 10) == 0")
assert "ACCOUNT_LOCKER_SLOT_COUNT = 5" in SQL_PLAYER
assert "slot < ACCOUNT_LOCKER_SLOT_COUNT" in format_account_lockers
assert "sql_format_account_locker_name_list(locker_names_buffer" in sql_delete
assert ".0.locker" not in sql_delete
player_remove = sql_delete.index('"DELETE FROM player_data WHERE pid=%d"')
projection_remove = index(sql_delete, '{ "account_characters", "account_name" }')
credential_remove = sql_delete.index('"DELETE FROM accounts WHERE LOWER(account_name)')
reconcile = sql_delete.index('"SELECT (SELECT COUNT(*) FROM accounts', credential_remove)
assert player_remove < projection_remove < credential_remove < reconcile
assert contains(sql_delete, "mysql_affected_rows(connection) != 1")
assert "status=1" in sql_delete
assert "(owner_type=4 AND (owner_id >> 32)=%d)" in sql_delete
assert "(owner_type=5 AND owner_id IN" in sql_delete
# Character names are escaped on the writer's own connection.
assert "mysql_real_escape_string(\n\t\t\t\t\tconnection, character.data()" in sql_delete
assert "UPDATE item_current_owner" not in sql_delete
assert "item_transfer_repository_destroy_owners(\n\t\t\t\t\t    connection," in sql_delete
assert "item_transfer_reason::destruction" in destroy_item_owners
assert "item_transfer_command_build" in destroy_item_owners
assert "item_transfer_repository_execute" in destroy_item_owners
assert "UPDATE guilds g JOIN guild_members gm" in sql_delete
assert sql_delete.index("UPDATE guilds g JOIN guild_members gm") < sql_delete.index(
    "DELETE FROM guild_members"
)

# The account's characters leave memory before the deletion is queued, so no save of
# theirs lands after it; the session waits for the reply with its input held.
mariadb = confirm_delete[confirm_delete.index("#ifndef __NO_MYSQL__") : confirm_delete.index("#else")]
assert mariadb.index("remove_deleted_account_runtime(d, identities)") < mariadb.index(
    "sql_delete_account("
)
# A refused deletion rolls back, so the names and grants leave memory only on success.
succeeded = mariadb[mariadb.index("if (deleted)") : mariadb.index("writer_replied(id))")]
assert "sql_player_names_forget(identity.pid)" in succeeded
assert "account_rewards_forget_account(account_name.c_str())" in succeeded
assert "polls_forget_account(account_name.c_str())" in succeeded
assert mariadb.index("wait_for_writer(d)") < mariadb.index("sql_delete_account(")
assert "writer_replied(id)" in mariadb
assert "finish_account_deletion(" in mariadb
assert "drain_guard" not in mariadb

# Flat-file deletion tombstones every character first, then publishes identity and
# credential removal through the recoverable authority journal, credential last.
character_remove = flat_delete.index("flatfile_character_delete(")
identity_remove = flat_delete.index("flatfile_identity_prepare_sync_account(")
credential_prepare = flat_delete.index("flatfile_account_prepare_remove(")
authority_commit = flat_delete.index("flatfile_authority_transaction_commit_operations(")
credential_check = flat_delete.rindex("flatfile_account_exists(")
identity_check = flat_delete.rindex("flatfile_identity_list_account(")
assert character_remove < identity_remove < credential_prepare < authority_commit
assert authority_commit < credential_check < identity_check

# Success destroys the live session credential and closes the connection; failure keeps
# the fence for a retry.
assert "d->account = free_account(d->account)" in finish_delete
assert "STATE(d) = CON_FLUSH" in finish_delete
assert "display_account_deletion_confirmation(d, true)" in finish_delete

print("account deletion safety contracts passed")
