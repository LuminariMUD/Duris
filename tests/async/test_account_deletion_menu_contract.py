#!/usr/bin/env python3
"""The implemented account deletion flow is reachable from the account menu."""

from _paths import SRC
from contract_text import contains


ACCOUNT = (SRC / "account.c").read_text(encoding="utf-8", errors="replace")


def body(signature: str) -> str:
    start = ACCOUNT.index(signature)
    opening = ACCOUNT.index("{", start)
    depth = 0
    for position in range(opening, len(ACCOUNT)):
        if ACCOUNT[position] == "{":
            depth += 1
        elif ACCOUNT[position] == "}":
            depth -= 1
            if depth == 0:
                return ACCOUNT[start : position + 1]
    raise AssertionError(f"unterminated function: {signature}")


menu = body("void display_account_menu(")
case_7 = menu[menu.index("case 7:") : menu.index("case 8:")]
delete = body("void delete_account(")
verify = body("void verify_delete_account(")

assert "Delete this account" in menu
assert "case 7:" in menu
assert "Account deletion is not available" not in menu
assert contains(case_7, "STATE(d) = CON_ACCT_DELETE_ACCT;")
assert contains(case_7, "delete_account(d, NULL);")
assert contains(delete, "password_login_submit(arg, d->account->acct_password, 0)")
assert contains(delete, "STATE(completed_desc) = CON_ACCT_VERIFY_DELETE_ACCT;")
assert contains(verify, "d->account->acct_blocked = ACCOUNT_BLOCK_DELETION")
assert contains(verify, "sql_delete_account(account_name.c_str(),")

# Character deletion waits for the writer's reply with the confirmed character held.
delete_char = body("void account_delete_char(")
assert contains(delete_char, "const uint64_t id = wait_for_writer(d);")
assert contains(delete_char, "delete_character(d->character, true,")
assert contains(delete_char, "finish_character_deletion(reader, result);")

# The websocket deletions load the character off the loop and delete it the same way.
WS = (SRC / "ws_handlers.c").read_text(encoding="utf-8", errors="replace")
for signature in ("void ws_cmd_delete_character(", "static void admin_delete_character_loaded("):
    start = WS.index(signature)
    ws = WS[start : WS.index("\n}\n", start)]
    assert "player_load_offline(" in ws and "delete_character(" in ws, signature
    assert "wait_for_writer(d)" in ws and "writer_replied(id)" in ws, signature
    assert "restoreCharOnly" not in ws and "deleteCharacter" not in ws, signature
    # A character in the game, linkdead or entering it is refused before anything is queued.
    refused = ws.index("if (is_pid_online(GET_PID(loaded), TRUE) ||")
    guard = ws[refused : ws.index(" delete_character(", refused)]
    assert "player_load_pipeline_pid_pending(GET_PID(loaded))" in guard, signature
    assert "Character is in the game" in guard and "return;" in guard, signature

print("account and character deletion are reachable and guarded from the account menu")
