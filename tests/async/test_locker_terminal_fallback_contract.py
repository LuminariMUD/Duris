#!/usr/bin/env python3
"""A terminal locker save that fails goes back to the writer; nothing writes it on the
game thread, and the locker character keeps the items until a save lands."""
from _paths import SRC

source = (SRC / "locker_async.c").read_text()


def body(signature):
    start = source.index(signature)
    end = source.index("\n}\n", start) + 3
    return source[start:end]


# No synchronous database fallback anywhere in the locker save path.
for forbidden in ("sql_save_locker", "writeCharacter", "qry(", "db_query", "sql_get_",
                  "mysql_", "sql_persistence_connection", "locker_sync_fallback_durable"):
    assert forbidden not in source, forbidden

# A retry waits, and nobody stays object-locked while it does: the user has left.
retry = body("static void slot_retry_later(")
assert "s->retry_at = s->dirty_at + LOCKER_ASYNC_RETRY_SECONDS;" in retry
assert "s->user_pid = 0;" in retry
assert "s->retry_at > now" in body("void locker_async_pulse(")

# A snapshot that cannot be captured or queued is retried if terminal, and never
# extracts the locker character.
start = body("static int start_one_snapshot(")
failed = start[start.index("if (!job.snapshot || !job_push("):start.index("s->state = LCHK_INFLIGHT;")]
assert failed.index("if (s->terminal)") < failed.index("slot_retry_later(s);")
assert "extract_char" not in failed

# The locker character is extracted only once its save landed; a failed terminal
# save is retried.
result = body("static void apply_result(")
assert result.index("if (r->ok && chLocker)") < result.index("extract_char(chLocker)")
assert "else if (r->ok || !s->terminal)" in result
assert result.index("else if (r->ok || !s->terminal)") < result.index("slot_retry_later(s);")

print("locker terminal saves retry through the writer and never write on the game thread")
