#!/usr/bin/env python3
"""Contracts for pre-entry Chaos equipment preparation."""

from __future__ import annotations

import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parents[2]
NANNY = (ROOT / "src/account/nanny.c").read_text(encoding="utf-8", errors="replace")
ACTWIZ = (ROOT / "src/cmd/actwiz.c").read_text(encoding="utf-8", errors="replace")
PROTOTYPES = (ROOT / "src/core/prototypes.h").read_text(
    encoding="utf-8", errors="replace"
)
TRANSACTION_C = (ROOT / "src/item/item_movement_transaction.c").read_text(
    encoding="utf-8", errors="replace"
)
TRANSACTION_H = (ROOT / "src/item/item_movement_transaction.h").read_text(
    encoding="utf-8", errors="replace"
)


keepchar = NANNY.split("\tcase CON_KEEPCHAR:", 1)[1].split("\tcase CON_ACCEPTWAIT:", 1)[0]
enter_game = NANNY.split("void enter_game", 1)[1].split("void reconnect", 1)[0]
chaos_loader = NANNY.split("static void load_chaos_new_character_kit", 1)[1].split(
    "void load_obj_to_newbies", 1
)[0]
# Automatic first kits are now withheld throughout pre-entry/approval states.
continuation = NANNY.split("void continue_kept_character", 1)[1].split("bool approve_kept_character", 1)[0]
assert "load_chaos_new_character_kit" not in continuation
assert "PLR3_STARTER_KIT_PENDING" in enter_game
assert "item_creation_grant_resume_starter(ch)" in enter_game
assert "load_chaos_new_character_kit(ch, true)" in enter_game
assert enter_game.index("writeCharacter(ch, 1, NOWHERE)") < enter_game.index("item_creation_grant_resume_starter(ch)")
assert "starter_kit_intent_bind(GET_PID(actor), command)" in TRANSACTION_C
assert "queue.baseline" in TRANSACTION_C and "revision.written_revision" in TRANSACTION_C
assert "starter_kit_intent_finish" in TRANSACTION_C

# The retired gate must not come back.
assert "official and legal response" not in NANNY
assert "case CON_DISCLMR:" not in NANNY
assert "case CON_GET_RETURN:" not in NANNY
assert "item_creation_grant_submit_batch_to_player_before_entry(ch, kit.roots.data()," in chaos_loader
assert "kit.count = 0;" in chaos_loader

# A pre-entry direct-to-player grant may validate by durable PID ownership, but
# target-container grants must not silently inherit this exception.
assert re.search(
    r"if \(!request\.allow_pre_entry && !find_live_player\(request\.recipient_pid\)\)",
    TRANSACTION_C,
)
assert "request.allow_pre_entry && request.target_container_uid" in TRANSACTION_C

# A staged pre-entry batch is command-blocking only once the descriptor is
# playing. Rules/MOTD Return must still reach nanny so enter_game can publish
# retained offline completions and release the whole-kit gate.
COMM = (ROOT / "src/net/comm.c").read_text(encoding="utf-8")
gate = re.search(r"creation_grant_input\s*=([^;]*item_creation_grant_blocks_commands[^;]*);", COMM)
assert gate is not None
assert "descriptor->connected == CON_PLAYING" in " ".join(gate.group(1).split())

# Maintenance must refuse before admission is quiesced: a multi-root kit can
# still have detached roots after the currently active operation is drained.
# These are static ordering checks; no copyover/shutdown/pwipe is executed.
COPYOVER = (ROOT / "src/persistence/copyover.c").read_text(encoding="utf-8")
copyover_start = COPYOVER.split("bool copyover_save(", 1)[1].split("maintenance_scheduler_quiesce();", 1)[0]
assert "if (item_creation_grant_batches_pending())" in copyover_start
assert "return false;" in copyover_start.split("if (item_creation_grant_batches_pending())", 1)[1]
shutdown_start = COMM.split("void game_loop(", 1)[1].split("critical_command_coordinator_quiesce();", 1)[0]
shutdown_guard = shutdown_start.split("if (!_pwipe && item_creation_grant_batches_pending())", 1)[1]
# Shutdown always goes (persistence reset step 8): a pending kit is reported, not a
# reason to keep running.
assert '"kit_pending"' in shutdown_guard and "goto resume_game_loop;" not in shutdown_guard
assert "bool item_creation_grant_batches_pending(void);" in TRANSACTION_H

# Nonplaying socket teardown must release the unsubmitted batch before freeing
# the actor. The active journaled head remains covered by the linked harness.
close_socket = COMM.split("void close_socket(", 1)[1]
cancel_at = close_socket.index("item_creation_grant_cancel_batch_before_entry(d->character);")
assert cancel_at < close_socket.index("free_char(d->character);", cancel_at)
assert "void item_creation_grant_cancel_batch_before_entry(P_char actor);" in TRANSACTION_H
assert "item creation grant batch cancelled before entry" in TRANSACTION_C

print("pre-entry Chaos grant contracts passed")
